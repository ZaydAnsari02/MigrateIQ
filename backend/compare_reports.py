#!/usr/bin/env python3
"""
Compare Tableau TWBX and Power BI PBIX files.

Usage:
    python compare_reports.py --twbx path/to/file.twbx --pbix path/to/file.pbix
    python compare_reports.py --twbx file.twbx --pbix file.pbix --output /path/to/output.json --verbose

When --output is omitted every run is saved to the results/ folder with a
timestamp in the filename so runs never overwrite each other:
    results/result_pass_20260309_120834.json
    results/result_fail_20260309_120834.json
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import pandas as pd
from parsers.twbx_parser import TwbxParser
from parsers.pbix_parser import PbixParser
from parsers.pbit_parser import PbitParser
from comparators.data_comparator import DataComparator
from comparators.data_comparator_pbit import PbitDataComparator
from comparators.data_router import run_data_comparison
from comparators.model_comparator import ModelComparator
from comparators.relationship_comparator import RelationshipComparator
from output.result_builder import ComparisonResultBuilder


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def validate_input_files(twbx_path: str, pbix_path: str) -> bool:
    """Validate that input files exist and have the right extensions."""
    twbx = Path(twbx_path)
    pbix = Path(pbix_path)

    if not twbx.exists():
        logging.error(f"TWBX file not found: {twbx_path}")
        return False
    if not pbix.exists():
        logging.error(f"PBIX file not found: {pbix_path}")
        return False
    if twbx.suffix.lower() != ".twbx":
        logging.error(f"Input file is not a .twbx file: {twbx_path}")
        return False
    if pbix.suffix.lower() != ".pbix":
        logging.error(f"Input file is not a .pbix file: {pbix_path}")
        return False

    return True


# ---------------------------------------------------------------------------
# Output path resolution
# ---------------------------------------------------------------------------

def _resolve_output_path(overall_result: str) -> str:
    """
    Return filename based on PASS/FAIL.
    Saved in current execution directory.
    """

    if overall_result.upper() == "PASS":
        return "result_pass.json"
    else:
        return "result_fail.json"


# ---------------------------------------------------------------------------
# Main comparison logic
# ---------------------------------------------------------------------------

def compare_reports(
    twbx_path: str,
    pbix_path: str,
    output_path: Optional[str],
    pbit_path: Optional[str] = None,
    verbose: bool = False,
) -> int:
    """
    Run the full comparison pipeline and save the result.

    Args:
        twbx_path:   Path to TWBX file.
        pbix_path:   Path to PBIX file.
        output_path: Explicit save path, or None to auto-route into results/.
        pbit_path:   Optional path to .pbit file used as schema fallback when
                     the PBIX DataModel is XPress9-compressed and unreadable.
        verbose:     Enable verbose logging.

    Returns:
        0 if overall result is PASS, 1 otherwise.
    """
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    # Capture run timestamp once — same value used in log lines and filename.
    run_dt = datetime.now()
    run_timestamp = run_dt.strftime("%Y%m%d_%H%M%S")

    logger.info("Starting report comparison")
    logger.info(f"Run timestamp : {run_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"TWBX: {twbx_path}")
    logger.info(f"PBIX: {pbix_path}")

    if not validate_input_files(twbx_path, pbix_path):
        return 1

    try:
        # ── Parse TWBX ──────────────────────────────────────────────────
        logger.info("Parsing TWBX file...")
        twbx_parser = TwbxParser(twbx_path)
        twbx_parser.parse()

        twbx_tables        = twbx_parser.get_data_tables()
        twbx_datasources   = twbx_parser.get_datasources()
        twbx_measures      = twbx_parser.get_measures()
        twbx_relationships = twbx_parser.get_relationships()

        logger.info(
            f"TWBX: Found {len(twbx_tables)} tables, "
            f"{len(twbx_measures)} measures, "
            f"{len(twbx_relationships)} relationships"
        )

        # ── Parse PBIX ──────────────────────────────────────────────────
        logger.info("Parsing PBIX file...")
        pbix_parser = PbixParser(pbix_path)
        pbix_parser.parse()

        pbix_tables           = pbix_parser.get_data_tables()
        pbix_measures         = pbix_parser.get_measures()
        pbix_relationships    = pbix_parser.get_relationships()
        pbix_tables_structure = pbix_parser.get_tables()
        pbix_is_remote        = pbix_parser.is_remote_dataset

        logger.info(
            f"PBIX: Found {len(pbix_tables)} tables, "
            f"{len(pbix_measures)} measures, "
            f"{len(pbix_relationships)} relationships"
        )

        # ── Use PBIT as primary schema source when provided ──────────────
        # PBIT DataModelSchema contains ALL columns (including those not used in
        # any visual) and is far more reliable than parsing the PBIX DataModel
        # (which is often XPress9-compressed) or the Report/Layout (which only
        # captures columns used in visuals).  When PBIT is supplied we replace
        # pbix_tables entirely with PBIT-derived DataFrames and mark every table
        # as schema-only (PBIT has no row data).
        # When PBIT is not provided we fall back to the PBIX-extracted tables.
        schema_only_tables: set = set()
        if pbit_path:
            try:
                pbit_primary = PbitParser(pbit_path)
                pbit_primary.parse()
                pbit_col_map = pbit_primary.get_data_tables()  # {name: [str | {"name":...}]}
                pbix_tables = {
                    tname: pd.DataFrame(columns=[
                        c["name"] if isinstance(c, dict) else c
                        for c in col_list
                    ])
                    for tname, col_list in pbit_col_map.items()
                }
                schema_only_tables = set(pbix_tables.keys())
                pbit_primary.cleanup()
                logger.info(
                    f"PBIT used as primary schema source: "
                    f"{len(pbix_tables)} table(s) — "
                    + ", ".join(
                        f"'{t}': {list(pbix_tables[t].columns)}"
                        for t in pbix_tables
                    )
                )
            except Exception as e:
                logger.warning(f"Could not use PBIT as primary schema source: {e}; falling back to PBIX")
                # Fall back to remote-dataset handling if applicable
                if pbix_is_remote:
                    schema_only_tables = set(pbix_tables.keys())
        elif pbix_is_remote:
            # No PBIT provided but PBIX connects to a remote Power BI Service
            # dataset — row data is unavailable locally.  Mark all tables as
            # schema-only so that row-count and value-overlap checks are skipped.
            schema_only_tables = set(pbix_tables.keys())
            logger.info(
                "Remote dataset detected — all tables marked as schema-only; "
                "data value analysis will be skipped."
            )

        # ── Compare data ────────────────────────────────────────────────
        logger.info("Comparing data...")
        data_comparator = DataComparator()
        data_result, data_details = run_data_comparison(
            twbx_tables,
            pbix_tables,
            pbix_path,
            verbose=verbose,
            schema_only_tables=schema_only_tables,
        )

        # ── Analyse column data content (L2) ────────────────────────────
        logger.info("Analysing column data content...")
        column_value_result, column_value_details = data_comparator.analyze_column_data(
            twbx_tables, pbix_tables, verbose=verbose,
            schema_only_tables=schema_only_tables,
        )

        # ── Compare semantic model ───────────────────────────────────────
        logger.info("Comparing semantic model...")
        model_comparator = ModelComparator()
        model_result, model_details = model_comparator.compare_measures(
            twbx_measures, pbix_measures, verbose=verbose
        )

        # ── Compare relationships ────────────────────────────────────────
        logger.info("Comparing relationships...")
        relationship_comparator = RelationshipComparator()
        relationships_result, relationships_details = (
            relationship_comparator.compare_relationships(
                twbx_relationships, pbix_relationships, verbose=verbose
            )
        )

        # ── Build result ─────────────────────────────────────────────────
        logger.info("Building result...")
        result_builder = ComparisonResultBuilder(twbx_path, pbix_path)
        result = result_builder.build_result(
            data_result,
            data_details,
            model_result,
            model_details,
            relationships_result,
            relationships_details,
            column_value_result=column_value_result,
            column_value_details=column_value_details,
            tolerance_pct=data_comparator.tolerance_pct,
        )

        # ── Resolve output path and save ─────────────────────────────────
        # Determine overall result explicitly
        overall_status = "PASS"
        if data_result == "FAIL" or model_result == "FAIL" or relationships_result == "FAIL" or column_value_result == "FAIL":
            overall_status = "FAIL"

        # Use API-provided output path if available
        if output_path:
            resolved_path = output_path
        else:
            resolved_path = _resolve_output_path(overall_status)

        Path(resolved_path).parent.mkdir(parents=True, exist_ok=True)
        output_file = result_builder.save_result(result, resolved_path)
        logger.info(f"Comparison result saved to {output_file}")

        # ── Print summary ────────────────────────────────────────────────
        ComparisonResultBuilder.print_result_summary(result)

        # ── Cleanup ──────────────────────────────────────────────────────
        twbx_parser.cleanup()
        pbix_parser.cleanup()

        return 0 if result["overall_result"] == "PASS" else 1

    except Exception as e:
        logger.error(f"Error during comparison: {e}", exc_info=True)
        return 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Compare Tableau TWBX and Power BI PBIX files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-saves to results/result_pass_<timestamp>.json or results/result_fail_<timestamp>.json
  python compare_reports.py --twbx report.twbx --pbix report.pbix

  # Save to an explicit path
  python compare_reports.py --twbx report.twbx --pbix report.pbix --output my_result.json

  # Verbose output
  python compare_reports.py --twbx report.twbx --pbix report.pbix --verbose
        """,
    )

    parser.add_argument(
        "--twbx",
        required=True,
        metavar="PATH",
        help="Path to the Tableau Packaged Workbook (.twbx) file",
    )
    parser.add_argument(
        "--pbix",
        required=True,
        metavar="PATH",
        help="Path to the Power BI Desktop (.pbix) file",
    )
    parser.add_argument(
        "--pbit",
        default=None,
        metavar="PATH",
        help=(
            "Optional Power BI Template (.pbit) file. When provided, its "
            "DataModelSchema is used as the primary schema source for L2 "
            "column comparison (more reliable than PBIX DataModel parsing)."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help=(
            "Path to save the JSON result file. "
            "If omitted, saves to results/result_pass_<timestamp>.json "
            "or results/result_fail_<timestamp>.json automatically."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging for detailed per-column information",
    )

    args = parser.parse_args()
    sys.exit(compare_reports(args.twbx, args.pbix, args.output, args.pbit, args.verbose))


if __name__ == "__main__":
    main()