"""Unit tests for data comparator."""
import unittest
import pandas as pd
from comparators.data_comparator import DataComparator


class TestDataComparator(unittest.TestCase):
    """Test cases for DataComparator."""

    def setUp(self):
        """Set up test fixtures."""
        self.comparator = DataComparator(tolerance_pct=0.5)

    def test_identical_tables(self):
        """Test comparison of identical tables."""
        twbx_tables = {
            "Users": pd.DataFrame({
                "UserID": [1, 2, 3],
                "Name": ["Alice", "Bob", "Charlie"],
            })
        }

        pbix_tables = {
            "Users": pd.DataFrame({
                "UserID": [1, 2, 3],
                "Name": ["Alice", "Bob", "Charlie"],
            })
        }

        result, details = self.comparator.compare_tables(twbx_tables, pbix_tables)
        self.assertEqual(result, "PASS")
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]["result"], "PASS")

    def test_missing_table_in_pbix(self):
        """Test when table exists in TWBX but not PBIX."""
        twbx_tables = {
            "Users": pd.DataFrame({"UserID": [1, 2]}),
            "Products": pd.DataFrame({"ProductID": [1, 2]}),
        }

        pbix_tables = {
            "Users": pd.DataFrame({"UserID": [1, 2]}),
        }

        result, details = self.comparator.compare_tables(twbx_tables, pbix_tables)
        self.assertEqual(result, "FAIL")

    def test_column_count_mismatch(self):
        """Test when column counts differ."""
        twbx_tables = {
            "Users": pd.DataFrame({
                "UserID": [1, 2],
                "Name": ["Alice", "Bob"],
            })
        }

        pbix_tables = {
            "Users": pd.DataFrame({
                "UserID": [1, 2],
            })
        }

        result, details = self.comparator.compare_tables(twbx_tables, pbix_tables)
        self.assertEqual(result, "FAIL")
        self.assertIn("Name", details[0]["columns_missing_in_pbix"])

    def test_data_type_mismatch(self):
        """Test when column data types differ."""
        twbx_tables = {
            "Users": pd.DataFrame({
                "UserID": [1, 2],
                "Name": ["Alice", "Bob"],
            })
        }

        pbix_tables = {
            "Users": pd.DataFrame({
                "UserID": ["1", "2"],
                "Name": ["Alice", "Bob"],
            })
        }

        result, details = self.comparator.compare_tables(twbx_tables, pbix_tables)
        self.assertEqual(result, "FAIL")
        self.assertEqual(len(details[0]["column_type_mismatches"]), 1)

    def test_row_count_within_tolerance(self):
        """Test row count difference within tolerance."""
        twbx_tables = {
            "Users": pd.DataFrame({"UserID": range(100)})
        }

        # 100 rows vs 100 rows (0% difference) - within 0.5% tolerance
        pbix_tables = {
            "Users": pd.DataFrame({"UserID": range(100)})
        }

        result, details = self.comparator.compare_tables(twbx_tables, pbix_tables)
        self.assertEqual(result, "PASS")
        self.assertEqual(details[0]["row_count_diff_pct"], 0.0)

    def test_row_count_exceeds_tolerance(self):
        """Test row count difference exceeding tolerance."""
        twbx_tables = {
            "Users": pd.DataFrame({"UserID": range(1000)})
        }

        # 1000 rows vs 994 rows (0.6% difference) - exceeds 0.5% tolerance
        pbix_tables = {
            "Users": pd.DataFrame({"UserID": range(994)})
        }

        result, details = self.comparator.compare_tables(twbx_tables, pbix_tables)
        self.assertEqual(result, "FAIL")
        self.assertGreater(details[0]["row_count_diff_pct"], 0.5)

    def test_case_insensitive_table_names(self):
        """Test that table name comparison is case-insensitive."""
        twbx_tables = {
            "Users": pd.DataFrame({"ID": [1, 2]})
        }

        pbix_tables = {
            "USERS": pd.DataFrame({"ID": [1, 2]})
        }

        result, details = self.comparator.compare_tables(twbx_tables, pbix_tables)
        self.assertEqual(result, "PASS")


class TestDataComparatorEdgeCases(unittest.TestCase):
    """Test edge cases for DataComparator."""

    def setUp(self):
        """Set up test fixtures."""
        self.comparator = DataComparator()

    def test_empty_tables(self):
        """Test comparison with empty tables."""
        twbx_tables = {
            "Users": pd.DataFrame()
        }

        pbix_tables = {
            "Users": pd.DataFrame()
        }

        result, details = self.comparator.compare_tables(twbx_tables, pbix_tables)
        self.assertEqual(result, "PASS")

    def test_no_tables(self):
        """Test comparison with no tables."""
        result, details = self.comparator.compare_tables({}, {})
        self.assertEqual(result, "PASS")
        self.assertEqual(len(details), 0)


if __name__ == "__main__":
    unittest.main()
