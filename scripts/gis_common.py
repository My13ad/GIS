"""Shared constants for the GIS blind-path (盲道) accessibility project.

Imported by:

- ``scripts/generate_demo_data.py`` (demo dataset builder, Wave 2)
- Later-wave modules (map builder, PNG exporter) that need the city/column
  contract.

Code identifiers stay ASCII; the Chinese strings below are *data values*
(street / district / enum labels), not Python names. Every constant in
this module is part of the frozen contract referenced by
``tests/test_dataset.py`` — do not rename keys or change values without
updating that test file.
"""

# --- City center coordinates (GCJ-02, (latitude, longitude)) -------------
CITY_CENTERS = {
    "西宁":   (36.617, 101.778),
    "格尔木": (36.407, 94.903),
}

# --- Per-city bounding boxes — must match the test contract exactly. -----
CITY_BOUNDS = {
    "西宁":   {"lon": (101.70, 101.87), "lat": (36.58, 36.68)},
    "格尔木": {"lon": (94.85, 94.96),   "lat": (36.35, 36.46)},
}

# --- Per-city street anchors. Coordinates are real street locations so --
# --- points scattered +/-0.008 deg around them roughly trace street lines --
# --- while remaining strictly inside CITY_BOUNDS. -----------------------
CITY_STREETS = {
    "西宁": [
        {"name": "五四大街",   "lon": 101.770, "lat": 36.620},
        {"name": "长江路",     "lon": 101.795, "lat": 36.625},
        {"name": "七一路",     "lon": 101.785, "lat": 36.615},
        {"name": "胜利路",     "lon": 101.755, "lat": 36.635},
        {"name": "昆仑西路",   "lon": 101.740, "lat": 36.605},
        {"name": "祁连路",     "lon": 101.760, "lat": 36.640},
        {"name": "八一路",     "lon": 101.815, "lat": 36.610},
        {"name": "大众街",     "lon": 101.800, "lat": 36.630},
        {"name": "东关大街",   "lon": 101.810, "lat": 36.635},
        {"name": "南川东路",   "lon": 101.825, "lat": 36.595},
    ],
    "格尔木": [
        {"name": "昆仑路",     "lon": 94.905, "lat": 36.405},
        {"name": "黄河路",     "lon": 94.910, "lat": 36.415},
        {"name": "柴达木路",   "lon": 94.895, "lat": 36.395},
        {"name": "盐桥路",     "lon": 94.925, "lat": 36.420},
        {"name": "江源路",     "lon": 94.880, "lat": 36.430},
        {"name": "八一路",     "lon": 94.915, "lat": 36.385},
        {"name": "建设路",     "lon": 94.935, "lat": 36.395},
        {"name": "中山路",     "lon": 94.920, "lat": 36.410},
    ],
}

# --- Per-city plausible district names (real administrative divisions). -
DISTRICTS = {
    "西宁":   ["城西区", "城东区", "城北区", "城中区"],
    "格尔木": ["昆仑路街道", "黄河路街道", "金峰路街道"],
}

# --- Taxonomy -----------------------------------------------------------
PROBLEM_TYPES = ["盲道占用", "盲道破损", "规划问题"]

SUBTYPES = [
    "共享单车",
    "私家车",
    "杂物摊位",
    "砖块缺失",
    "线路中断",
    "线路曲折",
]

# (problem_type -> allowed subtypes) -- the swap contract for real data.
PROBLEM_SUBTYPE_MAP = {
    "盲道占用": ["共享单车", "私家车", "杂物摊位"],
    "盲道破损": ["砖块缺失"],
    "规划问题": ["线路中断", "线路曲折"],
}

SEVERITIES = ["低", "中", "高"]

# Reference weights for heatmap rendering (severity -> intensity).
SEVERITY_WEIGHT = {"低": 0.4, "中": 0.7, "高": 1.0}

# --- Frozen CSV schema (the swap contract for real data) ----------------
COLUMNS = [
    "id",
    "city",
    "district",
    "street",
    "longitude",
    "latitude",
    "problem_type",
    "subtype",
    "severity",
    "confidence",
    "description",
    "detected_at",
    "data_source",
]

DATA_SOURCE = "示例数据"
