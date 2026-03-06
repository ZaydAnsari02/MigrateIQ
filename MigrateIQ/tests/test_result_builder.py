"""Tests for result builder."""
import unittest
import json
import tempfile
from pathlib import Path
from output.result_builder import ComparisonResultBuilder


class TestComparisonResultBuilder(unittest.TestCase):
    """Test cases for ComparisonResultBuilder."""

    def setUp(self):
        """Set up test fixtures."""
        self.builder = ComparisonResultBuilder("test.twbx", "test.pbix")
        self.temp_dir = tempfile.mkdtemp()

    def test_build_pass_result(self):
        """Test building a PASS result."""
        result = self.builder.build_result(
            data_result="PASS",
            data_details=[
                {
                    "table_name": "Users",
                    "result": "PASS",
                    "row_count_twbx": 100,
                    "row_count_pbix": 100,
                    "row_count_diff_pct": 0.0,
                    "columns_matched": ["ID", "Name"],
                    "columns_missing_in_pbix": [],
                    "columns_missing_in_twbx": [],
                    "column_type_mismatches": [],
                    "failure_reasons": [],
                }
            ],
            model_result="PASS",
            model_details={
                "measures_matched": ["Total Sales"],
                "measures_missing_in_pbix": [],
                "measures_missing_in_twbx": [],
                "expression_mismatches": [],
                "data_type_mismatches": [],
                "failure_reasons": [],
            },
            relationships_result="PASS",
            relationships_details={
                "relationships_matched": [{"from": "Orders[CustomerID]", "to": "Customers[CustomerID]"}],
                "relationships_missing_in_pbix": [],
                "relationships_missing_in_twbx": [],
                "cardinality_mismatches": [],
                "failure_reasons": [],
            },
        )

        self.assertEqual(result["overall_result"], "PASS")
        self.assertEqual(result["inputs"]["twbx_file"], "test.twbx")
        self.assertEqual(result["inputs"]["pbix_file"], "test.pbix")
        self.assertEqual(result["summary"]["total_failures"], 0)

    def test_build_fail_result(self):
        """Test building a FAIL result."""
        result = self.builder.build_result(
            data_result="FAIL",
            data_details=[
                {
                    "table_name": "Users",
                    "result": "FAIL",
                    "row_count_twbx": 100,
                    "row_count_pbix": 50,
                    "row_count_diff_pct": 50.0,
                    "columns_matched": [],
                    "columns_missing_in_pbix": ["Name"],
                    "columns_missing_in_twbx": [],
                    "column_type_mismatches": [],
                    "failure_reasons": ["Row count mismatch"],
                }
            ],
            model_result="PASS",
            model_details={
                "measures_matched": [],
                "measures_missing_in_pbix": [],
                "measures_missing_in_twbx": [],
                "expression_mismatches": [],
                "data_type_mismatches": [],
                "failure_reasons": [],
            },
            relationships_result="PASS",
            relationships_details={
                "relationships_matched": [],
                "relationships_missing_in_pbix": [],
                "relationships_missing_in_twbx": [],
                "cardinality_mismatches": [],
                "failure_reasons": [],
            },
        )

        self.assertEqual(result["overall_result"], "FAIL")
        self.assertIn("data", result["summary"]["failure_categories"])
        self.assertEqual(result["summary"]["total_failures"], 1)

    def test_save_and_load_result(self):
        """Test saving and loading a result."""
        result = self.builder.build_result(
            data_result="PASS",
            data_details=[],
            model_result="PASS",
            model_details={"failure_reasons": []},
            relationships_result="PASS",
            relationships_details={"failure_reasons": []},
        )

        output_path = Path(self.temp_dir) / "result.json"
        saved_path = self.builder.save_result(result, str(output_path))

        # Verify file was created
        self.assertTrue(Path(saved_path).exists())

        # Load and verify
        loaded = ComparisonResultBuilder.load_result(str(output_path))
        self.assertEqual(loaded["overall_result"], "PASS")
        self.assertEqual(loaded["comparison_id"], result["comparison_id"])

    def test_result_contains_required_fields(self):
        """Test that result contains all required fields."""
        result = self.builder.build_result(
            data_result="PASS",
            data_details=[],
            model_result="PASS",
            model_details={"failure_reasons": []},
            relationships_result="PASS",
            relationships_details={"failure_reasons": []},
        )

        # Check top-level fields
        self.assertIn("comparison_id", result)
        self.assertIn("timestamp", result)
        self.assertIn("inputs", result)
        self.assertIn("overall_result", result)
        self.assertIn("categories", result)
        self.assertIn("summary", result)

        # Check categories
        self.assertIn("data", result["categories"])
        self.assertIn("semantic_model", result["categories"])
        self.assertIn("relationships", result["categories"])

        # Check inputs
        self.assertIn("twbx_file", result["inputs"])
        self.assertIn("pbix_file", result["inputs"])


if __name__ == "__main__":
    unittest.main()
