"""Unit tests for relationship comparator."""
import unittest
from comparators.relationship_comparator import RelationshipComparator


class TestRelationshipComparator(unittest.TestCase):
    """Test cases for RelationshipComparator."""

    def setUp(self):
        """Set up test fixtures."""
        self.comparator = RelationshipComparator()

    def test_identical_relationships(self):
        """Test comparison of identical relationships."""
        twbx_rels = [
            {
                "from_table": "Orders",
                "from_column": "CustomerID",
                "to_table": "Customers",
                "to_column": "CustomerID",
                "cardinality": "many-to-one",
            }
        ]

        pbix_rels = [
            {
                "from_table": "Orders",
                "from_column": "CustomerID",
                "to_table": "Customers",
                "to_column": "CustomerID",
                "cardinality": "many-to-one",
            }
        ]

        result, details = self.comparator.compare_relationships(twbx_rels, pbix_rels)
        self.assertEqual(result, "PASS")
        self.assertEqual(len(details["relationships_matched"]), 1)

    def test_missing_relationship_in_pbix(self):
        """Test when relationship exists in TWBX but not PBIX."""
        twbx_rels = [
            {
                "from_table": "Orders",
                "from_column": "CustomerID",
                "to_table": "Customers",
                "to_column": "CustomerID",
            },
            {
                "from_table": "OrderItems",
                "from_column": "OrderID",
                "to_table": "Orders",
                "to_column": "OrderID",
            },
        ]

        pbix_rels = [
            {
                "from_table": "Orders",
                "from_column": "CustomerID",
                "to_table": "Customers",
                "to_column": "CustomerID",
            }
        ]

        result, details = self.comparator.compare_relationships(twbx_rels, pbix_rels)
        self.assertEqual(result, "FAIL")
        self.assertEqual(len(details["relationships_missing_in_pbix"]), 1)

    def test_cardinality_mismatch(self):
        """Test when relationship cardinality differs."""
        twbx_rels = [
            {
                "from_table": "Orders",
                "from_column": "CustomerID",
                "to_table": "Customers",
                "to_column": "CustomerID",
                "cardinality": "many-to-one",
            }
        ]

        pbix_rels = [
            {
                "from_table": "Orders",
                "from_column": "CustomerID",
                "to_table": "Customers",
                "to_column": "CustomerID",
                "cardinality": "one-to-many",
            }
        ]

        result, details = self.comparator.compare_relationships(twbx_rels, pbix_rels)
        self.assertEqual(result, "FAIL")
        self.assertEqual(len(details["cardinality_mismatches"]), 1)

    def test_case_insensitive_table_names(self):
        """Test that table name comparison is case-insensitive."""
        twbx_rels = [
            {
                "from_table": "Orders",
                "from_column": "CustomerID",
                "to_table": "Customers",
                "to_column": "CustomerID",
            }
        ]

        pbix_rels = [
            {
                "from_table": "orders",
                "from_column": "CustomerID",
                "to_table": "customers",
                "to_column": "CustomerID",
            }
        ]

        result, details = self.comparator.compare_relationships(twbx_rels, pbix_rels)
        self.assertEqual(result, "PASS")

    def test_normalize_relationships_pbix_format(self):
        """Test normalization of Power BI relationship format."""
        pbix_rels = [
            {
                "fromTable": "Orders",
                "fromColumn": "CustomerID",
                "toTable": "Customers",
                "toColumn": "CustomerID",
            }
        ]

        # Internally normalize to TWBX format
        normalized = self.comparator._normalize_relationships(pbix_rels)
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["from_table"], "Orders")

    def test_no_relationships(self):
        """Test comparison with no relationships."""
        result, details = self.comparator.compare_relationships([], [])
        self.assertEqual(result, "PASS")
        self.assertEqual(len(details["relationships_matched"]), 0)

    def test_extra_relationship_in_pbix(self):
        """Test when relationship exists in PBIX but not TWBX."""
        twbx_rels = [
            {
                "from_table": "Orders",
                "from_column": "CustomerID",
                "to_table": "Customers",
                "to_column": "CustomerID",
            }
        ]

        pbix_rels = [
            {
                "from_table": "Orders",
                "from_column": "CustomerID",
                "to_table": "Customers",
                "to_column": "CustomerID",
            },
            {
                "from_table": "OrderItems",
                "from_column": "OrderID",
                "to_table": "Orders",
                "to_column": "OrderID",
            },
        ]

        result, details = self.comparator.compare_relationships(twbx_rels, pbix_rels)
        self.assertEqual(result, "FAIL")
        self.assertEqual(len(details["relationships_missing_in_twbx"]), 1)


if __name__ == "__main__":
    unittest.main()
