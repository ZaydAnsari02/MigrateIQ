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
# Rules:
#   1. Case-insensitive
#   2. Spaces, underscores, hyphens, and dots are equivalent separators
#   3. CamelCase is split into tokens ("ProductID" → "product_id")
#   4. Power BI bracket notation stripped ("[Column Name]" → "column_name")
# ---------------------------------------------------------------------------
def _norm_col(name: str) -> str:
    """Normalise a column name for comparison."""
    s = name.strip()
    # Strip Power BI bracket notation: [Column Name] → Column Name
    s = re.sub(r'^\[|\]$', '', s)
    # CamelCase → snake_case: "ProductID" → "Product_ID", "myCol" → "my_Col"
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', s)
    # All separators (space, underscore, hyphen, dot) → underscore, lowercase
    s = re.sub(r'[ _\-\.]+', '_', s.lower())
    # Collapse multiple underscores and strip leading/trailing
    s = re.sub(r'_+', '_', s).strip('_')
    return s


# ---------------------------------------------------------------------------
# Fuzzy string similarity
# ---------------------------------------------------------------------------
def _norm_table_name(name: str) -> str:
    """
    Normalise a table name for fuzzy matching.
    Strips spaces, underscores, and hyphens; converts to lowercase.
    """
    return re.sub(r"[ _\-]+", "", name.lower().strip())


def _tokenize_name(name: str) -> set:
    """
    Split a table name into meaningful word tokens.
    Handles snake_case, kebab-case, space-separated, and camelCase names.
    Single-character tokens are ignored.
    """
    # Split on separators first
    parts = re.split(r"[ _\-]+", name.strip())
    tokens: set = set()
    for part in parts:
        # Also split camelCase: "testMetrics" -> ["test", "Metrics"]
        sub = re.sub(r"([a-z])([A-Z])", r"\1 \2", part).lower()
        tokens.update(t for t in sub.split() if len(t) > 1)
    return tokens


def _name_similarity(a: str, b: str) -> float:
    """
    Return 0–1 similarity between two table names.

    Tries three strategies and returns the maximum:
      1. Direct similarity on lowercased names (catches prefix/suffix diffs).
      2. Similarity after stripping separators (catches spacing/underscore diffs).
      3. Jaccard token overlap (catches same words in different order or with extras).
    """
    a_lo, b_lo = a.lower().strip(), b.lower().strip()
    score1 = SequenceMatcher(None, a_lo, b_lo).ratio()
    # Compare normalised (separators removed) versions
    a_norm, b_norm = _norm_table_name(a), _norm_table_name(b)
    score2 = SequenceMatcher(None, a_norm, b_norm).ratio() if (a_norm and b_norm) else 0.0
    # Token Jaccard overlap: "test_metrics" vs "dashboard_metrics" shares "metrics"
    a_tokens, b_tokens = _tokenize_name(a), _tokenize_name(b)
    if a_tokens and b_tokens:
        score3 = len(a_tokens & b_tokens) / len(a_tokens | b_tokens)
    else:
        score3 = 0.0
    return max(score1, score2, score3)


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
FUZZY_THRESHOLD = 0.45     # minimum similarity to accept a fuzzy name match
OVERLAP_THRESHOLD = 0.4    # minimum column overlap ratio to accept a column match
COL_FUZZY_THRESHOLD = 0.80 # minimum similarity to fuzzy-match individual columns


def _fuzzy_match_cols(
    unmatched_twbx: List[str],
    unmatched_pbix: List[str],
) -> List[Tuple[str, str, float]]:
    """
    Greedily match column names by similarity when exact normalisation fails.

    Returns a list of (twbx_col, pbix_col, score) pairs, best-score-first,
    ensuring each column is used at most once.
    """
    if not unmatched_twbx or not unmatched_pbix:
        return []
    candidates: List[Tuple[float, str, str]] = []
    for tc in unmatched_twbx:
        for pc in unmatched_pbix:
            score = _name_similarity(tc, pc)
            if score >= COL_FUZZY_THRESHOLD:
                candidates.append((score, tc, pc))
    candidates.sort(reverse=True)
    pairs: List[Tuple[str, str, float]] = []
    used_t: set = set()
    used_p: set = set()
    for score, tc, pc in candidates:
        if tc not in used_t and pc not in used_p:
            pairs.append((tc, pc, score))
            used_t.add(tc)
            used_p.add(pc)
    return pairs


