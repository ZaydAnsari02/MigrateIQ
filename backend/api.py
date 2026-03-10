import os
import sys
import json
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker, joinedload

from datetime import datetime

# ─── MigrateIQ Modules ────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent.resolve()
sys.path.append(str(BACKEND_DIR))

import config
from db.models import init_db, save_comparison_result, MigrationProject, ReportPair, ValidationRun, Status, VisualResult
from visual.pipeline import run_visual_validation

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

from fastapi.staticfiles import StaticFiles
(BACKEND_DIR / "screenshots").mkdir(exist_ok=True)
app.mount("/screenshots", StaticFiles(directory=str(BACKEND_DIR / "screenshots")), name="screenshots")

# ─── Directories ──────────────────────────────────────────────────────────────
(BACKEND_DIR / "temp").mkdir(exist_ok=True)
(BACKEND_DIR / "results").mkdir(exist_ok=True)


# ─── Startup Logic ────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup_event():
    pass

def get_screenshot_url(absolute_path: str | None) -> str | None:
    if not absolute_path: return None
    try:
        p = Path(absolute_path)
        parts = p.parts
        if "screenshots" in parts:
            idx = parts.index("screenshots")
            rel = Path(*parts[idx+1:])
            return f"{config.BASE_URL}/screenshots/{rel.as_posix()}"
        return f"{config.BASE_URL}/screenshots/{p.name}"
    except:
        return f"{config.BASE_URL}/screenshots/{Path(absolute_path).name}" if absolute_path else None
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


