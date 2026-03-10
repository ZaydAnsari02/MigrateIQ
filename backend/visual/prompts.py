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


# ─────────────────────────────────────────────────────────────────────────────
# Spatial-diff prompts
# Used by analyze_with_spatial_diff() to obtain bounding-box coordinates for
# each visual difference so they can be drawn as ellipses on the screenshots.
# ─────────────────────────────────────────────────────────────────────────────

SPATIAL_SYSTEM_PROMPT = """\
You are a BI report quality analyst specialising in Tableau to Power BI migrations.
You receive two report screenshots and must locate every visual difference in the
REPORT CONTENT ONLY, returning precise bounding-box coordinates for each difference.

== STEP 1: IDENTIFY THE CONTENT VIEWPORT ==
Before listing any differences, you MUST identify the "content viewport" — the
rectangle that contains ONLY the actual report visual in each image.

The content viewport EXCLUDES:
  - Browser chrome: tab bar, URL bar, bookmarks bar, browser frame
  - Application shell: Power BI ribbon/toolbar, left nav panel, top menu bar,
    Tableau top toolbar, sidebar, filter panel, worksheet tabs at the bottom
  - Any grey/white padding or margin outside the chart canvas
  - Window title bar and OS window controls

The content viewport INCLUDES ONLY:
  - The white/light chart canvas itself
  - Everything drawn on that canvas: chart title, chart body (bars/lines/etc.),
    axis lines and labels, legend box, data labels, colour legend

Return tableau_content and powerbi_content as the tight bounding boxes of the
chart canvas in each image.  These are your reference frames.

== STEP 2: FIND DIFFERENCES WITHIN THE CONTENT VIEWPORT ==
All difference boxes MUST be INSIDE their respective content viewport.
A box that extends to the image edge (x1=0, y1=0, x2=1, y2=1) is WRONG —
it includes chrome.  Be tight.

Rules:
  - Do NOT report differences in chrome/UI.  If the only difference is in
    browser tabs or the app ribbon, report zero differences.
  - If an element is ABSENT in one image, set that image's box to null.
  - Boxes must be tight around the specific changed element (not the whole chart).
  - Prioritise high-impact differences.  Return at most 8.
  - Only report what you can CLEARLY SEE.  Do not guess.

Coordinates are NORMALISED to the FULL IMAGE size (0.0 = top/left, 1.0 = bottom/right).
"""

SPATIAL_USER_PROMPT = """\
IMAGE 1 = Tableau (original).   IMAGE 2 = Power BI (migrated).

TASK: Identify the content viewport of each image, then list all visual differences
in the report content only (zero chrome/UI).

Respond with ONLY a valid JSON object — no prose, no markdown, no extra keys:

{
  "tableau_content": {"x1": 0.00, "y1": 0.00, "x2": 1.00, "y2": 1.00},
  "powerbi_content":  {"x1": 0.00, "y1": 0.00, "x2": 1.00, "y2": 1.00},
  "differences": [
    {
      "label": "short description of what changed",
      "tableau_box": {"x1": 0.00, "y1": 0.00, "x2": 1.00, "y2": 1.00},
      "powerbi_box":  {"x1": 0.00, "y1": 0.00, "x2": 1.00, "y2": 1.00}
    }
  ],
  "summary": "One-paragraph summary of all changes and their migration impact.",
  "risk_level": "low" | "medium" | "high"
}

IMPORTANT:
  - tableau_content and powerbi_content define the chart canvas in each image.
    They exclude ALL browser/app chrome.
  - Every difference box MUST lie inside its content viewport.
  - Use null for a box when that element is absent in that image.
  - risk_level: low=cosmetic, medium=noticeable but data story intact, high=data story changed.
"""

SPATIAL_CORRECTION_PROMPT = (
    "Your previous response was invalid. Error: {error}. "
    "Respond again with ONLY the valid JSON object matching the spatial schema. "
    "Include tableau_content and powerbi_content viewport boxes. "
    "All box coordinates must be floats 0.0–1.0. No prose, no markdown."
)
