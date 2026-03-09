from __future__ import annotations

import json
import logging
from typing import Optional

import config
from visual.pixel_diff import (
    compute_pixel_diff,
    GPT4O_CALL_THRESHOLD,
    PASS_THRESHOLD,
    REVIEW_THRESHOLD,
)
from visual.gpt4o_analyzer import analyze_with_gpt4o, VisionAnalysis
from db.models import VisualResult, ReportPair, Status, Risk

logger = logging.getLogger(__name__)


# ── Single report validation ───────────────────────────────────────────────────

def run_visual_validation(
    session,
    report_pair:     ReportPair,
    openai_api_key:  Optional[str] = None,
    diff_output_dir: str = "screenshots/diffs",
) -> VisualResult:
    """
    Run Layer 1 visual validation for a single ReportPair.

    Persists a VisualResult to the database and updates
    report_pair.overall_status with precedence-aware promotion
    (FAIL > REVIEW > PASS > PENDING).

    Args:
        session:         SQLAlchemy-compatible session
        report_pair:     must have tableau_screenshot and powerbi_screenshot set
        openai_api_key:  OpenAI key; falls back to OPENAI_API_KEY in config/env
        diff_output_dir: directory where the red-highlight diff PNG is saved

    Returns:
        VisualResult — the persisted record

    Raises:
        ValueError: if report_pair is missing screenshot paths
    """
    name = report_pair.report_name

    # Guard: both screenshots must be set before we can do anything.
    if not report_pair.tableau_screenshot:
        raise ValueError(f"[{name}] tableau_screenshot is not set on ReportPair")
    if not report_pair.powerbi_screenshot:
        raise ValueError(f"[{name}] powerbi_screenshot is not set on ReportPair")

    logger.info("Starting visual validation for %r", name)

    # ── Stage 1: Pixel diff ──────────────────────────────────────────────────
    pixel = compute_pixel_diff(
        tableau_path    = report_pair.tableau_screenshot,
        powerbi_path    = report_pair.powerbi_screenshot,
        diff_output_dir = diff_output_dir,
        report_name     = name,
    )

    logger.info(
        "[%s] Pixel similarity: %.1f%%  |  hash distance: %d/64",
        name, pixel.similarity_pct, pixel.hash_distance,
    )

    # ── Stage 2: GPT-4o Vision (only when needed) ────────────────────────────
    vision:       Optional[VisionAnalysis] = None
    gpt4o_called: bool                     = False

    if pixel.should_call_gpt4o:
        logger.info(
            "[%s] Similarity %.1f%% < %.1f%% threshold — calling GPT-4o Vision",
            name, pixel.similarity_pct, GPT4O_CALL_THRESHOLD,
        )
        vision       = analyze_with_gpt4o(
            tableau_path = report_pair.tableau_screenshot,
            powerbi_path = report_pair.powerbi_screenshot,
            api_key      = openai_api_key or config.OPENAI_API_KEY,
        )
        gpt4o_called = True
        logger.info("[%s] GPT-4o risk: %s", name, vision.risk_level.upper())

        for diff in vision.key_differences[:3]:   # log first 3 for visibility
            logger.info("[%s]   • %s", name, diff)
    else:
        logger.info(
            "[%s] Similarity %.1f%% ≥ %.1f%% — GPT-4o skipped (reports are visually identical)",
            name, pixel.similarity_pct, GPT4O_CALL_THRESHOLD,
        )

    # ── Stage 3: Determine final status ─────────────────────────────────────
    status = _determine_status(pixel.similarity_pct, vision)
    logger.info("[%s] Final status: %s", name, status.upper())

    # ── Stage 4: Persist to database ─────────────────────────────────────────
    vr = _build_visual_result(report_pair, pixel, vision, gpt4o_called, status)
    session.add(vr)

    _promote_pair_status(report_pair, status, vision)

    session.commit()

    return vr


