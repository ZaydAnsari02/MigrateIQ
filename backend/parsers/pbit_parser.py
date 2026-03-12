"""
PbitParser — Extract semantic model information from Power BI Template (.pbit)

Provides:
    parse()
    get_measures()
    get_data_tables()
    get_relationships()
    get_tables()
    cleanup()
"""

import zipfile
import json
import re
import os
import tempfile
import shutil
import logging


class PbitParser:

    def __init__(self, pbit_path: str):

        self.pbit_path = pbit_path
        self.tmp_dir = tempfile.mkdtemp()

        self.logger = logging.getLogger(__name__)

        self.measures = []
        self.tables = []
        self.relationships = []
        self.data_tables = {}

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    def _normalize_expression(self, expr):

        if isinstance(expr, list):
            return " ".join(str(x) for x in expr).strip()

        if isinstance(expr, str):
            return expr.strip()

        return str(expr) if expr else ""

    def _try_decode(self, raw):

        for enc in ("utf-16-le", "utf-16", "utf-8-sig", "utf-8"):
            try:
                return raw.decode(enc)
            except Exception:
                continue

        return None

    def _infer_table(self, expr):

        m = re.search(r'(\w+)\[', expr)

        if m:
            return m.group(1)

        return "Unknown"

    # --------------------------------------------------
    # Main Parse
    # --------------------------------------------------

    def parse(self):

        self.logger.info("Parsing PBIT file")

        with zipfile.ZipFile(self.pbit_path, "r") as zf:
            zf.extractall(self.tmp_dir)

        schema_path = None

        for root, _, files in os.walk(self.tmp_dir):

            for f in files:

                if f == "DataModelSchema":

                    schema_path = os.path.join(root, f)

        if not schema_path:
            raise RuntimeError("DataModelSchema not found in PBIT")

        with open(schema_path, "rb") as f:

            raw = f.read()

        text = self._try_decode(raw)

        if not text:
            raise RuntimeError("Could not decode DataModelSchema")

        model_json = json.loads(text)

        self._parse_model(model_json)

    # --------------------------------------------------
    # Model Extraction
    # --------------------------------------------------

    def _parse_model(self, model_json):

        model = model_json.get("model", model_json)

        for table in model.get("tables", []):

            tname = table.get("name")

            self.tables.append(tname)

            # --------------------------------
            # columns
            # --------------------------------

            table_columns = []

            for col in table.get("columns", []):

                cname = col.get("name")
                ctype = col.get("dataType", "string")

                table_columns.append({"name": cname, "dataType": ctype})

                # calculated column
                expr = col.get("expression")

                if expr:

                    self.measures.append({
                        "name": cname,
                        "table": tname,
                        "expression": self._normalize_expression(expr),
                        "type": "calculated_column"
                    })

            self.data_tables[tname] = table_columns

            # --------------------------------
            # measures
            # --------------------------------

            for m in table.get("measures", []):

                self.measures.append({
                    "name": m.get("name"),
                    "table": tname,
                    "expression": self._normalize_expression(m.get("expression")),
                    "type": "measure"
                })

        # --------------------------------
        # relationships
        # --------------------------------

        for rel in model.get("relationships", []):

            self.relationships.append({
                "from_table": rel.get("fromTable"),
                "from_column": rel.get("fromColumn"),
                "to_table": rel.get("toTable"),
                "to_column": rel.get("toColumn"),
                "type": rel.get("crossFilteringBehavior", "unknown")
            })

    # --------------------------------------------------
    # Public getters
    # --------------------------------------------------

    def get_measures(self):

        return self.measures

    def get_tables(self):

        return self.tables

    def get_data_tables(self):

        return self.data_tables

    def get_relationships(self):

        return self.relationships

    # --------------------------------------------------
    # Cleanup
    # --------------------------------------------------

    def cleanup(self):

        shutil.rmtree(self.tmp_dir, ignore_errors=True)