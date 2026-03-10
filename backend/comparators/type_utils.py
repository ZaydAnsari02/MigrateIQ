"""Shared type equivalence utilities for data and model comparators."""
from typing import Dict

# ---------------------------------------------------------------------------
# Type equivalence map
#
# Tableau types  ->  compatible Power BI types (and vice-versa).
# Keys are lowercased.  If two types share the same canonical group they are
# considered equivalent and the comparison PASSes for that column/measure.
# ---------------------------------------------------------------------------
_TYPE_GROUPS: Dict[str, str] = {
    # Text / string
    "string":   "text",
    "str":      "text",
    "text":     "text",
    "wstr":     "text",
    "object":   "text",       # pandas default for string columns
    # Integer
    "integer":  "integer",
    "int":      "integer",
    "int64":    "integer",
    "int32":    "integer",
    "int16":    "integer",
    "int8":     "integer",
    "long":     "integer",
    # Decimal / float
    "real":     "decimal",
    "double":   "decimal",
    "float":    "decimal",
    "float64":  "decimal",
    "float32":  "decimal",
    "decimal":  "decimal",
    "currency": "decimal",
    # Boolean
    "boolean":  "boolean",
    "bool":     "boolean",
    # Date / time
    "date":     "datetime",
    "datetime": "datetime",
    "datetime64[ns]": "datetime",
    "timestamp": "datetime",
    "time":     "datetime",
    "unknown":  "unknown",
}


def get_type_group(type_str: str) -> str:
    """Return the canonical type group for a given type string."""
    return _TYPE_GROUPS.get(type_str.lower().strip(), type_str.lower().strip())


def are_types_compatible(t1: str, t2: str) -> bool:
    """
    Return True if two type strings map to the same canonical group.
    'unknown' on either side is treated as compatible.
    """
    g1, g2 = get_type_group(t1), get_type_group(t2)
    if "unknown" in (g1, g2):
        return True
    return g1 == g2
