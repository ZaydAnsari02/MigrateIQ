"""
visual/prompts.py
-----------------
GPT-4o Vision prompt strings for the visual comparison layer.

Architecture:
  GPT now returns structured pass/fail/ignored per parameter — no boolean
  conversion needed.  The parameter table is the single source of truth and
  differences are generated only from failed parameters.
"""

from __future__ import annotations

import json as _json

# ── Parameter name mapping ────────────────────────────────────────────────────
# Maps internal backend key  →  GPT JSON key in "visual_parameters"

PARAM_TO_GPT: dict[str, str] = {
    "chart_type":   "chart_type_consistency",
    "color":        "color_consistency",
    "legend":       "legend_validation",
    "axis_labels":  "axis_labels",
    "axis_scale":   "axis_scale_consistency",
    "title":        "chart_title",
    "data_labels":  "data_labels",
    "layout":       "layout_alignment",
    "text_content": "text_content",
}

# Reverse mapping: GPT key → internal key
GPT_TO_PARAM: dict[str, str] = {v: k for k, v in PARAM_TO_GPT.items()}

# ── Default parameters (all enabled = strict mode) ────────────────────────────

DEFAULT_PARAMS: dict[str, bool] = {
    "chart_type":   True,
    "color":        True,
    "legend":       True,
    "axis_labels":  True,
    "axis_scale":   True,
    "title":        True,
    "data_labels":  True,
    "layout":       True,
    "text_content": True,
    "text_case":    True,   # sub-flag: affects text_content evaluation only
}

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert Business Intelligence dashboard migration validator.

Your task is to compare two chart screenshots:
  Image 1: Source chart from Tableau
  Image 2: Migrated chart from Power BI

You must determine whether the migrated chart faithfully reproduces the original visual representation.

Focus on visual structure and semantic meaning, not pixel similarity.

STRICT RULES:
1. Your output must be structured JSON only. Do not include any text outside the JSON.
2. Each parameter must return exactly one of: "pass", "fail", or "ignored".
3. "differences" must ONLY list items whose corresponding parameter is "fail".
   - If a parameter is "pass" or "ignored", do NOT mention it in differences.
   - If a parameter is "fail", its reason MUST appear in differences.
4. Do not guess — only report what you can clearly see.
5. Do not mark "pass" if a meaningful difference exists.
"""

# ── User prompt builder ───────────────────────────────────────────────────────

def build_user_prompt(params: dict | None = None) -> str:
    """
    Build the GPT-4o user prompt with per-parameter instructions.

    Excluded parameters (value = False in params) are listed in
    excluded_parameters so GPT marks them as "ignored" and omits
    them from the differences list.

    Args:
        params: dict of internal_key → bool.  False = excluded / ignored.
                Pass None for full strict validation (all enabled).

    Returns:
        Formatted prompt string.
    """
    p: dict[str, bool] = {**DEFAULT_PARAMS, **(params or {})}

    # Build GPT-name list of excluded parameters
    excluded_gpt: list[str] = [
        PARAM_TO_GPT[k]
        for k, enabled in p.items()
        if not enabled and k in PARAM_TO_GPT
    ]

    # Build case-sensitivity note for text_content
    case_note = (
        "Text comparison is CASE-SENSITIVE."
        if p.get("text_case", True)
        else "Text comparison is CASE-INSENSITIVE — ignore uppercase/lowercase differences."
    )

    excluded_block = ""
    if excluded_gpt:
        excluded_block = f"""
Excluded parameters (mark these as "ignored", do NOT evaluate them, do NOT include in differences):
{_json.dumps(excluded_gpt, indent=2)}
"""

    return f"""IMAGE 1 = Tableau (original source).  IMAGE 2 = Power BI (migrated).

Compare the migrated report against the original and evaluate each parameter below.
{excluded_block}
Parameters to evaluate:

1. chart_type_consistency
   Are both charts the same type? (bar, stacked bar, pie, line, scatter, etc.)
   Even subtle changes like "grouped bar" vs "stacked bar" count as FAIL.

2. color_consistency
   Are categories represented with equivalent color mappings?
   Minor shade variations are acceptable (pass). Different hues or swapped colors = FAIL.

3. legend_validation
   Are legends present and consistent in both charts?
   Missing legend or different labels = FAIL.

4. axis_labels
   Are axis label texts equivalent in both charts?
   Different label text or missing labels = FAIL.

5. axis_scale_consistency
   Are numeric scales comparable? (ranges, min/max, tick marks, orientation)
   Different numeric range or misleading scale = FAIL.

6. chart_title
   Do both charts contain the same or equivalent title?
   Missing or different title = FAIL.

7. data_labels
   Are data labels present/absent consistently?
   Present in one but not the other = FAIL.

8. layout_alignment
   Is the layout structure visually consistent? (bar orientation, chart positioning, spacing)
   Major layout changes = FAIL. Minor padding differences = PASS.

9. text_content
   Do text labels and visible text elements match semantically? {case_note}
   Different or missing text (not covered by other parameters) = FAIL.

Return ONLY valid JSON matching this exact schema — no prose, no markdown fences:

{{
  "visual_parameters": {{
    "chart_type_consistency": "pass" | "fail" | "ignored",
    "color_consistency":      "pass" | "fail" | "ignored",
    "legend_validation":      "pass" | "fail" | "ignored",
    "axis_labels":            "pass" | "fail" | "ignored",
    "axis_scale_consistency": "pass" | "fail" | "ignored",
    "chart_title":            "pass" | "fail" | "ignored",
    "data_labels":            "pass" | "fail" | "ignored",
    "layout_alignment":       "pass" | "fail" | "ignored",
    "text_content":           "pass" | "fail" | "ignored"
  }},
  "differences": [
    "Clear, factual description of difference 1",
    "Clear, factual description of difference 2"
  ],
  "risk_level": "low" | "medium" | "high",
  "summary": "One paragraph describing what changed and whether it impacts stakeholder acceptance.",
  "confidence": 0.0 to 1.0
}}

Risk level rules:
  low    — cosmetic differences only (minor colour shade, small padding)
  medium — noticeable differences but the data story is intact
  high   — chart type changed, axis scale misleads, key data elements missing

IMPORTANT:
- differences[] must ONLY contain items where the parameter is "fail".
- If visual_parameters has a "fail", its reason MUST be in differences[].
- If visual_parameters has "pass" or "ignored", do NOT mention it in differences[].
- excluded_parameters must be marked "ignored" — do not evaluate them.
- Return empty differences array [] if there are no failures.
- Be specific: "Stacked bar chart in Tableau replaced by grouped bar in Power BI" not "chart type differs".
"""


# ── Default USER_PROMPT (strict mode) ────────────────────────────────────────
USER_PROMPT = build_user_prompt(None)

# ── Self-correction prompt ────────────────────────────────────────────────────

CORRECTION_PROMPT = (
    "Your previous response was invalid. Error: {error}. "
    "Respond again with ONLY the valid JSON object matching the exact schema I requested. "
    "No prose, no markdown fences, no extra keys. "
    "Remember: differences[] must only contain items for parameters marked 'fail'. "
    "Excluded parameters must be 'ignored'. All 9 visual_parameters keys are required."
)


# ─────────────────────────────────────────────────────────────────────────────
# Spatial-diff prompts (unchanged)
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
  - Do NOT report differences in chrome/UI.
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
