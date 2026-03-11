"""Unit tests for model comparator."""
import unittest
from comparators.model_comparator import ModelComparator


class TestModelComparator(unittest.TestCase):
    """Test cases for ModelComparator."""

    def setUp(self):
        """Set up test fixtures."""
        self.comparator = ModelComparator()

    def test_identical_measures(self):
        """Test comparison of identical measures."""
        twbx_measures = [
            {
                "name": "Total Sales",
                "expression": "SUM([Sales])",
                "data_type": "decimal",
            }
        ]

        pbix_measures = [
            {
                "name": "Total Sales",
                "expression": "SUM([Sales])",
                "data_type": "decimal",
            }
        ]

        result, details = self.comparator.compare_measures(twbx_measures, pbix_measures)
        self.assertEqual(result, "PASS")
        self.assertIn("Total Sales", details["measures_matched"])

    def test_missing_measure_in_pbix(self):
        """Test when measure exists in TWBX but not PBIX."""
        twbx_measures = [
            {"name": "Total Sales", "expression": "SUM([Sales])", "data_type": "decimal"},
            {"name": "Avg Price", "expression": "AVG([Price])", "data_type": "decimal"},
        ]

        pbix_measures = [
            {"name": "Total Sales", "expression": "SUM([Sales])", "data_type": "decimal"},
        ]

        result, details = self.comparator.compare_measures(twbx_measures, pbix_measures)
        self.assertEqual(result, "FAIL")
        self.assertIn("Avg Price", details["measures_missing_in_pbix"])

    def test_expression_mismatch(self):
        """Test when measure expressions differ."""
        twbx_measures = [
            {
                "name": "Total Sales",
                "expression": "SUM([Sales])",
                "data_type": "decimal",
            }
        ]

        pbix_measures = [
            {
                "name": "Total Sales",
                "expression": "SUMX(Table, [Sales])",
                "data_type": "decimal",
            }
        ]

        result, details = self.comparator.compare_measures(twbx_measures, pbix_measures)
        self.assertEqual(result, "FAIL")
        self.assertEqual(len(details["expression_mismatches"]), 1)

    def test_data_type_mismatch(self):
        """Test when measure data types differ."""
        twbx_measures = [
            {
                "name": "Total Sales",
                "expression": "SUM([Sales])",
                "data_type": "decimal",
            }
        ]

        pbix_measures = [
            {
                "name": "Total Sales",
                "expression": "SUM([Sales])",
                "data_type": "integer",
            }
        ]

        result, details = self.comparator.compare_measures(twbx_measures, pbix_measures)
        self.assertEqual(result, "FAIL")
        self.assertEqual(len(details["data_type_mismatches"]), 1)

    def test_case_insensitive_measure_names(self):
        """Test that measure name comparison is case-insensitive."""
        twbx_measures = [
            {
                "name": "Total Sales",
                "expression": "SUM([Sales])",
                "data_type": "decimal",
            }
        ]

        pbix_measures = [
            {
                "name": "total sales",
                "expression": "SUM([Sales])",
                "data_type": "decimal",
            }
        ]

        result, details = self.comparator.compare_measures(twbx_measures, pbix_measures)
        self.assertEqual(result, "PASS")

    def test_no_measures(self):
        """Test comparison with no measures."""
        result, details = self.comparator.compare_measures([], [])
        self.assertEqual(result, "PASS")
        self.assertEqual(len(details["measures_matched"]), 0)


class TestTableStructureComparator(unittest.TestCase):
    """Test cases for table structure comparison."""

    def setUp(self):
        """Set up test fixtures."""
        self.comparator = ModelComparator()

    def test_identical_table_structures(self):
        """Test comparison of identical table structures."""
        twbx_tables = {
            "Users": {
                "name": "Users",
                "columns": [
                    {"name": "UserID"},
                    {"name": "Name"},
                ],
            }
        }

        pbix_tables = {
            "Users": {
                "name": "Users",
                "columns": [
                    {"name": "UserID"},
                    {"name": "Name"},
                ],
            }
        }

        result, details = self.comparator.compare_tables_structure(twbx_tables, pbix_tables)
        self.assertEqual(result, "PASS")
        self.assertIn("Users", details["tables_matched"])

    def test_missing_column_in_pbix(self):
        """Test when table has missing column in PBIX."""
        twbx_tables = {
            "Users": {
                "name": "Users",
                "columns": [
                    {"name": "UserID"},
                    {"name": "Name"},
                    {"name": "Email"},
                ],
            }
        }

        pbix_tables = {
            "Users": {
                "name": "Users",
                "columns": [
                    {"name": "UserID"},
                    {"name": "Name"},
                ],
            }
        }

        result, details = self.comparator.compare_tables_structure(twbx_tables, pbix_tables)
        self.assertEqual(result, "FAIL")


if __name__ == "__main__":
    unittest.main()
