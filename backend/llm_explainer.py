"""LLM-based formula equivalence judge for Tableau vs DAX measures."""
import json
import logging
import os
import re
from typing import Any, Dict, List

from groq import Groq

logger = logging.getLogger(__name__)

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = "llama-3.3-70b-versatile"  # best Groq model for reasoning tasks


# ---------------------------------------------------------------------------
# Core judge
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are an expert in both Tableau calculated fields and 
Power BI DAX expressions. Your job is to determine whether a Tableau formula 
and a DAX formula are semantically equivalent — i.e. they would produce the 
same result given the same underlying data.

Common equivalences to recognise:
- SUM([Field]) ↔ SUM(Table[Field])
- COUNTD([Field]) ↔ DISTINCTCOUNT(Table[Field])
- AVG([Field]) ↔ AVERAGE(Table[Field])
- IF condition THEN a ELSE b END ↔ IF(condition, a, b)
- FIXED [dim] : AGG([field]) ↔ CALCULATE(AGG(Table[field]), ALLEXCEPT(...))
- ZN([Field]) ↔ IF(ISBLANK(...), 0, ...)
- DATEDIFF('day', [a], [b]) ↔ DATEDIFF(DAY, Table[a], Table[b])

Be strict: different aggregation functions (SUM vs AVERAGE) or different 
filters are NOT equivalent even if they look similar."""


def judge_measure_pair(
    measure_name: str,
    tableau_formula: str,
    dax_formula: str,
) -> Dict[str, Any]:
    prompt = f"""Compare these two formulas for the measure '{measure_name}':

Tableau: {tableau_formula}
DAX:     {dax_formula}

Reply with ONLY a JSON object — no markdown, no explanation outside the JSON:
{{
  "verdict": "PASS" or "FAIL",
  "confidence": "high", "medium", or "low",
  "reason": "<one concise sentence>"
}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=256,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
        )
        raw = response.choices[0].message.content.strip()

        # Strip accidental markdown fences
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

        parsed = json.loads(raw)
        return {
            "measure":         measure_name,
            "verdict":         parsed.get("verdict", "UNKNOWN").upper(),
            "confidence":      parsed.get("confidence", "low"),
            "reason":          parsed.get("reason", ""),
            "tableau_formula": tableau_formula,
            "dax_formula":     dax_formula,
        }

    except Exception as e:
        logger.warning(f"LLM judgment failed for '{measure_name}': {e}")
        return {
            "measure":         measure_name,
            "verdict":         "UNKNOWN",
            "confidence":      "low",
            "reason":          f"LLM call failed: {e}",
            "tableau_formula": tableau_formula,
            "dax_formula":     dax_formula,
        }


# ---------------------------------------------------------------------------
# Batch entry point
# ---------------------------------------------------------------------------

def generate_explanations(
    matched_pairs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    results = []
    for pair in matched_pairs:
        result = judge_measure_pair(
            measure_name=pair["name"],
            tableau_formula=pair.get("tableau_formula", ""),
            dax_formula=pair.get("dax_formula", ""),
        )
        results.append(result)
        logger.info(
            f"[{result['measure']}] {result['verdict']} "
            f"({result['confidence']}) — {result['reason']}"
        )
    return results