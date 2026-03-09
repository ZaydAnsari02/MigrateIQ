"""Result builder for comparison output."""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
from pathlib import Path

import config

logger = logging.getLogger(__name__)


class ComparisonResultBuilder:
    """Build and save comparison results to JSON."""

    def __init__(self, twbx_file: str, pbix_file: str):
        """
        Initialize the result builder.

        Args:
            twbx_file: Path to the TWBX file
            pbix_file: Path to the PBIX file
        """
        self.comparison_id = str(uuid.uuid4())
        self.timestamp = datetime.utcnow().isoformat() + "Z"
        self.twbx_file = Path(twbx_file).name
        self.pbix_file = Path(pbix_file).name

    def build_result(
        self,
        data_result: str,
        data_details: List[Dict[str, Any]],
        model_result: str,
        model_details: Dict[str, Any],
        relationships_result: str,
        relationships_details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build the complete comparison result.

        Args:
            data_result: PASS or FAIL for data comparison
            data_details: List of table comparison details
            model_result: PASS or FAIL for model comparison
            model_details: Model comparison details
            relationships_result: PASS or FAIL for relationships
            relationships_details: Relationship comparison details

        Returns:
            Complete result dictionary
        """
        # Determine overall result
        overall_result = (
            "PASS"
            if (data_result == "PASS" and model_result == "PASS" and relationships_result == "PASS")
            else "FAIL"
        )

        # Collect failure categories
        failure_categories = []
        if data_result == "FAIL":
            failure_categories.append("data")
        if model_result == "FAIL":
            failure_categories.append("semantic_model")
        if relationships_result == "FAIL":
            failure_categories.append("relationships")

        # Build data section
        data_section = {
            "result": data_result,
            "tolerance_threshold_pct": config.TOLERANCE_PCT,
            "tables_compared": len(data_details),
            "details": data_details,
        }

        # Build model section
        model_section = {
            "result": model_result,
            "measures_compared": len(model_details.get("measures_matched", []))
            + len(model_details.get("measures_missing_in_pbix", []))
            + len(model_details.get("measures_missing_in_twbx", [])),
            "details": model_details,
        }

        # Build relationships section
        relationships_section = {
            "result": relationships_result,
            "relationships_compared": len(relationships_details.get("relationships_matched", []))
            + len(relationships_details.get("relationships_missing_in_pbix", []))
            + len(relationships_details.get("relationships_missing_in_twbx", [])),
            "details": relationships_details,
        }

        # Build complete result
        result = {
            "comparison_id": self.comparison_id,
            "timestamp": self.timestamp,
            "inputs": {
                "twbx_file": self.twbx_file,
                "pbix_file": self.pbix_file,
            },
            "overall_result": overall_result,
            "categories": {
                "data": data_section,
                "semantic_model": model_section,
                "relationships": relationships_section,
            },
            "summary": {
                "total_failures": len(failure_categories),
                "failure_categories": failure_categories,
                "notes": self._generate_notes(
                    data_details, model_details, relationships_details
                ),
            },
        }

        logger.info(f"Built comparison result: {overall_result}")
        return result

    def _generate_notes(
        self,
        data_details: List[Dict[str, Any]],
        model_details: Dict[str, Any],
        relationships_details: Dict[str, Any],
    ) -> str:
        """Generate summary notes."""
        notes = []

        # Data notes
        data_failures = [d for d in data_details if d["result"] == "FAIL"]
        if data_failures:
            notes.append(f"{len(data_failures)} table(s) have data mismatches")

        # Model notes
        model_failures = model_details.get("failure_reasons", [])
        if model_failures:
            notes.append(f"{len(model_failures)} semantic model issue(s) detected")

        # Relationship notes
        rel_failures = relationships_details.get("failure_reasons", [])
        if rel_failures:
            notes.append(f"{len(rel_failures)} relationship issue(s) detected")

        return "; ".join(notes) if notes else "All checks passed"

    def generate_output_filename(
        self,
        overall_result: str,
        output_dir: Path | None = None,
    ) -> Path:
        """
        Build a descriptive, unique output file path.

        Format: {twbx_stem}_vs_{pbix_stem}_{PASS|FAIL}_{YYYYMMDD_HHMMSS}.json
        If a file with that name already exists a numeric suffix (_1, _2, …)
        is appended so previous runs are never overwritten.

        Args:
            overall_result: "PASS" or "FAIL"
            output_dir: Directory to save into (defaults to config.OUTPUT_DIR)

        Returns:
            A Path that does not yet exist on disk.
        """
        if output_dir is None:
            output_dir = config.OUTPUT_DIR

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        twbx_stem = Path(self.twbx_file).stem
        pbix_stem = Path(self.pbix_file).stem
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base_name = f"{twbx_stem}_vs_{pbix_stem}_{overall_result}_{ts}"

        candidate = output_dir / f"{base_name}.json"
        counter = 1
        while candidate.exists():
            candidate = output_dir / f"{base_name}_{counter}.json"
            counter += 1

        return candidate

    def save_result(self, result: Dict[str, Any], output_path: str) -> str:
        """
        Save the result to a JSON file.

        Args:
            result: The result dictionary
            output_path: Path to save the JSON file

        Returns:
            The absolute path to the saved file
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        logger.info(f"Saved comparison result to {output_file}")
        return str(output_file.absolute())

    @staticmethod
    def load_result(output_path: str) -> Dict[str, Any]:
        """
        Load a comparison result from JSON.

        Args:
            output_path: Path to the JSON file

        Returns:
            The loaded result dictionary
        """
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def print_result_summary(result: Dict[str, Any]) -> None:
        """Print a human-readable summary of the result."""
        print("\n" + "=" * 70)
        print("COMPARISON RESULT SUMMARY")
        print("=" * 70)

        print(f"\nComparison ID: {result['comparison_id']}")
        print(f"Timestamp: {result['timestamp']}")
        print(f"TWBX File: {result['inputs']['twbx_file']}")
        print(f"PBIX File: {result['inputs']['pbix_file']}")

        print(f"\nOVERALL RESULT: {result['overall_result']}")

        print("\n--- DATA COMPARISON ---")
        data_cat = result["categories"]["data"]
        print(f"Result: {data_cat['result']}")
        print(f"Tables Compared: {data_cat['tables_compared']}")
        failed_tables = [d for d in data_cat["details"] if d["result"] == "FAIL"]
        if failed_tables:
            print(f"Failed Tables: {len(failed_tables)}")
            for table in failed_tables:
                print(f"  - {table['table_name']}: {', '.join(table['failure_reasons'][:2])}")

        print("\n--- SEMANTIC MODEL COMPARISON ---")
        model_cat = result["categories"]["semantic_model"]
        print(f"Result: {model_cat['result']}")
        print(f"Measures Compared: {model_cat['measures_compared']}")
        if model_cat["details"].get("failure_reasons"):
            print(f"Issues: {len(model_cat['details']['failure_reasons'])}")

        print("\n--- RELATIONSHIPS COMPARISON ---")
        rel_cat = result["categories"]["relationships"]
        print(f"Result: {rel_cat['result']}")
        print(f"Relationships Compared: {rel_cat['relationships_compared']}")
        if rel_cat["details"].get("failure_reasons"):
            print(f"Issues: {len(rel_cat['details']['failure_reasons'])}")

        print("\n--- SUMMARY ---")
        summary = result["summary"]
        print(f"Total Failures: {summary['total_failures']}")
        if summary["failure_categories"]:
            print(f"Failure Categories: {', '.join(summary['failure_categories'])}")
        print(f"Notes: {summary['notes']}")

        print("\n" + "=" * 70 + "\n")
