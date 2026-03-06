"""Semantic model comparison logic."""
import logging
from typing import Dict, List, Any, Tuple

logger = logging.getLogger(__name__)


class ModelComparator:
    """Compare semantic models (measures, calculated fields) between TWBX and PBIX."""

    def __init__(self):
        """Initialize the model comparator."""
        pass

    def compare_measures(
        self,
        twbx_measures: List[Dict[str, Any]],
        pbix_measures: List[Dict[str, Any]],
        verbose: bool = False,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Compare measures between TWBX and PBIX.

        Args:
            twbx_measures: List of measures from TWBX
            pbix_measures: List of measures from PBIX
            verbose: If True, log detailed information

        Returns:
            Tuple of (result, details)
        """
        result = "PASS"
        details = {
            "measures_matched": [],
            "measures_missing_in_pbix": [],
            "measures_missing_in_twbx": [],
            "expression_mismatches": [],
            "data_type_mismatches": [],
            "failure_reasons": [],
        }

        # Create lookup dictionaries by name (case-insensitive)
        twbx_by_name = {m["name"].lower(): m for m in twbx_measures}
        pbix_by_name = {m["name"].lower(): m for m in pbix_measures}

        all_measure_names = set(twbx_by_name.keys()) | set(pbix_by_name.keys())

        logger.info(f"Comparing {len(all_measure_names)} measures")

        for measure_key in sorted(all_measure_names):
            twbx_measure = twbx_by_name.get(measure_key)
            pbix_measure = pbix_by_name.get(measure_key)

            if twbx_measure and pbix_measure:
                # Both measures exist
                details["measures_matched"].append(twbx_measure["name"])

                # Compare expressions
                twbx_expr = twbx_measure.get("expression", "").strip()
                pbix_expr = pbix_measure.get("expression", "").strip()

                if twbx_expr and pbix_expr and twbx_expr != pbix_expr:
                    details["expression_mismatches"].append(
                        {
                            "measure": twbx_measure["name"],
                            "twbx_expression": twbx_expr[:100],  # Truncate for readability
                            "pbix_expression": pbix_expr[:100],
                        }
                    )
                    details["failure_reasons"].append(
                        f"Expression mismatch for measure {twbx_measure['name']}"
                    )
                    result = "FAIL"

                    if verbose:
                        logger.warning(
                            f"Measure '{twbx_measure['name']}' expressions differ"
                        )

                # Compare data types
                twbx_type = twbx_measure.get("data_type", "unknown")
                pbix_type = pbix_measure.get("data_type", "unknown")

                if twbx_type != pbix_type:
                    details["data_type_mismatches"].append(
                        {
                            "measure": twbx_measure["name"],
                            "twbx_type": twbx_type,
                            "pbix_type": pbix_type,
                        }
                    )
                    details["failure_reasons"].append(
                        f"Data type mismatch for measure {twbx_measure['name']}: {twbx_type} vs {pbix_type}"
                    )
                    result = "FAIL"

            elif twbx_measure:
                details["measures_missing_in_pbix"].append(twbx_measure["name"])
                details["failure_reasons"].append(
                    f"Measure '{twbx_measure['name']}' missing in PBIX"
                )
                result = "FAIL"

            else:  # pbix_measure
                details["measures_missing_in_twbx"].append(pbix_measure["name"])
                details["failure_reasons"].append(
                    f"Measure '{pbix_measure['name']}' missing in TWBX"
                )
                result = "FAIL"

        if verbose:
            logger.debug(f"Measure comparison: {len(details['measures_matched'])} matched")

        return result, details

    def compare_calculated_columns(
        self,
        twbx_columns: List[Dict[str, Any]],
        pbix_columns: List[Dict[str, Any]],
        verbose: bool = False,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Compare calculated columns between TWBX and PBIX.

        Args:
            twbx_columns: List of calculated columns from TWBX
            pbix_columns: List of calculated columns from PBIX
            verbose: If True, log detailed information

        Returns:
            Tuple of (result, details)
        """
        # Similar to measures, but focusing on calculated columns
        result = "PASS"
        details = {
            "columns_matched": [],
            "columns_missing_in_pbix": [],
            "columns_missing_in_twbx": [],
            "failure_reasons": [],
        }

        twbx_by_name = {col["name"].lower(): col for col in twbx_columns}
        pbix_by_name = {col["name"].lower(): col for col in pbix_columns}

        all_col_names = set(twbx_by_name.keys()) | set(pbix_by_name.keys())

        logger.info(f"Comparing {len(all_col_names)} calculated columns")

        for col_key in sorted(all_col_names):
            twbx_col = twbx_by_name.get(col_key)
            pbix_col = pbix_by_name.get(col_key)

            if twbx_col and pbix_col:
                details["columns_matched"].append(twbx_col["name"])
            elif twbx_col:
                details["columns_missing_in_pbix"].append(twbx_col["name"])
                result = "FAIL"
            else:
                details["columns_missing_in_twbx"].append(pbix_col["name"])
                result = "FAIL"

        return result, details

    def compare_tables_structure(
        self,
        twbx_tables: Dict[str, Dict[str, Any]],
        pbix_tables: Dict[str, Dict[str, Any]],
        verbose: bool = False,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Compare table structures (names, display names, columns).

        Args:
            twbx_tables: Table structures from TWBX
            pbix_tables: Table structures from PBIX
            verbose: If True, log detailed information

        Returns:
            Tuple of (result, details)
        """
        result = "PASS"
        details = {
            "tables_matched": [],
            "tables_missing_in_pbix": [],
            "tables_missing_in_twbx": [],
            "column_mismatches": [],
            "failure_reasons": [],
        }

        twbx_by_name = {name.lower(): name for name in twbx_tables.keys()}
        pbix_by_name = {name.lower(): name for name in pbix_tables.keys()}

        all_table_names = set(twbx_by_name.keys()) | set(pbix_by_name.keys())

        logger.info(f"Comparing {len(all_table_names)} table structures")

        for table_key in sorted(all_table_names):
            twbx_name = twbx_by_name.get(table_key)
            pbix_name = pbix_by_name.get(table_key)

            if twbx_name and pbix_name:
                details["tables_matched"].append(twbx_name)

                # Compare columns
                twbx_table = twbx_tables[twbx_name]
                pbix_table = pbix_tables[pbix_name]

                twbx_cols = {col["name"].lower() for col in twbx_table.get("columns", [])}
                pbix_cols = {
                    col["name"].lower() for col in pbix_table.get("columns", [])
                }

                if twbx_cols != pbix_cols:
                    result = "FAIL"
                    details["failure_reasons"].append(
                        f"Column mismatch in table {twbx_name}"
                    )

            elif twbx_name:
                details["tables_missing_in_pbix"].append(twbx_name)
                result = "FAIL"
                details["failure_reasons"].append(f"Table '{twbx_name}' missing in PBIX")

            else:
                details["tables_missing_in_twbx"].append(pbix_name)
                result = "FAIL"
                details["failure_reasons"].append(f"Table '{pbix_name}' missing in TWBX")

        if verbose:
            logger.debug(f"Table structure comparison: {len(details['tables_matched'])} matched")

        return result, details
