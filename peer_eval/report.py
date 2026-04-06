"""
Report generation and output formatting.
"""

import json
import logging
from pathlib import Path
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
            level = flag.get("suspicion_level", "baixo")

            level_emoji = {"alto": "🔴", "medio": "🟡", "baixo": "🟢"}.get(level, "⚪")

            print(f"{level_emoji} {flag_type.upper()} - {persons}")
            print(f"   MRs: {mrs}")
            print(f"   Evidência: {evidence}")
            print(f"   Alternativa legítima: {alternative}")
            print()

        summary = group_report.get("summary", {})
        summary_str = f"Total: {summary.get('total_mrs')} MRs, {summary.get('total_persons')} membros"
        flags_summary = summary.get("flags_by_level", {})
        if any(flags_summary.values()):
            summary_str += f" | Flags: 🔴 {flags_summary.get('alto', 0)} 🟡 {flags_summary.get('medio', 0)} 🟢 {flags_summary.get('baixo', 0)}"
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


def generate_narrative_report(
    mr_artifacts: List[Dict],
    llm_estimates: Optional[List[Dict]],
    scores: Dict,
    group_report: Optional[Dict],
    api_key: str,
    output_path: str = "output/narrative_report.txt"
) -> Optional[str]:
    """
    Generate a narrative text report via a single Claude API call (live mode only).

    Produces a human-readable analysis in the style of a conversational session:
    per-member qualitative breakdown, incident chains, alerts, and recommendations.
    Saved as plain text separate from the auditable JSON reports.

    Args:
        mr_artifacts: List of MR artifacts (with commit_log if available)
        llm_estimates: List of LLM estimates (E, A, T_review, P per MR)
        scores: Per-member scores from scorer.compute_scores()
        group_report: Group report with flags from Stage 2b
        api_key: Anthropic API key
        output_path: Where to save the narrative text file

    Returns:
        Generated narrative text, or None if the API call fails
    """
    import anthropic

    est_by_id = {e["mr_id"]: e for e in (llm_estimates or [])}

    # Compact MR summary
    mr_summaries = []
    for mr in mr_artifacts:
        est = est_by_id.get(mr["mr_id"], {})
        mr_summaries.append({
            "mr_id": mr["mr_id"],
            "author": mr.get("author"),
            "title": mr.get("title", "")[:80],
            "type": mr.get("type_declared"),
            "opened_at": mr.get("opened_at", "")[:10],
            "merged_at": mr.get("merged_at", "")[:10],
            "reviewers": mr.get("reviewers", []),
            "X": mr.get("quantitative", {}).get("X"),
            "E": est.get("E", {}).get("value"),
            "A": est.get("A", {}).get("value"),
            "T_review": est.get("T_review", {}).get("value"),
        })

    # Compact scores
    scores_summary = {
        member: {
            "nota": round(s["nota"], 3),
            "Abs": round(s["Abs"], 3),
            "Rel": round(s["Rel"], 3),
        }
        for member, s in scores.items()
    }

    # Commit timeline (capped at 100 entries to control token usage)
    timeline_entries = []
    for mr in mr_artifacts:
        for c in mr.get("commit_log", []):
            timeline_entries.append({
                "authored_at": c.get("authored_at", "")[:16],
                "author": c.get("author"),
                "message": c.get("message", "")[:80],
                "mr_id": mr["mr_id"],
            })
    timeline_entries.sort(key=lambda c: c["authored_at"])

    data = {
        "mrs": mr_summaries,
        "scores": scores_summary,
        "flags": group_report.get("flags", []) if group_report else [],
        "commit_timeline": timeline_entries[:100],
    }

    system_prompt = (
        "Você é um analista de contribuições em projetos de software acadêmicos.\n"
        "Recebe dados estruturados de um sprint e gera um relatório narrativo completo em português.\n\n"
        "SEÇÕES OBRIGATÓRIAS:\n"
        "1. Visão geral do período (datas, total de MRs, membros ativos)\n"
        "2. Tabela de contribuição por membro (MRs, nota, tipo predominante)\n"
        "3. Análise qualitativa individual (por membro: pontos fortes e padrões observados)\n"
        "4. Cadeia de problemas identificada (somente se houver flags cascata_de_fixes "
        "ou burst_de_vespera — caso contrário, omita a seção)\n"
        "5. Sinais de alerta e boas práticas\n"
        "6. Conclusão e recomendações\n\n"
        "REGRAS:\n"
        "- Use linguagem direta e objetiva.\n"
        "- Cite MR IDs e usernames como evidência.\n"
        "- Não invente dados. Se uma seção não tiver evidências, diga explicitamente.\n"
        "- Não repita os dados brutos — interprete-os.\n"
        "- Seção 4 deve reconstruir a cadeia causal (quem causou trabalho para quem e quando)."
    )

    user_message = (
        "Gere o relatório narrativo com base nos dados abaixo:\n\n"
        + json.dumps(data, ensure_ascii=False, indent=2)
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=config.LLM_MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        narrative = response.content[0].text

        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        output_path_obj.write_text(narrative, encoding="utf-8")

        logger.info(f"Narrative report saved to {output_path}")
        return narrative

    except Exception as e:
        logger.error(f"Failed to generate narrative report: {e}")
        return None
