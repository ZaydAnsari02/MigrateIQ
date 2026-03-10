from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from typing import List, Literal, Optional

try:
    from openai import OpenAI, AzureOpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False
    OpenAI = None       # type: ignore[assignment,misc]
    AzureOpenAI = None  # type: ignore[assignment,misc]

import config
from visual.prompts import (
    SYSTEM_PROMPT as _SYSTEM_PROMPT,
    USER_PROMPT as _USER_PROMPT,
    CORRECTION_PROMPT as _CORRECTION_PROMPT,
    SPATIAL_SYSTEM_PROMPT as _SPATIAL_SYSTEM_PROMPT,
    SPATIAL_USER_PROMPT as _SPATIAL_USER_PROMPT,
    SPATIAL_CORRECTION_PROMPT as _SPATIAL_CORRECTION_PROMPT,
)

logger = logging.getLogger(__name__)

# Valid risk level literals — used for validation after parsing.
RiskLevel = Literal["low", "medium", "high"]
_VALID_RISK_LEVELS: frozenset[str] = frozenset({"low", "medium", "high"})

# Required keys in the GPT-4o JSON response.
_REQUIRED_KEYS: frozenset[str] = frozenset({
    "chart_type_match",
    "color_scheme_match",
    "layout_match",
    "axis_labels_match",
    "legend_match",
    "title_match",
    "data_labels_match",
    "key_differences",
    "summary",
    "risk_level",
    "recommendation",
})


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class VisionAnalysis:
    """
    Fully structured, immutable output from GPT-4o Vision.
    Every field is typed — no raw dicts exposed to callers.
    """

    # Per-attribute match booleans
    chart_type_match:   bool
    color_scheme_match: bool
    layout_match:       bool
    axis_labels_match:  bool
    legend_match:       bool
    title_match:        bool
    data_labels_match:  bool

    # Narrative fields
    key_differences: tuple    # ("Bar chart is now a column chart", ...)
    summary:         str      # one-paragraph human-readable explanation
    risk_level:      str      # "low" | "medium" | "high"
    recommendation:  str      # what the migration team needs to fix

    # Audit trail — never displayed to end users
    raw_response: str

    # Whether this result came from a successful API call or the error fallback
    is_error_fallback: bool = False

    @property
    def match_count(self) -> int:
        """Number of visual attributes that match (out of 7)."""
        flags = [
            self.chart_type_match, self.color_scheme_match, self.layout_match,
            self.axis_labels_match, self.legend_match, self.title_match,
            self.data_labels_match,
        ]
        return sum(flags)

    @property
    def is_high_risk(self) -> bool:
        return self.risk_level == "high"


# ── Image encoding ─────────────────────────────────────────────────────────────

def _encode_image_b64(path: str) -> str:
    """
    Read a file and return its Base64-encoded content as a UTF-8 string.

    Raises:
        FileNotFoundError: if the path does not exist
    """
    p = os.path.abspath(path)
    if not os.path.exists(p):
        raise FileNotFoundError(f"Screenshot not found: {path}")
    with open(p, "rb") as fh:
        return base64.b64encode(fh.read()).decode("utf-8")


def _build_image_block(path: str) -> dict:
    """
    Build one OpenAI image content block from a local PNG file.
    detail="high" uses GPT-4o's full 2048-tile resolution — important for
    reading axis labels and small chart elements.
    """
    return {
        "type": "image_url",
        "image_url": {
            "url":    f"data:image/png;base64,{_encode_image_b64(path)}",
            "detail": "high",
        },
    }


# ── Response parsing ───────────────────────────────────────────────────────────

