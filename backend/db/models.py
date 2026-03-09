"""
Tables
------
migration_project    One record per client migration engagement
validation_run       One batch execution (manual or CI/CD triggered)
report_pair          One Tableau report matched to its Power BI counterpart
visual_result        Layer 1 — pixel diff score + GPT-4o analysis
semantic_result      Layer 2 — calc field audit summary per report
calc_field           One Tableau calculated field vs its DAX equivalent
data_result          Layer 3 — KPI / aggregation comparison
kpi_comparison       One KPI value diff (child of data_result)

"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from backend.config import DB_URL

logger = logging.getLogger(__name__)


# ── Status / Risk constants ────────────────────────────────────────────────────

class Status:
    PENDING = "pending"
    RUNNING = "running"
    PASS    = "pass"
    FAIL    = "fail"
    REVIEW  = "review"
    ERROR   = "error"


class Risk:
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


# ── Non-column relationship slots — excluded from INSERT ───────────────────────
# Add any future relationship-only slots here to keep _insert() robust.
_NON_COLUMN_SLOTS: frozenset[str] = frozenset({"visual_result"})


# ── DDL ───────────────────────────────────────────────────────────────────────

_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS migration_project (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT NOT NULL,
    client_name          TEXT,
    description          TEXT,
    tableau_server_url   TEXT,
    tableau_site         TEXT,
    powerbi_workspace_id TEXT,
    created_at           TEXT DEFAULT (datetime('now')),
    updated_at           TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS validation_run (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES migration_project(id),
    triggered_by  TEXT DEFAULT 'manual',
    status        TEXT DEFAULT 'pending',
    total_reports INTEGER DEFAULT 0,
    passed        INTEGER DEFAULT 0,
    failed        INTEGER DEFAULT 0,
    needs_review  INTEGER DEFAULT 0,
    errored       INTEGER DEFAULT 0,
    started_at    TEXT DEFAULT (datetime('now')),
    completed_at  TEXT
);

CREATE TABLE IF NOT EXISTS report_pair (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id          INTEGER NOT NULL REFERENCES migration_project(id),
    run_id              INTEGER REFERENCES validation_run(id),
    report_name         TEXT NOT NULL,
    tableau_workbook    TEXT,
    tableau_view_name   TEXT,
    tableau_view_id     TEXT,
    powerbi_report_name TEXT,
    powerbi_page_name   TEXT,
    powerbi_report_id   TEXT,
    tableau_screenshot  TEXT,
    powerbi_screenshot  TEXT,
    overall_status      TEXT DEFAULT 'pending',
    overall_risk        TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS visual_result (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    report_pair_id       INTEGER NOT NULL REFERENCES report_pair(id),
    pixel_similarity_pct REAL,
    pixel_diff_count     INTEGER,
    total_pixels         INTEGER,
    hash_distance        INTEGER,
    diff_image_path      TEXT,
    compared_width       INTEGER,
    compared_height      INTEGER,
    gpt4o_called         INTEGER DEFAULT 0,
    chart_type_match     INTEGER,
    color_scheme_match   INTEGER,
    layout_match         INTEGER,
    axis_labels_match    INTEGER,
    legend_match         INTEGER,
    title_match          INTEGER,
    data_labels_match    INTEGER,
    ai_summary           TEXT,
    ai_key_differences   TEXT,
    ai_recommendation    TEXT,
    ai_raw_response      TEXT,
    status               TEXT DEFAULT 'pending',
    pass_threshold_pct   REAL DEFAULT 95.0,
    gpt4o_risk_level     TEXT,
    created_at           TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS semantic_result (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    report_pair_id       INTEGER NOT NULL REFERENCES report_pair(id),
    total_fields         INTEGER DEFAULT 0,
    matched_fields       INTEGER DEFAULT 0,
    flagged_fields       INTEGER DEFAULT 0,
    manual_review_fields INTEGER DEFAULT 0,
    status               TEXT DEFAULT 'pending',
    created_at           TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS calc_field (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    semantic_result_id   INTEGER NOT NULL REFERENCES semantic_result(id),
    field_name           TEXT NOT NULL,
    tableau_formula      TEXT,
    dax_from_pbix        TEXT,
    claude_dax_suggested TEXT,
    is_equivalent        INTEGER,
    risk_level           TEXT,
    differences          TEXT,
    edge_cases           TEXT,
    ai_explanation       TEXT,
    status               TEXT DEFAULT 'pending',
    created_at           TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS data_result (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    report_pair_id     INTEGER NOT NULL REFERENCES report_pair(id),
    tableau_row_count  INTEGER,
    powerbi_row_count  INTEGER,
    row_count_match    INTEGER,
    total_kpis_checked INTEGER DEFAULT 0,
    kpis_matched       INTEGER DEFAULT 0,
    kpis_mismatched    INTEGER DEFAULT 0,
    status             TEXT DEFAULT 'pending',
    created_at         TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS kpi_comparison (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    data_result_id   INTEGER NOT NULL REFERENCES data_result(id),
    metric_name      TEXT NOT NULL,
    aggregation_type TEXT,
    tableau_value    REAL,
    powerbi_value    REAL,
    absolute_diff    REAL,
    percentage_diff  REAL,
    is_match         INTEGER,
    tolerance_pct    REAL DEFAULT 0.01,
    created_at       TEXT DEFAULT (datetime('now'))
);
"""


