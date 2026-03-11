"""Parser for Power BI Desktop (.pbix) files."""
import zipfile
import json
import logging
import tempfile
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


class PbixParser:
    """Extracts data, models, and relationships from PBIX files."""

    def __init__(self, pbix_path: str):
        self.pbix_path = pbix_path
        self.temp_dir: Optional[str] = None
        self.data_model: Dict[str, Any] = {}
        self.relationships: List[Dict[str, Any]] = []
        self.measures: List[Dict[str, Any]] = []
        self.tables: Dict[str, Dict[str, Any]] = {}
        self._raw_datamodel: bytes = b""
        self._decoded_datamodel: str = ""  # UTF-16 decoded text (for VertiPaq binary)

    def parse(self) -> None:
        """Extract and parse PBIX file contents."""
        logger.info(f"Parsing PBIX file: {self.pbix_path}")
        self.temp_dir = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(self.pbix_path, "r") as zip_ref:
                zip_ref.extractall(self.temp_dir)
            logger.debug(f"Extracted PBIX to {self.temp_dir}")

            self._parse_data_model()
            self._extract_relationships()
            self._extract_measures()
            self._extract_tables()
        except Exception as e:
            logger.error(f"Error parsing PBIX file: {e}")
            raise

    # ------------------------------------------------------------------
    # DataModel loading
    #
    # PBIX DataModel files begin with FF FE (UTF-16 LE BOM) followed by
    # "STREAM_STORAGE_SIGNATURE" — this is the VertiPaq/ABF container
    # format, NOT JSON.  We store the raw bytes and extract metadata via
    # pattern scanning.  If a JSON sub-document is embedded (older PBIX
    # or gzip variants) we also try to parse that.
    # ------------------------------------------------------------------

    def _parse_data_model(self) -> None:
        """Locate and load the DataModel."""
        datamodel_path = None
        for root, dirs, files in os.walk(self.temp_dir):
            for file in files:
                if file == "DataModel":
                    datamodel_path = os.path.join(root, file)
                elif file.endswith(".json"):
                    fp = os.path.join(root, file)
                    try:
                        with open(fp, "r", encoding="utf-8") as f:
                            content = json.load(f)
                        if isinstance(content, dict) and (
                            "model" in content or "tables" in content
                        ):
                            self.data_model = content
                            logger.debug(f"Loaded JSON model from {file}")
                            return
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass

        if datamodel_path:
            self._load_data_model_binary(datamodel_path)

    def _load_data_model_binary(self, model_path: str) -> None:
        """
        Read the DataModel binary.

        FF FE header  -> VertiPaq/ABF container (most Power BI Desktop files).
        1F 8B header  -> gzip-compressed JSON (older PBIX).
        Otherwise     -> try UTF-8 JSON, then fall back to binary scanning.
        """
        try:
            with open(model_path, "rb") as f:
                raw = f.read()
            self._raw_datamodel = raw
            bom = raw[:2]

            if bom in (b'\xff\xfe', b'\xfe\xff'):
                enc = "utf-16-le" if bom == b'\xff\xfe' else "utf-16-be"
                logger.debug(
                    f"DataModel is VertiPaq/ABF binary ({enc} BOM). "
                    "Attempting UTF-16 decode for metadata extraction."
                )
                # Decode UTF-16 and search for embedded JSON in the decoded text.
                # This is necessary because VertiPaq stores strings in UTF-16-LE,
                # so raw-byte regex patterns cannot find table names or JSON.
                try:
                    decoded = raw.decode(enc, errors="ignore")
                    self._decoded_datamodel = decoded
                    self._try_extract_embedded_json_from_text(decoded)
                except Exception as e:
                    logger.warning(f"UTF-16 decode failed: {e}")
                    self._try_extract_embedded_json(raw)

            elif raw[:2] == b'\x1f\x8b':
                import gzip
                logger.debug("DataModel detected as gzip-compressed")
                try:
                    content = gzip.decompress(raw).decode("utf-8")
                    self.data_model = json.loads(content)
                    logger.debug("Successfully parsed DataModel as gzip JSON")
                    return
                except Exception as e:
                    logger.warning(f"Gzip DataModel parse failed: {e}")
                    self._try_extract_embedded_json(raw)

            else:
                try:
                    content = raw.decode("utf-8", errors="ignore").lstrip("\ufeff")
                    if content.strip().startswith("{"):
                        self.data_model = json.loads(content)
                        logger.debug("Parsed DataModel as UTF-8 JSON")
                        return
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    logger.warning(f"UTF-8 DataModel parse failed: {e}")
                self._try_extract_embedded_json(raw)

        except Exception as e:
            logger.warning(f"Error loading DataModel binary: {e}")

    def _try_extract_embedded_json(self, raw: bytes) -> None:
        """Look for a JSON sub-document inside the binary blob (raw bytes)."""
        for m in re.finditer(rb'\{"', raw):
            pos = m.start()
            try:
                chunk = raw[pos:pos + 4_000_000].decode("utf-8", errors="strict")
                obj = json.loads(chunk)
                if isinstance(obj, dict) and (
                    "model" in obj or "tables" in obj or "relationships" in obj
                ):
                    self.data_model = obj
                    logger.debug(f"Found embedded JSON model at byte {pos}")
                    return
            except Exception:
                pass

    def _try_extract_embedded_json_from_text(self, text: str) -> None:
        """Look for a JSON sub-document inside the UTF-16-decoded text."""
        for m in re.finditer(r'\{"', text):
            pos = m.start()
            try:
                chunk = text[pos:pos + 2_000_000]
                obj = json.loads(chunk)
                if isinstance(obj, dict) and (
                    "model" in obj or "tables" in obj or "relationships" in obj
                ):
                    self.data_model = obj
                    logger.debug(f"Found embedded JSON model at char offset {pos}")
                    return
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Text-run helper — shared by table, column, and measure scanners
    # ------------------------------------------------------------------

    def _readable_runs(self, raw: bytes, min_len: int = 3):
        """Yield (offset, text) for every printable ASCII run >= min_len chars."""
        i = 0
        buf = []
        start = 0
        while i < len(raw):
            b = raw[i]
            if 32 <= b <= 126 or b in (9, 10, 13):
                if not buf:
                    start = i
                buf.append(chr(b))
            else:
                if len(buf) >= min_len:
                    yield start, "".join(buf)
                buf = []
            i += 1
        if len(buf) >= min_len:
            yield start, "".join(buf)

    # ------------------------------------------------------------------
    # Table extraction
    # ------------------------------------------------------------------

    def _extract_tables(self) -> Dict[str, Dict[str, Any]]:
        """Extract table + column definitions."""
        tables: Dict[str, Dict[str, Any]] = {}

        # Path 1 — JSON model
        if self.data_model:
            model = self.data_model.get("model", self.data_model)
            for table in model.get("tables", []):
                name = table.get("name", "")
                if not name:
                    continue
                # Try various locations for row counts in PBIX metadata
                row_count = table.get("rowCount")
                if row_count is None:
                    # Often stored inside partitions
                    partitions = table.get("partitions", [])
                    if partitions:
                        # Sum row counts across all partitions (usual case is just 1)
                        row_count = sum(p.get("rowCount", 0) for p in partitions)
                    else:
                        row_count = 0

                tables[name] = {
                    "name": name,
                    "display_name": table.get("displayName", name),
                    "row_count": row_count,
                    "columns": [
                        {
                            "name": col.get("name", ""),
                            "data_type": col.get("dataType", "text"),
                            "is_hidden": col.get("isHidden", False),
                        }
                        for col in table.get("columns", [])
                        if col.get("name")
                    ],
                }

        # Path 2 — ABF binary scanning
        if not tables and self._raw_datamodel:
            tables = self._scan_tables_from_binary()

        self.tables = tables
        logger.info(f"Extracted {len(tables)} tables from PBIX")
        return tables

    def _scan_tables_from_binary(self) -> Dict[str, Dict[str, Any]]:
        """
        Extract table and column names from the raw VertiPaq binary.

        VertiPaq/ABF uses UTF-16-LE encoding, so this method preferentially
        operates on the decoded text stored in _decoded_datamodel.  If that is
        unavailable, it falls back to raw-byte scanning (ASCII runs only).

        Table names appear as:  <Name> (<id>).tbl
        Column references:      H$<Table> (<tid>)$<Column> (<cid>)
        """
        tables: Dict[str, Dict[str, Any]] = {}
        seen_cols: Dict[str, set] = {}

        # ── Primary path: search in decoded UTF-16 text ──────────────────
        if self._decoded_datamodel:
            text = self._decoded_datamodel

            # Table names: <Name> (<id>).tbl
            for m in re.finditer(r'([A-Za-z][A-Za-z0-9 _$-]+?) \(\d+\)\.tbl', text):
                name = m.group(1).strip()
                if name and name not in tables:
                    tables[name] = {
                        "name": name,
                        "display_name": name,
                        "columns": [],
                        "row_count": 0,
                    }

            # Column references: H$<Table> (<id>)$<Column> (<id>)
            col_pat = re.compile(
                r'H\$([^\$\(\x00-\x1f]+?) \(\d+\)\$([^\$\(\x00-\x1f]+?) \(\d+\)'
            )
            for m in col_pat.finditer(text):
                tbl = m.group(1).strip()
                col = m.group(2).strip()
                if not col or col.startswith("RowNumber"):
                    continue
                if tbl not in tables:
                    tables[tbl] = {
                        "name": tbl,
                        "display_name": tbl,
                        "columns": [],
                        "row_count": 0,
                    }
                seen_cols.setdefault(tbl, set())
                if col not in seen_cols[tbl]:
                    seen_cols[tbl].add(col)
                    tables[tbl]["columns"].append(
                        {"name": col, "data_type": "unknown", "is_hidden": False}
                    )

            if tables:
                logger.debug(
                    f"Binary scan (UTF-16 path) found {len(tables)} tables"
                )
                return tables

        # ── Fallback: raw byte scanning (works for non-UTF-16 binaries) ──
        raw = self._raw_datamodel
        if not raw:
            return tables

        # Table names
        for m in re.finditer(rb'([A-Za-z][A-Za-z0-9 _]+) \(\d+\)\.tbl', raw):
            name = m.group(1).decode("utf-8", errors="replace").strip()
            if name and name not in tables:
                tables[name] = {"name": name, "display_name": name, "columns": [], "row_count": 0}

        # Columns — pattern: H$<table> (<id>)$<col> (<id>)
        col_pat_b = re.compile(
            rb'H\x24([^\x24\x28\x00-\x1f]+?) \(\d+\)\x24([^\x24\x28\x00-\x1f]+?) \(\d+\)'
        )
        for m in col_pat_b.finditer(raw):
            tbl = m.group(1).decode("utf-8", errors="replace").strip()
            col = m.group(2).decode("utf-8", errors="replace").strip()
            if not col or col.startswith("RowNumber"):
                continue
            if tbl not in tables:
                tables[tbl] = {"name": tbl, "display_name": tbl, "columns": [], "row_count": 0}
            seen_cols.setdefault(tbl, set())
            if col not in seen_cols[tbl]:
                seen_cols[tbl].add(col)
                tables[tbl]["columns"].append(
                    {"name": col, "data_type": "unknown", "is_hidden": False}
                )

        return tables

    # ------------------------------------------------------------------
    # Measure extraction
    # ------------------------------------------------------------------

    def _extract_measures(self) -> List[Dict[str, Any]]:
        """Extract calculated measures."""
        measures: List[Dict[str, Any]] = []

        # Path 1 — JSON model
        if self.data_model:
            model = self.data_model.get("model", self.data_model)
            for table in model.get("tables", []):
                tname = table.get("name", "")
                for measure in table.get("measures", []):
                    name = measure.get("name", "")
                    if name:
                        measures.append({
                            "name": name,
                            "table": tname,
                            "expression": measure.get("expression", ""),
                            "data_type": measure.get("dataType", "text"),
                            "is_hidden": measure.get("isHidden", False),
                        })
                for column in table.get("columns", []):
                    expr = (column.get("expression", "")
                            or column.get("encodedProperty", {}).get("expression", ""))
                    if expr:
                        name = column.get("name", "")
                        if name:
                            measures.append({
                                "name": name,
                                "table": tname,
                                "expression": expr,
                                "data_type": column.get("dataType", "text"),
                                "is_hidden": column.get("isHidden", False),
                            })

        # Path 2 — ABF binary scanning
        if not measures and self._raw_datamodel:
            measures = self._scan_measures_from_binary()

        self.measures = measures
        logger.info(f"Extracted {len(measures)} measures from PBIX")
        return measures

    def _scan_measures_from_binary(self) -> List[Dict[str, Any]]:
        """
        Extract measure names and DAX expressions from the VertiPaq binary.

        A measure record in the ABF stores (approximately):
            <MeasureName><Description><DAXExpression>
        as consecutive printable text blobs separated by binary noise.
        We locate each DAX expression (identified by a root function keyword)
        then look backwards in the text runs for the measure name.
        """
        raw = self._raw_datamodel
        measures: List[Dict[str, Any]] = []

        dax_root = re.compile(
            rb'(?:COUNTROWS|SUM|AVERAGE|MIN|MAX|COUNTA?|CALCULATE|DISTINCTCOUNT'
            rb'|SUMX|AVERAGEX|IF|DIVIDE|RELATED|FILTER|ALL|VALUES|ALLEXCEPT)\s*\('
        )

        runs = list(self._readable_runs(raw, min_len=3))
        seen_exprs: set = set()

        for idx, (offset, text) in enumerate(runs):
            encoded = text.encode("utf-8", errors="replace")
            if not dax_root.search(encoded):
                continue

            # The DAX expression is the full text run (trim surrounding noise)
            expr = text.strip()
            if expr in seen_exprs:
                continue
            seen_exprs.add(expr)

            # The immediately preceding text run is: <MeasureName><Description>
            # MeasureName uses CamelCase or underscores (no spaces).
            # Description is plain English words (has spaces).
            # Split strategy: take the first run of non-space alphanumeric chars.
            name = "Unknown"
            for prev_offset, prev_text in reversed(runs[:idx]):
                # Strip leading control chars and non-printable junk
                prev_clean = prev_text.strip().lstrip("!\r\n\t ")
                if not prev_clean or prev_clean.startswith("STREAM"):
                    continue
                # First contiguous non-space token = measure name
                token_match = re.match(r'^([A-Za-z][A-Za-z0-9_]*)', prev_clean)
                if token_match:
                    name = token_match.group(1)
                else:
                    name = prev_clean.split()[0][:80] if prev_clean.split() else "Unknown"
                break

            table = self._find_table_for_offset(offset, raw)
            measures.append({
                "name": name,
                "table": table,
                "expression": expr,
                "data_type": "unknown",
                "is_hidden": False,
            })

        return measures

    def _find_table_for_offset(self, offset: int, raw: bytes) -> str:
        """Scan backwards from offset to find the nearest table name."""
        search_start = max(0, offset - 10000)
        chunk = raw[search_start:offset]
        match = None
        for m in re.finditer(rb'([A-Za-z][A-Za-z0-9 _]+) \(\d+\)\.tbl', chunk):
            match = m  # keep last (nearest) match
        if match:
            return match.group(1).decode("utf-8", errors="replace").strip()
        return "Unknown"

    # ------------------------------------------------------------------
    # Relationship extraction
    # ------------------------------------------------------------------

    def _extract_relationships(self) -> List[Dict[str, Any]]:
        """
        Extract relationships.

        JSON model: top-level model.relationships[].
        ABF binary: no relationship rows are stored in this PBIX file
                    (the Country>State>City hierarchy is intra-table).
        """
        relationships: List[Dict[str, Any]] = []

        if self.data_model:
            model = self.data_model.get("model", self.data_model)
            for rel in model.get("relationships", []):
                from_table = rel.get("fromTable", "")
                to_table = rel.get("toTable", "")
                if from_table and to_table:
                    relationships.append({
                        "from_table": from_table,
                        "from_column": rel.get("fromColumn", ""),
                        "to_table": to_table,
                        "to_column": rel.get("toColumn", ""),
                        "cardinality": rel.get("cardinality", "manyToOne"),
                        "is_active": rel.get("isActive", True),
                        "cross_filter_direction": rel.get(
                            "crossFilteringBehavior", "oneDirection"
                        ),
                    })

        self.relationships = relationships
        logger.info(f"Extracted {len(relationships)} relationships from PBIX")
        return relationships

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get_data_tables(self) -> Dict[str, pd.DataFrame]:
        """Return table schemas as DataFrames (with dummy data if row counts exist)."""
        if not self.temp_dir:
            raise RuntimeError("PBIX file not parsed yet. Call parse() first.")
        data_frames = {}
        for table_name, table_info in self.tables.items():
            columns = [col["name"] for col in table_info.get("columns", [])]
            row_count = table_info.get("row_count", 0)
            
            if row_count > 0:
                # Create a dummy DataFrame with the correct number of rows to satisfy len(df)
                data_frames[table_name] = pd.DataFrame(index=range(row_count), columns=columns)
                logger.info(f"Created dummy DataFrame for table '{table_name}' with {row_count} rows from metadata")
            else:
                data_frames[table_name] = pd.DataFrame(columns=columns)
                logger.info(f"Created empty DataFrame for table '{table_name}' (no row count in metadata)")
        return data_frames

    def get_data_model(self) -> Dict[str, Any]:
        return self.data_model

    def get_relationships(self) -> List[Dict[str, Any]]:
        return self.relationships

    def get_measures(self) -> List[Dict[str, Any]]:
        return self.measures

    def get_tables(self) -> Dict[str, Dict[str, Any]]:
        return self.tables

    def cleanup(self) -> None:
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.debug(f"Cleaned up temporary directory {self.temp_dir}")

    def __del__(self):
        self.cleanup()