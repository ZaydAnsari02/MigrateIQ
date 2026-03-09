"""
visual/prompts.py
-----------------
All GPT-4o Vision prompt strings for the Layer 1 visual analysis.

Keeping prompts in a dedicated module makes them easy to:
  • Review and iterate on without touching business logic.
  • Diff across versions in git without noise from other changes.
  • Swap for A/B testing or model-specific variants.

These strings are imported by gpt4o_analyzer.py — do not import
business logic back from there (avoid circular imports).
"""

from __future__ import annotations

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are a BI report quality analyst specialising in Tableau to Power BI migrations. "
    "You receive two dashboard screenshots and identify visual differences that would cause "
    "stakeholders to reject the migrated report. Be specific and factual. "
    "Do not infer or guess — only report what you can clearly see in the images."
)

# ── User prompt ───────────────────────────────────────────────────────────────
# Sent alongside the two encoded images (Tableau first, Power BI second).

USER_PROMPT = """
The FIRST image is the original Tableau report.
The SECOND image is the migrated Power BI report.

Return ONLY a valid JSON object with exactly these keys. No prose, no markdown fences.

{
  "chart_type_match":   true or false,
  "color_scheme_match": true or false,
  "layout_match":       true or false,
  "axis_labels_match":  true or false,
  "legend_match":       true or false,
  "title_match":        true or false,
  "data_labels_match":  true or false,
  "key_differences": [
    "specific difference 1",
    "specific difference 2"
  ],
  "summary": "One paragraph. What changed and whether it would impact stakeholder acceptance.",
  "risk_level": "low" or "medium" or "high",
  "recommendation": "Concrete action the migration team must take before sign-off."
}

Risk level rules:
  low    — cosmetic differences only (minor colour shade, small padding change)
  medium — noticeable differences but the data story is intact
  high   — chart type changed, axis range misleads, data appears different

If the reports are visually identical return empty key_differences: []
Be specific: say "bar chart uses #1F77B4 blue in Tableau but #FF7F0E orange in Power BI"
not just "colours differ".
"""

# ── Self-correction prompt ────────────────────────────────────────────────────
# Appended when GPT-4o returns malformed or incomplete JSON so it can
# self-correct without starting a new API call.

CORRECTION_PROMPT = (
    "Your previous response was invalid. Error: {error}. "
    "Please respond again with ONLY a valid JSON object matching the exact schema "
    "I requested. No prose, no markdown fences, no extra keys."
)
