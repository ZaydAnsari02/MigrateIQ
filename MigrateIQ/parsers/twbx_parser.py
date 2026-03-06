"""Parser for Tableau Packaged Workbook (.twbx) files."""
import zipfile
import xml.etree.ElementTree as ET
import logging
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class TwbxParser:
    """Extracts data, models, and relationships from TWBX files."""

    def __init__(self, twbx_path: str):
        """
        Initialize the TWBX parser.

        Args:
            twbx_path: Path to the .twbx file
        """
        self.twbx_path = twbx_path
        self.temp_dir: Optional[str] = None
        self.workbook_xml: Optional[ET.Element] = None
        self.datasources: Dict[str, Dict[str, Any]] = {}
        self.relationships: List[Dict[str, Any]] = []
        self.measures: List[Dict[str, Any]] = []

    def parse(self) -> None:
        """Extract and parse TWBX file contents."""
        logger.info(f"Parsing TWBX file: {self.twbx_path}")
        self.temp_dir = tempfile.mkdtemp()

        try:
            # Extract TWBX (which is a ZIP)
            with zipfile.ZipFile(self.twbx_path, "r") as zip_ref:
                zip_ref.extractall(self.temp_dir)
            logger.debug(f"Extracted TWBX to {self.temp_dir}")

            # Find and parse the workbook.xml
            workbook_path = self._find_workbook_xml()
            if workbook_path:
                self._parse_workbook_xml(workbook_path)

            # Extract datasources and data
            self._extract_datasources()
            self._extract_relationships()
            self._extract_measures()

        except Exception as e:
            logger.error(f"Error parsing TWBX file: {e}")
            raise

    def _find_workbook_xml(self) -> Optional[str]:
        """Find the main Workbook.xml file in extracted TWBX."""
        for root, dirs, files in os.walk(self.temp_dir):
            for file in files:
                if file.lower() == "workbook.xml":
                    return os.path.join(root, file)
        logger.warning("Workbook.xml not found in TWBX")
        return None

    def _parse_workbook_xml(self, xml_path: str) -> None:
        """Parse the Workbook.xml file."""
        try:
            tree = ET.parse(xml_path)
            self.workbook_xml = tree.getroot()
            logger.debug("Successfully parsed Workbook.xml")
        except ET.ParseError as e:
            logger.error(f"Error parsing Workbook.xml: {e}")
            raise

    def _extract_datasources(self) -> Dict[str, Dict[str, Any]]:
        """Extract datasources and their tables from the workbook."""
        if not self.workbook_xml:
            logger.warning("Workbook XML not loaded, skipping datasource extraction")
            return {}

        datasources = {}

        # Parse datasources from XML
        # Tableau stores datasources with connections and columns
        for datasource_elem in self.workbook_xml.findall(".//datasource"):
            name = datasource_elem.get("name", "Unknown")
            datasources[name] = {
                "name": name,
                "tables": self._extract_tables_from_datasource(datasource_elem),
                "connections": self._extract_connections(datasource_elem),
            }

        self.datasources = datasources
        logger.info(f"Extracted {len(datasources)} datasources from TWBX")
        return datasources

    def _extract_tables_from_datasource(
        self, datasource_elem: ET.Element
    ) -> List[Dict[str, Any]]:
        """Extract table definitions from a datasource element."""
        tables = []

        # Look for column definitions which indicate tables
        for column_elem in datasource_elem.findall(".//column"):
            col_name = column_elem.get("name", "Unknown")
            col_type = column_elem.get("type", "string")

            table_name = column_elem.get("table", "default")

            # Find or create table entry
            table_entry = next(
                (t for t in tables if t["name"] == table_name), None
            )
            if not table_entry:
                table_entry = {"name": table_name, "columns": []}
                tables.append(table_entry)

            table_entry["columns"].append(
                {"name": col_name, "data_type": col_type, "caption": col_name}
            )

        return tables

    def _extract_connections(self, datasource_elem: ET.Element) -> List[Dict]:
        """Extract connection information from datasource."""
        connections = []

        for conn_elem in datasource_elem.findall(".//connection"):
            conn_info = {
                "class": conn_elem.get("class", "Unknown"),
                "dbname": conn_elem.get("dbname", "Unknown"),
                "server": conn_elem.get("server", "Unknown"),
            }
            connections.append(conn_info)

        return connections

    def _extract_relationships(self) -> List[Dict[str, Any]]:
        """Extract relationships between datasources."""
        if not self.workbook_xml:
            logger.warning("Workbook XML not loaded, skipping relationship extraction")
            return []

        relationships = []

        # Tableau stores relationships in the datasource definitions
        # Look for foreign key or join definitions
        for datasource_elem in self.workbook_xml.findall(".//datasource"):
            for relation in datasource_elem.findall(".//relation"):
                rel_info = {
                    "from_table": relation.get("left", ""),
                    "to_table": relation.get("right", ""),
                    "from_column": relation.get("left_key", ""),
                    "to_column": relation.get("right_key", ""),
                    "type": relation.get("type", "left"),
                }
                if rel_info["from_table"] and rel_info["to_table"]:
                    relationships.append(rel_info)

        self.relationships = relationships
        logger.info(f"Extracted {len(relationships)} relationships from TWBX")
        return relationships

    def _extract_measures(self) -> List[Dict[str, Any]]:
        """Extract calculated measures/fields from TWBX."""
        if not self.workbook_xml:
            logger.warning("Workbook XML not loaded, skipping measure extraction")
            return []

        measures = []

        # Extract calculated fields
        for calc_elem in self.workbook_xml.findall(".//calculated-field"):
            measure = {
                "name": calc_elem.get("name", "Unknown"),
                "expression": calc_elem.get("formula", ""),
                "data_type": calc_elem.get("type", "real"),
                "caption": calc_elem.get("caption", ""),
            }
            measures.append(measure)

        # Also look for measures in function definitions
        for func_elem in self.workbook_xml.findall(".//function"):
            measure = {
                "name": func_elem.get("name", "Unknown"),
                "expression": ET.tostring(func_elem, encoding="unicode"),
                "data_type": func_elem.get("type", "real"),
                "caption": func_elem.get("name", ""),
            }
            if measure["name"] != "Unknown":
                measures.append(measure)

        self.measures = measures
        logger.info(f"Extracted {len(measures)} measures from TWBX")
        return measures

    def _extract_hyper_data(
        self, hyper_files: List[str]
    ) -> Dict[str, pd.DataFrame]:
        """
        Extract data from Hyper extract files using tableauhyperapi.

        Args:
            hyper_files: List of paths to .hyper files

        Returns:
            Dictionary mapping table names to DataFrames
        """
        data_frames = {}

        try:
            from tableauhyperapi import HyperProcess, Connection, QueryExecutionMode
        except ImportError:
            logger.warning(
                "tableauhyperapi not installed, skipping Hyper file extraction"
            )
            return data_frames

        for hyper_file in hyper_files:
            try:
                with HyperProcess(telemetry=HyperProcess.Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
                    with Connection(
                        endpoint=hyper.endpoint, database=hyper_file
                    ) as connection:
                        # Get all tables
                        for table in connection.catalog.get_tables("public"):
                            table_name = table.name
                            query_result = connection.execute_query(
                                f'SELECT * FROM "{table_name}"'
                            )

                            # Convert to DataFrame
                            col_names = [col.name for col in query_result.columns]
                            data = [
                                list(row) for row in query_result.fetch_all()
                            ]
                            data_frames[table_name] = pd.DataFrame(data, columns=col_names)
                            logger.info(
                                f"Extracted {len(data_frames[table_name])} rows from table {table_name}"
                            )
            except Exception as e:
                logger.warning(f"Error extracting Hyper file {hyper_file}: {e}")

        return data_frames

    def get_data_tables(self) -> Dict[str, pd.DataFrame]:
        """
        Extract actual data tables from TWBX.

        Returns:
            Dictionary mapping table names to DataFrames
        """
        if not self.temp_dir:
            raise RuntimeError("TWBX file not parsed yet. Call parse() first.")

        data_frames = {}

        # Look for Hyper files (modern Tableau)
        hyper_files = []
        for root, dirs, files in os.walk(self.temp_dir):
            for file in files:
                if file.endswith(".hyper"):
                    hyper_files.append(os.path.join(root, file))

        if hyper_files:
            data_frames.update(self._extract_hyper_data(hyper_files))

        # Fallback: look for CSV data extracts
        if not data_frames:
            data_frames.update(self._extract_csv_data())

        logger.info(f"Retrieved {len(data_frames)} data tables from TWBX")
        return data_frames

    def _extract_csv_data(self) -> Dict[str, pd.DataFrame]:
        """Extract data from CSV files embedded in TWBX."""
        data_frames = {}

        for root, dirs, files in os.walk(self.temp_dir):
            for file in files:
                if file.endswith(".csv"):
                    file_path = os.path.join(root, file)
                    try:
                        table_name = Path(file).stem
                        data_frames[table_name] = pd.read_csv(file_path)
                        logger.info(f"Loaded CSV data from {file}")
                    except Exception as e:
                        logger.warning(f"Error reading CSV {file_path}: {e}")

        return data_frames

    def get_datasources(self) -> Dict[str, Dict[str, Any]]:
        """Return extracted datasources."""
        return self.datasources

    def get_relationships(self) -> List[Dict[str, Any]]:
        """Return extracted relationships."""
        return self.relationships

    def get_measures(self) -> List[Dict[str, Any]]:
        """Return extracted measures."""
        return self.measures

    def cleanup(self) -> None:
        """Clean up temporary directory."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.debug(f"Cleaned up temporary directory {self.temp_dir}")

    def __del__(self):
        """Ensure cleanup on object destruction."""
        self.cleanup()