def _parse_response(raw: str) -> VisionAnalysis:
    """
    Parse the raw GPT-4o JSON string into a VisionAnalysis.

    Raises:
        json.JSONDecodeError: if the response is not valid JSON
        ValueError: if required keys are missing or risk_level is unrecognised
    """
    data = json.loads(raw)    # raises json.JSONDecodeError if invalid

    # Validate all required keys are present
    missing = _REQUIRED_KEYS - data.keys()
    if missing:
        raise ValueError(f"GPT-4o response missing required keys: {missing!r}")

    # Validate risk_level value
    risk = str(data["risk_level"]).strip().lower()
    if risk not in _VALID_RISK_LEVELS:
        raise ValueError(
            f"Unexpected risk_level {risk!r}. Expected one of {_VALID_RISK_LEVELS}."
        )

    return VisionAnalysis(
        chart_type_match   = bool(data["chart_type_match"]),
        color_scheme_match = bool(data["color_scheme_match"]),
        layout_match       = bool(data["layout_match"]),
        axis_labels_match  = bool(data["axis_labels_match"]),
        legend_match       = bool(data["legend_match"]),
        title_match        = bool(data["title_match"]),
        data_labels_match  = bool(data["data_labels_match"]),
        key_differences    = tuple(data["key_differences"]),
        summary            = str(data["summary"]),
        risk_level         = risk,
        recommendation     = str(data["recommendation"]),
        raw_response       = raw,
        is_error_fallback  = False,
    )


def _make_error_result(reason: str) -> VisionAnalysis:
    """
    Fallback VisionAnalysis returned when all API retries are exhausted.
    Sets is_error_fallback=True and risk_level="high" so the pipeline
    escalates the pair to FAIL status, triggering manual review.
    """
    logger.error("GPT-4o analysis failed — returning error fallback. Reason: %s", reason)
    return VisionAnalysis(
        chart_type_match   = False,
        color_scheme_match = False,
        layout_match       = False,
        axis_labels_match  = False,
        legend_match       = False,
        title_match        = False,
        data_labels_match  = False,
        key_differences    = ("GPT-4o analysis failed — manual review required",),
        summary            = f"Automated analysis could not complete: {reason}",
        risk_level         = "high",
        recommendation     = "Review this report pair manually before sign-off.",
        raw_response       = "",
        is_error_fallback  = True,
    )


# ── Spatial diff dataclasses ───────────────────────────────────────────────────

@dataclass(frozen=True)
class DiffBox:
    """
    Normalised bounding box returned by GPT-4o spatial analysis.
    All values are floats in [0.0, 1.0] relative to image dimensions.
    """
    x1: float
    y1: float
    x2: float
    y2: float

    def is_valid(self) -> bool:
        """Return False if the box is degenerate (all-zero or inverted)."""
        return (
            0.0 <= self.x1 < self.x2 <= 1.0
            and 0.0 <= self.y1 < self.y2 <= 1.0
            and (self.x2 - self.x1) > 0.01   # at least 1 % of image width
            and (self.y2 - self.y1) > 0.01
        )

    def to_pixels(self, img_w: int, img_h: int) -> tuple:
        """Convert to integer pixel coordinates (x1, y1, x2, y2)."""
        return (
            max(0, int(self.x1 * img_w)),
            max(0, int(self.y1 * img_h)),
            min(img_w - 1, int(self.x2 * img_w)),
            min(img_h - 1, int(self.y2 * img_h)),
        )


@dataclass(frozen=True)
class SpatialDifference:
    """One localised difference between the Tableau and Power BI report."""
    label:       str
    tableau_box: Optional[DiffBox]   # None if element is absent in Tableau
    powerbi_box: Optional[DiffBox]   # None if element is absent in Power BI


@dataclass(frozen=True)
class SpatialAnalysis:
    """
    Full spatial analysis result from GPT-4o.
    Each entry in `differences` has normalised bounding boxes so callers can
    draw precise ellipses without any keyword-to-zone heuristics.

    tableau_content / powerbi_content are the chart-canvas viewports that
    GPT-4o identified — all difference boxes are clipped to these viewports
    so chrome regions can never be annotated.
    """
    differences:       tuple          # tuple[SpatialDifference, ...]
    summary:           str
    risk_level:        str            # "low" | "medium" | "high"
    raw_response:      str
    tableau_content:   Optional[DiffBox] = None   # chart canvas in Tableau image
    powerbi_content:   Optional[DiffBox] = None   # chart canvas in Power BI image
    is_error_fallback: bool = False