# ── Lightweight model classes ──────────────────────────────────────────────────
# Field names mirror the database column names exactly so _insert() can build
# INSERT statements generically from __slots__.

def _now() -> str:
    """UTC timestamp as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


class MigrationProject:
    __slots__ = [
        "id", "name", "client_name", "description",
        "tableau_server_url", "tableau_site", "powerbi_workspace_id",
        "created_at", "updated_at",
    ]

    def __init__(
        self,
        name: str,
        client_name: Optional[str]              = None,
        description: Optional[str]              = None,
        tableau_server_url: Optional[str]       = None,
        tableau_site: Optional[str]             = None,
        powerbi_workspace_id: Optional[str]     = None,
    ):
        self.id                   = None
        self.name                 = name
        self.client_name          = client_name
        self.description          = description
        self.tableau_server_url   = tableau_server_url
        self.tableau_site         = tableau_site
        self.powerbi_workspace_id = powerbi_workspace_id
        self.created_at           = _now()
        self.updated_at           = _now()


class ValidationRun:
    __slots__ = [
        "id", "project_id", "triggered_by", "status", "total_reports",
        "passed", "failed", "needs_review", "errored", "started_at", "completed_at",
    ]

    def __init__(self, project_id: int, triggered_by: str = "manual"):
        self.id            = None
        self.project_id    = project_id
        self.triggered_by  = triggered_by
        self.status        = Status.PENDING
        self.total_reports = 0
        self.passed        = 0
        self.failed        = 0
        self.needs_review  = 0
        self.errored       = 0
        self.started_at    = _now()
        self.completed_at  = None


class ReportPair:
    __slots__ = [
        "id", "project_id", "run_id", "report_name",
        "tableau_workbook", "tableau_view_name", "tableau_view_id",
        "powerbi_report_name", "powerbi_page_name", "powerbi_report_id",
        "tableau_screenshot", "powerbi_screenshot",
        "overall_status", "overall_risk", "created_at", "updated_at",
        # Relationship — NOT a database column; excluded from INSERT.
        "visual_result",
    ]

    def __init__(
        self,
        project_id: int,
        report_name: str,
        run_id: Optional[int]                   = None,
        tableau_workbook: Optional[str]         = None,
        tableau_view_name: Optional[str]        = None,
        tableau_view_id: Optional[str]          = None,
        powerbi_report_name: Optional[str]      = None,
        powerbi_page_name: Optional[str]        = None,
        powerbi_report_id: Optional[str]        = None,
        tableau_screenshot: Optional[str]       = None,
        powerbi_screenshot: Optional[str]       = None,
        overall_status: str                     = Status.PENDING,
        overall_risk: Optional[str]             = None,
        **_,  # absorb extra keyword args for forward-compatibility
    ):
        self.id                  = None
        self.project_id          = project_id
        self.run_id              = run_id
        self.report_name         = report_name
        self.tableau_workbook    = tableau_workbook
        self.tableau_view_name   = tableau_view_name
        self.tableau_view_id     = tableau_view_id
        self.powerbi_report_name = powerbi_report_name
        self.powerbi_page_name   = powerbi_page_name
        self.powerbi_report_id   = powerbi_report_id
        self.tableau_screenshot  = tableau_screenshot
        self.powerbi_screenshot  = powerbi_screenshot
        self.overall_status      = overall_status
        self.overall_risk        = overall_risk
        self.created_at          = _now()
        self.updated_at          = _now()
        self.visual_result       = None   # populated by session.refresh()


class VisualResult:
    __slots__ = [
        "id", "report_pair_id", "pixel_similarity_pct", "pixel_diff_count",
        "total_pixels", "hash_distance", "diff_image_path",
        "compared_width", "compared_height", "gpt4o_called",
        "chart_type_match", "color_scheme_match", "layout_match",
        "axis_labels_match", "legend_match", "title_match", "data_labels_match",
        "ai_summary", "ai_key_differences", "ai_recommendation", "ai_raw_response",
        "status", "pass_threshold_pct", "gpt4o_risk_level", "created_at",
    ]

    def __init__(
        self,
        report_pair_id: int,
        status: str                              = Status.PENDING,
        pixel_similarity_pct: Optional[float]   = None,
        pixel_diff_count: Optional[int]         = None,
        total_pixels: Optional[int]             = None,
        hash_distance: Optional[int]            = None,
        diff_image_path: Optional[str]          = None,
        compared_width: Optional[int]           = None,
        compared_height: Optional[int]          = None,
        gpt4o_called: bool                      = False,
        chart_type_match: Optional[bool]        = None,
        color_scheme_match: Optional[bool]      = None,
        layout_match: Optional[bool]            = None,
        axis_labels_match: Optional[bool]       = None,
        legend_match: Optional[bool]            = None,
        title_match: Optional[bool]             = None,
        data_labels_match: Optional[bool]       = None,
        ai_summary: Optional[str]               = None,
        ai_key_differences: Optional[str]       = None,
        ai_recommendation: Optional[str]        = None,
        ai_raw_response: Optional[str]          = None,
        pass_threshold_pct: float               = 95.0,
        gpt4o_risk_level: Optional[str]         = None,
        id: Optional[int]                       = None,
        **_,
    ):
        self.id                   = id
        self.report_pair_id       = report_pair_id
        self.pixel_similarity_pct = pixel_similarity_pct
        self.pixel_diff_count     = pixel_diff_count
        self.total_pixels         = total_pixels
        self.hash_distance        = hash_distance
        self.diff_image_path      = diff_image_path
        self.compared_width       = compared_width
        self.compared_height      = compared_height
        self.gpt4o_called         = gpt4o_called
        self.chart_type_match     = chart_type_match
        self.color_scheme_match   = color_scheme_match
        self.layout_match         = layout_match
        self.axis_labels_match    = axis_labels_match
        self.legend_match         = legend_match
        self.title_match          = title_match
        self.data_labels_match    = data_labels_match
        self.ai_summary           = ai_summary
        self.ai_key_differences   = ai_key_differences
        self.ai_recommendation    = ai_recommendation
        self.ai_raw_response      = ai_raw_response
        self.status               = status
        self.pass_threshold_pct   = pass_threshold_pct
        self.gpt4o_risk_level     = gpt4o_risk_level
        self.created_at           = _now()


class SemanticResult:
    __slots__ = [
        "id", "report_pair_id", "total_fields", "matched_fields",
        "flagged_fields", "manual_review_fields", "status", "created_at",
    ]

    def __init__(
        self,
        report_pair_id: int,
        total_fields: int      = 0,
        matched_fields: int    = 0,
        flagged_fields: int    = 0,
        manual_review_fields: int = 0,
        status: str            = Status.PENDING,
    ):
        self.id                  = None
        self.report_pair_id      = report_pair_id
        self.total_fields        = total_fields
        self.matched_fields      = matched_fields
        self.flagged_fields      = flagged_fields
        self.manual_review_fields= manual_review_fields
        self.status              = status
        self.created_at          = _now()


class CalcField:
    __slots__ = [
        "id", "semantic_result_id", "field_name", "tableau_formula",
        "dax_from_pbix", "claude_dax_suggested", "is_equivalent", "risk_level",
        "differences", "edge_cases", "ai_explanation", "status", "created_at",
    ]

    def __init__(
        self,
        semantic_result_id: int,
        field_name: str,
        tableau_formula: Optional[str]      = None,
        dax_from_pbix: Optional[str]        = None,
        claude_dax_suggested: Optional[str] = None,
        is_equivalent: Optional[bool]       = None,
        risk_level: Optional[str]           = None,
        differences: Optional[str]          = None,
        edge_cases: Optional[str]           = None,
        ai_explanation: Optional[str]       = None,
        status: str                         = Status.PENDING,
    ):
        self.id                   = None
        self.semantic_result_id   = semantic_result_id
        self.field_name           = field_name
        self.tableau_formula      = tableau_formula
        self.dax_from_pbix        = dax_from_pbix
        self.claude_dax_suggested = claude_dax_suggested
        self.is_equivalent        = is_equivalent
        self.risk_level           = risk_level
        self.differences          = differences
        self.edge_cases           = edge_cases
        self.ai_explanation       = ai_explanation
        self.status               = status
        self.created_at           = _now()


class DataResult:
    __slots__ = [
        "id", "report_pair_id", "tableau_row_count", "powerbi_row_count",
        "row_count_match", "total_kpis_checked", "kpis_matched",
        "kpis_mismatched", "status", "created_at",
    ]

    def __init__(
        self,
        report_pair_id: int,
        tableau_row_count: Optional[int] = None,
        powerbi_row_count: Optional[int] = None,
        row_count_match: Optional[bool]  = None,
        total_kpis_checked: int          = 0,
        kpis_matched: int                = 0,
        kpis_mismatched: int             = 0,
        status: str                      = Status.PENDING,
    ):
        self.id                = None
        self.report_pair_id    = report_pair_id
        self.tableau_row_count = tableau_row_count
        self.powerbi_row_count = powerbi_row_count
        self.row_count_match   = row_count_match
        self.total_kpis_checked= total_kpis_checked
        self.kpis_matched      = kpis_matched
        self.kpis_mismatched   = kpis_mismatched
        self.status            = status
        self.created_at        = _now()


class KpiComparison:
    __slots__ = [
        "id", "data_result_id", "metric_name", "aggregation_type",
        "tableau_value", "powerbi_value", "absolute_diff",
        "percentage_diff", "is_match", "tolerance_pct", "created_at",
    ]

    def __init__(
        self,
        data_result_id: int,
        metric_name: str,
        aggregation_type: Optional[str] = None,
        tableau_value: Optional[float]  = None,
        powerbi_value: Optional[float]  = None,
        absolute_diff: Optional[float]  = None,
        percentage_diff: Optional[float]= None,
        is_match: Optional[bool]        = None,
        tolerance_pct: float            = 0.01,
    ):
        self.id              = None
        self.data_result_id  = data_result_id
        self.metric_name     = metric_name
        self.aggregation_type= aggregation_type
        self.tableau_value   = tableau_value
        self.powerbi_value   = powerbi_value
        self.absolute_diff   = absolute_diff
        self.percentage_diff = percentage_diff
        self.is_match        = is_match
        self.tolerance_pct   = tolerance_pct
        self.created_at      = _now()


# ── Table name registry ────────────────────────────────────────────────────────

_TABLE_MAP: dict[str, str] = {
    "MigrationProject": "migration_project",
    "ValidationRun":    "validation_run",
    "ReportPair":       "report_pair",
    "VisualResult":     "visual_result",
    "SemanticResult":   "semantic_result",
    "CalcField":        "calc_field",
    "DataResult":       "data_result",
    "KpiComparison":    "kpi_comparison",
}


def _table_for(obj) -> str:
    """Return the database table name for a model instance."""
    class_name = type(obj).__name__
    try:
        return _TABLE_MAP[class_name]
    except KeyError:
        raise TypeError(
            f"Unknown model class {class_name!r}. "
            f"Known classes: {list(_TABLE_MAP.keys())}"
        )


# ── Session ────────────────────────────────────────────────────────────────────

class Session:
    """
    Lightweight sqlite3 session that mirrors enough of the SQLAlchemy Session
    API that pipeline code does not need to change when switching to SQLAlchemy.

    Supported: add(), flush(), commit(), refresh(), query().
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn    = conn
        self._pending: list = []

    # ── Write methods ─────────────────────────────────────────────────────────

    def add(self, obj) -> None:
        """Stage an object for INSERT on the next commit/flush."""
        self._pending.append(obj)

    def flush(self) -> None:
        """Write all pending objects to the DB and populate their .id attributes."""
        for obj in self._pending:
            self._insert(obj)
        self._pending.clear()

    def commit(self) -> None:
        """Flush pending objects then commit the transaction."""
        self.flush()
        self._conn.commit()

    def refresh(self, obj) -> None:
        """
        Reload an object's column attributes from the DB.
        For ReportPair, also loads the associated VisualResult into obj.visual_result.
        """
        table = _table_for(obj)
        row   = self._conn.execute(
            f"SELECT * FROM {table} WHERE id = ?", (obj.id,)
        ).fetchone()

        if row:
            for k, v in dict(row).items():
                if hasattr(obj, k):
                    setattr(obj, k, v)

        # Eagerly load the VisualResult relationship for ReportPair.
        if table == "report_pair":
            vr_row = self._conn.execute(
                "SELECT * FROM visual_result WHERE report_pair_id = ? "
                "ORDER BY id DESC LIMIT 1",
                (obj.id,),
            ).fetchone()

            if vr_row:
                d  = dict(vr_row)
                vr = VisualResult(report_pair_id=obj.id)
                for k, v in d.items():
                    if k in VisualResult.__slots__:
                        setattr(vr, k, v)
                obj.visual_result = vr
            else:
                obj.visual_result = None

    # ── Query helpers ─────────────────────────────────────────────────────────

    def query(self, *models):
        """Return a _Query builder for the given model class(es)."""
        return _Query(self._conn, models)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _insert(self, obj) -> None:
        """
        Build and execute an INSERT statement from a model's __slots__.

        Non-column slots (e.g. relationship fields like visual_result) are
        excluded via _NON_COLUMN_SLOTS, preventing accidental SQL errors when
        new relationship slots are added to a model.
        """
        table = _table_for(obj)
        data  = {
            k: getattr(obj, k, None)
            for k in obj.__slots__
            if k != "id"
            and not k.startswith("_")
            and k not in _NON_COLUMN_SLOTS
        }
        cols = ", ".join(data.keys())
        phs  = ", ".join("?" * len(data))
        cur  = self._conn.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({phs})",
            list(data.values()),
        )
        obj.id = cur.lastrowid
        logger.debug("Inserted %s id=%d into %s", type(obj).__name__, obj.id, table)

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()


