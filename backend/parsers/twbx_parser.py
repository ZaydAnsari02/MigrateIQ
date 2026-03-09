"""Parser for Tableau Packaged Workbook (.twbx) files."""
import zipfile
import xml.etree.ElementTree as ET
import logging
import tempfile
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class TwbxParser:
    """Extracts data, models, and relationships from TWBX files."""

    def __init__(self, twbx_path: str):
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
            with zipfile.ZipFile(self.twbx_path, "r") as zip_ref:
                zip_ref.extractall(self.temp_dir)
            logger.debug(f"Extracted TWBX to {self.temp_dir}")

            workbook_path = self._find_workbook_xml()
            if workbook_path:
                self._parse_workbook_xml(workbook_path)

            self._extract_datasources()
            self._extract_relationships()
            self._extract_measures()

        except Exception as e:
            logger.error(f"Error parsing TWBX file: {e}")
            raise

    # ------------------------------------------------------------------
    # Workbook location
    #
    # TWBX files contain a .twb file (Tableau Workbook XML) — NOT a file
    # named "workbook.xml".  The .twb lives at the root of the ZIP.
    # ------------------------------------------------------------------

    def _find_workbook_xml(self) -> Optional[str]:
        """
        Find the Tableau workbook descriptor inside the extracted TWBX.

        The correct file to look for is any *.twb file — NOT workbook.xml
        (that filename does not exist in Tableau's format).
        """
        for root, dirs, files in os.walk(self.temp_dir):
            for file in files:
                if file.lower().endswith(".twb"):
                    path = os.path.join(root, file)
                    logger.debug(f"Found Tableau workbook file: {file}")
                    return path

        # Legacy fallback
        for root, dirs, files in os.walk(self.temp_dir):
            for file in files:
                if file.lower() == "workbook.xml":
                    return os.path.join(root, file)

        logger.warning("No .twb file found in TWBX — contents:")
        for root, dirs, files in os.walk(self.temp_dir):
            for file in files:
                logger.warning(
                    f"  {os.path.relpath(os.path.join(root, file), self.temp_dir)}"
                )
        return None

    def _parse_workbook_xml(self, xml_path: str) -> None:
        """Parse the .twb XML file."""
        try:
            tree = ET.parse(xml_path)
            self.workbook_xml = tree.getroot()
            logger.debug("Successfully parsed Workbook.xml")
        except ET.ParseError as e:
            logger.error(f"Error parsing workbook XML: {e}")
            raise

    # ------------------------------------------------------------------
    # Datasource extraction
    #
    # Tableau datasources contain:
    #   <connection> elements with <named-connection> children
    #   <relation type="table"> elements that describe actual DB tables
    #     with <columns><column> children listing field names & types
    #   <relation type="join"> elements that describe joins between tables
    # ------------------------------------------------------------------

    def _extract_datasources(self) -> Dict[str, Dict[str, Any]]:
        """Extract datasource and table definitions from the workbook."""
        if not self.workbook_xml:
            logger.warning("Workbook XML not loaded, skipping datasource extraction")
            return {}

        datasources: Dict[str, Dict[str, Any]] = {}

        for ds_elem in self.workbook_xml.findall(".//datasource"):
            name = ds_elem.get("name", "Unknown")
            caption = ds_elem.get("caption", name)

            # Skip the built-in "Parameters" pseudo-datasource
            if name.lower() == "parameters":
                continue

            # Skip duplicate datasource elements (Tableau can emit the same
            # datasource multiple times in the XML; keep the richest entry)
            tables = self._extract_physical_tables(ds_elem)
            connections = self._extract_connections(ds_elem)
            calc_fields = self._extract_calculated_fields_from_ds(ds_elem)

            if name not in datasources or len(tables) > len(
                datasources[name].get("tables", [])
            ):
                datasources[name] = {
                    "name": name,
                    "caption": caption,
                    "tables": tables,
                    "connections": connections,
                    "calculated_fields": calc_fields,
                }

        self.datasources = datasources
        logger.info(f"Extracted {len(datasources)} datasources from TWBX")
        return datasources

    def _extract_physical_tables(
        self, ds_elem: ET.Element
    ) -> List[Dict[str, Any]]:
        """
        Extract physical table definitions from a datasource.

        Tableau stores actual table/sheet schemas inside:
            <relation type="table" name="Orders" table="[Orders$]">
              <columns>
                <column datatype="integer" name="Row ID" ordinal="0" />
                ...
              </columns>
            </relation>

        We use deduplication because the same table may appear multiple times
        when Tableau renders the join graph (once per join branch).
        """
        tables: Dict[str, Dict[str, Any]] = {}

        for rel in ds_elem.findall(".//relation[@type='table']"):
            rel_name = rel.get("name", "")
            if not rel_name:
                continue

            columns = []
            for col in rel.findall("columns/column"):
                col_name = col.get("name", "")
                if col_name:
                    columns.append({
                        "name": col_name,
                        "data_type": col.get("datatype", "string"),
                        "caption": col.get("caption", col_name),
                        "ordinal": col.get("ordinal", ""),
                    })

            # Keep the entry with the most columns (most complete definition)
            if rel_name not in tables or len(columns) > len(tables[rel_name]["columns"]):
                tables[rel_name] = {
                    "name": rel_name,
                    "source_table": rel.get("table", ""),
                    "connection": rel.get("connection", ""),
                    "columns": columns,
                }

        return list(tables.values())

    def _extract_connections(self, ds_elem: ET.Element) -> List[Dict]:
        """Extract connection metadata."""
        connections = []
        for conn in ds_elem.findall(".//connection"):
            connections.append({
                "class": conn.get("class", "Unknown"),
                "dbname": conn.get("dbname", ""),
                "server": conn.get("server", ""),
                "filename": conn.get("filename", ""),
            })
        return connections

    def _extract_calculated_fields_from_ds(
        self, ds_elem: ET.Element
    ) -> List[Dict[str, Any]]:
        """
        Extract calculated fields from a single datasource element.

        In Tableau XML, calculated fields are <column> elements that have a
        <calculation formula="..."> child.  The old code searched for a
        <calculated-field> tag which does not exist in Tableau's schema.
        """
        fields = []
        for col in ds_elem.findall(".//column"):
            calc = col.find("calculation")
            if calc is None:
                continue
            name = col.get("name", "").strip("[]")
            caption = col.get("caption", name)
            formula = calc.get("formula", "")
            fields.append({
                "name": caption or name,
                "raw_name": name,
                "expression": formula,
                "data_type": col.get("datatype", col.get("type", "real")),
                "role": col.get("role", ""),
                "caption": caption,
            })
        return fields

    # ------------------------------------------------------------------
    # Relationship extraction
    #
    # Tableau encodes joins as nested <relation type="join"> elements.
    # The join condition lives in a <clause><expression op="="> element
    # whose two children carry the operand references:
    #
    #   <expression op="=">
    #     <expression op="[Orders].[Order ID]" />
    #     <expression op="[Returns].[Order ID]" />
    #   </expression>
    #
    # Modern Tableau (2020.2+) also uses top-level <relationship> elements
    # for logical-layer relationships.
    # ------------------------------------------------------------------

    def _extract_relationships(self) -> List[Dict[str, Any]]:
        """Extract join and relationship definitions from the workbook."""
        if not self.workbook_xml:
            logger.warning("Workbook XML not loaded, skipping relationship extraction")
            return []

        relationships: List[Dict[str, Any]] = []
        seen: set = set()

        # --- Strategy 1: Classic join-based relations ---
        for ds_elem in self.workbook_xml.findall(".//datasource"):
            for join_rel in ds_elem.findall(".//relation[@type='join']"):
                join_type = join_rel.get("join", "inner")
                for clause in join_rel.findall(".//clause"):
                    for expr in clause.findall("expression"):
                        children = list(expr)
                        if len(children) < 2:
                            continue
                        left_op = children[0].get("op", "")
                        right_op = children[1].get("op", "")

                        # op values are like "[TableName].[ColumnName]"
                        left_table, left_col = self._parse_tableau_ref(left_op)
                        right_table, right_col = self._parse_tableau_ref(right_op)

                        if not (left_table and right_table):
                            continue

                        key = (left_table, left_col, right_table, right_col)
                        if key in seen:
                            continue
                        seen.add(key)

                        relationships.append({
                            "from_table": left_table,
                            "from_column": left_col,
                            "to_table": right_table,
                            "to_column": right_col,
                            "type": join_type,
                        })

        # --- Strategy 2: Modern logical relationships (Tableau 2020.2+) ---
        for rel_elem in self.workbook_xml.findall(".//relationship"):
            left_obj = rel_elem.get("left-object-id", "")
            right_obj = rel_elem.get("right-object-id", "")
            if not (left_obj and right_obj):
                continue
            for clause in rel_elem.findall(".//clause"):
                for expr in clause.findall(".//expression"):
                    children = list(expr)
                    if len(children) < 2:
                        continue
                    left_col = children[0].get("column",
                               children[0].get("name", "")).strip("[]")
                    right_col = children[1].get("column",
                                children[1].get("name", "")).strip("[]")
                    key = (left_obj, left_col, right_obj, right_col)
                    if key in seen:
                        continue
                    seen.add(key)
                    relationships.append({
                        "from_table": left_obj,
                        "from_column": left_col,
                        "to_table": right_obj,
                        "to_column": right_col,
                        "type": "relationship",
                    })

        self.relationships = relationships
        logger.info(f"Extracted {len(relationships)} relationships from TWBX")
        return relationships

    @staticmethod
    def _parse_tableau_ref(op: str):
        """
        Parse a Tableau column reference like '[Orders].[Order ID]'
        into ('Orders', 'Order ID').
        """
        parts = re.findall(r'\[([^\]]+)\]', op)
        if len(parts) >= 2:
            return parts[0], parts[1]
        if len(parts) == 1:
            return parts[0], ""
        return "", ""

    # ------------------------------------------------------------------
    # Measure / calculated-field extraction
    # ------------------------------------------------------------------

    def _extract_measures(self) -> List[Dict[str, Any]]:
        """
        Extract calculated fields (measures and calculated dimensions).

        Collects from all datasources in the workbook.
        """
        if not self.workbook_xml:
            logger.warning("Workbook XML not loaded, skipping measure extraction")
            return []

        measures: List[Dict[str, Any]] = []
        seen: set = set()

        for ds_elem in self.workbook_xml.findall(".//datasource"):
            ds_name = ds_elem.get("caption", ds_elem.get("name", "Unknown"))
            for field in self._extract_calculated_fields_from_ds(ds_elem):
                key = (ds_name, field["name"])
                if key in seen:
                    continue
                seen.add(key)
                field["datasource"] = ds_name
                measures.append(field)

        self.measures = measures
        logger.info(f"Extracted {len(measures)} measures from TWBX")
        return measures

    # ------------------------------------------------------------------
    # Hyper / CSV data extraction
    # ------------------------------------------------------------------

    def _extract_hyper_data(self, hyper_files: List[str]) -> Dict[str, pd.DataFrame]:
        """Extract data from Hyper extract files using tableauhyperapi."""
        data_frames: Dict[str, pd.DataFrame] = {}
        try:
            from tableauhyperapi import HyperProcess, Connection
        except ImportError:
            logger.warning("tableauhyperapi not installed, skipping Hyper file extraction")
            return data_frames

        for hyper_file in hyper_files:
            try:
                with HyperProcess(
                    telemetry=HyperProcess.Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU
                ) as hyper:
                    with Connection(
                        endpoint=hyper.endpoint, database=hyper_file
                    ) as connection:
                        for table in connection.catalog.get_tables("public"):
                            table_name = table.name
                            result = connection.execute_query(
                                f'SELECT * FROM "{table_name}"'
                            )
                            col_names = [col.name for col in result.columns]
                            data = [list(row) for row in result.fetch_all()]
                            data_frames[table_name] = pd.DataFrame(data, columns=col_names)
                            logger.info(
                                f"Extracted {len(data_frames[table_name])} rows "
                                f"from Hyper table {table_name}"
                            )
            except Exception as e:
                logger.warning(f"Error extracting Hyper file {hyper_file}: {e}")

        return data_frames

    def _extract_csv_data(self) -> Dict[str, pd.DataFrame]:
        """Extract data from CSV files embedded in TWBX."""
        data_frames: Dict[str, pd.DataFrame] = {}
        for root, dirs, files in os.walk(self.temp_dir):
            for file in files:
                if file.endswith(".csv"):
                    fp = os.path.join(root, file)
                    try:
                        table_name = Path(file).stem
                        data_frames[table_name] = pd.read_csv(fp)
                        logger.info(f"Loaded CSV data from {file}")
                    except Exception as e:
                        logger.warning(f"Error reading CSV {fp}: {e}")
        return data_frames

    def get_data_tables(self) -> Dict[str, pd.DataFrame]:
        """
        Return actual data tables from TWBX.

        Prefers Hyper extracts, falls back to embedded CSVs, then returns
        empty DataFrames built from the schema if neither is available.
        """
        if not self.temp_dir:
            raise RuntimeError("TWBX file not parsed yet. Call parse() first.")

        data_frames: Dict[str, pd.DataFrame] = {}

        hyper_files = [
            os.path.join(root, file)
            for root, dirs, files in os.walk(self.temp_dir)
            for file in files
            if file.endswith(".hyper")
        ]

        if hyper_files:
            data_frames.update(self._extract_hyper_data(hyper_files))

        if not data_frames:
            data_frames.update(self._extract_csv_data())

        # Last resort: build schema-only DataFrames from physical table defs
        if not data_frames:
            for ds_name, ds_info in self.datasources.items():
                for table in ds_info.get("tables", []):
                    tname = table.get("name", "")
                    if tname and tname not in data_frames:
                        cols = [c["name"] for c in table.get("columns", [])]
                        data_frames[tname] = pd.DataFrame(columns=cols)
                        logger.info(
                            f"Created schema-only DataFrame for table '{tname}' "
                            f"with {len(cols)} columns"
                        )

        logger.info(f"Retrieved {len(data_frames)} data tables from TWBX")
        return data_frames

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_datasources(self) -> Dict[str, Dict[str, Any]]:
        return self.datasources

    def get_relationships(self) -> List[Dict[str, Any]]:
        return self.relationships

    def get_measures(self) -> List[Dict[str, Any]]:
        return self.measures

    def cleanup(self) -> None:
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.debug(f"Cleaned up temporary directory {self.temp_dir}")

    def __del__(self):
        self.cleanup()