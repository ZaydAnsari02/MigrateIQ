"""Data comparison logic for TWBX and PBIX files."""
import logging
import re
from difflib import SequenceMatcher
from typing import Dict, List, Any, Tuple, Optional
import pandas as pd
from comparators.type_utils import get_type_group, are_types_compatible

logger = logging.getLogger(__name__)





# ---------------------------------------------------------------------------
# Column name normalisation
#
# Rules (per spec):
#   1. Case-insensitive
#   2. Spaces and underscores are equivalent
# ---------------------------------------------------------------------------
def _norm_col(name: str) -> str:
    """Normalise a column name for comparison."""
    return re.sub(r"[ _]+", "_", name.lower().strip())


# ---------------------------------------------------------------------------
# Fuzzy string similarity
# ---------------------------------------------------------------------------
def _name_similarity(a: str, b: str) -> float:
    """Return 0–1 similarity between two table names (case-insensitive)."""
    return SequenceMatcher(
        None, a.lower().strip(), b.lower().strip()
    ).ratio()


# ---------------------------------------------------------------------------
# Table-matching strategy
#
# Priority:
#   1. Exact name match (case-insensitive, spaces≈underscores)
#   2. Fuzzy name match  (similarity >= FUZZY_THRESHOLD)
#   3. Best column-overlap match (if no fuzzy match found)
#
# A TWBX table and a PBIX table can only be matched once (greedy best-first).
# ---------------------------------------------------------------------------
FUZZY_THRESHOLD = 0.6      # minimum similarity to accept a fuzzy name match
OVERLAP_THRESHOLD = 0.5    # minimum column overlap ratio to accept a column match


def _col_overlap(twbx_cols: List[str], pbix_cols: List[str]) -> float:
    """
    Return the Jaccard overlap of two normalised column name sets.
    Returns 0.0 if either set is empty.
    """
    a = {_norm_col(c) for c in twbx_cols}
    b = {_norm_col(c) for c in pbix_cols}
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _match_tables(
    twbx_tables: Dict[str, pd.DataFrame],
    pbix_tables: Dict[str, pd.DataFrame],
) -> List[Dict[str, Any]]:
    """
    Produce a list of match records, one per TWBX table.

    Each record has:
        twbx_name       : original TWBX table name
        pbix_name       : matched PBIX table name, or None
        match_method    : 'exact' | 'fuzzy' | 'column_overlap' | 'unmatched'
        name_note       : human-readable note if names differ
        similarity      : similarity score used (0–1)
    """
    matches: List[Dict[str, Any]] = []
    unmatched_pbix = set(pbix_tables.keys())

    def _best_pbix_for(twbx_name: str) -> Optional[Tuple[str, str, str, float]]:
        """Return (pbix_name, method, note, score) or None."""
        twbx_norm = _norm_col(twbx_name)

        # --- Pass 1: exact (normalised) name match ---
        for pbix_name in list(unmatched_pbix):
            if _norm_col(pbix_name) == twbx_norm:
                return pbix_name, "exact", "", 1.0

        # --- Pass 2: fuzzy name match ---
        best_name, best_score = None, 0.0
        for pbix_name in unmatched_pbix:
            score = _name_similarity(twbx_name, pbix_name)
            if score > best_score:
                best_score, best_name = score, pbix_name
        if best_name and best_score >= FUZZY_THRESHOLD:
            note = (
                f"Table name differs: TWBX='{twbx_name}' "
                f"PBIX='{best_name}' (similarity {best_score:.0%})"
            )
            return best_name, "fuzzy", note, best_score

        # --- Pass 3: column overlap ---
        twbx_cols = list(twbx_tables[twbx_name].columns)
        best_name, best_overlap = None, 0.0
        for pbix_name in unmatched_pbix:
            pbix_cols = list(pbix_tables[pbix_name].columns)
            overlap = _col_overlap(twbx_cols, pbix_cols)
            if overlap > best_overlap:
                best_overlap, best_name = overlap, pbix_name
        if best_name and best_overlap >= OVERLAP_THRESHOLD:
            note = (
                f"Table name differs: TWBX='{twbx_name}' "
                f"PBIX='{best_name}' (matched by column overlap {best_overlap:.0%})"
            )
            return best_name, "column_overlap", note, best_overlap

        return None

    for twbx_name in twbx_tables:
        result = _best_pbix_for(twbx_name)
        if result:
            pbix_name, method, note, score = result
            unmatched_pbix.discard(pbix_name)
            matches.append({
                "twbx_name": twbx_name,
                "pbix_name": pbix_name,
                "match_method": method,
                "name_note": note,
                "similarity": score,
            })
        else:
            matches.append({
                "twbx_name": twbx_name,
                "pbix_name": None,
                "match_method": "unmatched",
                "name_note": f"No matching table found in PBIX for TWBX table '{twbx_name}'",
                "similarity": 0.0,
            })

    # Tables that exist in PBIX but were never matched
    for pbix_name in unmatched_pbix:
        matches.append({
            "twbx_name": None,
            "pbix_name": pbix_name,
            "match_method": "unmatched",
            "name_note": f"No matching table found in TWBX for PBIX table '{pbix_name}'",
            "similarity": 0.0,
        })

    return matches