class _Query:
    """
    Minimal query builder for test and dashboard assertions.
    Supports the two query patterns used by the test suite and FastAPI backend.
    """

    def __init__(self, conn: sqlite3.Connection, models: tuple):
        self._conn    = conn
        self._models  = models
        self._filters : list = []
        self._groups  : list = []

    def join(self, model, condition=None):
        # Joins are implicit in the two-model all() path; this is a no-op stub
        # so the call chain `session.query(A, B).join(B, ...).filter(...).all()` works.
        return self

    def filter(self, *conditions):
        self._filters.extend(conditions)
        return self

    def group_by(self, *cols):
        self._groups.extend(cols)
        return self

    def all(self) -> list:
        """
        Execute the query and return results.

        Two supported patterns:
          1. query(ReportPair, VisualResult) → list of (ReportPair, VisualResult) tuples
          2. query(ReportPair).group_by(...) → list of (status, count) tuples
        """
        if len(self._models) == 2:
            return self._fetch_pair_results()

        if self._groups:
            return self._fetch_status_counts()

        return []

    def _fetch_pair_results(self) -> list[tuple]:
        """JOIN report_pair with visual_result and return typed object pairs."""
        # Build optional WHERE clause from project_id filters.
        where_clause = ""
        params: list = []
        for condition in self._filters:
            # Conditions are passed as pseudo-expressions; we parse project_id filters.
            if hasattr(condition, "_project_id_filter"):
                where_clause = "WHERE rp.project_id = ?"
                params.append(condition._project_id_filter)
                break

        rows = self._conn.execute(f"""
            SELECT
                rp.id, rp.project_id, rp.run_id, rp.report_name,
                rp.tableau_workbook, rp.tableau_view_name, rp.tableau_view_id,
                rp.powerbi_report_name, rp.powerbi_page_name, rp.powerbi_report_id,
                rp.tableau_screenshot, rp.powerbi_screenshot,
                rp.overall_status, rp.overall_risk, rp.created_at, rp.updated_at,
                vr.id              AS vr_id,
                vr.pixel_similarity_pct,
                vr.status          AS vr_status,
                vr.gpt4o_called,
                vr.ai_summary,
                vr.ai_key_differences,
                vr.diff_image_path,
                vr.hash_distance,
                vr.pixel_diff_count,
                vr.total_pixels,
                vr.compared_width,
                vr.compared_height,
                vr.pass_threshold_pct,
                vr.gpt4o_risk_level
            FROM report_pair rp
            JOIN visual_result vr ON rp.id = vr.report_pair_id
            {where_clause}
        """, params).fetchall()

        results = []
        for r in rows:
            d    = dict(r)
            pair = ReportPair(
                project_id          = d["project_id"],
                report_name         = d["report_name"],
                run_id              = d.get("run_id"),
                tableau_workbook    = d.get("tableau_workbook"),
                tableau_view_name   = d.get("tableau_view_name"),
                powerbi_report_name = d.get("powerbi_report_name"),
                powerbi_page_name   = d.get("powerbi_page_name"),
                tableau_screenshot  = d.get("tableau_screenshot"),
                powerbi_screenshot  = d.get("powerbi_screenshot"),
                overall_status      = d.get("overall_status", Status.PENDING),
                overall_risk        = d.get("overall_risk"),
            )
            pair.id = d["id"]

            vr = VisualResult(
                id                   = d.get("vr_id"),
                report_pair_id       = d["id"],
                pixel_similarity_pct = d.get("pixel_similarity_pct"),
                status               = d.get("vr_status", Status.PENDING),
                gpt4o_called         = bool(d.get("gpt4o_called")),
                ai_summary           = d.get("ai_summary"),
                ai_key_differences   = d.get("ai_key_differences"),
                diff_image_path      = d.get("diff_image_path"),
                hash_distance        = d.get("hash_distance"),
                pixel_diff_count     = d.get("pixel_diff_count"),
                total_pixels         = d.get("total_pixels"),
                compared_width       = d.get("compared_width"),
                compared_height      = d.get("compared_height"),
                pass_threshold_pct   = d.get("pass_threshold_pct", 95.0),
                gpt4o_risk_level     = d.get("gpt4o_risk_level"),
            )
            results.append((pair, vr))

        return results

    def _fetch_status_counts(self) -> list[tuple]:
        """Return overall_status distribution for all report pairs."""
        rows = self._conn.execute(
            "SELECT overall_status, COUNT(id) FROM report_pair GROUP BY overall_status"
        ).fetchall()
        return [(row[0], row[1]) for row in rows]


# ── DB setup helpers ───────────────────────────────────────────────────────────

def get_engine(db_url: str = DB_URL) -> sqlite3.Connection:
    """
    Return a sqlite3 Connection.

    Args:
        db_url: sqlite:///path/to/db.db  OR  a bare filesystem path

    Returns:
        sqlite3.Connection with row_factory set to sqlite3.Row
    """
    path = db_url.replace("sqlite:///", "") if db_url.startswith("sqlite") else db_url
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    logger.debug("Opened database: %s", path)
    return conn


def create_tables(engine: sqlite3.Connection) -> None:
    """Create all tables if they do not already exist."""
    engine.executescript(_DDL)
    engine.commit()
    logger.debug("Database tables created/verified.")


def get_session(engine: sqlite3.Connection) -> Session:
    """Return a Session wrapping the provided sqlite3 Connection."""
    return Session(engine)