def _col_overlap(twbx_cols: List[str], pbix_cols: List[str]) -> float:
    """
    Return the Jaccard overlap of two column name sets.

    Uses exact normalised matching first, then fuzzy fallback so that
    minor naming differences (e.g. "OrderID" vs "Order_ID") still contribute
    to the overlap score used for table matching.
    Returns 0.0 if either set is empty.
    """
    if not twbx_cols or not pbix_cols:
        return 0.0
    a = {_norm_col(c) for c in twbx_cols}
    b = {_norm_col(c) for c in pbix_cols}
    exact_count = len(a & b)
    unmatched_a = list(a - b)
    unmatched_b = list(b - a)
    # Fuzzy count: how many unmatched-a columns have a similar unmatched-b peer
    fuzzy_pairs = _fuzzy_match_cols(unmatched_a, unmatched_b)
    total_matched = exact_count + len(fuzzy_pairs)
    union_size = len(a | b)
    return total_matched / union_size if union_size > 0 else 0.0


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
        schema_only_tables: Optional[set] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Compare data tables from TWBX and PBIX.

        Matching strategy (per spec):
          1. Exact normalised name match
          2. Fuzzy name match (≥60% similarity)  → PASS with name-diff note
          3. Column-overlap fallback (≥50% Jaccard) → PASS with name-diff note
          4. No match found → FAIL

        schema_only_tables: table names (PBIX side) whose row count should be
            skipped because the DataModel was unreadable and columns were
            sourced from a PBIT template instead.

        Returns:
            (overall_result, list_of_per_table_results)
        """
        results: List[Dict[str, Any]] = []
        all_pass = True

        table_matches = _match_tables(twbx_tables, pbix_tables)
        logger.info(f"Comparing {len(table_matches)} tables")

        for match in table_matches:
            result = self._compare_matched_pair(
                match, twbx_tables, pbix_tables, verbose,
                schema_only_tables=schema_only_tables or set(),
            )
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
        schema_only_tables: Optional[set] = None,
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

        # ── Row count ───────────────────────────────────────────────────
        twbx_df = twbx_tables.get(twbx_name) if twbx_name else None
        pbix_df = pbix_tables.get(pbix_name) if pbix_name else None
        
        twbx_rows = len(twbx_df) if twbx_df is not None else 0
        pbix_rows = len(pbix_df) if pbix_df is not None else 0
        
        result["row_count_twbx"] = twbx_rows
        result["row_count_pbix"] = pbix_rows

        # ── Unmatched table → hard FAIL ─────────────────────────────────
        if match["match_method"] == "unmatched":
            result["result"] = "FAIL"
            result["failure_reasons"].append(match["name_note"])
            # Populate missing column lists so the UI can show what columns exist
            if twbx_name and twbx_name in twbx_tables:
                result["columns_missing_in_pbix"] = sorted(twbx_tables[twbx_name].columns.tolist())
            elif pbix_name and pbix_name in pbix_tables:
                result["columns_missing_in_twbx"] = sorted(pbix_tables[pbix_name].columns.tolist())
            
            # Record diff pct if one side is 0
            if twbx_rows == 0 or pbix_rows == 0:
                result["row_count_diff_pct"] = 100.0 if (twbx_rows + pbix_rows) > 0 else 0.0
            
            return result

        twbx_df = twbx_tables[twbx_name]
        pbix_df = pbix_tables[pbix_name]

        # Row count check is skipped for schema-only tables (columns sourced
        # from a PBIT template; the PBIX DataModel was unreadable, so 0 rows
        # does not mean the Power BI report is actually empty).
        is_schema_only = pbix_name in (schema_only_tables or set())

        if is_schema_only:
            result["row_count_diff_pct"] = None
            result["notes"].append(
                "Row count not available: PBIX DataModel is compressed; "
                "column schema sourced from PBIT template."
            )
        elif twbx_rows == 0 and pbix_rows == 0:
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

        # Exact-match results
        result["columns_matched"] = sorted(twbx_col_map[n] for n in matched_norm)

        # ── Fuzzy column fallback ───────────────────────────────────────
        # Try to pair remaining unmatched columns by name similarity so that
        # minor naming differences ("OrderID" ↔ "Order_ID", "SalesAmt" ↔
        # "Sales_Amount") don't produce false "missing" failures.
        unmatched_twbx_cols = [twbx_col_map[n] for n in missing_in_pbix_norm]
        unmatched_pbix_cols  = [pbix_col_map[n]  for n in missing_in_twbx_norm]
        fuzzy_col_pairs = _fuzzy_match_cols(unmatched_twbx_cols, unmatched_pbix_cols)

        fuzzy_matched_twbx_norm: set = set()
        fuzzy_matched_pbix_norm: set = set()
        for tc, pc, score in fuzzy_col_pairs:
            fn_t = _norm_col(tc)
            fn_p = _norm_col(pc)
            fuzzy_matched_twbx_norm.add(fn_t)
            fuzzy_matched_pbix_norm.add(fn_p)
            result["columns_matched"].append(tc)
            if tc != pc:
                note = (
                    f"Column fuzzy matched: TWBX='{tc}' ↔ PBIX='{pc}' "
                    f"(similarity {score:.0%})"
                )
                result["notes"].append(note)
                if verbose:
                    logger.info(f"[{display_name}] {note}")

        result["columns_matched"] = sorted(set(result["columns_matched"]))

        result["columns_missing_in_pbix"] = sorted(
            twbx_col_map[n] for n in missing_in_pbix_norm
            if n not in fuzzy_matched_twbx_norm
        )
        result["columns_missing_in_twbx"] = sorted(
            pbix_col_map[n] for n in missing_in_twbx_norm
            if n not in fuzzy_matched_pbix_norm
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

        # Type comparison for exact-matched columns (with equivalence map).
        # Skipped for schema-only tables: columns came from a PBIT template
        # (all-object dtype) and carry no real type information.
        if not is_schema_only:
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

        # Type comparison for fuzzy-matched columns (also skipped for schema-only)
        for tc, pc, _score in ([] if is_schema_only else fuzzy_col_pairs):
            twbx_dtype = str(twbx_df[tc].dtype)
            pbix_dtype  = str(pbix_df[pc].dtype)
            if not are_types_compatible(twbx_dtype, pbix_dtype):
                mismatch = {
                    "column": tc,
                    "twbx_type": twbx_dtype,
                    "pbix_type": pbix_dtype,
                    "twbx_canonical": get_type_group(twbx_dtype),
                    "pbix_canonical": get_type_group(pbix_dtype),
                }
                result["column_type_mismatches"].append(mismatch)
                result["result"] = "FAIL"
                result["failure_reasons"].append(
                    f"Incompatible type for column '{tc}' (fuzzy matched to '{pc}'): "
                    f"TWBX={twbx_dtype} ({get_type_group(twbx_dtype)}) "
                    f"PBIX={pbix_dtype} ({get_type_group(pbix_dtype)})"
                )
                if verbose:
                    logger.warning(
                        f"[{display_name}.{tc}↔{pc}] Type incompatible: "
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
    # Column Data Content Analysis  (L2 – semantic layer)
    # ------------------------------------------------------------------

    def analyze_column_data(
        self,
        twbx_tables: Dict[str, pd.DataFrame],
        pbix_tables: Dict[str, pd.DataFrame],
        max_unique: int = 500,
        overlap_threshold_pct: float = 100.0,
        verbose: bool = False,
        schema_only_tables: Optional[set] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Analyse actual data values in matched columns across matched tables.

        For every column that exists in both Tableau and Power BI this method
        computes:
          • The unique-value sets in each source (capped at max_unique to
            protect memory on large tables).
          • Values present only in Tableau, and values present only in Power BI.
          • An overlap percentage — 100 % means the value sets are identical.
          • For numeric columns: mean / std / min / max comparison.

        A column is flagged FAIL when overlap_pct < overlap_threshold_pct
        (default 100 %, so any value-set difference is surfaced).

        This method re-uses the same `_match_tables()` helper as
        `compare_tables()` but is otherwise completely independent of it —
        calling `analyze_column_data()` does NOT alter the L3 structural
        comparison in any way.

        Returns:
            (overall_result, list_of_per_table_results)
        """
        results: List[Dict[str, Any]] = []
        all_pass = True

        table_matches = _match_tables(twbx_tables, pbix_tables)

        for match in table_matches:
            twbx_name = match["twbx_name"]
            pbix_name  = match["pbix_name"]

            # Skip tables that could not be paired
            if match["match_method"] == "unmatched":
                display = twbx_name or pbix_name or "Unknown"
                twbx_cols = list(twbx_tables[twbx_name].columns) if twbx_name and twbx_name in twbx_tables else []
                pbix_cols = list(pbix_tables[pbix_name].columns) if pbix_name and pbix_name in pbix_tables else []
                unmatched_twbx_rows = len(twbx_tables[twbx_name]) if twbx_name and twbx_name in twbx_tables else 0
                unmatched_pbix_rows = len(pbix_tables[pbix_name]) if pbix_name and pbix_name in pbix_tables else 0
                results.append({
                    "table_name": display,
                    "twbx_name": twbx_name,
                    "pbix_name": pbix_name,
                    "result": "SKIPPED",
                    "reason": match["name_note"],
                    "column_analyses": [],
                    "columns_analyzed": 0,
                    "mismatched_columns": 0,
                    "failure_reasons": [match["name_note"]],
                    "twbx_columns": twbx_cols,
                    "pbix_columns": pbix_cols,
                    "twbx_row_count": unmatched_twbx_rows,
                    "pbix_row_count": unmatched_pbix_rows,
                })
                continue

            # Skip value analysis for schema-only tables (PBIX DataModel is
            # compressed or data is in the remote Power BI Service — actual
            # rows are unavailable, so value-overlap would always be 0 %).
            if pbix_name in (schema_only_tables or set()):
                results.append({
                    "table_name": twbx_name,
                    "twbx_name": twbx_name,
                    "pbix_name": pbix_name,
                    "result": "SKIPPED",
                    "reason": (
                        "Power BI data not available locally "
                        "(remote dataset or compressed DataModel). "
                        "Schema comparison was performed instead."
                    ),
                    "column_analyses": [],
                    "columns_analyzed": 0,
                    "mismatched_columns": 0,
                    "failure_reasons": [],
                    "twbx_row_count": len(twbx_tables[twbx_name]),
                    "pbix_row_count": 0,
                })
                continue

            twbx_df = twbx_tables[twbx_name]
            pbix_df  = pbix_tables[pbix_name]

            # Determine matched columns: exact normalisation + fuzzy fallback
            twbx_col_map: Dict[str, str] = {_norm_col(c): c for c in twbx_df.columns}
            pbix_col_map:  Dict[str, str] = {_norm_col(c): c for c in pbix_df.columns}
            exact_matched_norm = sorted(
                set(twbx_col_map.keys()) & set(pbix_col_map.keys())
            )
            missing_t = [twbx_col_map[n] for n in set(twbx_col_map) - set(pbix_col_map)]
            missing_p = [pbix_col_map[n]  for n in set(pbix_col_map) - set(twbx_col_map)]
            fuzzy_col_pairs_l3 = _fuzzy_match_cols(missing_t, missing_p)

            # Build a unified list of (twbx_orig, pbix_orig) pairs to analyse
            col_pairs: List[Tuple[str, str]] = [
                (twbx_col_map[n], pbix_col_map[n]) for n in exact_matched_norm
            ] + [(tc, pc) for tc, pc, _ in fuzzy_col_pairs_l3]

            table_result: Dict[str, Any] = {
                "table_name": twbx_name,
                "pbix_name":  pbix_name,
                "result": "PASS",
                "column_analyses": [],
                "columns_analyzed": len(col_pairs),
                "mismatched_columns": 0,
                "failure_reasons": [],
                "twbx_row_count": len(twbx_df),
                "pbix_row_count": len(pbix_df),
            }

            for twbx_orig, pbix_orig in col_pairs:
                col_analysis = self._analyze_column_values(
                    twbx_df[twbx_orig],
                    pbix_df[pbix_orig],
                    twbx_orig,
                    max_unique=max_unique,
                    overlap_threshold_pct=overlap_threshold_pct,
                )
                table_result["column_analyses"].append(col_analysis)

                if col_analysis["result"] == "FAIL":
                    table_result["mismatched_columns"] += 1
                    table_result["result"] = "FAIL"
                    table_result["failure_reasons"].append(
                        f"Column '{twbx_orig}': "
                        f"{col_analysis['overlap_pct']:.1f}% value overlap "
                        f"({col_analysis['only_in_twbx_count']} value(s) only in Tableau, "
                        f"{col_analysis['only_in_pbix_count']} value(s) only in Power BI)"
                    )
                    if verbose:
                        logger.warning(
                            f"[{twbx_name}.{twbx_orig}] Value overlap "
                            f"{col_analysis['overlap_pct']:.1f}% < "
                            f"{overlap_threshold_pct}%"
                        )

            if table_result["result"] == "FAIL":
                all_pass = False

            results.append(table_result)

        overall = "PASS" if all_pass else "FAIL"
        logger.info(f"Column data content analysis result: {overall}")
        return overall, results

    def _analyze_column_values(
        self,
        twbx_col: "pd.Series",
        pbix_col:  "pd.Series",
        col_name: str,
        max_unique: int = 500,
        overlap_threshold_pct: float = 100.0,
    ) -> Dict[str, Any]:
        """
        Compare the unique value sets of two columns.

        Returns a dict with:
          column_name, result (PASS/FAIL), overlap_pct,
          twbx_unique_count, pbix_unique_count,
          only_in_twbx (preview list), only_in_pbix (preview list),
          only_in_twbx_count, only_in_pbix_count,
          twbx_preview_truncated, pbix_preview_truncated,
          numeric_stats (optional).
        """
        MAX_PREVIEW = 10   # maximum sample values to surface per side

        # Convert to strings so mixed-type columns compare safely
        def _safe_unique(series: "pd.Series") -> set:
            vals = series.dropna()
            if len(vals) == 0:
                return set()
            str_vals = vals.astype(str).unique()
            if len(str_vals) > max_unique:
                # Cap to avoid memory blow-up on high-cardinality columns
                return set(str_vals[:max_unique])
            return set(str_vals)

        twbx_vals = _safe_unique(twbx_col)
        pbix_vals  = _safe_unique(pbix_col)

        only_in_twbx_full = sorted(twbx_vals - pbix_vals)
        only_in_pbix_full  = sorted(pbix_vals  - twbx_vals)

        union_size = len(twbx_vals | pbix_vals)
        inter_size = len(twbx_vals & pbix_vals)
        overlap_pct = round(inter_size / union_size * 100, 2) if union_size > 0 else 100.0
        mismatch_pct = round(100.0 - overlap_pct, 2)

        analysis: Dict[str, Any] = {
            "column_name":           col_name,
            "result":                "FAIL" if overlap_pct < overlap_threshold_pct else "PASS",
            "overlap_pct":           overlap_pct,
            "mismatch_pct":          mismatch_pct,
            "twbx_unique_count":     len(twbx_vals),
            "pbix_unique_count":     len(pbix_vals),
            "only_in_twbx":          only_in_twbx_full[:MAX_PREVIEW],
            "only_in_pbix":          only_in_pbix_full[:MAX_PREVIEW],
            "only_in_twbx_count":    len(only_in_twbx_full),
            "only_in_pbix_count":    len(only_in_pbix_full),
            "twbx_preview_truncated": len(only_in_twbx_full) > MAX_PREVIEW,
            "pbix_preview_truncated":  len(only_in_pbix_full) > MAX_PREVIEW,
        }

        # Numeric stats comparison (best-effort; silently skipped for non-numeric)
        try:
            twbx_num = pd.to_numeric(twbx_col.dropna(), errors="raise")
            pbix_num  = pd.to_numeric(pbix_col.dropna(),  errors="raise")

            def _stats(s: "pd.Series") -> Dict[str, Optional[float]]:
                if len(s) == 0:
                    return {"mean": None, "std": None, "min": None, "max": None}
                return {
                    "mean": round(float(s.mean()), 4),
                    "std":  round(float(s.std()),  4) if len(s) > 1 else None,
                    "min":  round(float(s.min()),  4),
                    "max":  round(float(s.max()),  4),
                }

            twbx_stats = _stats(twbx_num)
            pbix_stats  = _stats(pbix_num)

            mean_diff = None
            mean_diff_pct = None
            if twbx_stats["mean"] is not None and pbix_stats["mean"] is not None:
                mean_diff = round(abs(twbx_stats["mean"] - pbix_stats["mean"]), 4)
                if twbx_stats["mean"] != 0:
                    mean_diff_pct = round(
                        mean_diff / abs(twbx_stats["mean"]) * 100, 2
                    )

            analysis["numeric_stats"] = {
                "twbx": twbx_stats,
                "pbix":  pbix_stats,
                "mean_diff":     mean_diff,
                "mean_diff_pct": mean_diff_pct,
            }
        except (ValueError, TypeError):
            pass  # Non-numeric column — no numeric stats

        return analysis

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
    
    def compare_measures(self, twbx_measures, pbit_measures, tables):

        results = []

        df = list(tables.values())[0]

        for t in twbx_measures:

            name = t["name"]
            t_formula = t.get("expression")

            p = next((m for m in pbit_measures if m["name"] == name), None)

            if not p:
                continue

            p_formula = p.get("expression")

            t_value = self.execute_formula(t_formula, df)
            p_value = self.execute_formula(p_formula, df)

            status = "PASS" if t_value == p_value else "FAIL"

            results.append({
                "measure": name,
                "tableau_formula": t_formula,
                "powerbi_formula": p_formula,
                "tableau_value": t_value,
                "powerbi_value": p_value,
                "status": status
            })

        return results