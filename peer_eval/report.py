"""
Report generation and output formatting.
"""

import json
import logging
from typing import Optional, List, Dict
from datetime import datetime
from . import config

logger = logging.getLogger(__name__)


def print_summary(scores: dict, group_report: Optional[dict] = None) -> None:
    """
    Print formatted summary table to terminal.

    Table shows: Aluno, S(p), Abs, Rel, and Nota (%) for each member.

    If group_report has flags, print alerts section below table.

    Args:
        scores: Dict of member scores from scorer.compute_scores()
        group_report: Optional group report dict from Stage 2b
    """
    # Sort by nota descending
    sorted_members = sorted(scores.items(), key=lambda item: item[1]["nota"], reverse=True)

    # Print header
    print()
    print("┌─────────────────────────────────────────────┐")
    print("│  RESULTADO — Modelo de Contribuição v3.0    │")
    print("├──────────┬───────┬───────┬───────┬──────────┤")
    print("│  Aluno   │  S(p) │  Abs  │  Rel  │  Nota    │")
    print("├──────────┼───────┼───────┼───────┼──────────┤")

    # Print rows
    for member_name, member_scores in sorted_members:
        S = member_scores["S"]
        Abs = member_scores["Abs"]
        Rel = member_scores["Rel"]
        nota_pct = member_scores["nota"] * 100

        print(f"│ {member_name:8} │ {S:5.2f} │ {Abs:5.2f} │ {Rel:5.2f} │ {nota_pct:6.1f}%  │")

    print("└──────────┴───────┴───────┴───────┴──────────┘")
    print()

    # Print alerts if any
    if group_report and group_report.get("flags"):
        print("⚠️  ALERTAS DETECTADOS:")
        print()

        for flag in group_report["flags"]:
            flag_type = flag.get("type", "unknown")
            persons = ", ".join(flag.get("persons", []))
            mrs = ", ".join(flag.get("mr_ids", []))
            evidence = flag.get("evidence", "")
            alternative = flag.get("alternative", "")
            level = flag.get("suspicion_level", "bajo")

            level_emoji = {"alto": "🔴", "medio": "🟡", "bajo": "🟢"}.get(level, "⚪")

            print(f"{level_emoji} {flag_type.upper()} - {persons}")
            print(f"   MRs: {mrs}")
            print(f"   Evidência: {evidence}")
            print(f"   Alternativa legítima: {alternative}")
            print()

        summary = group_report.get("summary", {})
        summary_str = f"Total: {summary.get('total_mrs')} MRs, {summary.get('total_persons')} membros"
        flags_summary = summary.get("flags_by_level", {})
        if any(flags_summary.values()):
            summary_str += f" | Flags: 🔴 {flags_summary.get('alto', 0)} 🟡 {flags_summary.get('medio', 0)} 🟢 {flags_summary.get('bajo', 0)}"
        print(summary_str)
        print()


def export_full_report(
    mr_artifacts: List[Dict],
    llm_estimates: Optional[List[Dict]],
    scores: Dict,
    group_report: Optional[Dict],
    output_path: str = "output/full_report.json"
) -> None:
    """
    Export comprehensive JSON report with all details.

    Includes:
    - Full mr_artifacts with added computed fields
    - LLM estimates (or None if not available)
    - Per-member scores with mr_contributions
    - Group report with flags
    - Timestamp and model metadata

    Args:
        mr_artifacts: List of MR artifacts
        llm_estimates: Optional list of LLM estimates
        scores: Member scores dict
        group_report: Optional group report
        output_path: Where to save report
    """
    # Build lookup by MR ID for easy access
    mr_by_id = {mr["mr_id"]: mr for mr in mr_artifacts}
    est_by_id = {}
    if llm_estimates:
        est_by_id = {est["mr_id"]: est for est in llm_estimates}

    # Enrich MR artifacts with computed components if available
    enriched_mrs = []
    for mr in mr_artifacts:
        mr_copy = dict(mr)
        # Add estimated components if available from scores
        if llm_estimates:
            est = est_by_id.get(mr["mr_id"])
            if est:
                mr_copy["estimates"] = est
        enriched_mrs.append(mr_copy)

    # Build full report
    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "model_version": "3.0",
        "configuration": {
            "L": config.L,
            "ALPHA": config.ALPHA,
            "BETA": config.BETA,
            "GATE_A": config.GATE_A,
            "GATE_X": config.GATE_X,
            "GATE_PENALTY": config.GATE_PENALTY,
            "T_AUTHOR": config.T_AUTHOR,
            "T_REVIEWER_MAX": config.T_REVIEWER_MAX
        },
        "artifacts": {
            "total_mrs": len(mr_artifacts),
            "mrs": enriched_mrs
        },
        "estimates": {
            "total_estimates": len(llm_estimates) if llm_estimates else 0,
            "estimates": llm_estimates if llm_estimates else []
        },
        "scores": {
            "members": scores
        },
        "analysis": group_report if group_report else {}
    }

    # Save to disk
    from . import loader
    loader.save_json(report, output_path)

    logger.info(f"Full report exported to {output_path}")
