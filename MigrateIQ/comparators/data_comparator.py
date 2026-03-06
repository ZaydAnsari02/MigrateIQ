"""Data comparison logic for TWBX and PBIX files."""
import logging
from typing import Dict, List, Any, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


class DataComparator:
    """Compare data tables between TWBX and PBIX."""

    TOLERANCE_PCT = 0.5

    def __init__(self, tolerance_pct: float = 0.5):
        """
        Initialize the data comparator.

        Args:
            tolerance_pct: Acceptable percentage difference for numeric metrics
        """
        self.tolerance_pct = tolerance_pct

    def compare_tables(
        self,
        twbx_tables: Dict[str, pd.DataFrame],
        pbix_tables: Dict[str, pd.DataFrame],
        verbose: bool = False,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Compare data tables from TWBX and PBIX.

        Args:
            twbx_tables: Dictionary of table names to DataFrames from TWBX
            pbix_tables: Dictionary of table names to DataFrames from PBIX
            verbose: If True, log detailed per-column information

        Returns:
            Tuple of (overall_result, detailed_comparisons)
        """
        results = []
        all_pass = True

        # Get all unique table names (case-insensitive)
        twbx_table_names = {name.lower(): name for name in twbx_tables.keys()}
        pbix_table_names = {name.lower(): name for name in pbix_tables.keys()}

        all_table_names = set(twbx_table_names.keys()) | set(pbix_table_names.keys())

        logger.info(f"Comparing {len(all_table_names)} tables")

        for table_key in sorted(all_table_names):
            twbx_name = twbx_table_names.get(table_key)
            pbix_name = pbix_table_names.get(table_key)

            result = self._compare_single_table(
                twbx_name,
                pbix_name,
                twbx_tables,
                pbix_tables,
                verbose,
            )

            results.append(result)

            if result["result"] == "FAIL":
                all_pass = False

        overall_result = "PASS" if all_pass else "FAIL"
        logger.info(f"Data comparison result: {overall_result}")

        return overall_result, results

    def _compare_single_table(
        self,
        twbx_name: str,
        pbix_name: str,
        twbx_tables: Dict[str, pd.DataFrame],
        pbix_tables: Dict[str, pd.DataFrame],
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """Compare a single table between TWBX and PBIX."""
        result = {
            "table_name": twbx_name or pbix_name or "Unknown",
            "result": "PASS",
            "row_count_twbx": None,
            "row_count_pbix": None,
            "row_count_diff_pct": None,
            "columns_matched": [],
            "columns_missing_in_pbix": [],
            "columns_missing_in_twbx": [],
            "column_type_mismatches": [],
            "failure_reasons": [],
        }

        # Check if tables exist in both files
        if not twbx_name or twbx_name not in twbx_tables:
            result["failure_reasons"].append(
                f"Table '{result['table_name']}' missing in TWBX"
            )
            result["result"] = "FAIL"

        if not pbix_name or pbix_name not in pbix_tables:
            result["failure_reasons"].append(
                f"Table '{result['table_name']}' missing in PBIX"
            )
            result["result"] = "FAIL"

        if result["result"] == "FAIL":
            return result

        # Both tables exist, now compare them
        twbx_df = twbx_tables[twbx_name]
        pbix_df = pbix_tables[pbix_name]

        # Compare row counts
        twbx_rows = len(twbx_df)
        pbix_rows = len(pbix_df)
        result["row_count_twbx"] = twbx_rows
        result["row_count_pbix"] = pbix_rows

        if twbx_rows > 0:
            row_diff_pct = abs(twbx_rows - pbix_rows) / twbx_rows * 100
            result["row_count_diff_pct"] = round(row_diff_pct, 2)

            if row_diff_pct >= self.tolerance_pct:
                result["failure_reasons"].append(
                    f"Row count difference {row_diff_pct:.2f}% exceeds tolerance {self.tolerance_pct}%"
                )
                result["result"] = "FAIL"
        else:
            result["row_count_diff_pct"] = 0.0

        # Compare columns
        twbx_cols = set(twbx_df.columns)
        pbix_cols = set(pbix_df.columns)

        result["columns_matched"] = sorted(list(twbx_cols & pbix_cols))
        result["columns_missing_in_pbix"] = sorted(list(twbx_cols - pbix_cols))
        result["columns_missing_in_twbx"] = sorted(list(pbix_cols - twbx_cols))

        if result["columns_missing_in_pbix"]:
            result["failure_reasons"].append(
                f"Columns missing in PBIX: {', '.join(result['columns_missing_in_pbix'])}"
            )
            result["result"] = "FAIL"

        if result["columns_missing_in_twbx"]:
            result["failure_reasons"].append(
                f"Columns missing in TWBX: {', '.join(result['columns_missing_in_twbx'])}"
            )
            result["result"] = "FAIL"

        # Compare data types for matched columns
        for col in result["columns_matched"]:
            twbx_dtype = str(twbx_df[col].dtype)
            pbix_dtype = str(pbix_df[col].dtype)

            if twbx_dtype != pbix_dtype:
                mismatch = {
                    "column": col,
                    "twbx_type": twbx_dtype,
                    "pbix_type": pbix_dtype,
                }
                result["column_type_mismatches"].append(mismatch)

                if verbose:
                    logger.warning(
                        f"Type mismatch in {result['table_name']}.{col}: "
                        f"{twbx_dtype} vs {pbix_dtype}"
                    )

                # Data type mismatch is a failure
                result["failure_reasons"].append(
                    f"Type mismatch in column {col}: {twbx_dtype} vs {pbix_dtype}"
                )
                result["result"] = "FAIL"

        if verbose and result["columns_matched"]:
            logger.debug(
                f"Table {result['table_name']}: {len(result['columns_matched'])} columns matched"
            )

        return result

    def get_summary_stats(self, tables: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Calculate summary statistics for tables."""
        stats = {}

        for table_name, df in tables.items():
            stats[table_name] = {
                "row_count": len(df),
                "column_count": len(df.columns),
                "column_types": {col: str(df[col].dtype) for col in df.columns},
            }

        return stats
