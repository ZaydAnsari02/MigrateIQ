"""
MigrateIQ — SQLAlchemy ORM Models (SQLite)
Schema: 8 tables, 57 columns, 8 relations
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Constants & Enums
# ---------------------------------------------------------------------------

class Status:
    PASS    = "pass"
    FAIL    = "fail"
    PENDING = "pending"
    RUNNING = "running"
    REVIEW  = "review"
    ERROR   = "error"

class Risk:
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# 0. user  (AUTH)
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "user"

    id:            Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    username:      Mapped[str]      = mapped_column(String(100), nullable=False, unique=True)
    password_hash: Mapped[str]      = mapped_column(String(64),  nullable=False)
    created_at:    Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


# ---------------------------------------------------------------------------
# 1. migration_project  (ROOT)
# ---------------------------------------------------------------------------

class MigrationProject(Base):
    __tablename__ = "migration_project"

    id: Mapped[int]                           = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str]                         = mapped_column(String, nullable=False)
    client_name: Mapped[Optional[str]]        = mapped_column(String,  nullable=True)
    description: Mapped[Optional[str]]        = mapped_column(Text,    nullable=True)
    tableau_server_url: Mapped[Optional[str]] = mapped_column(String,  nullable=True)
    tableau_site: Mapped[Optional[str]]       = mapped_column(String,  nullable=True)
    powerbi_workspace_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    owner: Mapped[Optional[str]]              = mapped_column(String,  nullable=True)
    created_at: Mapped[datetime]              = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime]              = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    runs:  Mapped[list["ValidationRun"]]  = relationship("ValidationRun",  back_populates="project", cascade="all, delete-orphan")
    pairs: Mapped[list["ReportPair"]]     = relationship("ReportPair",     back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<MigrationProject id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# 2. validation_run  (BATCH)
# ---------------------------------------------------------------------------

class ValidationRun(Base):
    __tablename__ = "validation_run"

    id: Mapped[int]                          = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int]                  = mapped_column(Integer, ForeignKey("migration_project.id"), nullable=False)
    triggered_by: Mapped[str]               = mapped_column(String,  nullable=False)
    status: Mapped[str]                      = mapped_column(String,  nullable=False)
    total_reports: Mapped[int]               = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int]                      = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int]                      = mapped_column(Integer, nullable=False, default=0)
    errored: Mapped[int]                     = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime]             = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    project: Mapped["MigrationProject"]  = relationship("MigrationProject", back_populates="runs")
    pairs:   Mapped[list["ReportPair"]]  = relationship("ReportPair", back_populates="run")

    def __repr__(self) -> str:
        return f"<ValidationRun id={self.id} status={self.status!r}>"


# ---------------------------------------------------------------------------
# 3. report_pair  (CENTRAL)
# ---------------------------------------------------------------------------

class ReportPair(Base):
    __tablename__ = "report_pair"

    id: Mapped[int]                              = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int]                      = mapped_column(Integer, ForeignKey("migration_project.id"), nullable=False)
    run_id: Mapped[Optional[int]]                = mapped_column(Integer, ForeignKey("validation_run.id"),    nullable=True)
    report_name: Mapped[str]                     = mapped_column(String, nullable=False)

    # Tableau
    tableau_workbook: Mapped[Optional[str]]      = mapped_column(String, nullable=True)
    tableau_view_name: Mapped[Optional[str]]     = mapped_column(String, nullable=True)
    tableau_screenshot: Mapped[Optional[str]]    = mapped_column(String, nullable=True)

    # Power BI
    powerbi_report_name: Mapped[Optional[str]]   = mapped_column(String, nullable=True)
    powerbi_page_name: Mapped[Optional[str]]     = mapped_column(String, nullable=True)
    powerbi_screenshot: Mapped[Optional[str]]    = mapped_column(String, nullable=True)

    # L3 Measure Equivalence (from l3_pipeline)
    l3_result_json: Mapped[Optional[str]]        = mapped_column(Text, nullable=True)

    # Aggregate result
    overall_status: Mapped[str]                  = mapped_column(String, nullable=False)
    created_at: Mapped[datetime]                 = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime]                 = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project:         Mapped["MigrationProject"]       = relationship("MigrationProject", back_populates="pairs")
    run:             Mapped[Optional["ValidationRun"]] = relationship("ValidationRun",    back_populates="pairs")
    
    relationship_result: Mapped[Optional["RelationshipResult"]] = relationship("RelationshipResult", back_populates="report_pair", uselist=False, cascade="all, delete-orphan")
    semantic_result:     Mapped[Optional["SemanticResult"]]     = relationship("SemanticResult",     back_populates="report_pair", uselist=False, cascade="all, delete-orphan")
    data_result:         Mapped[Optional["DataResult"]]         = relationship("DataResult",         back_populates="report_pair", uselist=False, cascade="all, delete-orphan")
    visual_result:       Mapped[Optional["VisualResult"]]       = relationship("VisualResult",       back_populates="report_pair", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ReportPair id={self.id} report_name={self.report_name!r} status={self.overall_status!r}>"


# ---------------------------------------------------------------------------
# 4. relationship_result  (LAYER 1)
# ---------------------------------------------------------------------------

class RelationshipResult(Base):
    __tablename__ = "relationship_result"

    id: Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_pair_id: Mapped[int] = mapped_column(Integer, ForeignKey("report_pair.id"), nullable=False)
    relationships_compared: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str]         = mapped_column(String,  nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    report_pair: Mapped["ReportPair"] = relationship("ReportPair", back_populates="relationship_result")
    details:     Mapped[list["RelationshipDetail"]] = relationship("RelationshipDetail", back_populates="relationship_result", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<RelationshipResult id={self.id} status={self.status!r}>"


class RelationshipDetail(Base):
    __tablename__ = "relationship_detail"

    id: Mapped[int]                      = mapped_column(Integer, primary_key=True, autoincrement=True)
    relationship_result_id: Mapped[int]  = mapped_column(Integer, ForeignKey("relationship_result.id"), nullable=False)
    source_desc: Mapped[str]             = mapped_column(String, nullable=False)  # e.g. "Orders[CustomerID]"
    target_desc: Mapped[str]             = mapped_column(String, nullable=False) 
    type: Mapped[str]                    = mapped_column(String, nullable=False)  # MATCH, MISSING, MISMATCH
    detail: Mapped[Optional[str]]        = mapped_column(Text,   nullable=True)
    created_at: Mapped[datetime]         = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    relationship_result: Mapped["RelationshipResult"] = relationship("RelationshipResult", back_populates="details")


# ---------------------------------------------------------------------------
# 5. visual_result  (RESERVED FOR FUTURE)
# ---------------------------------------------------------------------------

class VisualResult(Base):
    __tablename__ = "visual_result"

    id: Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_pair_id: Mapped[int] = mapped_column(Integer, ForeignKey("report_pair.id"), nullable=False)
    
    # Pixel diff metrics
    pixel_similarity_pct: Mapped[Optional[float]] = mapped_column(Float,   nullable=True)
    pixel_diff_count:     Mapped[Optional[int]]   = mapped_column(Integer, nullable=True)
    total_pixels:         Mapped[Optional[int]]   = mapped_column(Integer, nullable=True)
    hash_distance:        Mapped[Optional[int]]   = mapped_column(Integer, nullable=True)
    diff_image_path:      Mapped[Optional[str]]   = mapped_column(String,  nullable=True)
    compared_width:       Mapped[Optional[int]]   = mapped_column(Integer, nullable=True)
    compared_height:      Mapped[Optional[int]]   = mapped_column(Integer, nullable=True)
    tableau_annotated_path:  Mapped[Optional[str]] = mapped_column(String, nullable=True)
    powerbi_annotated_path:  Mapped[Optional[str]] = mapped_column(String, nullable=True)
    comparison_image_path:   Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # GPT-4o Vision fields
    gpt4o_called:       Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    chart_type_match:   Mapped[Optional[str]]  = mapped_column(String,  nullable=True)
    color_scheme_match: Mapped[Optional[str]]  = mapped_column(String,  nullable=True)
    layout_match:       Mapped[Optional[str]]  = mapped_column(String,  nullable=True)
    axis_labels_match:  Mapped[Optional[str]]  = mapped_column(String,  nullable=True)
    axis_scale_match:   Mapped[Optional[str]]  = mapped_column(String,  nullable=True)
    legend_match:       Mapped[Optional[str]]  = mapped_column(String,  nullable=True)
    title_match:        Mapped[Optional[str]]  = mapped_column(String,  nullable=True)
    data_labels_match:  Mapped[Optional[str]]  = mapped_column(String,  nullable=True)
    text_content_match: Mapped[Optional[str]]  = mapped_column(String,  nullable=True)
    ai_summary:         Mapped[Optional[str]]  = mapped_column(Text,    nullable=True)
    ai_key_differences: Mapped[Optional[str]]  = mapped_column(Text,    nullable=True) # JSON list
    ai_recommendation:  Mapped[Optional[str]]  = mapped_column(Text,    nullable=True)
    ai_raw_response:    Mapped[Optional[str]]  = mapped_column(Text,    nullable=True)
    gpt4o_risk_level:   Mapped[Optional[str]]  = mapped_column(String,  nullable=True)
    
    status:             Mapped[str]            = mapped_column(String,  nullable=False)
    pass_threshold_pct: Mapped[Optional[float]] = mapped_column(Float,  nullable=True)
    visual_parameters:  Mapped[Optional[str]]  = mapped_column(Text,    nullable=True)  # JSON dict of param flags
    created_at:         Mapped[datetime]       = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    report_pair: Mapped["ReportPair"] = relationship("ReportPair", back_populates="visual_result")


# ---------------------------------------------------------------------------
# 6. semantic_result  (LAYER 2)
# ---------------------------------------------------------------------------

class SemanticResult(Base):
    __tablename__ = "semantic_result"

    id: Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_pair_id: Mapped[int] = mapped_column(Integer, ForeignKey("report_pair.id"), nullable=False)
    total_fields:   Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_fields: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    flagged_fields: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status:         Mapped[str] = mapped_column(String,  nullable=False)
    # L2 — Column data content analysis (stored as JSON)
    column_value_status:  Mapped[Optional[str]] = mapped_column(String, nullable=True)
    column_value_details: Mapped[Optional[str]] = mapped_column(Text,   nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    report_pair:  Mapped["ReportPair"]         = relationship("ReportPair",  back_populates="semantic_result")
    calc_fields:  Mapped[list["CalcField"]]    = relationship("CalcField",   back_populates="semantic_result", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<SemanticResult id={self.id} status={self.status!r}>"


class CalcField(Base):
    __tablename__ = "calc_field"

    id: Mapped[int]                        = mapped_column(Integer, primary_key=True, autoincrement=True)
    semantic_result_id: Mapped[int]        = mapped_column(Integer, ForeignKey("semantic_result.id"), nullable=False)
    field_name: Mapped[str]                = mapped_column(String, nullable=False)
    tableau_formula: Mapped[Optional[str]] = mapped_column(Text,   nullable=True)
    dax_from_pbix:   Mapped[Optional[str]] = mapped_column(Text,   nullable=True)
    is_equivalent:   Mapped[Optional[bool]]= mapped_column(Boolean,nullable=True)
    differences:     Mapped[Optional[str]] = mapped_column(Text,   nullable=True)
    ai_explanation:  Mapped[Optional[str]] = mapped_column(Text,   nullable=True)
    status: Mapped[str]                    = mapped_column(String, nullable=False)
    created_at: Mapped[datetime]           = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    semantic_result: Mapped["SemanticResult"] = relationship("SemanticResult", back_populates="calc_fields")


# ---------------------------------------------------------------------------
# 7. data_result  (LAYER 3)
# ---------------------------------------------------------------------------

class DataResult(Base):
    __tablename__ = "data_result"

    id: Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_pair_id: Mapped[int] = mapped_column(Integer, ForeignKey("report_pair.id"), nullable=False)
    tables_compared: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status:          Mapped[str] = mapped_column(String,  nullable=False)
    created_at:      Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    report_pair:       Mapped["ReportPair"]           = relationship("ReportPair", back_populates="data_result")
    table_comparisons: Mapped[list["TableComparison"]] = relationship("TableComparison", back_populates="data_result", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<DataResult id={self.id} status={self.status!r}>"


class TableComparison(Base):
    __tablename__ = "table_comparison"

    id: Mapped[int]                          = mapped_column(Integer, primary_key=True, autoincrement=True)
    data_result_id: Mapped[int]              = mapped_column(Integer, ForeignKey("data_result.id"), nullable=False)
    table_name: Mapped[str]                  = mapped_column(String, nullable=False)
    result:     Mapped[str]                  = mapped_column(String, nullable=False)
    row_count_twbx:    Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    row_count_pbix:    Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    row_count_diff_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    failure_reasons:   Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Column-level analysis fields (stored as JSON strings)
    columns_matched:          Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    columns_missing_in_pbix:  Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    columns_missing_in_twbx:  Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    column_type_mismatches:   Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    column_count_twbx:        Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    column_count_pbix:        Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    match_method:             Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime]             = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    data_result: Mapped["DataResult"] = relationship("DataResult", back_populates="table_comparisons")


# ---------------------------------------------------------------------------
# DB initialisation helper
# ---------------------------------------------------------------------------

def init_db(db_url: str = "sqlite:///migrateiq.db") -> "Engine":
    """Create all tables and run lightweight column migrations."""
    from sqlalchemy import create_engine
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    _migrate_columns(engine)
    return engine


def _migrate_columns(engine) -> None:
    """Add columns that exist in the model but are missing from the DB.

    Only runs for SQLite (uses PRAGMA which is SQLite-specific).
    For other databases, create_all() handles the full schema.
    """
    if engine.dialect.name != "sqlite":
        return

    from sqlalchemy import text

    migrations: dict[str, list[tuple[str, str]]] = {
        "migration_project": [
            ("owner", "TEXT"),
        ],
        "visual_result": [
            ("pixel_diff_count",       "INTEGER"),
            ("total_pixels",           "INTEGER"),
            ("hash_distance",          "INTEGER"),
            ("diff_image_path",        "TEXT"),
            ("compared_width",         "INTEGER"),
            ("compared_height",        "INTEGER"),
            ("tableau_annotated_path", "TEXT"),
            ("powerbi_annotated_path", "TEXT"),
            ("comparison_image_path",  "TEXT"),
            ("gpt4o_called",           "BOOLEAN"),
            ("chart_type_match",       "TEXT"),
            ("color_scheme_match",     "TEXT"),
            ("layout_match",           "TEXT"),
            ("axis_labels_match",      "TEXT"),
            ("axis_scale_match",       "TEXT"),
            ("legend_match",           "TEXT"),
            ("title_match",            "TEXT"),
            ("data_labels_match",      "TEXT"),
            ("text_content_match",     "TEXT"),
            ("ai_summary",             "TEXT"),
            ("ai_key_differences",     "TEXT"),
            ("ai_recommendation",      "TEXT"),
            ("ai_raw_response",        "TEXT"),
            ("gpt4o_risk_level",       "TEXT"),
            ("pass_threshold_pct",     "REAL"),
            ("visual_parameters",      "TEXT"),
        ],
        "report_pair": [
            ("run_id", "INTEGER"),
            ("l3_result_json", "TEXT"),
        ],
        "validation_run": [
            ("errored", "INTEGER"),
        ],
        "table_comparison": [
            ("columns_matched",         "TEXT"),
            ("columns_missing_in_pbix", "TEXT"),
            ("columns_missing_in_twbx", "TEXT"),
            ("column_type_mismatches",  "TEXT"),
            ("column_count_twbx",       "INTEGER"),
            ("column_count_pbix",       "INTEGER"),
            ("match_method",            "TEXT"),
        ],
        "semantic_result": [
            ("column_value_status",  "TEXT"),
            ("column_value_details", "TEXT"),
        ],
    }

    with engine.connect() as conn:
        for table, columns in migrations.items():
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            existing = {row[1] for row in rows}  # column name is at index 1
            for col_name, col_type in columns:
                if col_name not in existing:
                    conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
                    ))
        conn.commit()


# ---------------------------------------------------------------------------
# Persist JSON Result
# ---------------------------------------------------------------------------

def save_comparison_result(
    session,
    result_json: dict,
    project_id: int,
    run_id: Optional[int] = None,
    tableau_screenshot: Optional[str] = None,
    powerbi_screenshot: Optional[str] = None,
    l3_result: Optional[dict] = None,
) -> ReportPair:
    """
    Persist the full 3-layer JSON result into the normalised schema.
    """
    inputs = result_json.get("inputs", {})
    cats   = result_json.get("categories", {})
    
    # Helper to clean filenames
    def clean(name: str):
        if not name: return ""
        import re
        # Strip 36-char UUID prefix and any file extension
        name = re.sub(r'^[0-9a-fA-F-]{36}_', '', name)
        return re.sub(r'\.[^/.]+$', '', name)

    twName = clean(inputs.get("twbx_file"))
    pbName = clean(inputs.get("pbix_file"))

    # 1. Report Pair
    import json as _json2
    pair = ReportPair(
        project_id     = project_id,
        run_id         = run_id,
        report_name    = f"{twName} vs {pbName}",
        tableau_workbook   = twName,
        powerbi_report_name= pbName,
        tableau_screenshot = tableau_screenshot,
        powerbi_screenshot = powerbi_screenshot,
        overall_status = result_json.get("overall_result", "PENDING"),
        l3_result_json = _json2.dumps(l3_result) if l3_result else None,
    )
    session.add(pair)
    session.flush()

    # 2. Layer 1: Relationships
    rel_cat = cats.get("relationships", {})
    rel_res = RelationshipResult(
        report_pair_id = pair.id,
        relationships_compared = rel_cat.get("relationships_compared", 0),
        status = rel_cat.get("result", "PENDING")
    )
    session.add(rel_res)
    session.flush()

    rel_details = rel_cat.get("details", {})
    for item in rel_details.get("relationships_matched", []):
        session.add(RelationshipDetail(
            relationship_result_id = rel_res.id,
            source_desc = item.get("from", "unknown"),
            target_desc = item.get("to", "unknown"),
            type = "MATCH"
        ))
    for item in rel_details.get("relationships_missing_in_pbix", []):
        session.add(RelationshipDetail(
            relationship_result_id = rel_res.id,
            source_desc = str(item),
            target_desc = "MISSING",
            type = "MISSING",
            detail = "Missing in Power BI"
        ))

    import json as _json

    # 3. Layer 2: Semantic Model
    sem_cat = cats.get("semantic_model", {})
    sem_details = sem_cat.get("details", {})
    cv_analysis = sem_cat.get("column_value_analysis", {})
    semantic = SemanticResult(
        report_pair_id        = pair.id,
        total_fields          = sem_cat.get("measures_compared", 0),
        matched_fields        = len(sem_details.get("measures_matched", [])),
        flagged_fields        = len(sem_details.get("expression_mismatches", [])),
        status                = sem_cat.get("result", "PENDING"),
        column_value_status   = cv_analysis.get("result"),
        column_value_details  = _json.dumps(cv_analysis.get("details", [])),
    )
    session.add(semantic)
    session.flush()

    for mismatch in sem_details.get("expression_mismatches", []):
        session.add(CalcField(
            semantic_result_id = semantic.id,
            field_name = mismatch.get("field_name", "unknown"),
            tableau_formula = mismatch.get("tableau_formula"),
            dax_from_pbix = mismatch.get("dax_expression"),
            is_equivalent = mismatch.get("is_equivalent"),
            differences = mismatch.get("differences"),
            ai_explanation = mismatch.get("ai_explanation"),
            status = "MISMATCH"
        ))

    # 4. Layer 3: Data
    data_cat = cats.get("data", {})
    data_res = DataResult(
        report_pair_id = pair.id,
        tables_compared = data_cat.get("tables_compared", 0),
        status = data_cat.get("result", "PENDING")
    )
    session.add(data_res)
    session.flush()

    for detail in data_cat.get("details", []):
        session.add(TableComparison(
            data_result_id      = data_res.id,
            table_name          = detail.get("table_name", "unknown"),
            result              = detail.get("result", "PENDING"),
            row_count_twbx      = detail.get("row_count_twbx"),
            row_count_pbix      = detail.get("row_count_pbix"),
            row_count_diff_pct  = detail.get("row_count_diff_pct"),
            failure_reasons     = ", ".join(detail.get("failure_reasons", [])),
            columns_matched         = _json.dumps(detail.get("columns_matched", [])),
            columns_missing_in_pbix = _json.dumps(detail.get("columns_missing_in_pbix", [])),
            columns_missing_in_twbx = _json.dumps(detail.get("columns_missing_in_twbx", [])),
            column_type_mismatches  = _json.dumps(detail.get("column_type_mismatches", [])),
            column_count_twbx       = detail.get("column_count_twbx"),
            column_count_pbix       = detail.get("column_count_pbix"),
            match_method            = detail.get("match_method"),
        ))

    return pair


if __name__ == "__main__":
    # Test initialization
    engine = init_db("sqlite:///migrateiq.db")
    print("Database initialized.")


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from sqlalchemy.orm import sessionmaker

    engine  = init_db("sqlite:///migrateiq.db")
    Session = sessionmaker(bind=engine)

    # Create a default project
    with Session() as session:
        project = MigrationProject(name="Default Migration Project")
        session.add(project)
        session.commit()

        # Load and save example JSON files (adjust paths as needed)
        sample_files = [
            "ebce2643-9056-4a33-b58b-dcfcfa95c003.json",
            "adfa3a77-5f9a-4f19-9fde-b7d800791546.json",
            "a3b26d57-f012-4a94-b254-b0772aa1688a.json",
            "3651b608-0b75-4129-9a3e-4bbbaf85ab73.json",
        ]
        for path in sample_files:
            try:
                with open(path) as f:
                    data = json.load(f)
                pair = save_comparison_result(session, data, project_id=project.id)
                print(f"Saved: {pair}")
            except FileNotFoundError:
                print(f"File not found (skipped): {path}")

        session.commit()
        print("Done.")