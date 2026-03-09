from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Literal, Optional

try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False
    OpenAI = None  # type: ignore[assignment,misc]

import config
from visual.prompts import (
    SYSTEM_PROMPT as _SYSTEM_PROMPT,
    USER_PROMPT as _USER_PROMPT,
    CORRECTION_PROMPT as _CORRECTION_PROMPT,
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

    resolved_key = api_key or config.OPENAI_API_KEY
    if not resolved_key:
        return _make_error_result(
            "No OpenAI API key provided. Set OPENAI_API_KEY in .env or pass api_key."
        )

    client = OpenAI(api_key=resolved_key, timeout=timeout)

    logger.info(
        "Calling %s Vision for: Tableau=%r  PowerBI=%r",
        config.GPT4O_MODEL, tableau_path, powerbi_path,
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
        logger.debug("%s attempt %d/%d", config.GPT4O_MODEL, attempt + 1, max_retries + 1)

        try:
            response = client.chat.completions.create(
                model           = config.GPT4O_MODEL,
                messages        = messages,
                response_format = {"type": "json_object"},  # guarantees valid JSON wrapper
                max_tokens      = config.GPT4O_MAX_TOKENS,
                temperature     = config.GPT4O_TEMPERATURE,
            )
        except Exception as exc:
            last_error = f"OpenAI API error: {exc}"
            logger.warning("%s API call failed (attempt %d): %s", config.GPT4O_MODEL, attempt + 1, exc)
            # No retry correction possible without a response — break immediately.
            break

        raw = response.choices[0].message.content or ""

        try:
            result = _parse_response(raw)
            logger.info(
                "%s analysis complete: risk=%s, differences=%d",
                config.GPT4O_MODEL, result.risk_level, len(result.key_differences),
            )
            return result

        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            last_error = str(exc)
            logger.warning(
                "%s response parse failed (attempt %d): %s", config.GPT4O_MODEL, attempt + 1, exc
            )

            if attempt < max_retries:
                # Feed the bad response back so GPT-4o can self-correct.
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": _CORRECTION_PROMPT.format(error=last_error),
                })

    return _make_error_result(last_error)