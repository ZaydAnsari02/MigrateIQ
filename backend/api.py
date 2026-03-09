import os
import json
import uuid
import shutil
import subprocess
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MigrateIQ API", version="1.0.0")

# ─── CORS ─────────────────────────────────────────────────────────────────────
# Allow the Next.js dev server (port 3000) and any production origin you add.
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
Path("temp").mkdir(exist_ok=True)
Path("results").mkdir(exist_ok=True)


# ─── POST /validate ───────────────────────────────────────────────────────────
# Accepts .twbx and .pbix files, runs compare_reports.py, returns JSON result.
# The run_id is embedded in the response so the frontend can poll /results/{run_id}.
@app.post("/validate")
async def validate_reports(
    twbx: UploadFile = File(...),
    pbix:  UploadFile = File(...),
):
    run_id = str(uuid.uuid4())

    twbx_path   = f"temp/{run_id}_{twbx.filename}"
    pbix_path   = f"temp/{run_id}_{pbix.filename}"
    output_path = f"results/{run_id}.json"

    # Save uploaded files to disk
    try:
        with open(twbx_path, "wb") as f:
            shutil.copyfileobj(twbx.file, f)
        with open(pbix_path, "wb") as f:
            shutil.copyfileobj(pbix.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {e}")

    # Run the comparison script
    proc = subprocess.run(
    [
        "python",
        "compare_reports.py",
        "--twbx", twbx_path,
        "--pbix", pbix_path,
        "--output", output_path,
    ],
    capture_output=True,
    text=True,
)

    if proc.returncode not in (0, 1):  # 0 = PASS, 1 = FAIL are both valid
        raise HTTPException(
            status_code=500,
            detail=f"Comparison script error: {proc.stderr}",
        )

    if not Path(output_path).exists():
        raise HTTPException(status_code=500, detail="Result file was not generated.")

    with open(output_path) as f:
        result = json.load(f)

    # Attach the run_id so the frontend can reference it later
    result["run_id"] = run_id

    # Clean up temp input files (keep results/)
    Path(twbx_path).unlink(missing_ok=True)
    Path(pbix_path).unlink(missing_ok=True)

    return result


# ─── GET /results/{run_id} ────────────────────────────────────────────────────
# Fetch a previously-generated result by run ID.
@app.get("/results/{run_id}")
async def get_result(run_id: str):
    output_path = Path(f"results/{run_id}.json")
    if not output_path.exists():
        raise HTTPException(status_code=404, detail=f"Result {run_id} not found.")
    with open(output_path) as f:
        return json.load(f)


# ─── GET /results ─────────────────────────────────────────────────────────────
# List all stored result run IDs (lightweight — no full payloads).
@app.get("/results")
async def list_results():
    results_dir = Path("results")
    run_ids = [f.stem for f in results_dir.glob("*.json")]
    return {"run_ids": run_ids, "count": len(run_ids)}


# ─── GET /health ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "MigrateIQ API"}