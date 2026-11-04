"""Tests may point the scripts at other data. Normal runs never can (see eod/scenario.py)."""
import os

os.environ["EOD_TESTING"] = "1"
