import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eod import site_check
from eod.scenario import EodError
from tests.helpers import FIXTURES, copy_fixture_data

FLOOD = "Site {} is inside the saved 100-year layer, not cleared for this drill"
CAPACITY = "Site {} capacity {} is below demand {} in this synthetic drill, not cleared"
PASS = "Site {} cleared for this drill against synthetic data only"


class RayCastingTests(unittest.TestCase):
    SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    HOLE = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]

    def test_inside_and_outside(self):
        self.assertTrue(site_check.point_in_polygon(1, 1, [self.SQUARE]))
        self.assertFalse(site_check.point_in_polygon(11, 1, [self.SQUARE]))

    def test_hole_is_not_inside_but_the_ring_around_it_is(self):
        polygon = [self.SQUARE, self.HOLE]
        self.assertFalse(site_check.point_in_polygon(5, 5, polygon))
        self.assertTrue(site_check.point_in_polygon(3, 5, polygon))

    def test_concave_shape(self):
        u_shape = [[0, 0], [6, 0], [6, 6], [4, 6], [4, 2], [2, 2], [2, 6], [0, 6], [0, 0]]
        self.assertFalse(site_check.point_in_polygon(3, 4, [u_shape]))
        self.assertTrue(site_check.point_in_polygon(1, 4, [u_shape]))
        self.assertTrue(site_check.point_in_polygon(5, 4, [u_shape]))

    def test_extra_elevation_coordinate_is_ignored(self):
        square = [[0, 0, 7], [10, 0, 7], [10, 10, 7], [0, 10, 7], [0, 0, 7]]
        self.assertTrue(site_check.point_in_polygon(1, 1, [square]))


class CheckSiteTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"EOD_DATA_DIR": str(FIXTURES)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_site_in_zone_fails_with_exact_wording(self):
        result = site_check.check_site("A", 1, "R1")
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["reasons"], [FLOOD.format("A")])

    def test_site_out_of_zone_with_room_passes_with_exact_wording(self):
        result = site_check.check_site("C", 1, "R2")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["reasons"], [PASS.format("C")])
        self.assertEqual(result["demand"], 300)

    def test_site_inside_a_hole_is_not_in_the_zone(self):
        self.assertEqual(site_check.check_site("D", 1, "R2")["status"], "pass")

    def test_site_in_a_multipolygon_part_fails(self):
        result = site_check.check_site("E", 1, "R2")
        self.assertEqual(result["reasons"], [FLOOD.format("E")])

    def test_under_capacity_fails_with_exact_wording(self):
        result = site_check.check_site("B", 1, "R1")
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["reasons"], [CAPACITY.format("B", 50, 100)])

    def test_capacity_exactly_equal_to_demand_passes(self):
        self.assertEqual(site_check.check_site("F", 1, "R2")["status"], "pass")

    def test_same_site_fails_when_demand_grows(self):
        result = site_check.check_site("C", 2, "R3")
        self.assertEqual(result["reasons"], [CAPACITY.format("C", 500, 700)])

    def test_unknown_site_is_an_error(self):
        with self.assertRaises(EodError):
            site_check.check_site("Z", 1, "R1")

    def test_site_with_a_capacity_but_no_location_is_an_error(self):
        with self.assertRaises(EodError):
            site_check.check_site("G", 1, "R1")

    def test_both_failures_are_reported_together(self):
        with tempfile.TemporaryDirectory() as folder:
            data = copy_fixture_data(folder)
            scenario = json.loads((data / "scenario.json").read_text())
            scenario["sites"]["A"]["capacity"] = 1
            (data / "scenario.json").write_text(json.dumps(scenario))
            with mock.patch.dict(os.environ, {"EOD_DATA_DIR": str(data)}):
                result = site_check.check_site("A", 1, "R1")
        self.assertEqual(result["reasons"], [FLOOD.format("A"), CAPACITY.format("A", 1, 100)])


class BadFloodDataMustNotPassASiteTests(unittest.TestCase):
    """A broken flood layer must stop the check, not quietly clear every site."""

    def check_with_zone(self, zone):
        with tempfile.TemporaryDirectory() as folder:
            data = copy_fixture_data(folder)
            (data / "flood-zone.geojson").write_text(json.dumps(zone))
            with mock.patch.dict(os.environ, {"EOD_DATA_DIR": str(data)}):
                return site_check.check_site("C", 1, "R2")

    def test_zone_with_no_polygons_is_an_error(self):
        with self.assertRaises(EodError):
            self.check_with_zone({"type": "FeatureCollection", "features": []})

    def test_zone_not_in_lon_lat_is_an_error(self):
        utm_square = [[700000, 4300000], [710000, 4300000], [710000, 4310000], [700000, 4300000]]
        feature = {"type": "Feature", "properties": {},
                   "geometry": {"type": "Polygon", "coordinates": [utm_square]}}
        with self.assertRaises(EodError):
            self.check_with_zone({"type": "FeatureCollection", "features": [feature]})

    def test_zone_with_another_geometry_type_is_an_error(self):
        feature = {"type": "Feature", "properties": {},
                   "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}}
        with self.assertRaises(EodError):
            self.check_with_zone({"type": "FeatureCollection", "features": [feature]})

    def test_malformed_zone_is_an_error(self):
        polygon = {"type": "Polygon", "coordinates": [[["x", "y"], [1, 1], [2, 2]]]}
        for features in (["not a feature"], [{"geometry": {"type": "Polygon"}}], [{"geometry": polygon}]):
            with self.subTest(features=features):
                with self.assertRaises(EodError):
                    self.check_with_zone({"type": "FeatureCollection", "features": features})

    def test_missing_zone_file_is_an_error(self):
        with tempfile.TemporaryDirectory() as folder:
            data = copy_fixture_data(folder)
            (data / "flood-zone.geojson").unlink()
            with mock.patch.dict(os.environ, {"EOD_DATA_DIR": str(data)}):
                with self.assertRaises(EodError):
                    site_check.check_site("C", 1, "R2")


if __name__ == "__main__":
    unittest.main()
