from __future__ import annotations

import json
import logging
from typing import Dict, Optional

import config
from visual.gpt4o_analyzer import analyze_with_gpt4o, VisionAnalysis
from db.models import VisualResult, ReportPair, Status, Risk

logger = logging.getLogger(__name__)


# ── Single report validation ───────────────────────────────────────────────────

def run_visual_validation(
    session,
    report_pair:     ReportPair,
    openai_api_key:  Optional[str] = None,
    diff_output_dir: str = "screenshots/diffs",
    parameters:      Optional[Dict[str, bool]] = None,
) -> VisualResult:
    """
    Run visual validation for a single ReportPair using GPT-4o Vision only.

    Persists a VisualResult to the database and updates
    report_pair.overall_status with precedence-aware promotion
    (FAIL > REVIEW > PASS > PENDING).

    Args:
        session:         SQLAlchemy-compatible session
        report_pair:     must have tableau_screenshot and powerbi_screenshot set
        openai_api_key:  OpenAI key; falls back to OPENAI_API_KEY in config/env
        diff_output_dir: unused (kept for API compatibility)
        parameters:      dict of enabled flags (True = validate); None = all enabled

    Returns:
        VisualResult — the persisted record

    Raises:
        ValueError: if report_pair is missing screenshot paths
    """
    name = report_pair.report_name

    if not report_pair.tableau_screenshot:
        raise ValueError(f"[{name}] tableau_screenshot is not set on ReportPair")
    if not report_pair.powerbi_screenshot:
        raise ValueError(f"[{name}] powerbi_screenshot is not set on ReportPair")

    logger.info("Starting visual validation for %r", name)

    # ── GPT-4o Vision analysis ────────────────────────────────────────────────
    vision: VisionAnalysis = analyze_with_gpt4o(
        tableau_path = report_pair.tableau_screenshot,
        powerbi_path = report_pair.powerbi_screenshot,
        api_key      = openai_api_key or config.OPENAI_API_KEY,
        parameters   = parameters,
    )

    logger.info("[%s] GPT-4o risk: %s", name, vision.risk_level.upper())
    for diff in vision.key_differences[:3]:
        logger.info("[%s]   • %s", name, diff)

    # ── Determine final status ────────────────────────────────────────────────
    status = _determine_status(vision, parameters)
    logger.info("[%s] Final status: %s", name, status.upper())

    # ── Persist to database ───────────────────────────────────────────────────
    vr = _build_visual_result(report_pair, vision, status, parameters)
    session.add(vr)

    _promote_pair_status(report_pair, status, vision)

    session.commit()

    return vr


def _determine_status(
    vision: VisionAnalysis,
    parameters: Optional[Dict[str, bool]] = None,
) -> str:
    """
    Derive the final PASS / FAIL status from GPT-4o match flags.

    PASS  = No FAIL parameters (excluding ignored)
    FAIL  = Any parameter that is not excluded returns False from GPT

    Args:
        vision:     GPT-4o result
        parameters: dict of enabled flags (True = validate); None = all enabled

    Returns:
        One of Status.PASS, Status.FAIL
    """
    if vision.is_error_fallback:
        logger.info("Status set to FAIL because GPT-4o call failed (error fallback)")
        return Status.FAIL

    # PASS = no parameter has status "fail" (ignored params don't count)
    for param_key, status in vision.visual_parameters.items():
        if status == "fail":
            logger.info("Status set to FAIL: GPT-4o reports mismatch in '%s'", param_key)
            return Status.FAIL

    return Status.PASS