def _determine_status(
    similarity_pct: float,
    vision: Optional[VisionAnalysis],
) -> str:
    """
    Derive the final PASS / REVIEW / FAIL status from pixel similarity and
    optional GPT-4o risk level.

    Escalation rules:
      - PASS or REVIEW + GPT-4o HIGH risk → FAIL
        (GPT-4o may catch meaningful structural issues the pixel diff misses)
      - REVIEW + non-HIGH GPT-4o risk → stays REVIEW
      - FAIL is never downgraded

    Args:
        similarity_pct: pixel similarity percentage (0.0–100.0)
        vision:         GPT-4o result, or None if GPT-4o was not called

    Returns:
        One of Status.PASS, Status.REVIEW, Status.FAIL
    """
    if similarity_pct >= PASS_THRESHOLD:
        base_status = Status.PASS
    elif similarity_pct >= REVIEW_THRESHOLD:
        base_status = Status.REVIEW
    else:
        base_status = Status.FAIL

    # Escalate to FAIL if GPT-4o signals high risk — regardless of base status.
    # This catches cases where the pixel diff is small but the change is critical
    # (e.g. axis labels truncated, chart type subtly changed).
    if vision and vision.is_high_risk and base_status in (Status.PASS, Status.REVIEW):
        logger.info(
            "Status escalated %s → FAIL because GPT-4o flagged high risk",
            base_status.upper(),
        )
        return Status.FAIL

    return base_status


def _build_visual_result(
    report_pair:  ReportPair,
    pixel,
    vision:       Optional[VisionAnalysis],
    gpt4o_called: bool,
    status:       str,
) -> VisualResult:
    """
    Construct a VisualResult ORM object from pipeline outputs.
    Keeps the pipeline function readable by isolating field mapping here.
    """
    return VisualResult(
        report_pair_id       = report_pair.id,

        # Pixel diff metrics
        pixel_similarity_pct = pixel.similarity_pct,
        pixel_diff_count     = pixel.diff_pixel_count,
        total_pixels         = pixel.total_pixels,
        hash_distance        = pixel.hash_distance,
        diff_image_path      = pixel.diff_image_path,
        compared_width       = pixel.compared_width,
        compared_height      = pixel.compared_height,

        # GPT-4o fields (None when GPT-4o was not called)
        gpt4o_called       = gpt4o_called,
        chart_type_match   = vision.chart_type_match   if vision else None,
        color_scheme_match = vision.color_scheme_match if vision else None,
        layout_match       = vision.layout_match       if vision else None,
        axis_labels_match  = vision.axis_labels_match  if vision else None,
        legend_match       = vision.legend_match       if vision else None,
        title_match        = vision.title_match        if vision else None,
        data_labels_match  = vision.data_labels_match  if vision else None,
        ai_summary         = vision.summary            if vision else None,
        ai_key_differences = json.dumps(list(vision.key_differences)) if vision else None,
        ai_recommendation  = vision.recommendation     if vision else None,
        ai_raw_response    = vision.raw_response       if vision else None,
        gpt4o_risk_level   = vision.risk_level         if vision else None,

        status             = status,
        pass_threshold_pct = PASS_THRESHOLD,
    )


# ── Status promotion ───────────────────────────────────────────────────────────

# Shared precedence map: ERROR > FAIL > REVIEW > PASS > PENDING
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
    vision:      Optional[VisionAnalysis],
) -> None:
    """
    Update report_pair.overall_status using worst-case precedence.

    Precedence: ERROR > FAIL > REVIEW > PASS > PENDING

    overall_status only moves in the direction of greater severity —
    a later PASS result never overwrites an earlier FAIL.
    """
    current_rank = _STATUS_PRECEDENCE.get(report_pair.overall_status, 0)
    new_rank     = _STATUS_PRECEDENCE.get(new_status, 0)

    if new_rank > current_rank:
        report_pair.overall_status = new_status
        # Attach the risk level from GPT-4o when available.
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

    Errors on individual pairs are caught so one bad screenshot does not
    abort the whole batch.  Failed pairs receive an ERROR status record.

    Args:
        session:         SQLAlchemy-compatible session
        report_pairs:    list of ReportPair objects to validate
        openai_api_key:  OpenAI key; falls back to OPENAI_API_KEY in config/env
        diff_output_dir: directory where diff PNGs will be saved

    Returns:
        List of VisualResult objects in the same order as report_pairs.
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
    """Log a human-readable summary table after a batch run completes."""
    counts = {
        Status.PASS:   0,
        Status.FAIL:   0,
        Status.REVIEW: 0,
        Status.ERROR:  0,
    }
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

    # Also print to stdout for CI/CD pipeline visibility.
    print(f"\n{separator}")
    print(f"Batch complete: {total} reports")
    print(f"  PASS:   {counts[Status.PASS]}")
    print(f"  FAIL:   {counts[Status.FAIL]}")
    print(f"  REVIEW: {counts[Status.REVIEW]}")
    print(f"  ERROR:  {counts[Status.ERROR]}")
    print(separator)