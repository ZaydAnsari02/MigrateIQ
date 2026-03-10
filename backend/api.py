import os
import sys
import json
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker, joinedload
from datetime import datetime

# ─── MigrateIQ Modules ────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent.resolve()
sys.path.append(str(BACKEND_DIR))

from auth import USERS
import config
from db.models import init_db, save_comparison_result, MigrationProject, ReportPair, ValidationRun

# ─── Database Setup ───────────────────────────────────────────────────────────
engine = init_db(config.DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="MigrateIQ API", version="1.0.0")

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Directories ──────────────────────────────────────────────────────────────
(BACKEND_DIR / "temp").mkdir(exist_ok=True)
(BACKEND_DIR / "results").mkdir(exist_ok=True)


# ─── Startup Logic ────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup_event():
    # Ensure at least one project exists
    db = SessionLocal()
    project = db.query(MigrationProject).first()
    if not project:
        project = MigrationProject(
            name="Default Migration Project",
            client_name="AI Telekom",
            description="Initial project for report validation"
        )
        db.add(project)
        db.commit()
    db.close()


# ─── In-memory session store ──────────────────────────────────────────────────
# Maps token → username. Resets on server restart (sufficient for development).
SESSIONS: dict[str, str] = {}


# ─── POST /validate ───────────────────────────────────────────────────────────
@app.post("/validate")
async def validate_reports(
    twbx: UploadFile = File(...),
    pbix:  UploadFile = File(...),
    db: Session = Depends(get_db),
    x_token: Optional[str] = Header(None),
):
    import traceback
    # Resolve the username from the session token (fall back to "Web UI")
    triggered_by = SESSIONS.get(x_token, "Web UI") if x_token else "Web UI"

    try:
        run_id = str(uuid.uuid4())
        start_time = datetime.utcnow()

        project = db.query(MigrationProject).first()

        # Create an initial ValidationRun — record who triggered it
        v_run = ValidationRun(
            project_id=project.id,
            triggered_by=triggered_by,
            status="RUNNING",
            total_reports=1,
            started_at=start_time
        )
        db.add(v_run)
        db.commit()
        db.refresh(v_run)

        twbx_path   = str(BACKEND_DIR / "temp" / f"{run_id}_{twbx.filename}")
        pbix_path   = str(BACKEND_DIR / "temp" / f"{run_id}_{pbix.filename}")
        output_path = str(BACKEND_DIR / "results" / f"{run_id}.json")

        # Save uploaded files to disk
        try:
            with open(twbx_path, "wb") as f:
                shutil.copyfileobj(twbx.file, f)
            with open(pbix_path, "wb") as f:
                shutil.copyfileobj(pbix.file, f)
        except Exception as e:
            v_run.status = "ERROR"
            db.commit()
            raise HTTPException(status_code=500, detail=f"File save failed: {e}")

        script_path = Path(__file__).parent / "compare_reports.py"

        # Run the comparison script
        proc = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--twbx", twbx_path,
                "--pbix", pbix_path,
                "--output", output_path,
            ],
            capture_output=True,
            text=True,
            cwd=str(BACKEND_DIR),
        )

        if proc.returncode not in (0, 1):
            v_run.status = "ERROR"
            db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Comparison script error: {proc.stderr}",
            )

        if not Path(output_path).exists():
            v_run.status = "ERROR"
            db.commit()
            raise HTTPException(
                status_code=500,
                detail=f"Result file was not generated."
            )

        with open(output_path) as f:
            result = json.load(f)

        # ─── Persist to DB ───────────────────────────────────────────────────────
        try:
            # Update the ValidationRun
            v_run.status = result.get("overall_result", "PENDING")
            v_run.passed = 1 if result.get("overall_result") == "PASS" else 0
            v_run.failed = 1 if result.get("overall_result") == "FAIL" else 0
            v_run.completed_at = datetime.utcnow()
            
            # Save the report pair details
            save_comparison_result(db, result, project_id=project.id, run_id=v_run.id)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"FAILED TO SAVE TO DB: {e}")

        # Attach the run_id so the frontend can reference it later
        result["run_id"] = run_id

        # Clean up temp input files
        Path(twbx_path).unlink(missing_ok=True)
        Path(pbix_path).unlink(missing_ok=True)

        return result
    except HTTPException:
        # Re-raise HTTP exceptions so FastAPI handles them correctly
        raise
    except Exception as e:
        err_trace = traceback.format_exc()
        print(f"CRITICAL ERROR IN /validate:\n{err_trace}")
        # Return the traceback in development to help the user identify the issue
        raise HTTPException(
            status_code=500, 
            detail=f"Internal Server Error: {str(e)}\n\nTraceback:\n{err_trace}"
        )


