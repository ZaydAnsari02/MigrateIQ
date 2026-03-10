"""
Standalone test for the Layer 1 visual pipeline.

Tests:
  1. Pixel diff  (compute_pixel_diff)   — fast, no API call
  2. GPT-4o Vision (analyze_with_gpt4o) — real API call

Usage (run from the backend/ directory):
    python test_visual.py

Output:
  - Console: formatted summary
  - File:    test_visual_output.json  (full structured result)
"""

from __future__ import annotations

import json
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_visual")

# ── Resolve image paths ────────────────────────────────────────────────────────
# backend/ is the working dir; files_testing/ is one level up
_REPO_ROOT    = Path(__file__).parent.parent          # MigrateIQ/
_IMAGES_DIR   = _REPO_ROOT / "files_testing"

TABLEAU_PATH  = str(_IMAGES_DIR / "tableau screenshot.png")
POWERBI_PATH  = str(_IMAGES_DIR / "powerbi screenshot.png")
DIFF_OUT_DIR  = str(Path(__file__).parent / "test_output" / "diffs")
OUTPUT_JSON   = str(Path(__file__).parent / "test_visual_output.json")

# ── Validate image files exist before anything else ───────────────────────────
def _check_images() -> bool:
    ok = True
    for label, path in [("Tableau", TABLEAU_PATH), ("Power BI", POWERBI_PATH)]:
        if not Path(path).exists():
            logger.error("MISSING: %s screenshot not found at %s", label, path)
            ok = False
        else:
            size_kb = Path(path).stat().st_size // 1024
            logger.info("FOUND: %s screenshot  →  %s  (%d KB)", label, path, size_kb)
    return ok


# ── Test 1: Pixel diff ─────────────────────────────────────────────────────────
def test_pixel_diff() -> dict:
    from visual.pixel_diff import compute_pixel_diff, PASS_THRESHOLD, REVIEW_THRESHOLD, GPT4O_CALL_THRESHOLD

    print("\n" + "=" * 60)
    print("  LAYER 1a — PIXEL DIFF")
    print("=" * 60)

    result = compute_pixel_diff(
        tableau_path    = TABLEAU_PATH,
        powerbi_path    = POWERBI_PATH,
        diff_output_dir = DIFF_OUT_DIR,
        report_name     = "test_report",
    )

    print(f"  Pixel similarity     : {result.similarity_pct:.2f} %")
    print(f"  Differing pixels     : {result.diff_pixel_count:,} / {result.total_pixels:,}")
    print(f"  Perceptual hash dist : {result.hash_distance} / 64")
    print(f"  Status               : {result.status.upper()}")
    print(f"  GPT-4o needed?       : {'YES' if result.should_call_gpt4o else 'NO'}")
    print(f"  Diff image saved to  : {result.diff_image_path}")
    print(f"\n  Thresholds used:")
    print(f"    PASS   if similarity >= {PASS_THRESHOLD}%")
    print(f"    REVIEW if similarity >= {REVIEW_THRESHOLD}%")
    print(f"    FAIL   below that")
    print(f"    GPT-4o called when similarity < {GPT4O_CALL_THRESHOLD}%")

    return {
        "similarity_pct"   : result.similarity_pct,
        "diff_pixel_count" : result.diff_pixel_count,
        "total_pixels"     : result.total_pixels,
        "hash_distance"    : result.hash_distance,
        "status"           : result.status,
        "should_call_gpt4o": result.should_call_gpt4o,
        "diff_image_path"  : result.diff_image_path,
    }


