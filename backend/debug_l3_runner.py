#!/usr/bin/env python3
"""
Debug runner for Layer 3 (Data Validation)

Compares:
    Tableau TWBX
        vs
    Power BI PBIT

Example:
python debug/debug_l3_runner.py \
    --twbx temp/report.twbx \
    --pbit temp/report.pbit \
    --verbose
"""

import argparse
import logging
from pathlib import Path

from parsers.twbx_parser import TwbxParser
from parsers.pbit_parser import PbitParser
from comparators.data_router import run_data_comparison
from comparators.data_comparator import DataComparator


def setup_logging(verbose=False):

    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )


def validate_files(twbx_path, pbit_path):

    if not Path(twbx_path).exists():
        raise FileNotFoundError(f"TWBX not found: {twbx_path}")

    if not Path(pbit_path).exists():
        raise FileNotFoundError(f"PBIT not found: {pbit_path}")


def extract_formula(measure_dict):
    """
    Safely extract formula/expression from parser output.
    Supports multiple parser formats.
    """

    return (
        measure_dict.get("formula")
        or measure_dict.get("expression")
        or measure_dict.get("calculation")
        or measure_dict.get("value")
        or "UNKNOWN_FORMULA"
    )


def run_debug(twbx_path, pbit_path, verbose):

    logger = logging.getLogger("L3_DEBUG")

    logger.info("========== L3 DEBUG START ==========")

    validate_files(twbx_path, pbit_path)

    # --------------------------------------------------
    # STEP 1 — Parse TWBX
    # --------------------------------------------------

    logger.info("STEP 1: Parsing TWBX")

    twbx_parser = TwbxParser(twbx_path)
    twbx_parser.parse()

    twbx_tables = twbx_parser.get_data_tables()

    logger.info(f"TWBX tables: {len(twbx_tables)}")

    if verbose:
        for t in twbx_tables:
            logger.debug(f"TWBX table: {t}")

    twbx_measures = twbx_parser.get_measures()

    print("\nTWBX MEASURES")
    print("-" * 40)

    if not twbx_measures:
        print("No measures found in TWBX")

    for m in twbx_measures:
        name = m.get("name", "UNKNOWN_MEASURE")
        formula = extract_formula(m)
        print(f"{name} : {formula}")

    # --------------------------------------------------
    # STEP 2 — Parse PBIT
    # --------------------------------------------------

    logger.info("STEP 2: Parsing PBIT")

    pbit_parser = PbitParser(pbit_path)
    pbit_parser.parse()

    pbit_tables = pbit_parser.get_data_tables()

    logger.info(f"PBIT tables: {len(pbit_tables)}")

    if verbose:
        for t in pbit_tables:
            logger.debug(f"PBIT table: {t}")

    pbit_measures = pbit_parser.get_measures()

    print("\nPBIT MEASURES")
    print("-" * 40)

    if not pbit_measures:
        print("No measures found in PBIT")

    for m in pbit_measures:
        name = m.get("name", "UNKNOWN_MEASURE")
        expression = extract_formula(m)
        print(f"{name} : {expression}")

    # --------------------------------------------------
    # STEP 3 — Table comparison
    # --------------------------------------------------

    logger.info("STEP 3: Table structure comparison (PBIT mode)")

    table_details = []

    for table in twbx_tables:

        if table in pbit_tables:

            table_details.append({
                "table_name": table,
                "result": "PASS",
                "reason": "Table exists in both TWBX and PBIT"
            })

        else:

            table_details.append({
                "table_name": table,
                "result": "FAIL",
                "reason": "Missing in PBIT"
            })

    table_result = "PASS" if all(t["result"] == "PASS" for t in table_details) else "FAIL"

    # --------------------------------------------------
    # STEP 4 — Column analysis
    # --------------------------------------------------

    logger.info("STEP 4: Column value analysis")

    logger.info("Skipping column value comparison (PBIT has no data)")

    column_result = "SKIPPED"
    column_details = [
        "Column value comparison skipped because PBIT contains no data."
    ]

    # --------------------------------------------------
    # Print details
    # --------------------------------------------------

    print("\n===== TABLE DETAILS =====\n")

    for d in table_details:
        print(d)

    print("\n===== COLUMN DETAILS =====\n")

    for d in column_details:
        print(d)

    # --------------------------------------------------

    twbx_parser.cleanup()
    pbit_parser.cleanup()

    logger.info("========== L3 DEBUG COMPLETE ==========")


def main():

    parser = argparse.ArgumentParser(description="Debug Layer 3 comparison")

    parser.add_argument("--twbx", required=True)
    parser.add_argument("--pbit", required=True)
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    setup_logging(args.verbose)

    run_debug(
        args.twbx,
        args.pbit,
        args.verbose
    )


if __name__ == "__main__":
    main()