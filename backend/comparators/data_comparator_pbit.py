import logging
from typing import Dict, Tuple, List, Any
import pandas as pd

from comparators.data_comparator import _match_tables

logger = logging.getLogger(__name__)


class PbitDataComparator:

    def __init__(self, tolerance_pct: float = 0.5):
        self.tolerance_pct = tolerance_pct

    def compare_tables(
        self,
        twbx_tables: Dict[str, pd.DataFrame],
        pbit_tables: Dict[str, pd.DataFrame],
        verbose: bool = False,
    ) -> Tuple[str, List[Dict[str, Any]]]:

        results = []
        all_pass = True

        table_matches = _match_tables(twbx_tables, pbit_tables)

        for match in table_matches:
            twbx_name = match["twbx_name"]
            pbit_name = match["pbix_name"]
            display_name = twbx_name or pbit_name or "Unknown"

            if match["match_method"] == "unmatched":
                results.append({
                    "table_name": display_name,
                    "twbx_name": twbx_name,
                    "pbix_name": pbit_name,
                    "match_method": "unmatched",
                    "result": "FAIL",
                    "reason": match["name_note"],
                    "failure_reasons": [match["name_note"]],
                })
                all_pass = False
                continue

            twbx_df = twbx_tables[twbx_name]
            pbit_df = pbit_tables[pbit_name]
            twbx_rows = len(twbx_df)
            pbit_rows = len(pbit_df)

            result: Dict[str, Any] = {
                "table_name": display_name,
                "twbx_name": twbx_name,
                "pbix_name": pbit_name,
                "match_method": match["match_method"],
                "result": "PASS",
                "notes": [match["name_note"]] if match["name_note"] else [],
                "row_count_twbx": twbx_rows,
                "row_count_pbix": pbit_rows,
                "failure_reasons": [],
            }

            if twbx_rows != pbit_rows:
                diff_pct = abs(twbx_rows - pbit_rows) / twbx_rows * 100 if twbx_rows > 0 else 100.0
                if diff_pct >= self.tolerance_pct:
                    result["result"] = "FAIL"
                    result["failure_reasons"].append(
                        f"Row count mismatch: Tableau={twbx_rows}, Power BI={pbit_rows}"
                    )
                    all_pass = False

            results.append(result)

        overall = "PASS" if all_pass else "FAIL"
        return overall, results
