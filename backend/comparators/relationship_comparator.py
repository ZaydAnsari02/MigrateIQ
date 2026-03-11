"""Relationship comparison logic."""
import logging
from typing import Dict, List, Any, Tuple

logger = logging.getLogger(__name__)


class RelationshipComparator:
    """Compare relationships between TWBX and PBIX."""

    def __init__(self):
        """Initialize the relationship comparator."""
        pass

    def compare_relationships(
        self,
        twbx_relationships: List[Dict[str, Any]],
        pbix_relationships: List[Dict[str, Any]],
        verbose: bool = False,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Compare relationships between TWBX and PBIX.

        Args:
            twbx_relationships: List of relationships from TWBX
            pbix_relationships: List of relationships from PBIX
            verbose: If True, log detailed information

        Returns:
            Tuple of (result, details)
        """
        result = "PASS"
        details = {
            "relationships_matched": [],
            "relationships_missing_in_pbix": [],
            "relationships_missing_in_twbx": [],
            "cardinality_mismatches": [],
            "failure_reasons": [],
        }

        # Normalize relationships for comparison
        twbx_rels = self._normalize_relationships(twbx_relationships)
        pbix_rels = self._normalize_relationships(pbix_relationships)

        logger.info(f"Comparing {max(len(twbx_rels), len(pbix_rels))} relationships")

        # Find matched relationships
        matched_rel_keys = set()

        for twbx_rel in twbx_rels:
            rel_key = self._relationship_key(twbx_rel)

            # Look for matching relationship in PBIX
            pbix_match = None
            for pbix_rel in pbix_rels:
                if rel_key == self._relationship_key(pbix_rel):
                    pbix_match = pbix_rel
                    matched_rel_keys.add(rel_key)
                    break

            if pbix_match:
                # Relationship exists in both, check if details match
                matched_info = {
                    "from": f"{twbx_rel.get('from_table')}[{twbx_rel.get('from_column')}]",
                    "to": f"{twbx_rel.get('to_table')}[{twbx_rel.get('to_column')}]",
                    "cardinality": twbx_rel.get("cardinality", "unknown"),
                }
                details["relationships_matched"].append(matched_info)

                # Check cardinality
                twbx_card = twbx_rel.get("cardinality", "").lower()
                pbix_card = pbix_rel.get("cardinality", "").lower()

                if twbx_card and pbix_card and twbx_card != pbix_card:
                    details["cardinality_mismatches"].append(
                        {
                            "relationship": matched_info["from"] + " -> " + matched_info["to"],
                            "twbx_cardinality": twbx_card,
                            "pbix_cardinality": pbix_card,
                        }
                    )
                    details["failure_reasons"].append(
                        f"Cardinality mismatch for {matched_info['from']} -> {matched_info['to']}: "
                        f"{twbx_card} vs {pbix_card}"
                    )
                    result = "FAIL"

                if verbose:
                    logger.debug(f"Relationship matched: {matched_info}")

            else:
                # Relationship missing in PBIX
                rel_str = f"{twbx_rel.get('from_table')}[{twbx_rel.get('from_column')}] -> {twbx_rel.get('to_table')}[{twbx_rel.get('to_column')}]"
                details["relationships_missing_in_pbix"].append(rel_str)
                details["failure_reasons"].append(f"Relationship missing in PBIX: {rel_str}")
                result = "FAIL"

        # Find relationships in PBIX but not in TWBX
        for pbix_rel in pbix_rels:
            rel_key = self._relationship_key(pbix_rel)

            if rel_key not in matched_rel_keys:
                rel_str = f"{pbix_rel.get('from_table')}[{pbix_rel.get('from_column')}] -> {pbix_rel.get('to_table')}[{pbix_rel.get('to_column')}]"
                details["relationships_missing_in_twbx"].append(rel_str)
                details["failure_reasons"].append(f"Relationship missing in TWBX: {rel_str}")
                result = "FAIL"

        if verbose:
            logger.debug(f"Relationship comparison: {len(details['relationships_matched'])} matched")

        return result, details

    def _normalize_relationships(
        self, relationships: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Normalize relationship format for comparison.

        Handles variations in schema between TWBX and PBIX.
        """
        normalized = []

        for rel in relationships:
            # Handle different key names between formats
            norm_rel = {
                "from_table": rel.get("from_table") or rel.get("fromTable") or "",
                "from_column": rel.get("from_column")
                or rel.get("fromColumn")
                or rel.get("left_key")
                or "",
                "to_table": rel.get("to_table") or rel.get("toTable") or "",
                "to_column": rel.get("to_column")
                or rel.get("toColumn")
                or rel.get("right_key")
                or "",
                "cardinality": rel.get("cardinality") or rel.get("type") or "unknown",
                "is_active": rel.get("is_active") or rel.get("isActive") or True,
                "cross_filter": rel.get("cross_filter_direction")
                or rel.get("crossFilteringBehavior")
                or "",
            }

            # Only add if we have meaningful relationship info
            if norm_rel["from_table"] and norm_rel["to_table"]:
                normalized.append(norm_rel)

        return normalized

    def _relationship_key(self, relationship: Dict[str, Any]) -> Tuple:
        """Create a comparable key for a relationship."""
        return (
            relationship.get("from_table", "").lower(),
            relationship.get("from_column", "").lower(),
            relationship.get("to_table", "").lower(),
            relationship.get("to_column", "").lower(),
        )
