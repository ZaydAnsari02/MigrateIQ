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
    print(f"  Diff image           : {result.diff_image_path}")
    print(f"  Tableau annotated    : {result.tableau_annotated_path}")
    print(f"  Power BI annotated   : {result.powerbi_annotated_path}")
    print(f"  Side-by-side         : {result.comparison_image_path}")
    print(f"\n  Thresholds used:")
    print(f"    PASS   if similarity >= {PASS_THRESHOLD}%")
    print(f"    REVIEW if similarity >= {REVIEW_THRESHOLD}%")
    print(f"    FAIL   below that")
    print(f"    GPT-4o called when similarity < {GPT4O_CALL_THRESHOLD}%")

    return {
        "similarity_pct"        : result.similarity_pct,
        "diff_pixel_count"      : result.diff_pixel_count,
        "total_pixels"          : result.total_pixels,
        "hash_distance"         : result.hash_distance,
        "status"                : result.status,
        "should_call_gpt4o"     : result.should_call_gpt4o,
        "diff_image_path"       : result.diff_image_path,
        "tableau_annotated_path": result.tableau_annotated_path,
        "powerbi_annotated_path": result.powerbi_annotated_path,
        "comparison_image_path" : result.comparison_image_path,
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

    use_azure = bool(config.AZURE_OPENAI_ENDPOINT)
    active_key = config.AZURE_OPENAI_API_KEY if use_azure else config.OPENAI_API_KEY
    if not active_key:
        print("  ERROR: No API key configured. Set OPENAI_API_KEY or AZURE_OPENAI_API_KEY in backend/.env")
        return {"error": "API key not configured"}

    if use_azure:
        print(f"  Provider      : Azure OpenAI")
        print(f"  Endpoint      : {config.AZURE_OPENAI_ENDPOINT}")
        print(f"  Deployment    : {config.AZURE_OPENAI_DEPLOYMENT}")
        print(f"  API version   : {config.AZURE_OPENAI_API_VERSION}")
    else:
        print(f"  Provider      : OpenAI")
        print(f"  Model         : {config.GPT4O_MODEL}")
    print(f"  Max tokens    : {config.GPT4O_MAX_TOKENS}")
    print(f"  Temperature   : {config.GPT4O_TEMPERATURE}")
    print(f"  API key       : {'*' * 8}{active_key[-4:]}  (last 4 chars)")
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

    # ── Spatial GPT-4o annotation ─────────────────────────────────────────────
    # Ask GPT-4o to return precise bounding-box coordinates for each difference,
    # ignoring browser/app chrome. Then draw ellipses directly from those coords.
    print("\n" + "=" * 60)
    print("  SPATIAL GPT-4o ANNOTATION")
    print("=" * 60)
    print("  Asking GPT-4o for exact bounding boxes of each difference…")

    from visual.gpt4o_analyzer import analyze_with_spatial_diff
    from visual.pixel_diff import build_gpt4o_annotated_images, _load_normalised

    spatial = analyze_with_spatial_diff(
        tableau_path = TABLEAU_PATH,
        powerbi_path = POWERBI_PATH,
        max_retries  = 2,
        timeout      = 90,
    )

    print(f"  is_error_fallback : {spatial.is_error_fallback}")
    print(f"  Risk level        : {spatial.risk_level.upper()}")
    print(f"  Differences found : {len(spatial.differences)}")
    for i, d in enumerate(spatial.differences, 1):
        tab_box = f"({d.tableau_box.x1:.2f},{d.tableau_box.y1:.2f})-({d.tableau_box.x2:.2f},{d.tableau_box.y2:.2f})" if d.tableau_box else "absent"
        pbi_box = f"({d.powerbi_box.x1:.2f},{d.powerbi_box.y1:.2f})-({d.powerbi_box.x2:.2f},{d.powerbi_box.y2:.2f})" if d.powerbi_box else "absent"
        print(f"  {i}. {d.label}")
        print(f"     Tableau  box: {tab_box}")
        print(f"     Power BI box: {pbi_box}")

    tab_gpt_path  = str(Path(DIFF_OUT_DIR) / "test_report_tableau_gpt4o.png")
    pbi_gpt_path  = str(Path(DIFF_OUT_DIR) / "test_report_powerbi_gpt4o.png")
    comp_gpt_path = str(Path(DIFF_OUT_DIR) / "test_report_comparison_gpt4o.png")

    if not spatial.is_error_fallback and spatial.differences:
        arr_t = _load_normalised(TABLEAU_PATH)
        arr_p = _load_normalised(POWERBI_PATH)
        build_gpt4o_annotated_images(
            arr_t, arr_p, spatial,
            tab_gpt_path, pbi_gpt_path,
            comp_out_path  = comp_gpt_path,
            similarity_pct = pixel_result["similarity_pct"],
        )
        print(f"\n  Tableau  (spatial ellipses): {tab_gpt_path}")
        print(f"  Power BI (spatial ellipses): {pbi_gpt_path}")
        print(f"  Comparison (spatial):        {comp_gpt_path}")

    spatial_diffs_out = [
        {
            "label":       d.label,
            "tableau_box": {"x1": d.tableau_box.x1, "y1": d.tableau_box.y1,
                            "x2": d.tableau_box.x2, "y2": d.tableau_box.y2}
                           if d.tableau_box else None,
            "powerbi_box": {"x1": d.powerbi_box.x1, "y1": d.powerbi_box.y1,
                            "x2": d.powerbi_box.x2, "y2": d.powerbi_box.y2}
                           if d.powerbi_box else None,
        }
        for d in spatial.differences
    ]
    output["spatial_annotation"] = {
        "risk_level":       spatial.risk_level,
        "is_error":         spatial.is_error_fallback,
        "differences":      spatial_diffs_out,
        "summary":          spatial.summary,
        "tableau_path":     tab_gpt_path,
        "powerbi_path":     pbi_gpt_path,
        "comparison_path":  comp_gpt_path,
    }

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