# ---------------------------------------------------------------------------
# Main comparator class
# ---------------------------------------------------------------------------
class DataComparator:
    """Compare data tables between TWBX and PBIX."""

    def __init__(self, tolerance_pct: float = 0.5):
        """
        Args:
            tolerance_pct: Acceptable % row-count difference before FAIL.
        """
        self.tolerance_pct = tolerance_pct

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def compare_tables(
        self,
        twbx_tables: Dict[str, pd.DataFrame],
        pbix_tables: Dict[str, pd.DataFrame],
        verbose: bool = False,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Compare data tables from TWBX and PBIX.

        Matching strategy (per spec):
          1. Exact normalised name match
          2. Fuzzy name match (≥60% similarity)  → PASS with name-diff note
          3. Column-overlap fallback (≥50% Jaccard) → PASS with name-diff note
          4. No match found → FAIL

        Returns:
            (overall_result, list_of_per_table_results)
        """
        results: List[Dict[str, Any]] = []
        all_pass = True

        table_matches = _match_tables(twbx_tables, pbix_tables)
        logger.info(f"Comparing {len(table_matches)} tables")

        for match in table_matches:
            result = self._compare_matched_pair(match, twbx_tables, pbix_tables, verbose)
            results.append(result)
            if result["result"] == "FAIL":
                all_pass = False

        overall = "PASS" if all_pass else "FAIL"
        logger.info(f"Data comparison result: {overall}")
        return overall, results

    # ------------------------------------------------------------------
    # Per-pair comparison
    # ------------------------------------------------------------------

    def _compare_matched_pair(
        self,
        match: Dict[str, Any],
        twbx_tables: Dict[str, pd.DataFrame],
        pbix_tables: Dict[str, pd.DataFrame],
        verbose: bool,
    ) -> Dict[str, Any]:
        """Run all checks for a single matched (or unmatched) table pair."""

        twbx_name = match["twbx_name"]
        pbix_name = match["pbix_name"]
        display_name = twbx_name or pbix_name or "Unknown"

        result: Dict[str, Any] = {
            "table_name": display_name,
            "twbx_name": twbx_name,
            "pbix_name": pbix_name,
            "match_method": match["match_method"],
            "result": "PASS",
            "notes": [],
            # Check 1
            "name_match": match["match_method"] == "exact",
            # Check 2
            "column_count_twbx": None,
            "column_count_pbix": None,
            "column_count_match": None,
            # Check 3
            "columns_matched": [],
            "columns_missing_in_pbix": [],
            "columns_missing_in_twbx": [],
            "column_type_mismatches": [],
            # Row count (retained for compatibility)
            "row_count_twbx": None,
            "row_count_pbix": None,
            "row_count_diff_pct": None,
            "failure_reasons": [],
        }

        # ── Check 1: table name ─────────────────────────────────────────
        if match["name_note"]:
            result["notes"].append(match["name_note"])
            if verbose:
                logger.info(f"[TABLE NAME NOTE] {match['name_note']}")

        # ── Unmatched table → hard FAIL ─────────────────────────────────
        if match["match_method"] == "unmatched":
            result["result"] = "FAIL"
            result["failure_reasons"].append(match["name_note"])
            return result

        twbx_df = twbx_tables[twbx_name]
        pbix_df = pbix_tables[pbix_name]

        # ── Row count ───────────────────────────────────────────────────
        twbx_rows = len(twbx_df)
        pbix_rows = len(pbix_df)
        result["row_count_twbx"] = twbx_rows
        result["row_count_pbix"] = pbix_rows

        if twbx_rows == 0 and pbix_rows == 0:
            result["row_count_diff_pct"] = 0.0
        elif twbx_rows == 0:
            result["row_count_diff_pct"] = 100.0
            result["result"] = "FAIL"
            result["failure_reasons"].append(
                f"Row count mismatch: TWBX has 0 rows, but PBIX has {pbix_rows}"
            )
        else:
            diff_pct = abs(twbx_rows - pbix_rows) / twbx_rows * 100
            result["row_count_diff_pct"] = round(diff_pct, 2)
            if diff_pct >= self.tolerance_pct:
                result["result"] = "FAIL"
                result["failure_reasons"].append(
                    f"Row count difference {diff_pct:.2f}% exceeds "
                    f"tolerance {self.tolerance_pct}%"
                )

        # ── Check 2: column count ───────────────────────────────────────
        twbx_col_count = len(twbx_df.columns)
        pbix_col_count = len(pbix_df.columns)
        result["column_count_twbx"] = twbx_col_count
        result["column_count_pbix"] = pbix_col_count
        result["column_count_match"] = twbx_col_count == pbix_col_count

        if not result["column_count_match"]:
            result["result"] = "FAIL"
            result["failure_reasons"].append(
                f"Column count mismatch: TWBX has {twbx_col_count} "
                f"column(s), PBIX has {pbix_col_count}"
            )
            if verbose:
                logger.warning(
                    f"[{display_name}] Column count: "
                    f"TWBX={twbx_col_count} PBIX={pbix_col_count}"
                )

        # ── Check 3: column names + types ──────────────────────────────
        # Build normalised-name → original-name lookup for each side
        twbx_col_map: Dict[str, str] = {_norm_col(c): c for c in twbx_df.columns}
        pbix_col_map: Dict[str, str] = {_norm_col(c): c for c in pbix_df.columns}

        twbx_norm_set = set(twbx_col_map.keys())
        pbix_norm_set = set(pbix_col_map.keys())

        matched_norm = twbx_norm_set & pbix_norm_set
        missing_in_pbix_norm = twbx_norm_set - pbix_norm_set
        missing_in_twbx_norm = pbix_norm_set - twbx_norm_set

        # Report using original names for readability
        result["columns_matched"] = sorted(
            twbx_col_map[n] for n in matched_norm
        )
        result["columns_missing_in_pbix"] = sorted(
            twbx_col_map[n] for n in missing_in_pbix_norm
        )
        result["columns_missing_in_twbx"] = sorted(
            pbix_col_map[n] for n in missing_in_twbx_norm
        )

        if result["columns_missing_in_pbix"]:
            result["result"] = "FAIL"
            result["failure_reasons"].append(
                f"Columns missing in PBIX: "
                f"{', '.join(result['columns_missing_in_pbix'])}"
            )

        if result["columns_missing_in_twbx"]:
            result["result"] = "FAIL"
            result["failure_reasons"].append(
                f"Columns missing in TWBX: "
                f"{', '.join(result['columns_missing_in_twbx'])}"
            )

        # Type comparison for matched columns (with equivalence map)
        for norm_name in sorted(matched_norm):
            twbx_orig = twbx_col_map[norm_name]
            pbix_orig = pbix_col_map[norm_name]

            twbx_dtype = str(twbx_df[twbx_orig].dtype)
            pbix_dtype = str(pbix_df[pbix_orig].dtype)

            if not are_types_compatible(twbx_dtype, pbix_dtype):
                mismatch = {
                    "column": twbx_orig,
                    "twbx_type": twbx_dtype,
                    "pbix_type": pbix_dtype,
                    "twbx_canonical": get_type_group(twbx_dtype),
                    "pbix_canonical": get_type_group(pbix_dtype),
                }
                result["column_type_mismatches"].append(mismatch)
                result["result"] = "FAIL"
                result["failure_reasons"].append(
                    f"Incompatible type for column '{twbx_orig}': "
                    f"TWBX={twbx_dtype} ({get_type_group(twbx_dtype)}) "
                    f"PBIX={pbix_dtype} ({get_type_group(pbix_dtype)})"
                )
                if verbose:
                    logger.warning(
                        f"[{display_name}.{twbx_orig}] Type incompatible: "
                        f"{twbx_dtype} vs {pbix_dtype}"
                    )
            else:
                if twbx_dtype != pbix_dtype and verbose:
                    logger.debug(
                        f"[{display_name}.{twbx_orig}] Types differ but "
                        f"are compatible: {twbx_dtype} ≈ {pbix_dtype}"
                    )

        if verbose and result["columns_matched"]:
            logger.debug(
                f"[{display_name}] {len(result['columns_matched'])} "
                f"columns matched"
            )

        return result

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def get_summary_stats(
        self, tables: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """Calculate summary statistics for a set of tables."""
        return {
            table_name: {
                "row_count": len(df),
                "column_count": len(df.columns),
                "column_types": {col: str(df[col].dtype) for col in df.columns},
            }
            for table_name, df in tables.items()
        }