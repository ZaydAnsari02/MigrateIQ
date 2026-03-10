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
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


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
    
    # Pixel diff / GPT-4o Vision placeholders
    pixel_similarity_pct: Mapped[Optional[float]] = mapped_column(Float,   nullable=True)
    ai_summary:          Mapped[Optional[str]]     = mapped_column(Text,    nullable=True)
    status:             Mapped[str]                = mapped_column(String, nullable=False)
    created_at:         Mapped[datetime]           = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

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
    created_at: Mapped[datetime]             = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    data_result: Mapped["DataResult"] = relationship("DataResult", back_populates="table_comparisons")


# ---------------------------------------------------------------------------
# DB initialisation helper
# ---------------------------------------------------------------------------

def init_db(db_url: str = "sqlite:///migrateiq.db") -> "Engine":
    """Create all tables and return the engine."""
    from sqlalchemy import create_engine
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return engine


# ---------------------------------------------------------------------------
# Persist JSON Result
# ---------------------------------------------------------------------------

def save_comparison_result(session, result_json: dict, project_id: int, run_id: Optional[int] = None) -> ReportPair:
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
    pair = ReportPair(
        project_id     = project_id,
        run_id         = run_id,
        report_name    = f"{twName} vs {pbName}",
        tableau_workbook   = twName,
        powerbi_report_name= pbName,
        overall_status = result_json.get("overall_result", "PENDING"),
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

    # 3. Layer 2: Semantic Model
    sem_cat = cats.get("semantic_model", {})
    sem_details = sem_cat.get("details", {})
    semantic = SemanticResult(
        report_pair_id = pair.id,
        total_fields   = sem_cat.get("measures_compared", 0),
        matched_fields = len(sem_details.get("measures_matched", [])),
        flagged_fields = len(sem_details.get("expression_mismatches", [])),
        status         = sem_cat.get("result", "PENDING"),
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
            data_result_id = data_res.id,
            table_name = detail.get("table_name", "unknown"),
            result = detail.get("result", "PENDING"),
            row_count_twbx = detail.get("row_count_twbx"),
            row_count_pbix = detail.get("row_count_pbix"),
            row_count_diff_pct = detail.get("row_count_diff_pct"),
            failure_reasons = ", ".join(detail.get("failure_reasons", []))
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