import logging
from typing import Dict, Tuple, List, Any
import pandas as pd

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

        for table_name, twbx_df in twbx_tables.items():

            if table_name not in pbit_tables:

                results.append({
                    "table_name": table_name,
                    "result": "FAIL",
                    "reason": f"Table missing in PBIT: {table_name}"
                })

                all_pass = False
                continue

            pbit_df = pbit_tables[table_name]

            if len(twbx_df) != len(pbit_df):

                results.append({
                    "table_name": table_name,
                    "result": "FAIL",
                    "reason": f"Row count mismatch {len(twbx_df)} vs {len(pbit_df)}"
                })

                all_pass = False
                continue

            results.append({
                "table_name": table_name,
                "result": "PASS"
            })

        overall = "PASS" if all_pass else "FAIL"
        return overall, results