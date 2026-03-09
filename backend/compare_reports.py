#!/usr/bin/env python3
"""
Compare Tableau TWBX and Power BI PBIX files.

This CLI tool validates that two BI reports represent the same data,
semantic model, and relationships by comparing their structures and content.

Usage:
    python compare_reports.py --twbx path/to/file.twbx --pbix path/to/file.pbix
    python compare_reports.py --twbx file.twbx --pbix file.pbix --output /path/to/output.json --verbose
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

import config

from parsers.twbx_parser import TwbxParser
from parsers.pbix_parser import PbixParser
from comparators.data_comparator import DataComparator
from comparators.model_comparator import ModelComparator
from comparators.relationship_comparator import RelationshipComparator
from output.result_builder import ComparisonResultBuilder


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else getattr(logging, config.LOG_LEVEL, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def validate_input_files(twbx_path: str, pbix_path: str) -> bool:
    """Validate that input files exist and are accessible."""
    twbx = Path(twbx_path)
    pbix = Path(pbix_path)

    if not twbx.exists():
        logging.error(f"TWBX file not found: {twbx_path}")
        return False

    if not pbix.exists():
        logging.error(f"PBIX file not found: {pbix_path}")
        return False

    if not twbx.suffix.lower() == ".twbx":
        logging.error(f"Input file is not a .twbx file: {twbx_path}")
        return False

    if not pbix.suffix.lower() == ".pbix":
        logging.error(f"Input file is not a .pbix file: {pbix_path}")
        return False

    return True


def compare_reports(
    twbx_path: str,
    pbix_path: str,
    output_path: str,
    verbose: bool = False,
) -> int:
    """
    Main comparison logic.

    Args:
        twbx_path: Path to TWBX file
        pbix_path: Path to PBIX file
        output_path: Path to save JSON result
        verbose: Enable verbose logging

    Returns:
        Exit code (0 for success, 1 for errors)
    """
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    logger.info("Starting report comparison")
    logger.info(f"TWBX: {twbx_path}")
    logger.info(f"PBIX: {pbix_path}")

    # Validate inputs
    if not validate_input_files(twbx_path, pbix_path):
        return 1

    try:
        # Parse TWBX
        logger.info("Parsing TWBX file...")
        twbx_parser = TwbxParser(twbx_path)
        twbx_parser.parse()

        twbx_tables = twbx_parser.get_data_tables()
        twbx_datasources = twbx_parser.get_datasources()
        twbx_measures = twbx_parser.get_measures()
        twbx_relationships = twbx_parser.get_relationships()

        logger.info(f"TWBX: Found {len(twbx_tables)} tables, {len(twbx_measures)} measures, {len(twbx_relationships)} relationships")

        # Parse PBIX
        logger.info("Parsing PBIX file...")
        pbix_parser = PbixParser(pbix_path)
        pbix_parser.parse()

        pbix_tables = pbix_parser.get_data_tables()
        pbix_measures = pbix_parser.get_measures()
        pbix_relationships = pbix_parser.get_relationships()
        pbix_tables_structure = pbix_parser.get_tables()

        logger.info(f"PBIX: Found {len(pbix_tables)} tables, {len(pbix_measures)} measures, {len(pbix_relationships)} relationships")

        # Compare data
        logger.info("Comparing data...")
        data_comparator = DataComparator(tolerance_pct=config.TOLERANCE_PCT)
        data_result, data_details = data_comparator.compare_tables(
            twbx_tables,
            pbix_tables,
            verbose=verbose,
        )

        # Compare semantic model
        logger.info("Comparing semantic model...")
        model_comparator = ModelComparator()
        model_result, model_details = model_comparator.compare_measures(
            twbx_measures,
            pbix_measures,
            verbose=verbose,
        )

        # Compare relationships
        logger.info("Comparing relationships...")
        relationship_comparator = RelationshipComparator()
        relationships_result, relationships_details = relationship_comparator.compare_relationships(
            twbx_relationships,
            pbix_relationships,
            verbose=verbose,
        )

        # Build and save result
        logger.info("Building result...")
        result_builder = ComparisonResultBuilder(twbx_path, pbix_path)
        result = result_builder.build_result(
            data_result,
            data_details,
            model_result,
            model_details,
            relationships_result,
            relationships_details,
        )

        # Save result
        # If no explicit output path was given, build a descriptive unique filename.
        if output_path:
            output_file = result_builder.save_result(result, output_path)
        else:
            auto_path = result_builder.generate_output_filename(
                result["overall_result"]
            )
            output_file = result_builder.save_result(result, str(auto_path))
        logger.info(f"Comparison result saved to {output_file}")

        # Print summary
        ComparisonResultBuilder.print_result_summary(result)

        # Cleanup
        twbx_parser.cleanup()
        pbix_parser.cleanup()

        # Return exit code based on result
        return 0 if result["overall_result"] == "PASS" else 1

    except Exception as e:
        logger.error(f"Error during comparison: {e}", exc_info=True)
        return 1


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Compare Tableau TWBX and Power BI PBIX files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python compare_reports.py --twbx report.twbx --pbix report.pbix
  python compare_reports.py --twbx report.twbx --pbix report.pbix --output comparison_result.json
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
        "--output",
        default=None,
        metavar="PATH",
        help=(
            "Path to save the JSON result file. "
            "Defaults to output_json/{twbx}_vs_{pbix}_{PASS|FAIL}_{timestamp}.json"
        ),
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        default=config.VERBOSE,
        help="Enable verbose logging for detailed per-column information",
    )

    args = parser.parse_args()

    exit_code = compare_reports(
        args.twbx,
        args.pbix,
        args.output,
        args.verbose,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
