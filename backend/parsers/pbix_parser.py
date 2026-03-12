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
        self.datamodel_xpress9: bool = False  # True when DataModel is XPress9-compressed
        self.is_remote_dataset: bool = False  # True when data lives in Power BI Service

    def parse(self) -> None:
        """Extract and parse PBIX file contents."""
        logger.info(f"Parsing PBIX file: {self.pbix_path}")
        self.temp_dir = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(self.pbix_path, "r") as zip_ref:
                zip_ref.extractall(self.temp_dir)
            logger.debug(f"Extracted PBIX to {self.temp_dir}")

            self._detect_remote_dataset()
            self._parse_data_model()
            self._extract_relationships()
            self._extract_measures()
            self._extract_tables()
        except Exception as e:
            logger.error(f"Error parsing PBIX file: {e}")
            raise

    def _detect_remote_dataset(self) -> None:
        """
        Detect whether this PBIX report connects to a remote Power BI Service
        dataset rather than embedding its own data.

        When `Connections` contains a `RemoteArtifacts` entry with a
        `DatasetId`, the DataModel binary holds only metadata/schema — the
        actual row data lives in the cloud and cannot be read locally.
        """
        connections_path = os.path.join(self.temp_dir, "Connections")
        if not os.path.exists(connections_path):
            return
        try:
            with open(connections_path, "rb") as f:
                raw = f.read()
            # Connections is UTF-8 JSON (no BOM in most versions)
            for enc in ("utf-8", "utf-16-le", "utf-8-sig"):
                try:
                    text = raw.decode(enc)
                    break
                except Exception:
                    text = None
            if not text:
                return
            conn = json.loads(text)
            artifacts = conn.get("RemoteArtifacts", [])
            if artifacts and any(a.get("DatasetId") for a in artifacts):
                self.is_remote_dataset = True
                logger.info(
                    "PBIX uses a remote Power BI Service dataset — "
                    "row data is not available locally."
                )
        except Exception as e:
            logger.debug(f"Could not read Connections: {e}")

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
                # Detect XPress9 compression: UTF-16 LE content without BOM.
                # "This backup was created using XPress9 compression." is the header.
                _xpress9_sig = b"T\x00h\x00i\x00s\x00 \x00b\x00a\x00c\x00k\x00u\x00p\x00"
                if raw[:len(_xpress9_sig)] == _xpress9_sig:
                    self.datamodel_xpress9 = True
                    logger.warning(
                        "DataModel is XPress9-compressed — table schema unavailable from DataModel. "
                        "Will fall back to Report/Layout and PBIT if provided."
                    )
                    return

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

        # Path 3 — Report/Layout JSON (fallback when DataModel is compressed
        # or in an unsupported format, e.g. XPress9-compressed PBIX files).
        # Also used to fill in missing columns for tables found in path 2.
        if self.temp_dir:
            layout_tables = self._extract_tables_from_layout()
            if layout_tables:
                if not tables:
                    tables = layout_tables
                    logger.info(
                        f"Extracted {len(tables)} tables from Report/Layout"
                    )
                else:
                    # Merge: add columns that the binary scan missed
                    for tname, linfo in layout_tables.items():
                        if tname not in tables:
                            tables[tname] = linfo
                        elif not tables[tname]["columns"] and linfo["columns"]:
                            tables[tname]["columns"] = linfo["columns"]
                            logger.debug(
                                f"Filled columns for '{tname}' from layout"
                            )

        self.tables = tables
        logger.info(f"Extracted {len(tables)} tables from PBIX")
        return tables

    def _extract_tables_from_layout(self) -> Dict[str, Dict[str, Any]]:
        """
        Extract table and column names from the Report/Layout JSON.

        The layout file is stored as UTF-16-LE (often without BOM) and
        contains visual configurations. Each visual's prototypeQuery carries
        a 'From' list (entity aliases → table names) and a 'Select' list
        (column Property references).  This method collects all unique
        Entity → Property pairs across every visual in the report.
        """
        layout_path = os.path.join(self.temp_dir, "Report", "Layout")
        if not os.path.exists(layout_path):
            return {}

        try:
            with open(layout_path, "rb") as f:
                raw = f.read()
            # Layout is UTF-16-LE (may lack BOM)
            text = raw.decode("utf-16-le", errors="ignore")
            layout_json = json.loads(text)
        except Exception as e:
            logger.warning(f"Could not parse Report/Layout: {e}")
            return {}

        tables: Dict[str, set] = {}

        def _walk(obj: Any) -> None:
            """Recursively walk any JSON value, parsing nested JSON strings."""
            if isinstance(obj, dict):
                # prototypeQuery carries From + Select
                if "From" in obj and "Select" in obj:
                    alias_map: Dict[str, str] = {}
                    for item in obj.get("From", []):
                        if isinstance(item, dict):
                            alias = item.get("Name", "")
                            entity = item.get("Entity", "")
                            if alias and entity:
                                alias_map[alias] = entity
                                if entity not in tables:
                                    tables[entity] = set()

                    def _extract_col(node: Any) -> None:
                        """
                        Recursively extract Column.Property refs.
                        Skips Measure nodes — measures are not table columns.
                        Handles Aggregation nodes by drilling into their inner
                        Column (e.g. CountNonNull wrapping a Column ref).
                        """
                        if not isinstance(node, dict):
                            if isinstance(node, list):
                                for item in node:
                                    _extract_col(item)
                            return
                        for key, val in node.items():
                            if key == "Measure":
                                # Measures are NOT table columns — skip entirely
                                continue
                            elif key == "Column" and isinstance(val, dict):
                                # Direct column reference: extract its Property
                                prop = val.get("Property", "")
                                src = (
                                    val.get("Expression", {})
                                    .get("SourceRef", {})
                                    .get("Source", "")
                                )
                                entity = alias_map.get(src)
                                if entity and prop:
                                    tables[entity].add(prop)
                                # Still recurse in case of nested structures
                                _extract_col(val)
                            elif isinstance(val, (dict, list)):
                                _extract_col(val)

                    for sel in obj.get("Select", []):
                        _extract_col(sel)

                for v in obj.values():
                    _walk(v)

            elif isinstance(obj, list):
                for item in obj:
                    _walk(item)

            elif isinstance(obj, str):
                # Nested JSON strings are common in Layout config/query fields
                stripped = obj.strip()
                if stripped.startswith("{") or stripped.startswith("["):
                    try:
                        _walk(json.loads(stripped))
                    except Exception:
                        pass

        _walk(layout_json)

        result: Dict[str, Dict[str, Any]] = {}
        for entity, cols in tables.items():
            result[entity] = {
                "name": entity,
                "display_name": entity,
                "row_count": 0,
                "columns": [
                    {"name": c, "data_type": "unknown", "is_hidden": False}
                    for c in sorted(cols)
                ],
            }
        return result

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

            # Table names: <Name> (<id>).tbl  (space before paren is optional)
            for m in re.finditer(
                r'([A-Za-z0-9][A-Za-z0-9 _$\-\.]*?)\s*\(\d+\)\.tbl', text
            ):
                name = m.group(1).strip()
                if name and name not in tables:
                    tables[name] = {
                        "name": name,
                        "display_name": name,
                        "columns": [],
                        "row_count": 0,
                    }

            # Column references: H$<Table> (<id>)$<Column> (<id>)
            # Space before the id-parenthesis is optional in some PBI versions.
            col_pat = re.compile(
                r'H\$([^\$\x00-\x1f]+?)\s*\(\d+\)\$([^\$\x00-\x1f]+?)\s*\(\d+\)'
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

        # Table names (space before paren optional)
        for m in re.finditer(rb'([A-Za-z0-9][A-Za-z0-9 _\-\.]*?)\s*\(\d+\)\.tbl', raw):
            name = m.group(1).decode("utf-8", errors="replace").strip()
            if name and name not in tables:
                tables[name] = {"name": name, "display_name": name, "columns": [], "row_count": 0}

        # Columns — pattern: H$<table> (<id>)$<col> (<id>)  (space optional)
        col_pat_b = re.compile(
            rb'H\x24([^\x24\x00-\x1f]+?)\s*\(\d+\)\x24([^\x24\x00-\x1f]+?)\s*\(\d+\)'
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
        """Return table schemas as DataFrames.

        NOTE: PBIX files store data in VertiPaq (ABF) binary format which
        cannot be decoded to extract actual row values locally.  This method
        returns DataFrames with the correct column schema and row count from
        embedded metadata (all cell values are NaN).  Callers must treat these
        as schema-only; use a PBIT file for column names and this row count
        only for display purposes.
        """
        if not self.temp_dir:
            raise RuntimeError("PBIX file not parsed yet. Call parse() first.")
        data_frames = {}
        for table_name, table_info in self.tables.items():
            columns = [col["name"] for col in table_info.get("columns", [])]
            row_count = table_info.get("row_count", 0)

            if row_count > 0:
                # Shape is correct (rows from metadata) but all values are NaN —
                # VertiPaq-encoded data cannot be read locally.
                data_frames[table_name] = pd.DataFrame(index=range(row_count), columns=columns)
                logger.info(
                    f"PBIX table '{table_name}': {row_count} rows (metadata), "
                    f"{len(columns)} cols — values unavailable (VertiPaq binary)"
                )
            else:
                data_frames[table_name] = pd.DataFrame(columns=columns)
                logger.info(
                    f"PBIX table '{table_name}': row count not in metadata, "
                    f"{len(columns)} cols — schema only"
                )

        logger.info(
            f"PBIX get_data_tables: {len(data_frames)} table(s) — "
            f"row counts from metadata: { {n: len(df) for n, df in data_frames.items()} }"
        )
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