def _clip_box(box: Optional[DiffBox], viewport: Optional[DiffBox]) -> Optional[DiffBox]:
    """
    Clip `box` so it lies entirely within `viewport`.

    If viewport is None or invalid, the box is returned unmodified.
    If the clipped box becomes degenerate (zero area), None is returned.
    """
    if box is None:
        return None
    if viewport is None or not viewport.is_valid():
        return box

    cx1 = max(box.x1, viewport.x1)
    cy1 = max(box.y1, viewport.y1)
    cx2 = min(box.x2, viewport.x2)
    cy2 = min(box.y2, viewport.y2)

    if cx1 >= cx2 or cy1 >= cy2:
        return None   # box is entirely outside the viewport

    clipped = DiffBox(x1=cx1, y1=cy1, x2=cx2, y2=cy2)
    return clipped if clipped.is_valid() else None


def _parse_spatial_response(raw: str) -> SpatialAnalysis:
    """
    Parse GPT-4o JSON into a SpatialAnalysis.

    Content viewports (tableau_content / powerbi_content) are parsed first,
    then all difference boxes are clipped to their respective viewports so
    chrome regions are guaranteed to be excluded from annotations.
    """
    data = json.loads(raw)

    if "differences" not in data:
        raise ValueError("Response missing 'differences' key")
    if "summary" not in data or "risk_level" not in data:
        raise ValueError("Response missing 'summary' or 'risk_level'")

    risk = str(data["risk_level"]).strip().lower()
    if risk not in _VALID_RISK_LEVELS:
        raise ValueError(f"Unexpected risk_level {risk!r}")

    def _parse_box(raw_box) -> Optional[DiffBox]:
        if raw_box is None:
            return None
        return DiffBox(
            x1=float(raw_box["x1"]),
            y1=float(raw_box["y1"]),
            x2=float(raw_box["x2"]),
            y2=float(raw_box["y2"]),
        )

    # Parse content viewports
    tab_content = _parse_box(data.get("tableau_content"))
    pbi_content = _parse_box(data.get("powerbi_content"))

    # Validate viewports — if malformed, log a warning but continue
    if tab_content and not tab_content.is_valid():
        logger.warning("tableau_content box is invalid: %s — ignoring", tab_content)
        tab_content = None
    if pbi_content and not pbi_content.is_valid():
        logger.warning("powerbi_content box is invalid: %s — ignoring", pbi_content)
        pbi_content = None

    diffs: List[SpatialDifference] = []
    for i, item in enumerate(data["differences"]):
        if "label" not in item:
            raise ValueError(f"differences[{i}] missing 'label'")

        # Parse raw boxes then clip to content viewport
        raw_tab = _parse_box(item.get("tableau_box"))
        raw_pbi = _parse_box(item.get("powerbi_box"))

        clipped_tab = _clip_box(raw_tab, tab_content)
        clipped_pbi = _clip_box(raw_pbi, pbi_content)

        # Skip this difference entirely if BOTH boxes were clipped away (pure chrome)
        if raw_tab is not None and clipped_tab is None and raw_pbi is not None and clipped_pbi is None:
            logger.debug("Skipping difference %d (%r) — both boxes outside content viewports", i, item["label"])
            continue

        diffs.append(SpatialDifference(
            label       = str(item["label"]),
            tableau_box = clipped_tab,
            powerbi_box = clipped_pbi,
        ))

    logger.debug(
        "Parsed %d differences (from %d raw); tab_content=%s pbi_content=%s",
        len(diffs), len(data["differences"]), tab_content, pbi_content,
    )

    return SpatialAnalysis(
        differences      = tuple(diffs),
        summary          = str(data["summary"]),
        risk_level       = risk,
        raw_response     = raw,
        tableau_content  = tab_content,
        powerbi_content  = pbi_content,
    )