def _build_visual_result(
    report_pair:  ReportPair,
    vision:       VisionAnalysis,
    status:       str,
    parameters:   Optional[Dict[str, bool]] = None,
) -> VisualResult:
    """
    Construct a VisualResult ORM object from GPT-4o pipeline outputs.
    Pixel diff fields are left as None — visual comparison is semantic-only.
    """
    return VisualResult(
        report_pair_id          = report_pair.id,

        # Pixel diff fields — not used; set to None
        pixel_similarity_pct    = None,
        pixel_diff_count        = None,
        total_pixels            = None,
        hash_distance           = None,
        diff_image_path         = None,
        compared_width          = None,
        compared_height         = None,
        tableau_annotated_path  = None,
        powerbi_annotated_path  = None,
        comparison_image_path   = None,

        # GPT-4o fields — store "pass"/"fail"/"ignored" strings from structured result
        gpt4o_called        = True,
        chart_type_match    = vision.visual_parameters.get("chart_type", "ignored"),
        color_scheme_match  = vision.visual_parameters.get("color", "ignored"),
        layout_match        = vision.visual_parameters.get("layout", "ignored"),
        axis_labels_match   = vision.visual_parameters.get("axis_labels", "ignored"),
        axis_scale_match    = vision.visual_parameters.get("axis_scale", "ignored"),
        legend_match        = vision.visual_parameters.get("legend", "ignored"),
        title_match         = vision.visual_parameters.get("title", "ignored"),
        data_labels_match   = vision.visual_parameters.get("data_labels", "ignored"),
        text_content_match  = vision.visual_parameters.get("text_content", "ignored"),
        ai_summary          = vision.summary,
        ai_key_differences  = json.dumps(list(vision.differences)),
        ai_recommendation   = vision.recommendation,
        ai_raw_response     = vision.raw_response,
        gpt4o_risk_level    = vision.risk_level,

        status              = status,
        pass_threshold_pct  = None,
        visual_parameters   = json.dumps(parameters) if parameters else None,
    )


# ── Status promotion ───────────────────────────────────────────────────────────

_STATUS_PRECEDENCE: dict[str, int] = {
    Status.ERROR:   5,
    Status.FAIL:    4,
    Status.REVIEW:  3,
    Status.PASS:    2,
    Status.PENDING: 1,
}


def _promote_pair_status(
    report_pair: ReportPair,
    new_status:  str,
    vision:      VisionAnalysis,
) -> None:
    """
    Update report_pair.overall_status using worst-case precedence.
    Precedence: ERROR > FAIL > REVIEW > PASS > PENDING
    """
    current_rank = _STATUS_PRECEDENCE.get(report_pair.overall_status, 0)
    new_rank     = _STATUS_PRECEDENCE.get(new_status, 0)

    if new_rank > current_rank:
        report_pair.overall_status = new_status
        if vision:
            report_pair.overall_risk = vision.risk_level


# ── Batch runner ───────────────────────────────────────────────────────────────

def run_batch(
    session,
    report_pairs:    list[ReportPair],
    openai_api_key:  Optional[str] = None,
    diff_output_dir: str = "screenshots/diffs",
) -> list[VisualResult]:
    """
    Run visual validation for every ReportPair in the list.
    """
    results: list[VisualResult] = []
    total = len(report_pairs)

    logger.info("Starting batch validation: %d report pairs", total)

    for i, pair in enumerate(report_pairs, 1):
        logger.info("[%d/%d] Processing %r", i, total, pair.report_name)
        try:
            vr = run_visual_validation(session, pair, openai_api_key, diff_output_dir)
            results.append(vr)
        except Exception as exc:
            logger.exception("Unhandled error processing %r: %s", pair.report_name, exc)
            err_vr = VisualResult(
                report_pair_id = pair.id,
                status         = Status.ERROR,
                ai_summary     = f"Pipeline error: {exc}",
            )
            session.add(err_vr)
            pair.overall_status = Status.ERROR
            session.commit()
            results.append(err_vr)

    _log_batch_summary(results, total)
    return results


def _log_batch_summary(results: list[VisualResult], total: int) -> None:
    counts = {Status.PASS: 0, Status.FAIL: 0, Status.REVIEW: 0, Status.ERROR: 0}
    for r in results:
        if r.status in counts:
            counts[r.status] += 1

    separator = "─" * 40
    logger.info(separator)
    logger.info("Batch complete: %d reports", total)
    logger.info("  PASS:   %d", counts[Status.PASS])
    logger.info("  FAIL:   %d", counts[Status.FAIL])
    logger.info("  REVIEW: %d", counts[Status.REVIEW])
    logger.info("  ERROR:  %d", counts[Status.ERROR])
    logger.info(separator)

    print(f"\n{separator}")
    print(f"Batch complete: {total} reports")
    print(f"  PASS:   {counts[Status.PASS]}")
    print(f"  FAIL:   {counts[Status.FAIL]}")
    print(f"  REVIEW: {counts[Status.REVIEW]}")
    print(f"  ERROR:  {counts[Status.ERROR]}")
    print(separator)
