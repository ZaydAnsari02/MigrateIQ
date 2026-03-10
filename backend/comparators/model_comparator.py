"""Semantic model comparison logic."""
import logging
import re
from typing import Dict, List, Any, Tuple
from comparators.type_utils import get_type_group, are_types_compatible

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared normalisation (mirrors data_comparator rules)
# ---------------------------------------------------------------------------

def _norm_name(name: str) -> str:
    """
    Normalise a measure / column name for comparison.
    Rules: case-insensitive, spaces and underscores are equivalent.
    """
    return re.sub(r"[ _]+", "_", name.lower().strip())





# ---------------------------------------------------------------------------
# ModelComparator
# ---------------------------------------------------------------------------

class ModelComparator:
    """Compare semantic models (measures, calculated fields) between TWBX and PBIX."""

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # Measures
    # ------------------------------------------------------------------

    def compare_measures(
        self,
        twbx_measures: List[Dict[str, Any]],
        pbix_measures: List[Dict[str, Any]],
        verbose: bool = False,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Compare measures between TWBX and PBIX.

        Matching: case-insensitive, spaces ≈ underscores.
        Type comparison uses the equivalence map — compatible types PASS.

        Returns:
            (result, details)
        """
        result = "PASS"
        details: Dict[str, Any] = {
            "measures_matched": [],
            "measures_missing_in_pbix": [],
            "measures_missing_in_twbx": [],
            "expression_mismatches": [],
            "data_type_mismatches": [],
            "failure_reasons": [],
        }

        # Build normalised-name → measure lookup
        twbx_by_norm = {_norm_name(m["name"]): m for m in twbx_measures}
        pbix_by_norm  = {_norm_name(m["name"]): m for m in pbix_measures}

        all_keys = set(twbx_by_norm) | set(pbix_by_norm)
        logger.info(f"Comparing {len(all_keys)} measures")

        for key in sorted(all_keys):
            tw = twbx_by_norm.get(key)
            pb = pbix_by_norm.get(key)

            if tw and pb:
                details["measures_matched"].append(tw["name"])

                # Expression comparison
                tw_expr = tw.get("expression", "").strip()
                pb_expr = pb.get("expression", "").strip()
                if tw_expr and pb_expr and tw_expr != pb_expr:
                    details["expression_mismatches"].append({
                        "measure":          tw["name"],
                        "twbx_expression":  tw_expr[:100],
                        "pbix_expression":  pb_expr[:100],
                    })
                    details["failure_reasons"].append(
                        f"Expression mismatch for measure '{tw['name']}'"
                    )
                    result = "FAIL"
                    if verbose:
                        logger.warning(
                            f"Measure '{tw['name']}': expressions differ"
                        )

                # Type comparison (with equivalence map)
                tw_type = tw.get("data_type", "unknown")
                pb_type = pb.get("data_type", "unknown")
                if not are_types_compatible(tw_type, pb_type):
                    details["data_type_mismatches"].append({
                        "measure":      tw["name"],
                        "twbx_type":    tw_type,
                        "pbix_type":    pb_type,
                        "twbx_canonical": get_type_group(tw_type),
                        "pbix_canonical": get_type_group(pb_type),
                    })
                    details["failure_reasons"].append(
                        f"Incompatible type for measure '{tw['name']}': "
                        f"TWBX={tw_type} ({get_type_group(tw_type)}) "
                        f"PBIX={pb_type} ({get_type_group(pb_type)})"
                    )
                    result = "FAIL"

            elif tw:
                details["measures_missing_in_pbix"].append(tw["name"])
                details["failure_reasons"].append(
                    f"Measure '{tw['name']}' missing in PBIX"
                )
                result = "FAIL"

            else:
                details["measures_missing_in_twbx"].append(pb["name"])
                details["failure_reasons"].append(
                    f"Measure '{pb['name']}' missing in TWBX"
                )
                result = "FAIL"

        if verbose:
            logger.debug(
                f"Measure comparison: {len(details['measures_matched'])} matched"
            )

        return result, details

    # ------------------------------------------------------------------
    # Calculated columns
    # ------------------------------------------------------------------

    def compare_calculated_columns(
        self,
        twbx_columns: List[Dict[str, Any]],
        pbix_columns: List[Dict[str, Any]],
        verbose: bool = False,
    ) -> Tuple[str, Dict[str, Any]]:
        """Compare calculated columns between TWBX and PBIX."""
        result = "PASS"
        details: Dict[str, Any] = {
            "columns_matched": [],
            "columns_missing_in_pbix": [],
            "columns_missing_in_twbx": [],
            "failure_reasons": [],
        }

        twbx_by_norm = {_norm_name(c["name"]): c for c in twbx_columns}
        pbix_by_norm  = {_norm_name(c["name"]): c for c in pbix_columns}
        all_keys = set(twbx_by_norm) | set(pbix_by_norm)

        logger.info(f"Comparing {len(all_keys)} calculated columns")

        for key in sorted(all_keys):
            tw = twbx_by_norm.get(key)
            pb = pbix_by_norm.get(key)
            if tw and pb:
                details["columns_matched"].append(tw["name"])
            elif tw:
                details["columns_missing_in_pbix"].append(tw["name"])
                result = "FAIL"
            else:
                details["columns_missing_in_twbx"].append(pb["name"])
                result = "FAIL"

        return result, details

    # ------------------------------------------------------------------
    # Table structures
    # ------------------------------------------------------------------

    def compare_tables_structure(
        self,
        twbx_tables: Dict[str, Dict[str, Any]],
        pbix_tables: Dict[str, Dict[str, Any]],
        verbose: bool = False,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Compare table structures (names, column names, column types).

        Uses the same normalisation rules as DataComparator:
          • Case-insensitive
          • Spaces ≈ underscores
          • Type equivalence map for compatible-type PASS
        """
        result = "PASS"
        details: Dict[str, Any] = {
            "tables_matched": [],
            "tables_missing_in_pbix": [],
            "tables_missing_in_twbx": [],
            "column_mismatches": [],
            "failure_reasons": [],
            "notes": [],
        }

        twbx_by_norm = {_norm_name(n): n for n in twbx_tables}
        pbix_by_norm  = {_norm_name(n): n for n in pbix_tables}
        all_keys = set(twbx_by_norm) | set(pbix_by_norm)

        logger.info(f"Comparing {len(all_keys)} table structures")

        for key in sorted(all_keys):
            tw_name = twbx_by_norm.get(key)
            pb_name = pbix_by_norm.get(key)

            if tw_name and pb_name:
                details["tables_matched"].append(tw_name)

                # Note if display names differ even though normalised names match
                if tw_name != pb_name:
                    details["notes"].append(
                        f"Table name differs: TWBX='{tw_name}' PBIX='{pb_name}'"
                    )

                tw_table = twbx_tables[tw_name]
                pb_table = pbix_tables[pb_name]

                # Build normalised column maps
                tw_col_map = {
                    _norm_name(c["name"]): c
                    for c in tw_table.get("columns", [])
                }
                pb_col_map = {
                    _norm_name(c["name"]): c
                    for c in pb_table.get("columns", [])
                }

                tw_norm = set(tw_col_map)
                pb_norm = set(pb_col_map)

                missing_in_pbix = sorted(
                    tw_col_map[n]["name"] for n in tw_norm - pb_norm
                )
                missing_in_twbx = sorted(
                    pb_col_map[n]["name"] for n in pb_norm - tw_norm
                )

                col_mismatch: Dict[str, Any] = {
                    "table": tw_name,
                    "columns_missing_in_pbix": missing_in_pbix,
                    "columns_missing_in_twbx": missing_in_twbx,
                    "type_mismatches": [],
                }

                if missing_in_pbix or missing_in_twbx:
                    result = "FAIL"
                    if missing_in_pbix:
                        details["failure_reasons"].append(
                            f"Table '{tw_name}': columns missing in PBIX: "
                            f"{', '.join(missing_in_pbix)}"
                        )
                    if missing_in_twbx:
                        details["failure_reasons"].append(
                            f"Table '{tw_name}': columns missing in TWBX: "
                            f"{', '.join(missing_in_twbx)}"
                        )

                # Type check on matched columns
                for norm_col in tw_norm & pb_norm:
                    tw_col = tw_col_map[norm_col]
                    pb_col = pb_col_map[norm_col]
                    tw_type = tw_col.get("data_type", "unknown")
                    pb_type = pb_col.get("data_type", "unknown")
                    if not are_types_compatible(tw_type, pb_type):
                        col_mismatch["type_mismatches"].append({
                            "column":           tw_col["name"],
                            "twbx_type":        tw_type,
                            "pbix_type":        pb_type,
                            "twbx_canonical":   get_type_group(tw_type),
                            "pbix_canonical":   get_type_group(pb_type),
                        })
                        result = "FAIL"
                        details["failure_reasons"].append(
                            f"Table '{tw_name}', column '{tw_col['name']}': "
                            f"incompatible types TWBX={tw_type} "
                            f"PBIX={pb_type}"
                        )

                if (col_mismatch["columns_missing_in_pbix"]
                        or col_mismatch["columns_missing_in_twbx"]
                        or col_mismatch["type_mismatches"]):
                    details["column_mismatches"].append(col_mismatch)

            elif tw_name:
                details["tables_missing_in_pbix"].append(tw_name)
                result = "FAIL"
                details["failure_reasons"].append(
                    f"Table '{tw_name}' missing in PBIX"
                )

            else:
                details["tables_missing_in_twbx"].append(pb_name)
                result = "FAIL"
                details["failure_reasons"].append(
                    f"Table '{pb_name}' missing in TWBX"
                )

        if verbose:
            logger.debug(
                f"Table structure comparison: "
                f"{len(details['tables_matched'])} matched"
            )

        return result, details