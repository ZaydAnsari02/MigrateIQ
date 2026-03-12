import os
import sys
import json
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker, joinedload
from datetime import datetime

# ─── MigrateIQ Modules ────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent.resolve()
sys.path.append(str(BACKEND_DIR))

from auth import USERS
import config  # loads .env via python-dotenv — must come before l3_pipeline
from l3_pipeline import run_l3_validation
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
    # Ensure one project exists per user
    db = SessionLocal()
    for username in USERS:
        project = db.query(MigrationProject).filter(MigrationProject.owner == username).first()
        if not project:
            db.add(MigrationProject(
                name="Default Migration Project",
                client_name="AI Telekom",
                description="Initial project for report validation",
                owner=username
            ))
    db.commit()
    db.close()


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


# ─── In-memory session store ──────────────────────────────────────────────────
# Maps token → username. Resets on server restart (sufficient for development).
SESSIONS: dict[str, str] = {}


def get_current_username(
    x_token: Optional[str] = Header(None),
    x_username: Optional[str] = Header(None),
) -> str:
    """Resolve username from session token or x-username header. Raises 401 if unrecognised."""
    username = SESSIONS.get(x_token) if x_token else None
    if not username and x_username and x_username in USERS:
        username = x_username
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return username


# ─── POST /validate ───────────────────────────────────────────────────────────
@app.post("/validate")
async def validate_reports(
    twbx: UploadFile = File(...),
    pbix:  UploadFile = File(...),
    pbit: Optional[UploadFile] = File(None), 
    tableau_screenshot: Optional[UploadFile] = File(None),
    pbi_screenshot: Optional[UploadFile] = File(None),
    visual_parameters: Optional[str] = Form(None),  # JSON string of param flags
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_username),
):
    import traceback
    triggered_by = current_user

    try:
        run_id = str(uuid.uuid4())
        start_time = datetime.utcnow()

        project = db.query(MigrationProject).filter(MigrationProject.owner == current_user).first()

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
        # ── 3. Save the pbit file to disk (after saving twbx and pbix) ───────────────
        pbit_path = None
        if pbit:
            pbit_path = str(BACKEND_DIR / "temp" / f"{run_id}_{pbit.filename}")
            with open(pbit_path, "wb") as f:
                shutil.copyfileobj(pbit.file, f)
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
        cmd = [
            sys.executable,
            str(script_path),
            "--twbx", twbx_path,
            "--pbix", pbix_path,
            "--output", output_path,
        ]
        if pbit_path:
            cmd += ["--pbit", pbit_path]

        proc = subprocess.run(
            cmd,
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

        # ── 4. Run L3 if pbit was uploaded — add this AFTER result = json.load(f) ────
        l3_result = None
        if pbit_path:
            try:
                l3_result = run_l3_validation(twbx_path, pbit_path)
                result["l3_result"] = l3_result
            except Exception as e:
                result["l3_result"] = {
                    "layer": "L3",
                    "status": "ERROR",
                    "error": str(e),
                    "summary": {},
                    "measure_results": []
                }

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
                powerbi_screenshot = pbi_screenshot_path,
                l3_result          = l3_result,
            )
            db.commit()
            
            # ─── Layer 1: Visual Validation ───────────────────────────────────
            if tab_screenshot_path and pbi_screenshot_path:
                try:
                    _vis_params = json.loads(visual_parameters) if visual_parameters else None
                    run_visual_validation(
                        db, pair,
                        openai_api_key  = config.OPENAI_API_KEY,
                        diff_output_dir = str(BACKEND_DIR / "screenshots" / "diffs"),
                        parameters      = _vis_params,
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
        if pbit_path:
            Path(pbit_path).unlink(missing_ok=True)
        
        # Clean up screenshot temp files and extracted dirs inside temp/
        # (do NOT remove the directory itself — uvicorn's reload watcher will
        #  crash if it tries to scan a directory that has been deleted)
        temp_dir = BACKEND_DIR / "temp"
        for item in temp_dir.iterdir():
            try:
                if item.is_dir():
                    shutil.rmtree(str(item), ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
            except Exception:
                pass

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


def _build_visual_result_dict(vr) -> dict:
    """Serialize a VisualResult ORM object for the frontend, including parameter results."""
    from visual.prompts import DEFAULT_PARAMS
    stored_params = json.loads(vr.visual_parameters) if vr.visual_parameters else None
    params_used = {**DEFAULT_PARAMS, **(stored_params or {})}

    def _match_status(field_val, param_key: str) -> str:
        """Return pass/fail/ignored/skipped for a single parameter."""
        if field_val is None:
            return "skipped"
        # New format: DB stores "pass"/"fail"/"ignored" strings directly from GPT
        if isinstance(field_val, str) and field_val.lower() in ("pass", "fail", "ignored"):
            return field_val.lower()
        # Legacy format: "True"/"False" strings or actual bools — apply params_used check
        if not params_used.get(param_key, True):
            return "ignored"
        if isinstance(field_val, str):
            return "pass" if field_val.lower() == "true" else "fail"
        return "pass" if field_val else "fail"

    # Build parameter results — one entry per visual parameter
    param_results = {
        "chart_type":   _match_status(vr.chart_type_match,    "chart_type"),
        "color":        _match_status(vr.color_scheme_match,  "color"),
        "legend":       _match_status(vr.legend_match,        "legend"),
        "axis_labels":  _match_status(vr.axis_labels_match,   "axis_labels"),
        "axis_scale":   _match_status(vr.axis_scale_match,    "axis_scale"),
        "title":        _match_status(vr.title_match,         "title"),
        "data_labels":  _match_status(vr.data_labels_match,   "data_labels"),
        "layout":       _match_status(vr.layout_match,        "layout"),
        "text_content": _match_status(vr.text_content_match,  "text_content"),
    }

    # Derive overall result from parameter results
    has_fail = any(s == "fail" for s in param_results.values())
    derived_status = "fail" if has_fail else (vr.status or "skipped")

    return {
        "status":           derived_status,
        "gpt4oCalled":      vr.gpt4o_called,
        "aiSummary":        vr.ai_summary,
        "aiKeyDifferences": json.loads(vr.ai_key_differences) if vr.ai_key_differences else [],
        "gpt4oRiskLevel":   vr.gpt4o_risk_level,
        "parametersUsed":   params_used,
        "parameterResults": param_results,
        # Match booleans for client-side re-computation
        "chartTypeMatch":   vr.chart_type_match,
        "colorSchemeMatch": vr.color_scheme_match,
        "legendMatch":      vr.legend_match,
        "axisLabelsMatch":  vr.axis_labels_match,
        "axisScaleMatch":   vr.axis_scale_match,
        "titleMatch":       vr.title_match,
        "dataLabelsMatch":  vr.data_labels_match,
        "layoutMatch":      vr.layout_match,
        "textContentMatch": vr.text_content_match,
    }


def _visual_diff_type(detail: str) -> str:
    """Derive a human-readable difference type from the AI-generated detail text."""
    d = detail.lower()
    if any(k in d for k in ("chart type", "bar chart", "pie chart", "line chart", "stacked bar", "donut", "scatter")):
        return "Chart Type Difference"
    if any(k in d for k in ("color scheme", "colour scheme", "color differ", "colour differ", "shade of", "palette")):
        return "Color Scheme Difference"
    if "legend" in d:
        return "Legend Difference"
    if "title" in d:
        return "Title Difference"
    if "data label" in d:
        return "Data Labels Difference"
    if any(k in d for k in ("axis", "x-axis", "y-axis", "axis label")):
        return "Axis Labels Difference"
    if any(k in d for k in ("filter", "slicer")):
        return "Filter Difference"
    if any(k in d for k in ("layout", "position", "alignment")):
        return "Layout Difference"
    if any(k in d for k in ("missing", "absent", "not present", "not found")):
        return "Missing Element"
    if any(k in d for k in ("tooltip", "hover")):
        return "Tooltip Difference"
    if any(k in d for k in ("font", "text size", "font size")):
        return "Text Style Difference"
    return "Visual Difference"


# ─── POST /report-pairs/{pair_id}/visual-validate ────────────────────────────
# Re-run visual validation for an existing report pair with custom parameters.

class VisualValidateRequest(BaseModel):
    parameters: Optional[dict] = None   # e.g. {"color": False, "legend": True, ...}


@app.post("/report-pairs/{pair_id}/visual-validate")
async def re_run_visual_validate(
    pair_id: int,
    body: VisualValidateRequest,
    db: Session = Depends(get_db),
    x_token: Optional[str] = Header(None),
):
    """Re-run Layer 1 visual comparison for an existing report pair.

    Accepts a parameters dict so users can selectively enable/disable
    comparison attributes (color, legend, axis_labels, etc.).
    All parameters default to True (strict mode) when omitted.
    """
    pair = db.query(ReportPair).filter(ReportPair.id == pair_id).first()
    if not pair:
        raise HTTPException(status_code=404, detail=f"Report pair {pair_id} not found.")

    if not pair.tableau_screenshot or not pair.powerbi_screenshot:
        raise HTTPException(
            status_code=422,
            detail="Report pair is missing Tableau or Power BI screenshot paths.",
        )

    # Resolve absolute paths (stored as relative "screenshots/<name>")
    def _abs(rel: str) -> str:
        if os.path.isabs(rel):
            return rel
        return str(BACKEND_DIR / rel)

    tab_abs = _abs(pair.tableau_screenshot)
    pbi_abs = _abs(pair.powerbi_screenshot)

    for label, path in [("Tableau", tab_abs), ("Power BI", pbi_abs)]:
        if not os.path.exists(path):
            raise HTTPException(
                status_code=422,
                detail=f"{label} screenshot file not found on server: {path}",
            )

    # Update the pair screenshot paths to absolute so the pipeline can open them
    pair.tableau_screenshot = tab_abs
    pair.powerbi_screenshot = pbi_abs

    # Delete existing VisualResult so we can create a fresh one
    from db.models import VisualResult as VisualResultModel
    existing_vr = db.query(VisualResultModel).filter(
        VisualResultModel.report_pair_id == pair_id
    ).first()
    if existing_vr:
        db.delete(existing_vr)
        db.commit()

    try:
        vr = run_visual_validation(
            db, pair,
            openai_api_key  = config.OPENAI_API_KEY,
            diff_output_dir = str(BACKEND_DIR / "screenshots" / "diffs"),
            parameters      = body.parameters,
        )
        db.refresh(pair)
    except Exception as exc:
        import traceback
        raise HTTPException(status_code=500, detail=f"Visual validation failed: {exc}\n{traceback.format_exc()}")

    # Delegate to the shared serializer so the response shape is identical
    # to what /report-pairs returns via _build_visual_result_dict.
    # We need to temporarily set visual_parameters on vr so the serializer
    # picks up the parameters used in this run.
    if body.parameters and not vr.visual_parameters:
        vr.visual_parameters = json.dumps(body.parameters)

    return _build_visual_result_dict(vr)


# ─── Layer-status helpers ─────────────────────────────────────────────────────

def _infer_semantic_status(sem) -> str:
    """Return the true layer-2 status inferred from actual field data.

    column_value_status is authoritative: if it has run and passed, L2 = PASS.
    DAX expression mismatches (flagged_fields / calc_fields) are only used as
    a fallback when column_value_status has not run (None/PENDING), because the
    model comparator often produces false-positives when the PBIX DataModel is
    XPress9-compressed and its measures cannot be extracted.
    """
    if sem is None:
        return "skipped"

    cv = (getattr(sem, "column_value_status", None) or "").upper()

    # Column value analysis is authoritative when it has actually run.
    if cv == "FAIL":
        return "FAIL"
    if cv == "PASS":
        return "PASS"

    # column_value_status not yet run — fall back to DAX expression comparison.
    if sem.flagged_fields and sem.flagged_fields > 0:
        return "FAIL"
    if any(getattr(cf, "status", None) not in ("MATCH", "PASS", None) for cf in (sem.calc_fields or [])):
        return "FAIL"
    if sem.matched_fields and sem.matched_fields > 0:
        return "PASS"
    if sem.calc_fields and all(getattr(cf, "status", None) in ("MATCH", "PASS") for cf in sem.calc_fields):
        return "PASS"

    # Last resort: use the stored status
    s = (sem.status or "PENDING").upper()
    if s not in ("PENDING", ""):
        return s
    return "PENDING"


def _infer_data_status(dat) -> str:
    """Return the true layer-3 status, inferring from table comparisons when stored status is PENDING."""
    if dat is None:
        return "skipped"
    s = (dat.status or "PENDING").upper()
    if s not in ("PENDING", ""):
        return s
    # Infer: any failing table comparison → FAIL
    comparisons = dat.table_comparisons or []
    if any(getattr(t, "result", None) not in ("PASS", "pass", None) for t in comparisons):
        return "FAIL"
    if comparisons:
        return "PASS"
    return "PENDING"


# ─── GET /report-pairs ────────────────────────────────────────────────────────
@app.get("/report-pairs")
async def list_report_pairs(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_username),
):
    from db.models import RelationshipResult, RelationshipDetail, SemanticResult, CalcField, DataResult, TableComparison

    user_project = db.query(MigrationProject).filter(MigrationProject.owner == current_user).first()
    project_id = user_project.id if user_project else -1

    pairs = db.query(ReportPair).filter(ReportPair.project_id == project_id).options(
        joinedload(ReportPair.relationship_result).joinedload(RelationshipResult.details),
        joinedload(ReportPair.semantic_result).joinedload(SemanticResult.calc_fields),
        joinedload(ReportPair.data_result).joinedload(DataResult.table_comparisons),
        joinedload(ReportPair.visual_result)
    ).order_by(ReportPair.created_at.desc()).all()
    
    output = []
    # Maps the diff-type label (from _visual_diff_type) → parameter key used in params_used.
    # Only types that map 1:1 to a configurable parameter are listed here.
    # Generic types (Filter Difference, Missing Element, etc.) are intentionally absent
    # so they are always included in the regression log regardless of exclusions.
    _DIFF_TYPE_TO_PARAM: dict[str, str] = {
        "Chart Type Difference":   "chart_type",
        "Color Scheme Difference": "color",
        "Legend Difference":       "legend",
        "Title Difference":        "title",
        "Data Labels Difference":  "data_labels",
        "Axis Labels Difference":  "axis_labels",
        "Layout Difference":       "layout",
        "Text Style Difference":   "text_content",
    }

    for p in pairs:
        differences = []

        # Pre-compute visual result dict once — reused for layer1Status and diff filtering.
        vis_dict = _build_visual_result_dict(p.visual_result) if p.visual_result else None

        # Resolve which parameters are active for this pair (used to filter regression log).
        if p.visual_result and p.visual_result.visual_parameters:
            from visual.prompts import DEFAULT_PARAMS as _DEFAULT_PARAMS
            _stored = json.loads(p.visual_result.visual_parameters)
            _params_used: dict[str, bool] = {**_DEFAULT_PARAMS, **_stored}
        elif p.visual_result:
            from visual.prompts import DEFAULT_PARAMS as _DEFAULT_PARAMS
            _params_used = dict(_DEFAULT_PARAMS)
        else:
            _params_used = {}

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
        # Only add a regression log entry when the difference's mapped parameter is NOT excluded.
        if p.visual_result and p.visual_result.ai_key_differences:
            try:
                visual_diffs = json.loads(p.visual_result.ai_key_differences)
                for vd in visual_diffs:
                    diff_type = _visual_diff_type(vd)
                    param_key = _DIFF_TYPE_TO_PARAM.get(diff_type)
                    # If this diff maps to a known parameter and that parameter is excluded, skip it.
                    if param_key and not _params_used.get(param_key, True):
                        continue
                    differences.append({
                        "type": diff_type,
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

        # Layer 2: Semantic Model — column data content mismatches
        if p.semantic_result and getattr(p.semantic_result, "column_value_status", None) == "FAIL":
            try:
                cv_details = json.loads(p.semantic_result.column_value_details or "[]")
                for tbl in cv_details:
                    if tbl.get("result") == "FAIL":
                        mismatched = tbl.get("mismatched_columns", 0)
                        total = tbl.get("columns_analyzed", 0)
                        differences.append({
                            "type": "Data Content Mismatch",
                            "detail": (
                                f"Table '{tbl.get('table_name', 'Unknown')}': "
                                f"{mismatched}/{total} column(s) have value-set differences"
                            ),
                            "severity": "high",
                            "layer": "L2"
                        })
            except Exception:
                pass

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

        # Derive effective L1 status from parameterResults so excluded params don't cause FAIL.
        # vis_dict["status"] is already computed by _build_visual_result_dict using params_used.
        effective_l1 = vis_dict["status"] if vis_dict else "skipped"
        l2_status    = _infer_semantic_status(p.semantic_result)

        # ── L3: read measure equivalence result before computing l3_status ────────────────
        # l3_result_data must be resolved first so that l3_status is driven by the PBIT
        # measure-equivalence output, not the table-level DataResult comparisons.
        l3_result_data = json.loads(p.l3_result_json) if p.l3_result_json else None
        if l3_result_data and "description" not in l3_result_data:
            _s   = l3_result_data.get("summary", {})
            _tot = _s.get("total_measures", 0)
            _f   = _s.get("failed", 0)
            _u   = _s.get("unknown", 0)
            _mp  = _s.get("missing_in_pbit", [])
            _mt  = _s.get("missing_in_twbx", [])
            if not l3_result_data.get("measure_results") and _tot == 0:
                l3_result_data["description"] = "No measures found to compare."
                l3_result_data["status"] = "PASS"
            elif l3_result_data.get("status") == "PASS":
                l3_result_data["description"] = (
                    f"All {_tot} measure(s) are semantically equivalent between Tableau and Power BI."
                )
            else:
                _parts = []
                if _f:  _parts.append(f"{_f} measure(s) failed equivalence check")
                if _u:  _parts.append(f"{_u} measure(s) could not be determined")
                if _mp: _parts.append(f"{len(_mp)} measure(s) missing in Power BI")
                if _mt: _parts.append(f"{len(_mt)} measure(s) missing in Tableau")
                l3_result_data["description"] = (
                    f"Measure equivalence check failed: {', '.join(_parts)} (out of {_tot} total measure(s))."
                    if _parts else "Measure equivalence check failed."
                )

        # L3 = measure equivalence (PBIT) only.  When no PBIT was uploaded, L3 is skipped.
        # Table-schema comparison lives in l2/data and is captured separately below.
        if l3_result_data and l3_result_data.get("status"):
            l3_status = l3_result_data["status"].upper()
        else:
            l3_status = "skipped"

        # Data-layer status (table schema comparison) — separate from L3 measure equivalence.
        # Contributes to overall even when L3 is skipped (no PBIT uploaded).
        data_status = _infer_data_status(p.data_result)

        # Recompute overall status from effective layer results — never use the stale stored value,
        # because parameter exclusions may have changed L1 from FAIL → PASS after the original run.
        # Rule: FAIL if any layer = FAIL, otherwise PASS.
        effective_overall = (
            "FAIL"
            if any((s or "").upper() == "FAIL" for s in [effective_l1, l2_status, l3_status, data_status])
            else "PASS"
        )

        # ── Append L3 measure failures to the regression log differences ──────────
        if l3_result_data:
            for m in l3_result_data.get("measure_results", []):
                if m.get("verdict") == "FAIL":
                    differences.append({
                        "type": "Measure Mismatch",
                        "detail": m.get("reason") or f"Measure '{m.get('measure', 'unknown')}' failed equivalence check.",
                        "severity": "high",
                        "layer": "L3",
                    })
            for name in l3_result_data.get("summary", {}).get("missing_in_pbit", []):
                differences.append({
                    "type": "Measure Mismatch",
                    "detail": f"Measure '{name}' exists in Tableau but is missing in Power BI.",
                    "severity": "high",
                    "layer": "L3",
                })
            for name in l3_result_data.get("summary", {}).get("missing_in_twbx", []):
                differences.append({
                    "type": "Measure Mismatch",
                    "detail": f"Measure '{name}' exists in Power BI but is missing in Tableau.",
                    "severity": "high",
                    "layer": "L3",
                })

        # ── L3 description from measure equivalence result ───────────────────────
        layer3_description = l3_result_data.get("description") if l3_result_data else None

        output.append({
            "id": str(p.id),
            "runId": str(p.run_id) if p.run_id else None,
            "reportName": p.report_name,
            "overallStatus": effective_overall,
            "layer1Status": effective_l1,
            "layer2Status": l2_status,
            "layer3Status": l3_status,
            "differences": differences,
            "visualResult": vis_dict,
            "tableauWorkbook": p.tableau_workbook,
            "powerbiReportName": p.powerbi_report_name,
            "tableauScreenshot": get_screenshot_url(p.tableau_screenshot),
            "powerBiScreenshot": get_screenshot_url(p.powerbi_screenshot),
            "createdAt": p.created_at.isoformat(),
            "layer2Details": {
                "columnValueStatus":  getattr(p.semantic_result, "column_value_status", None),
                "columnValueDetails": [
                    {
                        "tableName":          tbl.get("table_name", "Unknown"),
                        "pbixTableName":      tbl.get("pbix_name"),
                        "result":             tbl.get("result", "SKIPPED"),
                        "columnsAnalyzed":    tbl.get("columns_analyzed", 0),
                        "mismatchedColumns":  tbl.get("mismatched_columns", 0),
                        "failureReasons":     tbl.get("failure_reasons", []),
                        "twbxColumns":        tbl.get("twbx_columns", []),
                        "pbixColumns":        tbl.get("pbix_columns", []),
                        "rowCountTableau":    tbl.get("twbx_row_count"),
                        "rowCountPowerBi":    tbl.get("pbix_row_count"),
                        "columnAnalyses": [
                            {
                                "columnName":          col.get("column_name"),
                                "result":              col.get("result", "PASS"),
                                "overlapPct":          col.get("overlap_pct", 100.0),
                                "mismatchPct":         col.get("mismatch_pct", 0.0),
                                "twbxUniqueCount":     col.get("twbx_unique_count", 0),
                                "pbixUniqueCount":     col.get("pbix_unique_count", 0),
                                "onlyInTwbx":          col.get("only_in_twbx", []),
                                "onlyInPbix":          col.get("only_in_pbix", []),
                                "onlyInTwbxCount":     col.get("only_in_twbx_count", 0),
                                "onlyInPbixCount":     col.get("only_in_pbix_count", 0),
                                "twbxPreviewTruncated": col.get("twbx_preview_truncated", False),
                                "pbixPreviewTruncated": col.get("pbix_preview_truncated", False),
                                "numericStats":        col.get("numeric_stats"),
                            }
                            for col in tbl.get("column_analyses", [])
                        ],
                    }
                    for tbl in json.loads(
                        getattr(p.semantic_result, "column_value_details", None) or "[]"
                    )
                ] if p.semantic_result else [],
            } if p.semantic_result else None,
            "layer3Details": [
                {
                    "tableName":            t.table_name,
                    "result":               t.result,
                    "matchMethod":          t.match_method,
                    "rowCountTableau":      t.row_count_twbx,
                    "rowCountPowerBi":      t.row_count_pbix,
                    "rowCountDiffPct":      t.row_count_diff_pct,
                    "columnCountTableau":   t.column_count_twbx,
                    "columnCountPowerBi":   t.column_count_pbix,
                    "columnsMatched":       json.loads(t.columns_matched or "[]"),
                    "columnsMissingInPbi":  json.loads(t.columns_missing_in_pbix or "[]"),
                    "columnsMissingInTwbx": json.loads(t.columns_missing_in_twbx or "[]"),
                    "columnTypeMismatches": json.loads(t.column_type_mismatches or "[]"),
                    "failureReasons":       t.failure_reasons.split(", ") if t.failure_reasons else [],
                }
                for t in (p.data_result.table_comparisons if p.data_result else [])
            ] if p.data_result else [],
            "l3Result": l3_result_data,
            "layer3Description": layer3_description,
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
                        "match_method": t.match_method or "unknown",
                        "row_count_twbx": t.row_count_twbx,
                        "row_count_pbix": t.row_count_pbix,
                        "row_count_diff_pct": t.row_count_diff_pct,
                        "column_count_twbx": t.column_count_twbx,
                        "column_count_pbix": t.column_count_pbix,
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
                },
                "column_value_analysis": {
                    "result": pair.semantic_result.column_value_status if pair.semantic_result else "PENDING",
                    "details": json.loads(pair.semantic_result.column_value_details or "[]") if pair.semantic_result else []
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
async def list_results(
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_username),
):
    user_project = db.query(MigrationProject).filter(MigrationProject.owner == current_user).first()
    project_id = user_project.id if user_project else -1

    # Only return run IDs that belong to this user's project
    runs = db.query(ValidationRun).filter(ValidationRun.project_id == project_id).all()
    run_ids = [str(r.id) for r in runs]

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


# ─── POST /debug/parse-tables ──────────────────────────────────────────────────
@app.post("/debug/parse-tables")
async def debug_parse_tables(
    twbx: UploadFile = File(...),
    pbix: UploadFile = File(...),
):
    """
    Debug endpoint: parse both files and return the raw table names found
    in each, plus what _match_tables() produces.  Useful for diagnosing
    why a table shows as 'unmatched' in L2.
    """
    import tempfile, shutil
    from parsers.twbx_parser import TwbxParser
    from parsers.pbix_parser import PbixParser
    from comparators.data_comparator import _match_tables, _name_similarity

    import tempfile, shutil as _shutil, zipfile as _zipfile
    tmp = tempfile.mkdtemp()
    try:
        twbx_path = os.path.join(tmp, twbx.filename)
        pbix_path = os.path.join(tmp, pbix.filename)
        with open(twbx_path, "wb") as f:
            shutil.copyfileobj(twbx.file, f)
        with open(pbix_path, "wb") as f:
            shutil.copyfileobj(pbix.file, f)

        # ── PBIX zip inventory ────────────────────────────────────────────
        pbix_zip_files = []
        datamodel_header_hex = None
        datamodel_size = None
        try:
            with _zipfile.ZipFile(pbix_path, "r") as zf:
                pbix_zip_files = zf.namelist()
                for name in zf.namelist():
                    if name.endswith("DataModel") or name == "DataModel":
                        info = zf.getinfo(name)
                        datamodel_size = info.file_size
                        with zf.open(name) as dm:
                            first_bytes = dm.read(16)
                        datamodel_header_hex = first_bytes.hex()
        except Exception as ze:
            pbix_zip_files = [f"zip read error: {ze}"]

        tw = TwbxParser(twbx_path)
        tw.parse()
        twbx_tables = tw.get_data_tables()

        pb = PbixParser(pbix_path)
        pb.parse()
        pbix_tables = pb.get_data_tables()

        # ── Internal parser state diagnostics ────────────────────────────
        pbix_raw_tables = pb.tables  # Dict[str, Dict] with name/columns/row_count
        data_model_keys = list(pb.data_model.keys()) if pb.data_model else []
        decoded_datamodel_len = len(pb._decoded_datamodel) if pb._decoded_datamodel else 0
        raw_datamodel_len = len(pb._raw_datamodel) if pb._raw_datamodel else 0

        # Similarity matrix between all pairs
        similarity_matrix = []
        for t in twbx_tables:
            for p in pbix_tables:
                similarity_matrix.append({
                    "twbx": t,
                    "pbix": p,
                    "similarity": round(_name_similarity(t, p), 3),
                })
        similarity_matrix.sort(key=lambda x: -x["similarity"])

        matches = _match_tables(twbx_tables, pbix_tables)

        tw.cleanup()
        pb.cleanup()

        return {
            "twbx_tables": {
                name: {"rows": len(df), "columns": list(df.columns)}
                for name, df in twbx_tables.items()
            },
            "pbix_tables": {
                name: {"rows": len(df), "columns": list(df.columns)}
                for name, df in pbix_tables.items()
            },
            "similarity_matrix": similarity_matrix[:30],
            "match_results": matches,
            # ── Diagnostics ──────────────────────────────────────────────
            "pbix_diagnostics": {
                "zip_contents": pbix_zip_files,
                "datamodel_found": any("DataModel" in n for n in pbix_zip_files),
                "datamodel_size_bytes": datamodel_size,
                "datamodel_header_hex": datamodel_header_hex,
                "data_model_json_keys": data_model_keys,
                "decoded_datamodel_chars": decoded_datamodel_len,
                "raw_datamodel_bytes": raw_datamodel_len,
                "raw_tables_extracted": {
                    name: {
                        "columns": [c["name"] for c in info.get("columns", [])],
                        "row_count": info.get("row_count"),
                    }
                    for name, info in pbix_raw_tables.items()
                },
            },
        }
    finally:
        _shutil.rmtree(tmp, ignore_errors=True)


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