# ─── GET /report-pairs ────────────────────────────────────────────────────────
@app.get("/report-pairs")
async def list_report_pairs(db: Session = Depends(get_db)):
    from db.models import RelationshipResult, RelationshipDetail, SemanticResult, CalcField, DataResult, TableComparison
    
    pairs = db.query(ReportPair).options(
        joinedload(ReportPair.relationship_result).joinedload(RelationshipResult.details),
        joinedload(ReportPair.semantic_result).joinedload(SemanticResult.calc_fields),
        joinedload(ReportPair.data_result).joinedload(DataResult.table_comparisons)
    ).order_by(ReportPair.created_at.desc()).all()
    
    output = []
    for p in pairs:
        differences = []
        
        # Layer 1: Relationships
        if p.relationship_result:
            for d in p.relationship_result.details:
                if d.type != "MATCH":
                    differences.append({
                        "type": "Missing Filter" if d.type == "MISSING" else "Relationship Mismatch",
                        "detail": d.detail or f"Issue with {d.source_desc}",
                        "severity": "high",
                        "layer": "L1"
                    })
        
        # Layer 2: Semantic Model
        if p.semantic_result:
            for f in p.semantic_result.calc_fields:
                if f.status != "MATCH":
                    differences.append({
                        "type": "DAX Mismatch",
                        "detail": f.differences or f"Mismatch in field '{f.field_name}'",
                        "severity": "high",
                        "layer": "L2"
                    })
        
        # Layer 3: Data
        if p.data_result:
            for t in p.data_result.table_comparisons:
                if t.result != "PASS":
                    differences.append({
                        "type": "Data Regression",
                        "detail": t.failure_reasons or f"Table '{t.table_name}' validation failed",
                        "severity": "high",
                        "layer": "L3"
                    })

        output.append({
            "id": str(p.id),
            "runId": str(p.run_id) if p.run_id else None,
            "reportName": p.report_name,
            "overallStatus": p.overall_status,
            "layer1Status": p.relationship_result.status if p.relationship_result else "PENDING",
            "layer2Status": p.semantic_result.status if p.semantic_result else "PENDING",
            "layer3Status": p.data_result.status if p.data_result else "PENDING",
            "differences": differences,
            "tableauWorkbook": p.tableau_workbook,
            "powerbiReportName": p.powerbi_report_name,
            "tableauScreenshot": p.tableau_screenshot,
            "powerBiScreenshot": p.powerbi_screenshot,
            "createdAt": p.created_at.isoformat()
        })
    return output


# ─── GET /results/{run_id} ────────────────────────────────────────────────────
@app.get("/results/{run_id}")
async def get_result(run_id: str, db: Session = Depends(get_db)):
    from db.models import RelationshipResult, RelationshipDetail, SemanticResult, CalcField, DataResult, TableComparison

    # First try fetching from database if it's a numeric ID or UUID
    # For now, we still support loading from JSON files if run_id matches a filename
    output_path = BACKEND_DIR / "results" / f"{run_id}.json"
    if output_path.exists():
        with open(output_path) as f:
            return json.load(f)
    
    # Fallback: Query DB for details (reconstruct JSON — basic version)
    pair = db.query(ReportPair).filter(ReportPair.run_id == run_id).options(
        joinedload(ReportPair.relationship_result).joinedload(RelationshipResult.details),
        joinedload(ReportPair.semantic_result).joinedload(SemanticResult.calc_fields),
        joinedload(ReportPair.data_result).joinedload(DataResult.table_comparisons)
    ).first()
    
    if not pair:
        # Check if it's the pair ID
        pair = db.query(ReportPair).options(
            joinedload(ReportPair.relationship_result).joinedload(RelationshipResult.details),
            joinedload(ReportPair.semantic_result).joinedload(SemanticResult.calc_fields),
            joinedload(ReportPair.data_result).joinedload(DataResult.table_comparisons)
        ).get(run_id)
        
    if not pair:
        raise HTTPException(status_code=404, detail=f"Result {run_id} not found.")
    
    # Reconstructing minimal JSON for frontend compatibility
    return {
        "comparison_id": str(pair.id),
        "timestamp": pair.created_at.isoformat(),
        "inputs": {
            "twbx_file": pair.tableau_workbook,
            "pbix_file": pair.powerbi_report_name
        },
        "overall_result": pair.overall_status,
        "categories": {
            "data": {
                "result": pair.data_result.status if pair.data_result else "PENDING", 
                "details": [
                    {
                        "table_name": t.table_name,
                        "result": t.result,
                        "failure_reasons": t.failure_reasons.split(", ") if t.failure_reasons else []
                    } for t in (pair.data_result.table_comparisons if pair.data_result else [])
                ]
            },
            "semantic_model": {
                "result": pair.semantic_result.status if pair.semantic_result else "PENDING", 
                "details": {
                    "failure_reasons": [
                        f.differences for f in (pair.semantic_result.calc_fields if pair.semantic_result else []) 
                        if f.status != "MATCH" and f.differences
                    ]
                }
            },
            "relationships": {
                "result": pair.relationship_result.status if pair.relationship_result else "PENDING", 
                "details": {
                    "failure_reasons": [
                        d.detail or f"Issue with {d.source_desc}" 
                        for d in (pair.relationship_result.details if pair.relationship_result else [])
                        if d.type != "MATCH"
                    ]
                }
            }
        }
    }


# ─── GET /results ─────────────────────────────────────────────────────────────
@app.get("/results")
async def list_results(db: Session = Depends(get_db)):
    # 1. Start with JSON files on disk
    results_dir = BACKEND_DIR / "results"
    run_ids = [f.stem for f in results_dir.glob("*.json")]
    
    # 2. Add database runs
    runs = db.query(ValidationRun).all()
    for r in runs:
        if str(r.id) not in run_ids:
            run_ids.append(str(r.id))
            
    return {"run_ids": run_ids, "count": len(run_ids)}


# ─── GET /runs ─────────────────────────────────────────────────────────────
@app.get("/runs")
async def list_runs(db: Session = Depends(get_db)):
    runs = db.query(ValidationRun).order_by(ValidationRun.started_at.desc()).all()
    # Return in a format compatible with frontend expectations if needed
    return runs


# ─── GET /health ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "MigrateIQ API"}


# ─── POST /login ──────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/login")
def login(body: LoginRequest):
    if body.username not in USERS or USERS[body.username] != body.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = str(uuid.uuid4())
    SESSIONS[token] = body.username
    return {"token": token, "username": body.username}