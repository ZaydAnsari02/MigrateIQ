"""Parser for Power BI Desktop (.pbix) files."""
import zipfile
import json
import logging
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class PbixParser:
    """Extracts data, models, and relationships from PBIX files."""

    def __init__(self, pbix_path: str):
        """
        Initialize the PBIX parser.

        Args:
            pbix_path: Path to the .pbix file
        """
        self.pbix_path = pbix_path
        self.temp_dir: Optional[str] = None
        self.data_model: Dict[str, Any] = {}
        self.relationships: List[Dict[str, Any]] = []
        self.measures: List[Dict[str, Any]] = []
        self.tables: Dict[str, Dict[str, Any]] = {}

    def parse(self) -> None:
        """Extract and parse PBIX file contents."""
        logger.info(f"Parsing PBIX file: {self.pbix_path}")
        self.temp_dir = tempfile.mkdtemp()

        try:
            # Extract PBIX (which is a ZIP)
            with zipfile.ZipFile(self.pbix_path, "r") as zip_ref:
                zip_ref.extractall(self.temp_dir)
            logger.debug(f"Extracted PBIX to {self.temp_dir}")

            # Parse the data model
            self._parse_data_model()
            self._extract_relationships()
            self._extract_measures()
            self._extract_tables()

        except Exception as e:
            logger.error(f"Error parsing PBIX file: {e}")
            raise

    def _parse_data_model(self) -> None:
        """Find and parse the DataModel JSON."""
        # Common PBIX structure paths
        model_paths = [
            "DataModel",
            "DataMashup",
            "[Content_Types].xml",
            "Metadata",
        ]

        for root, dirs, files in os.walk(self.temp_dir):
            for file in files:
                if file == "DataModel":
                    self._load_data_model_binary(os.path.join(root, file))
                    return
                elif file.endswith(".json"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = json.load(f)
                            # Check if this looks like a model file
                            if isinstance(content, dict) and (
                                "model" in content or "tables" in content
                            ):
                                self.data_model = content
                                logger.debug(f"Loaded model from {file}")
                                return
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass

    def _load_data_model_binary(self, model_path: str) -> None:
        """Load DataModel binary file (compressed JSON)."""
        try:
            with open(model_path, "rb") as f:
                # DataModel files are typically gzip-compressed JSON
                import gzip

                try:
                    content = gzip.decompress(f.read()).decode("utf-8")
                    self.data_model = json.loads(content)
                    logger.debug("Successfully decompressed and parsed DataModel")
                except Exception as e:
                    # Try reading as raw JSON if not gzipped
                    f.seek(0)
                    content = f.read().decode("utf-8", errors="ignore")
                    if content.strip():
                        try:
                            self.data_model = json.loads(content)
                        except json.JSONDecodeError:
                            logger.warning(f"Could not parse DataModel as JSON: {e}")
        except Exception as e:
            logger.warning(f"Error loading DataModel binary: {e}")

    def _extract_relationships(self) -> List[Dict[str, Any]]:
        """Extract relationships from the data model."""
        relationships = []

        # Power BI stores relationships in the model
        if isinstance(self.data_model, dict):
            # Check for tables in model
            tables = self.data_model.get("model", {}).get("tables", [])

            for table in tables:
                table_name = table.get("name", "")

                # Look for relationships
                for rel in table.get("relationships", []):
                    rel_info = {
                        "from_table": table_name,
                        "from_column": rel.get("fromColumn", {}).get("name", ""),
                        "to_table": rel.get("toTable", ""),
                        "to_column": rel.get("toColumn", {}).get("name", ""),
                        "cardinality": rel.get("cardinality", "many-to-one"),
                        "is_active": rel.get("isActive", True),
                        "cross_filter_direction": rel.get(
                            "crossFilteringBehavior", "bothDirections"
                        ),
                    }
                    relationships.append(rel_info)

        self.relationships = relationships
        logger.info(f"Extracted {len(relationships)} relationships from PBIX")
        return relationships

    def _extract_measures(self) -> List[Dict[str, Any]]:
        """Extract calculated measures from the data model."""
        measures = []

        if isinstance(self.data_model, dict):
            tables = self.data_model.get("model", {}).get("tables", [])

            for table in tables:
                table_name = table.get("name", "")

                # Get measures from columns
                for column in table.get("columns", []):
                    if column.get("encodedProperty", {}).get("expression"):
                        measure = {
                            "name": column.get("name", ""),
                            "table": table_name,
                            "expression": column.get("encodedProperty", {}).get(
                                "expression", ""
                            ),
                            "data_type": column.get("dataType", "text"),
                            "is_hidden": column.get("isHidden", False),
                        }
                        measures.append(measure)

                # Also check for explicit measures
                for measure in table.get("measures", []):
                    m = {
                        "name": measure.get("name", ""),
                        "table": table_name,
                        "expression": measure.get("expression", ""),
                        "data_type": measure.get("dataType", "text"),
                        "is_hidden": measure.get("isHidden", False),
                    }
                    measures.append(m)

        self.measures = measures
        logger.info(f"Extracted {len(measures)} measures from PBIX")
        return measures

    def _extract_tables(self) -> Dict[str, Dict[str, Any]]:
        """Extract table definitions from the data model."""
        tables = {}

        if isinstance(self.data_model, dict):
            model_tables = self.data_model.get("model", {}).get("tables", [])

            for table in model_tables:
                table_name = table.get("name", "")
                tables[table_name] = {
                    "name": table_name,
                    "display_name": table.get("displayName", table_name),
                    "columns": [],
                }

                # Extract columns/fields
                for col in table.get("columns", []):
                    column_info = {
                        "name": col.get("name", ""),
                        "data_type": col.get("dataType", "text"),
                        "is_hidden": col.get("isHidden", False),
                    }
                    tables[table_name]["columns"].append(column_info)

        self.tables = tables
        logger.info(f"Extracted {len(tables)} tables from PBIX")
        return tables

    def get_data_tables(self) -> Dict[str, pd.DataFrame]:
        """
        Extract actual data tables from PBIX.

        Note: Extracting actual data from PBIX is complex and requires
        decompressing the VertiPaq model. For now, we return table schema info.

        Returns:
            Dictionary with table structures (column names, not actual data rows)
        """
        if not self.temp_dir:
            raise RuntimeError("PBIX file not parsed yet. Call parse() first.")

        data_frames = {}

        # Create DataFrames from table schema
        for table_name, table_info in self.tables.items():
            columns = [col["name"] for col in table_info.get("columns", [])]

            # Create an empty DataFrame with the columns
            # In a production scenario, you'd extract actual data from the model
            data_frames[table_name] = pd.DataFrame(columns=columns)
            logger.info(f"Created schema for table {table_name} with {len(columns)} columns")

        return data_frames

    def get_data_model(self) -> Dict[str, Any]:
        """Return the extracted data model."""
        return self.data_model

    def get_relationships(self) -> List[Dict[str, Any]]:
        """Return extracted relationships."""
        return self.relationships

    def get_measures(self) -> List[Dict[str, Any]]:
        """Return extracted measures."""
        return self.measures

    def get_tables(self) -> Dict[str, Dict[str, Any]]:
        """Return extracted tables."""
        return self.tables

    def cleanup(self) -> None:
        """Clean up temporary directory."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil

            shutil.rmtree(self.temp_dir)
            logger.debug(f"Cleaned up temporary directory {self.temp_dir}")

    def __del__(self):
        """Ensure cleanup on object destruction."""
        self.cleanup()