# ── Test 2: GPT-4o Vision ──────────────────────────────────────────────────────
def test_gpt4o_vision(force_call: bool = False) -> dict:
    """
    force_call=True bypasses the pixel-similarity gate and always calls GPT-4o.
    Useful to verify the API key and response parsing even when images are similar.
    """
    import config
    from visual.gpt4o_analyzer import analyze_with_gpt4o

    print("\n" + "=" * 60)
    print("  LAYER 1b — GPT-4o VISION ANALYSIS")
    print("=" * 60)

    if not config.OPENAI_API_KEY:
        print("  ERROR: OPENAI_API_KEY is not set in backend/.env or environment.")
        return {"error": "OPENAI_API_KEY not configured"}

    print(f"  Model         : {config.GPT4O_MODEL}")
    print(f"  Max tokens    : {config.GPT4O_MAX_TOKENS}")
    print(f"  Temperature   : {config.GPT4O_TEMPERATURE}")
    print(f"  API key       : {'*' * 8}{config.OPENAI_API_KEY[-4:]}  (last 4 chars)")
    print("  Calling API   ...")

    result = analyze_with_gpt4o(
        tableau_path = TABLEAU_PATH,
        powerbi_path = POWERBI_PATH,
        max_retries  = 2,
        timeout      = 60,
    )

    print()
    print(f"  is_error_fallback  : {result.is_error_fallback}")
    print(f"  Risk level         : {result.risk_level.upper()}")
    print(f"  Attributes matched : {result.match_count} / 7")
    print()
    print("  Attribute breakdown:")
    print(f"    chart_type_match   : {result.chart_type_match}")
    print(f"    color_scheme_match : {result.color_scheme_match}")
    print(f"    layout_match       : {result.layout_match}")
    print(f"    axis_labels_match  : {result.axis_labels_match}")
    print(f"    legend_match       : {result.legend_match}")
    print(f"    title_match        : {result.title_match}")
    print(f"    data_labels_match  : {result.data_labels_match}")
    print()
    print(f"  Summary:")
    print(f"    {result.summary}")
    print()
    print(f"  Key differences ({len(result.key_differences)}):")
    for i, diff in enumerate(result.key_differences, 1):
        print(f"    {i}. {diff}")
    print()
    print(f"  Recommendation:")
    print(f"    {result.recommendation}")

    return {
        "is_error_fallback"  : result.is_error_fallback,
        "risk_level"         : result.risk_level,
        "match_count"        : result.match_count,
        "chart_type_match"   : result.chart_type_match,
        "color_scheme_match" : result.color_scheme_match,
        "layout_match"       : result.layout_match,
        "axis_labels_match"  : result.axis_labels_match,
        "legend_match"       : result.legend_match,
        "title_match"        : result.title_match,
        "data_labels_match"  : result.data_labels_match,
        "key_differences"    : list(result.key_differences),
        "summary"            : result.summary,
        "recommendation"     : result.recommendation,
        "raw_response"       : result.raw_response,
    }


# ── Save output ────────────────────────────────────────────────────────────────
def save_output(data: dict) -> None:
    out = Path(OUTPUT_JSON)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n{'=' * 60}")
    print(f"  Full output saved to: {out}")
    print(f"{'=' * 60}\n")


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    print("\n" + "=" * 60)
    print("  MigrateIQ — Visual Layer Test")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print(f"  Tableau  : {TABLEAU_PATH}")
    print(f"  Power BI : {POWERBI_PATH}")

    if not _check_images():
        print("\nAborting: one or more image files are missing.")
        sys.exit(1)

    output: dict = {
        "test_timestamp": datetime.now().isoformat(),
        "images": {
            "tableau": TABLEAU_PATH,
            "powerbi": POWERBI_PATH,
        },
    }

    # Test 1 — Pixel diff (always runs, no API)
    pixel_result = test_pixel_diff()
    output["pixel_diff"] = pixel_result

    # Test 2 — GPT-4o (always forced in this test script so you can verify the API)
    gpt4o_result = test_gpt4o_vision(force_call=True)
    output["gpt4o_vision"] = gpt4o_result

    # Derive overall pipeline decision
    similarity = pixel_result["similarity_pct"]
    if gpt4o_result.get("error"):
        pipeline_status = "ERROR"
    elif gpt4o_result.get("risk_level") == "high":
        pipeline_status = "FAIL (GPT-4o high risk)"
    elif similarity >= 95.0:
        pipeline_status = "PASS"
    elif similarity >= 80.0:
        pipeline_status = "REVIEW"
    else:
        pipeline_status = "FAIL (low similarity)"

    output["pipeline_decision"] = pipeline_status

    print("\n" + "=" * 60)
    print(f"  FINAL PIPELINE DECISION: {pipeline_status}")
    print("=" * 60)

    save_output(output)


if __name__ == "__main__":
    main()