def _make_spatial_error(reason: str) -> SpatialAnalysis:
    logger.error("Spatial analysis failed — returning error fallback. Reason: %s", reason)
    return SpatialAnalysis(
        differences       = (),
        summary           = f"Automated spatial analysis could not complete: {reason}",
        risk_level        = "high",
        raw_response      = "",
        is_error_fallback = True,
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def analyze_with_gpt4o(
    tableau_path: str,
    powerbi_path: str,
    api_key:      Optional[str] = None,
    max_retries:  int = 2,
    timeout:      int = 60,
) -> VisionAnalysis:
    """
    Send a Tableau + Power BI screenshot pair to GPT-4o Vision for analysis.

    The function builds the image pair message once, then retries up to
    max_retries times if GPT-4o returns malformed or incomplete JSON,
    feeding the bad response back with a correction prompt each time.

    Args:
        tableau_path:  local path to the Tableau screenshot PNG
        powerbi_path:  local path to the Power BI screenshot PNG
        api_key:       OpenAI API key; falls back to OPENAI_API_KEY in config/env
        max_retries:   number of extra attempts if JSON is malformed (default 2)
        timeout:       HTTP request timeout in seconds (default 60)

    Returns:
        VisionAnalysis — fully typed and immutable; callers must check
        is_error_fallback to distinguish real results from safe fallbacks.

    Raises:
        FileNotFoundError: immediately if either screenshot path does not exist
        (all other errors are caught internally and returned as error fallbacks)
    """
    if not _OPENAI_AVAILABLE:
        return _make_error_result(
            "openai package not installed — run: pip install openai"
        )

    # Validate paths before making any API call — fast-fail with a clear message.
    for label, path in [("Tableau", tableau_path), ("Power BI", powerbi_path)]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"{label} screenshot not found: {path}")

    # Prefer Azure when endpoint is configured; fall back to standard OpenAI.
    use_azure = bool(config.AZURE_OPENAI_ENDPOINT)

    if use_azure:
        resolved_key = api_key or config.AZURE_OPENAI_API_KEY
        if not resolved_key:
            return _make_error_result(
                "No Azure OpenAI API key provided. Set AZURE_OPENAI_API_KEY in .env."
            )
        client = AzureOpenAI(
            api_key        = resolved_key,
            azure_endpoint = config.AZURE_OPENAI_ENDPOINT,
            api_version    = config.AZURE_OPENAI_API_VERSION,
            timeout        = timeout,
        )
        model_or_deployment = config.AZURE_OPENAI_DEPLOYMENT
        logger.info(
            "Calling Azure OpenAI deployment=%r for: Tableau=%r  PowerBI=%r",
            model_or_deployment, tableau_path, powerbi_path,
        )
    else:
        resolved_key = api_key or config.OPENAI_API_KEY
        if not resolved_key:
            return _make_error_result(
                "No OpenAI API key provided. Set OPENAI_API_KEY in .env or pass api_key."
            )
        client = OpenAI(api_key=resolved_key, timeout=timeout)
        model_or_deployment = config.GPT4O_MODEL
        logger.info(
            "Calling %s Vision for: Tableau=%r  PowerBI=%r",
            model_or_deployment, tableau_path, powerbi_path,
        )

    # Build the initial message list.
    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                _build_image_block(tableau_path),   # first image  = Tableau original
                _build_image_block(powerbi_path),   # second image = Power BI migration
                {"type": "text", "text": _USER_PROMPT},
            ],
        },
    ]

    last_error = "unknown error"

    for attempt in range(max_retries + 1):
        logger.debug("%s attempt %d/%d", model_or_deployment, attempt + 1, max_retries + 1)

        try:
            response = client.chat.completions.create(
                model           = model_or_deployment,
                messages        = messages,
                response_format = {"type": "json_object"},  # guarantees valid JSON wrapper
                max_tokens      = config.GPT4O_MAX_TOKENS,
                temperature     = config.GPT4O_TEMPERATURE,
            )
        except Exception as exc:
            last_error = f"OpenAI API error: {exc}"
            logger.warning("%s API call failed (attempt %d): %s", model_or_deployment, attempt + 1, exc)
            # No retry correction possible without a response — break immediately.
            break

        raw = response.choices[0].message.content or ""

        try:
            result = _parse_response(raw)
            logger.info(
                "%s analysis complete: risk=%s, differences=%d",
                model_or_deployment, result.risk_level, len(result.key_differences),
            )
            return result

        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            last_error = str(exc)
            logger.warning(
                "%s response parse failed (attempt %d): %s", model_or_deployment, attempt + 1, exc
            )

            if attempt < max_retries:
                # Feed the bad response back so GPT-4o can self-correct.
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": _CORRECTION_PROMPT.format(error=last_error),
                })

    return _make_error_result(last_error)


