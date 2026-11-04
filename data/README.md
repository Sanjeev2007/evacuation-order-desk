# Data sources and licences

Everything here supports a **hypothetical drill**. No real flood, release, order or alert is involved.

**The repo's MIT licence covers the code only. It does not cover the files in this folder.** Each file keeps the terms below.

| File | Real or synthetic | Licence |
|---|---|---|
| `flood-zone.geojson` | Real official hazard data, converted and clipped by this project | CC BY 4.0 |
| `sites.geojson` | Real OpenStreetMap locations, labelled A, B, C | ODbL 1.0 |
| `scenario.json` | Numbers invented; town names real | ODbL 1.0 |

## flood-zone.geojson

- **Source:** MITECO, *Peligrosidad por inundación fluvial T=100* (layer `NZ.Flood.FluvialT100`, identifier `ESNZSNCZIMPFT100`), from the national flood map system (SNCZI). Served by the [IDEE INSPIRE WMS](https://servicios.idee.es/wms-inspire/riesgos-naturales/inundaciones?request=getcapabilities&service=wms).
- **Retrieved:** 4 Nov 2026
- **Licence:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), as stated on the [datos.gob.es record](https://datos.gob.es/en/catalogo/e0dat0002-peligrosidad-por-inundacion-fluvial-t100).
- **Attribution to use:**
  > Flood hazard data: Ministerio para la Transición Ecológica y el Reto Demográfico (MITECO), Sistema Nacional de Cartografía de Zonas Inundables, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Traced to polygons, clipped and simplified by this project. MITECO does not endorse this project.

### What this file is, and isn't

**This is the official layer's picture turned into polygons, not an official vector file.** The official vector downloads and MITECO's own WMS are on `gis.miteco.gob.es`, which reset every connection on 4 Nov 2026. So this project did the following:

1. Requested the layer as one PNG (GetMap) for lon -0.66 to -0.3999, lat 39.16 to 39.37, at 1734 x 1400 pixels. Each pixel is about 13 m by 17 m.
2. Counted a pixel as flooded when its alpha was 128 or more.
3. Traced the outlines, removed patches and pin-holes under 4 pixels, and simplified by half a pixel.

**Checks:** 4,995 of 5,000 random points agreed between the polygons and the source image, and no ring crosses itself.

**Limits:**
- Edges are accurate only to about a pixel or two. Don't use this file for anything except the drill.
- Depth classes were dropped. The file only says flooded or not flooded.
- The clip is a rectangle, so it also includes flood areas from other watercourses inside it, such as the plain where the Magro nears the Júcar.
- The layer models a 100-year flood. It doesn't model a release from Forata, and it covers only the river stretches MITECO studied.
- The river's upper stretch, from Forata to about Montroi, is outside the clip.

## sites.geojson

- **Source:** [OpenStreetMap](https://www.openstreetmap.org/copyright), through the Overpass API (`overpass-api.de`). Database timestamp about 07:21 UTC on 4 Nov 2026.
- **Retrieved:** 4 Nov 2026
- **Licence:** [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/)
- **Attribution to use:** © OpenStreetMap contributors
- **Real:** the three points started as the centres of mapped `leisure=sports_centre` areas.
- **Changed on purpose:** coordinates are rounded to 3 decimal places, about 100 m, so a point doesn't mark a specific building exactly.
- **Deliberately left out:** building names, addresses and OSM IDs. The project refers only to Site A, B and C, and never calls a real building unsafe.

| Site | Point-in-polygon result, using the rounded point |
|---|---|
| A | Inside |
| B | Outside |
| C | Outside |

**How the sites were chosen:** all sports centres, sports halls and schools in the clip area within 2 km of a Magro town were tested. A was chosen for being furthest inside the zone. B and C were chosen for being clear of it and near the at-risk towns. Being "inside" means inside the saved layer, for this drill only. **It says nothing about whether a real building is safe, and neither does "outside".**

## scenario.json

- **Source:** written by this project on 4 Nov 2026.
- **Synthetic:** every number, including inflow, level, releases, thresholds, evacuees, staff, boats and capacities. None is a measurement, an estimate or a real population figure.
- **Real:** the five town names, listed in river order below Forata.
- **Licence:** [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/). The numbers are this project's own, but its site capacities are keyed to Sites A, B and C, so the cautious choice is to offer it under the same licence as `sites.geojson`.

**How the river order was checked:**

| Town | River km below Forata | Distance from river |
|---|---|---|
| Montroi | 38.0 | 0.20 km |
| Alfarb | 48.2 | 0.44 km |
| Carlet | 57.0 | 0.37 km |
| l'Alcúdia | 59.8 | 1.49 km |
| Algemesí | 66.1 | 0.65 km |

These were measured along the OSM river line (`Riu Magre`, 9 connected ways, 69 km from the dam to the Júcar). The order also matches the [Spanish Wikipedia article on the Magro](https://es.wikipedia.org/wiki/R%C3%ADo_Magro), which mentions the same towns in the same order, although it isn't written as an ordered list. l'Alcúdia's position comes from its nearest point on the river, as it sits about 1.5 km away.

## What the ODbL requires here

*This is a plain reading by a non-lawyer, not legal advice.* Sources: [ODbL 1.0 full text](https://opendatacommons.org/licenses/odbl/1-0/), [ODbL summary](https://opendatacommons.org/licenses/odbl/summary/), [OSMF licence FAQ](https://wiki.osmfoundation.org/wiki/Licence/Licence_and_Legal_FAQ), [OSMF Substantial guideline](https://osmfoundation.org/wiki/Licence/Community_Guidelines/Substantial_-_Guideline), [OSMF attribution guideline](https://wiki.osmfoundation.org/wiki/Licence/Attribution_Guidelines). Only the licence text is binding. The guidelines are community policy.

**Attribution and notices (sections 4.2 and 4.3).** Anyone sharing the data must keep the licence and copyright notices with it. A public work made from the data, such as the demo video or a screenshot of site results, needs a notice too. ODbL's own example wording works:

> Contains information from [OpenStreetMap](https://www.openstreetmap.org/), which is made available here under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1-0/).

`sites.geojson` carries the attribution and licence as top-level fields, and this file repeats them.

**Share-alike (sections 4.4 to 4.6).** A Derivative Database that is used publicly must stay under the ODbL, and recipients must be offered a copy or the method for making it. That applies to extracting a *Substantial* part of OSM.
- The OSMF guideline treats fewer than 100 features as not Substantial, **if the extraction is one-off and not repeated for the same or a similar project**. It counts repeated small extractions as one big one.
- This file has 3 features, so under that guideline it probably doesn't trigger share-alike.
- The licence itself doesn't set a number, and the guideline isn't binding.
- **To stay within the guideline, don't re-extract repeatedly from OSM for this project.**

**This project's approach:** `sites.geojson` is offered under the ODbL anyway. That's the cautious choice, and it costs nothing because the file is public and the selection method is described above. Other independent files don't become ODbL just by sitting beside it (section 4.5a), and images or video made from it are Produced Works, which need the notice above but aren't themselves share-alike (section 4.5b).

The root README and the video must carry both attributions, and the root README repeats that MIT doesn't cover `data/`.
