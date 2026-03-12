"""Layer 3 pipeline — measure-level equivalence validation.

Usage:
    python l3_pipeline.py --twbx path/to/file.twbx --pbit path/to/file.pbit
"""
import argparse
import json
import logging
import re
from typing import Any, Dict, List

from parsers.twbx_parser import TwbxParser
from parsers.pbit_parser import PbitParser
from llm_explainer import generate_explanations

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Name normalisation (spaces ≈ underscores, case-insensitive)
# ---------------------------------------------------------------------------

def _norm(name: str) -> str:
    return re.sub(r"[ _]+", "_", name.lower().strip())


# ---------------------------------------------------------------------------
# Measure matching
# ---------------------------------------------------------------------------

def _match_measures(
    twbx_measures: List[Dict[str, Any]],
    pbit_measures: List[Dict[str, Any]],
) -> Dict[str, List]:
    twbx_by_norm = {_norm(m["name"]): m for m in twbx_measures}
    pbit_by_norm  = {_norm(m["name"]): m for m in pbit_measures}

    matched, missing_in_pbit, missing_in_twbx = [], [], []

    for key in sorted(set(twbx_by_norm) | set(pbit_by_norm)):
        tw = twbx_by_norm.get(key)
        pb = pbit_by_norm.get(key)

        if tw and pb:
            matched.append({
                "name":            tw["name"],
                "tableau_formula": tw.get("expression", ""),
                "dax_formula":     pb.get("expression", ""),
            })
        elif tw:
            missing_in_pbit.append(tw["name"])
        else:
            missing_in_twbx.append(pb["name"])

    return {
        "matched":         matched,
        "missing_in_pbit": missing_in_pbit,
        "missing_in_twbx": missing_in_twbx,
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_l3_validation(twbx_path: str, pbit_path: str) -> Dict[str, Any]:

    # ── 1. Parse ─────────────────────────────────────────────────────────
    logger.info("Parsing TWBX")
    twbx = TwbxParser(twbx_path)
    twbx.parse()
    twbx_measures = twbx.get_measures()
    logger.info(f"TWBX: {len(twbx_measures)} measures found")

    logger.info("Parsing PBIT")
    pbit = PbitParser(pbit_path)
    pbit.parse()
    pbit_measures = pbit.get_measures()
    logger.info(f"PBIT: {len(pbit_measures)} measures found")

    # ── 2. Match measures ─────────────────────────────────────────────────
    match_result = _match_measures(twbx_measures, pbit_measures)
    matched      = match_result["matched"]
    missing_pbit = match_result["missing_in_pbit"]
    missing_twbx = match_result["missing_in_twbx"]

    logger.info(
        f"Measure matching: {len(matched)} matched, "
        f"{len(missing_pbit)} missing in PBIT, "
        f"{len(missing_twbx)} missing in TWBX"
    )

    # ── 3. LLM judgment on matched pairs ──────────────────────────────────
    judged = generate_explanations(matched) if matched else []

    # ── 4. Auto-FAIL unmatched measures ───────────────────────────────────
    for name in missing_pbit:
        judged.append({
            "measure":         name,
            "verdict":         "FAIL",
            "confidence":      "high",
            "reason":          f"Measure '{name}' exists in Tableau but is missing in Power BI.",
            "tableau_formula": next(
                (m.get("expression", "") for m in twbx_measures if m["name"] == name), ""
            ),
            "dax_formula": "",
        })

    for name in missing_twbx:
        judged.append({
            "measure":         name,
            "verdict":         "FAIL",
            "confidence":      "high",
            "reason":          f"Measure '{name}' exists in Power BI but is missing in Tableau.",
            "tableau_formula": "",
            "dax_formula":     next(
                (m.get("expression", "") for m in pbit_measures if m["name"] == name), ""
            ),
        })

    # ── 5. Overall status ─────────────────────────────────────────────────
    overall_status = (
        "PASS"
        if not judged or all(r["verdict"] == "PASS" for r in judged)
        else "FAIL"
    )

    # ── 5a. Top-level description ──────────────────────────────────────────
    total   = len(judged)
    passed  = sum(1 for r in judged if r["verdict"] == "PASS")
    failed  = sum(1 for r in judged if r["verdict"] == "FAIL")
    unknown = sum(1 for r in judged if r["verdict"] == "UNKNOWN")

    if not judged:
        description = "No measures found to compare."
    elif overall_status == "PASS":
        description = (
            f"All {total} measure(s) are semantically equivalent "
            "between Tableau and Power BI."
        )
    else:
        parts: List[str] = []
        if failed:
            parts.append(f"{failed} measure(s) failed equivalence check")
        if unknown:
            parts.append(f"{unknown} measure(s) could not be determined")
        if missing_pbit:
            parts.append(f"{len(missing_pbit)} measure(s) missing in Power BI")
        if missing_twbx:
            parts.append(f"{len(missing_twbx)} measure(s) missing in Tableau")
        description = (
            f"Measure equivalence check failed: {', '.join(parts)} "
            f"(out of {total} total measure(s))."
        )

    # ── 6. Cleanup ────────────────────────────────────────────────────────
    twbx.cleanup()
    pbit.cleanup()

    return {
        "layer":       "L3",
        "status":      overall_status,
        "description": description,
        "summary": {
            "total_measures":  total,
            "passed":          passed,
            "failed":          failed,
            "unknown":         unknown,
            "missing_in_pbit": missing_pbit,
            "missing_in_twbx": missing_twbx,
        },
        "measure_results": judged,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )

    parser = argparse.ArgumentParser(description="L3 measure equivalence validation")
    parser.add_argument("--twbx", required=True, help="Path to .twbx file")
    parser.add_argument("--pbit", required=True, help="Path to .pbit file")
    args = parser.parse_args()

    result = run_l3_validation(args.twbx, args.pbit)
    print(json.dumps(result, indent=2))