"""
Example usage of the MigrateIQ comparison tool.

This script demonstrates how to programmatically use the tool
without the CLI interface.
"""

from pathlib import Path
from parsers.twbx_parser import TwbxParser
from parsers.pbix_parser import PbixParser
from comparators.data_comparator import DataComparator
from comparators.model_comparator import ModelComparator
from comparators.relationship_comparator import RelationshipComparator
from output.result_builder import ComparisonResultBuilder
import config


def example_programmatic_usage():
    """
    Example of using the comparison tool programmatically.
    """

    # Initialize parsers
    twbx_parser = TwbxParser("path/to/your_workbook.twbx")
    pbix_parser = PbixParser("path/to/your_report.pbix")

    # Parse files
    twbx_parser.parse()
    pbix_parser.parse()

    # Extract parsed data
    twbx_tables = twbx_parser.get_data_tables()
    twbx_measures = twbx_parser.get_measures()
    twbx_relationships = twbx_parser.get_relationships()

    pbix_tables = pbix_parser.get_data_tables()
    pbix_measures = pbix_parser.get_measures()
    pbix_relationships = pbix_parser.get_relationships()

    # Compare data
    data_comparator = DataComparator(tolerance_pct=config.TOLERANCE_PCT)
    data_result, data_details = data_comparator.compare_tables(
        twbx_tables,
        pbix_tables,
        verbose=True,
    )

    # Compare measures
    model_comparator = ModelComparator()
    model_result, model_details = model_comparator.compare_measures(
        twbx_measures,
        pbix_measures,
        verbose=True,
    )

    # Compare relationships
    relationship_comparator = RelationshipComparator()
    relationships_result, relationships_details = relationship_comparator.compare_relationships(
        twbx_relationships,
        pbix_relationships,
        verbose=True,
    )

    # Build result
    result_builder = ComparisonResultBuilder(
        "path/to/your_workbook.twbx",
        "path/to/your_report.pbix",
    )
    result = result_builder.build_result(
        data_result,
        data_details,
        model_result,
        model_details,
        relationships_result,
        relationships_details,
    )

    # Save result
    output_path = str(config.OUTPUT_DIR / config.DEFAULT_OUTPUT_FILENAME)
    result_builder.save_result(result, output_path)

    # Print summary
    ComparisonResultBuilder.print_result_summary(result)

    # Access specific result data
    print(f"\nData comparison result: {result['categories']['data']['result']}")
    print(f"Model comparison result: {result['categories']['semantic_model']['result']}")
    print(f"Relationships comparison result: {result['categories']['relationships']['result']}")
    print(f"Overall result: {result['overall_result']}")

    # Cleanup
    twbx_parser.cleanup()
    pbix_parser.cleanup()


def example_custom_parsing():
    """
    Example of custom parsing and comparison logic.
    """

    # You can extend the parsers for custom logic
    class CustomTwbxParser(TwbxParser):
        """Custom TWBX parser with additional data extraction."""

        def get_custom_metadata(self):
            """Extract custom metadata from TWBX."""
            # Implement custom extraction logic
            pass

    # Use custom parser
    custom_parser = CustomTwbxParser("path/to/workbook.twbx")
    custom_parser.parse()

    # Access both standard and custom data
    tables = custom_parser.get_data_tables()
    custom_data = custom_parser.get_custom_metadata()

    custom_parser.cleanup()


def example_batch_comparison():
    """
    Example of batch comparing multiple file pairs.
    """

    file_pairs = [
        ("file1.twbx", "file1.pbix"),
        ("file2.twbx", "file2.pbix"),
        ("file3.twbx", "file3.pbix"),
    ]

    results = []

    for twbx_file, pbix_file in file_pairs:
        try:
            # Initialize and parse
            twbx_parser = TwbxParser(twbx_file)
            pbix_parser = PbixParser(pbix_file)

            twbx_parser.parse()
            pbix_parser.parse()

            # Perform comparisons
            data_comparator = DataComparator()
            model_comparator = ModelComparator()
            relationship_comparator = RelationshipComparator()

            data_result, data_details = data_comparator.compare_tables(
                twbx_parser.get_data_tables(),
                pbix_parser.get_data_tables(),
            )

            model_result, model_details = model_comparator.compare_measures(
                twbx_parser.get_measures(),
                pbix_parser.get_measures(),
            )

            relationships_result, relationships_details = relationship_comparator.compare_relationships(
                twbx_parser.get_relationships(),
                pbix_parser.get_relationships(),
            )

            # Build and save result
            builder = ComparisonResultBuilder(twbx_file, pbix_file)
            result = builder.build_result(
                data_result,
                data_details,
                model_result,
                model_details,
                relationships_result,
                relationships_details,
            )

            output_path = str(config.OUTPUT_DIR / f"result_{Path(twbx_file).stem}.json")
            builder.save_result(result, output_path)

            results.append({
                "files": (twbx_file, pbix_file),
                "result": result["overall_result"],
                "output": output_path,
            })

            # Cleanup
            twbx_parser.cleanup()
            pbix_parser.cleanup()

        except Exception as e:
            print(f"Error comparing {twbx_file} and {pbix_file}: {e}")

    # Print batch summary
    print("\n" + "=" * 70)
    print("BATCH COMPARISON SUMMARY")
    print("=" * 70)
    for batch_result in results:
        twbx, pbix = batch_result["files"]
        print(f"{twbx} vs {pbix}: {batch_result['result']}")
        print(f"  → Output: {batch_result['output']}")


if __name__ == "__main__":
    print("MigrateIQ - BI Report Comparison Tool")
    print("Example Usage Script")
    print("=" * 70)
    print("\nThis script demonstrates how to use the tool programmatically.")
    print("Uncomment the function calls below to run examples.")
    print("\n# example_programmatic_usage()")
    print("# example_custom_parsing()")
    print("# example_batch_comparison()")