# ─── POST /validate ───────────────────────────────────────────────────────────
@app.post("/validate")
async def validate_reports(
    twbx: UploadFile = File(...),
    pbix:  UploadFile = File(...),
    tableau_screenshot: UploadFile = File(None),
    pbi_screenshot: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    import traceback
    try:
        run_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        project = db.query(MigrationProject).first()
        
        # Create an initial ValidationRun
        v_run = ValidationRun(
            project_id=project.id,
            triggered_by="Web UI",
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

        # ─── Screenshot Handling ────────────────────────────────────────────────
        tab_screenshot_path = None
        pbi_screenshot_path = None

        def process_screenshot(file: UploadFile, suffix: str) -> Optional[str]:
            if not file: return None
            target_dir = BACKEND_DIR / "screenshots"
            target_dir.mkdir(exist_ok=True)
            
            temp_path = BACKEND_DIR / "temp" / f"{run_id}_{suffix}_{file.filename}"
            with open(temp_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            if file.filename.lower().endswith(".zip"):
                import zipfile
                extract_dir = BACKEND_DIR / "temp" / f"{run_id}_{suffix}_extracted"
                extract_dir.mkdir(exist_ok=True)
                with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                # Find the first image
                for p in extract_dir.rglob("*"):
                    if p.suffix.lower() in (".png", ".jpg", ".jpeg"):
                        final_path = target_dir / f"{run_id}_{suffix}{p.suffix}"
                        shutil.copy(p, final_path)
                        return f"screenshots/{final_path.name}"
                return None
            else:
                final_path = target_dir / f"{run_id}_{suffix}{Path(file.filename).suffix}"
                shutil.move(str(temp_path), str(final_path))
                return f"screenshots/{final_path.name}"

        tab_screenshot_path = process_screenshot(tableau_screenshot, "tableau")
        pbi_screenshot_path = process_screenshot(pbi_screenshot, "pbi")

        # ─── Persist to DB ───────────────────────────────────────────────────────
        try:
            # Update the ValidationRun
            v_run.status = result.get("overall_result", "PENDING")
            v_run.passed = 1 if result.get("overall_result") == "PASS" else 0
            v_run.failed = 1 if result.get("overall_result") == "FAIL" else 0
            v_run.completed_at = datetime.utcnow()
            
            # Save the report pair details
            pair = save_comparison_result(
                db, result, 
                project_id         = project.id, 
                run_id             = v_run.id,
                tableau_screenshot = tab_screenshot_path,
                powerbi_screenshot = pbi_screenshot_path
            )
            db.commit()
            
            # ─── Layer 1: Visual Validation ───────────────────────────────────
            if tab_screenshot_path and pbi_screenshot_path:
                try:
                    run_visual_validation(
                        db, pair,
                        openai_api_key  = config.OPENAI_API_KEY,
                        diff_output_dir = str(BACKEND_DIR / "screenshots" / "diffs")
                    )
                    # Status is updated and committed inside run_visual_validation;
                    # refresh pair so overall_status reflects those DB writes.
                    db.refresh(pair)
                except Exception as ve:
                    print(f"Visual validation failed: {ve}")

            # Always sync the run's final status from the pair (with or without screenshots).
            # Normalize to uppercase — the visual pipeline stores lowercase via Status constants.
            db.refresh(pair)
            db.refresh(v_run)
            v_run.status = pair.overall_status.upper()
            v_run.passed = 1 if pair.overall_status.lower() == "pass" else 0
            v_run.failed = 1 if pair.overall_status.lower() == "fail" else 0
            db.commit()
            
        except Exception as e:
            db.rollback()
            print(f"FAILED TO SAVE TO DB: {e}")
            traceback.print_exc()

        # Attach the run_id so the frontend can reference it later
        result["run_id"] = run_id

        # Clean up temp input files
        Path(twbx_path).unlink(missing_ok=True)
        Path(pbix_path).unlink(missing_ok=True)
        
        # Clean up screenshot temp files and extracted dirs
        shutil.rmtree(str(BACKEND_DIR / "temp"), ignore_errors=True)
        (BACKEND_DIR / "temp").mkdir(exist_ok=True)

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
        joinedload(ReportPair.data_result).joinedload(DataResult.table_comparisons),
        joinedload(ReportPair.visual_result)
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
        
        # Layer 1: Visual (Mismatches from AI)
        if p.visual_result and p.visual_result.status != "PASS":
            if p.visual_result.ai_key_differences:
                try:
                    visual_diffs = json.loads(p.visual_result.ai_key_differences)
                    for vd in visual_diffs:
                        differences.append({
                            "type": "Visual Dismatch",
                            "detail": vd,
                            "severity": "medium",
                            "layer": "L1"
                        })
                except:
                    pass
        
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
            "layer1Status": p.visual_result.status if p.visual_result else "skipped",
            "layer2Status": p.semantic_result.status if p.semantic_result else "PENDING",
            "layer3Status": p.data_result.status if p.data_result else "PENDING",
            "differences": differences,
            "visualResult": {
                "status": p.visual_result.status,
                "pixelSimilarityPct": p.visual_result.pixel_similarity_pct,
                "aiSummary": p.visual_result.ai_summary,
                "aiKeyDifferences": json.loads(p.visual_result.ai_key_differences) if p.visual_result.ai_key_differences else [],
                "gpt4oRiskLevel": p.visual_result.gpt4o_risk_level,
                "tableauAnnotatedPath": get_screenshot_url(p.visual_result.tableau_annotated_path),
                "powerbiAnnotatedPath": get_screenshot_url(p.visual_result.powerbi_annotated_path),
                "comparisonImagePath": get_screenshot_url(p.visual_result.comparison_image_path),
                "diffImagePath": get_screenshot_url(p.visual_result.diff_image_path),
            } if p.visual_result else None,
            "tableauWorkbook": p.tableau_workbook,
            "powerbiReportName": p.powerbi_report_name,
            "tableauScreenshot": get_screenshot_url(p.tableau_screenshot),
            "powerBiScreenshot": get_screenshot_url(p.powerbi_screenshot),
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
        joinedload(ReportPair.data_result).joinedload(DataResult.table_comparisons),
        joinedload(ReportPair.visual_result)
    ).first()
    
    if not pair:
        # Check if it's the pair ID
        pair = db.query(ReportPair).options(
            joinedload(ReportPair.relationship_result).joinedload(RelationshipResult.details),
            joinedload(ReportPair.semantic_result).joinedload(SemanticResult.calc_fields),
            joinedload(ReportPair.data_result).joinedload(DataResult.table_comparisons),
            joinedload(ReportPair.visual_result)
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
            "visual": {
                "result": pair.visual_result.status if pair.visual_result else "PENDING",
                "metrics": {
                    "similarity": pair.visual_result.pixel_similarity_pct if pair.visual_result else None,
                    "gpt4o_called": pair.visual_result.gpt4o_called if pair.visual_result else False,
                    "risk_level": pair.visual_result.gpt4o_risk_level if pair.visual_result else None,
                } if pair.visual_result else None,
                "images": {
                    "tableau_annotated": get_screenshot_url(pair.visual_result.tableau_annotated_path) if pair.visual_result else None,
                    "powerbi_annotated": get_screenshot_url(pair.visual_result.powerbi_annotated_path) if pair.visual_result else None,
                    "comparison": get_screenshot_url(pair.visual_result.comparison_image_path) if pair.visual_result else None,
                    "diff": get_screenshot_url(pair.visual_result.diff_image_path) if pair.visual_result else None,
                } if pair.visual_result else None,
                "ai_analysis": {
                    "summary": pair.visual_result.ai_summary if pair.visual_result else None,
                    "key_differences": json.loads(pair.visual_result.ai_key_differences) if pair.visual_result and pair.visual_result.ai_key_differences else [],
                    "recommendation": pair.visual_result.ai_recommendation if pair.visual_result else None,
                } if pair.visual_result else None
            },
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