def analyze_with_spatial_diff(
    tableau_path: str,
    powerbi_path: str,
    api_key:      Optional[str] = None,
    max_retries:  int = 2,
    timeout:      int = 90,
) -> SpatialAnalysis:
    """
    Send a Tableau + Power BI screenshot pair to GPT-4o Vision and ask it to
    return BOUNDING BOX COORDINATES for each visual difference.

    GPT-4o is instructed to:
      • Ignore all application chrome (browser tabs, sidebars, toolbars)
      • Focus exclusively on the report visual area
      • Return normalised (0.0–1.0) x1/y1/x2/y2 boxes for both images
      • Mark absent elements (e.g. legend only in Power BI) with null boxes

    The result is a SpatialAnalysis whose .differences tuple contains
    SpatialDifference objects, each with a DiffBox for Tableau and Power BI.
    Callers can convert to pixel coords via DiffBox.to_pixels(img_w, img_h).

    Returns:
        SpatialAnalysis — callers should check is_error_fallback.
    """
    if not _OPENAI_AVAILABLE:
        return _make_spatial_error("openai package not installed")

    for label, path in [("Tableau", tableau_path), ("Power BI", powerbi_path)]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"{label} screenshot not found: {path}")

    use_azure = bool(config.AZURE_OPENAI_ENDPOINT)

    if use_azure:
        resolved_key = api_key or config.AZURE_OPENAI_API_KEY
        if not resolved_key:
            return _make_spatial_error("No Azure OpenAI API key configured")
        client = AzureOpenAI(
            api_key        = resolved_key,
            azure_endpoint = config.AZURE_OPENAI_ENDPOINT,
            api_version    = config.AZURE_OPENAI_API_VERSION,
            timeout        = timeout,
        )
        model_or_deployment = config.AZURE_OPENAI_DEPLOYMENT
    else:
        resolved_key = api_key or config.OPENAI_API_KEY
        if not resolved_key:
            return _make_spatial_error("No OpenAI API key configured")
        client = OpenAI(api_key=resolved_key, timeout=timeout)
        model_or_deployment = config.GPT4O_MODEL

    logger.info(
        "Spatial diff: calling %r for Tableau=%r  PowerBI=%r",
        model_or_deployment, tableau_path, powerbi_path,
    )

    messages: list[dict] = [
        {"role": "system", "content": _SPATIAL_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                _build_image_block(tableau_path),
                _build_image_block(powerbi_path),
                {"type": "text", "text": _SPATIAL_USER_PROMPT},
            ],
        },
    ]

    last_error = "unknown error"

    for attempt in range(max_retries + 1):
        logger.debug("Spatial diff attempt %d/%d", attempt + 1, max_retries + 1)
        try:
            response = client.chat.completions.create(
                model           = model_or_deployment,
                messages        = messages,
                response_format = {"type": "json_object"},
                max_tokens      = max(config.GPT4O_MAX_TOKENS, 1500),
                temperature     = config.GPT4O_TEMPERATURE,
            )
        except Exception as exc:
            last_error = f"API error: {exc}"
            logger.warning("Spatial diff API call failed (attempt %d): %s", attempt + 1, exc)
            break

        raw = response.choices[0].message.content or ""

        try:
            result = _parse_spatial_response(raw)
            logger.info(
                "Spatial diff complete: risk=%s, regions=%d",
                result.risk_level, len(result.differences),
            )
            return result
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            last_error = str(exc)
            logger.warning("Spatial diff parse failed (attempt %d): %s", attempt + 1, exc)
            if attempt < max_retries:
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": _SPATIAL_CORRECTION_PROMPT.format(error=last_error),
                })

    return _make_spatial_error(last_error)