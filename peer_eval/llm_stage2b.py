"""
Stage 2.1 — Detecção de padrões suspeitos cross-MR.

Executado ANTES das avaliações LLM. Detecta:
  - cascata_de_fixes
  - fragmentacao_artificial
  - burst_de_vespera
  - commit_inflado

Os padrões detectados são passados como contexto (context_by_mr, context_by_sha)
para o Stage 2.2 (commits) e Stage 2.3 (MRs).
"""

import anthropic
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from . import config
from .llm_stage2a import load_prompt


# ═══════════════════════════════════════════════════════════════════════════
# Tool Schema — enforces structured group report without text parsing
# ═══════════════════════════════════════════════════════════════════════════

GROUP_ANALYSIS_TOOL: dict = {
    "name": "submit_group_analysis",
    "description": (
        "Submit the structured cross-MR pattern analysis for the group. "
        "Report all detected anomalies with evidence and suspicion level."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "flags": {
                "type": "array",
                "description": "List of detected suspicious patterns",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": [
                                "fragmentacao_artificial",
                                "burst_de_vespera",
                                "commit_inflado",
                                "padding_de_volume",
                                "cascata_de_fixes"
                            ]
                        },
                        "persons":         {"type": "array", "items": {"type": "string"}},
                        "mr_ids":          {"type": "array", "items": {"type": "string"}},
                        "evidence":        {"type": "string"},
                        "alternative":     {"type": "string"},
                        "suspicion_level": {"type": "string", "enum": ["baixo", "medio", "alto"]}
                    },
                    "required": ["type", "persons", "mr_ids", "evidence", "alternative", "suspicion_level"]
                }
            },
            "observations": {
                "type": "array",
                "description": "General observations about the group's workflow",
                "items": {"type": "string"}
            }
        },
        "required": ["flags", "observations"]
    }
}

logger = logging.getLogger(__name__)


def _extract_commit_type(message: str) -> str:
    """Extract conventional commit type from the first line of a commit message."""
    match = re.match(r'^(feat|fix|refactor|revert|docs|test|chore|ci)[\(:! ]', message.lower())
    return match.group(1) if match else "unknown"


def _build_cross_mr_timeline(mr_artifacts: List[Dict]) -> List[Dict]:
    """
    Build a global timeline of all commits across all MRs, sorted by authored_at.

    MRs without commit_log (e.g., fixture data) are skipped gracefully.

    Returns:
        List of {sha, author, authored_at, message, type, files_touched, mr_id}
        sorted chronologically.
    """
    timeline = []
    for mr in mr_artifacts:
        for commit in mr.get("commit_log", []):
            timeline.append({
                "sha": commit["sha"],
                "author": commit.get("author", mr.get("author", "unknown")),
                "authored_at": commit["authored_at"],
                "message": commit["message"],
                "type": _extract_commit_type(commit["message"]),
                "files_touched": commit.get("files_touched", []),
                "mr_id": mr["mr_id"],
            })
    timeline.sort(key=lambda c: c["authored_at"])
    return timeline


def _mock_group_report(
    mr_artifacts: List[Dict],
    llm_estimates: List[Dict],
    members: List[str],
    deadline: str
) -> dict:
    """
    Detect suspicious patterns heuristically from fixture.

    Looks for:
    - fragmentacao_artificial: MRs from same author < 2h apart, same files
    - burst_de_vespera: ≥50% of MRs in last 3 days
    - commit_inflado: High X but low A/E
    - padding_de_volume: High X but low A/E

    Args:
        mr_artifacts: List of MR artifacts
        llm_estimates: List of LLM estimates (with E, A, P values)
        members: List of team members
        deadline: Deadline ISO string

    Returns:
        Group report dict with flags and observations
    """
    flags = []
    observations = []
    flags_by_level = {"alto": 0, "medio": 0, "baixo": 0}

    # Build lookup tables
    mr_by_id = {mr["mr_id"]: mr for mr in mr_artifacts}
    est_by_id = {est["mr_id"]: est for est in llm_estimates}

    # Parse deadline
    try:
        deadline_dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        deadline_dt = datetime.now()

    # ===== Check for burst_de_vespera =====
    # Last 3 days before deadline
    three_days_before = deadline_dt - timedelta(days=3)

    for member in members:
        member_mrs = [mr for mr in mr_artifacts if mr.get("author") == member]
        if len(member_mrs) < 2:
            continue

        # Count MRs in last 3 days
        try:
            recent_mrs = [
                mr for mr in member_mrs
                if datetime.fromisoformat(mr.get("opened_at", "").replace("Z", "+00:00")) > three_days_before
            ]
        except (ValueError, AttributeError):
            recent_mrs = []

        if len(recent_mrs) >= max(2, len(member_mrs) * 0.5):  # ≥50% or at least 2
            # Check average T_review
            avg_t_review = 0.0
            review_count = 0
            for mr in member_mrs:
                est = est_by_id.get(mr["mr_id"])
                if est and "T_review" in est:
                    avg_t_review += est["T_review"].get("value", 0.0)
                    review_count += 1

            if review_count > 0:
                avg_t_review /= review_count

            if avg_t_review < 0.10:
                flags.append({
                    "type": "burst_de_vespera",
                    "persons": [member],
                    "mr_ids": [mr["mr_id"] for mr in recent_mrs],
                    "evidence": f"{len(recent_mrs)} of {len(member_mrs)} MRs em últimos 3 dias, T_review médio=0.{int(avg_t_review*100):.0f}",
                    "alternative": "Planejamento pobre ou sprint final intenso legítimo",
                    "suspicion_level": "medio"
                })
                flags_by_level["medio"] += 1

    # ===== Check for fragmentacao_artificial =====
    for member in members:
        member_mrs = sorted(
            [mr for mr in mr_artifacts if mr.get("author") == member],
            key=lambda m: m.get("opened_at", "")
        )

        if len(member_mrs) < 2:
            continue

        for i in range(len(member_mrs) - 1):
            mr1 = member_mrs[i]
            mr2 = member_mrs[i + 1]

            try:
                t1 = datetime.fromisoformat(mr1.get("opened_at", "").replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(mr2.get("opened_at", "").replace("Z", "+00:00"))
                delta = (t2 - t1).total_seconds() / 3600  # hours
            except (ValueError, AttributeError):
                continue

            # Check if < 2 hours apart
            if delta < 2.0:
                # Check if they touch same files
                files1 = set(f["file"] for f in mr1.get("diff_summary", []))
                files2 = set(f["file"] for f in mr2.get("diff_summary", []))
                overlap = files1 & files2

                if overlap:
                    flags.append({
                        "type": "fragmentacao_artificial",
                        "persons": [member],
                        "mr_ids": [mr1["mr_id"], mr2["mr_id"]],
                        "evidence": f"{mr1['mr_id']} e {mr2['mr_id']} abertos com {delta:.1f}h de intervalo, {len(overlap)} arquivos em comum",
                        "alternative": "Múltiplos PRs independentes para refatoração em paralelo",
                        "suspicion_level": "baixo"
                    })
                    flags_by_level["baixo"] += 1

    # ===== Check for commit_inflado =====
    for member in members:
        member_mrs = [mr for mr in mr_artifacts if mr.get("author") == member]
        if len(member_mrs) < 2:
            continue

        inflated_count = 0
        for mr in member_mrs:
            quant = mr.get("quantitative", {})
            est = est_by_id.get(mr["mr_id"], {})
            X = quant.get("X", 0.0)
            E_val = est.get("E", {}).get("value", 0.5)
            type_decl = mr.get("type_declared", "").lower()

            # High X but low E on feat/fix = suspicious
            if X > 0.5 and E_val < 0.4 and type_decl in ["feat", "fix"]:
                inflated_count += 1

        if inflated_count >= max(2, len(member_mrs) * 0.5):
            flags.append({
                "type": "commit_inflado",
                "persons": [member],
                "mr_ids": [mr["mr_id"] for mr in member_mrs],
                "evidence": f"{inflated_count} de {len(member_mrs)} MRs com X alto mas E baixo",
                "alternative": "Refatoração genuína que não afeta features (alto X, baixo E é normal)",
                "suspicion_level": "medio"
            })
            flags_by_level["medio"] += 1

    # ===== Check for cascata_de_fixes =====
    timeline = _build_cross_mr_timeline(mr_artifacts)
    if timeline:
        for i, commit_a in enumerate(timeline):
            if commit_a["type"] not in ("feat", "refactor"):
                continue
            files_a = set(commit_a["files_touched"])
            if not files_a:
                continue

            try:
                dt_a = datetime.fromisoformat(commit_a["authored_at"])
            except ValueError:
                continue

            author_a = commit_a["author"]
            cascade_commits = []

            for commit_b in timeline[i + 1:]:
                try:
                    dt_b = datetime.fromisoformat(commit_b["authored_at"])
                except ValueError:
                    continue

                if (dt_b - dt_a).total_seconds() > 48 * 3600:
                    break  # timeline sorted — no point continuing

                if commit_b["author"] == author_a:
                    continue
                if commit_b["type"] not in ("fix", "revert"):
                    continue
                if set(commit_b["files_touched"]) & files_a:
                    cascade_commits.append(commit_b)

            if len(cascade_commits) >= 3:
                authors_b = list({c["author"] for c in cascade_commits})
                suspicion = "alto" if len(cascade_commits) >= 5 else "medio"
                flags.append({
                    "type": "cascata_de_fixes",
                    "persons": [author_a] + authors_b,
                    "mr_ids": list({c["mr_id"] for c in [commit_a] + cascade_commits}),
                    "evidence": (
                        f"Commit {commit_a['sha']} ({commit_a['type']}) de {author_a} "
                        f"seguido de {len(cascade_commits)} fix/revert(s) de "
                        f"{', '.join(authors_b)} nos mesmos arquivos em 48h"
                    ),
                    "alternative": "Refatoração legítima com ajustes subsequentes planejados",
                    "suspicion_level": suspicion
                })
                flags_by_level[suspicion] += 1

    observations.append(f"Análise de {len(mr_artifacts)} MRs de {len(members)} membros")
    observations.append("Padrões: fragmentação artificial, burst de véspera, commits inflados, cascata de fixes")

    group_report = {
        "project": "peer-eval-project",
        "analyzed_at": datetime.utcnow().isoformat() + "Z",
        "flags": flags,
        "observations": observations,
        "summary": {
            "total_mrs": len(mr_artifacts),
            "total_persons": len(members),
            "flags_by_level": flags_by_level
        }
    }
    group_report["context_by_mr"], group_report["context_by_sha"] = \
        extract_context_flags(group_report)
    return group_report


def extract_context_flags(group_report: dict):
    """
    Extrai dicts de contexto indexados por mr_id e sha a partir dos flags detectados.

    Retorna:
        context_by_mr  — {mr_id: [flag_type, ...]}
        context_by_sha — {sha:   [flag_type, ...]}

    Usado pelo Stage 2.2 e Stage 2.3 para enriquecer os prompts LLM.
    """
    context_by_mr: Dict[str, List[str]] = {}
    context_by_sha: Dict[str, List[str]] = {}

    for flag in group_report.get("flags", []):
        flag_type = flag.get("type", "unknown")

        for mr_id in flag.get("mr_ids", []):
            context_by_mr.setdefault(mr_id, []).append(flag_type)

        # cascata_de_fixes registra commits individuais no evidence
        # Para shas, examinamos o commit_a no pattern (se disponível)
        for sha in flag.get("shas", []):
            context_by_sha.setdefault(sha, []).append(flag_type)

    return context_by_mr, context_by_sha


def _get_client(api_key: str) -> anthropic.Anthropic:
    """Create and return Anthropic client."""
    return anthropic.Anthropic(api_key=api_key)


def _consolidate_group_data(
    mr_artifacts: List[Dict],
    llm_estimates: List[Dict],
    members: List[str],
    deadline: str
) -> str:
    """
    Consolidate MR and estimate data into a compact format for group-level analysis.

    Reduces token usage by summarizing key patterns and metrics.
    """
    # Build efficient summary
    summary = {
        "deadline": deadline,
        "group_size": len(members),
        "total_mrs": len(mr_artifacts),
        "mrs_by_member": {}
    }

    # Create lookup
    est_by_id = {est["mr_id"]: est for est in llm_estimates}

    # Group MRs by author
    for member in members:
        member_mrs = [mr for mr in mr_artifacts if mr.get("author") == member]
        if not member_mrs:
            continue

        # Summarize for this member
        member_summary = []
        for mr in member_mrs:
            est = est_by_id.get(mr["mr_id"], {})
            commit_log_summary = [
                {
                    "sha": c["sha"],
                    "authored_at": c.get("authored_at", "")[:16],
                    "message": c.get("message", "")[:80],
                    "files_touched": c.get("files_touched", [])[:5],
                }
                for c in mr.get("commit_log", [])
            ]
            mr_summary = {
                "mr_id": mr["mr_id"],
                "title": mr.get("title", "")[:60],
                "opened_at": mr.get("opened_at", ""),
                "merged_at": mr.get("merged_at", ""),
                "diff_summary": mr.get("diff_summary", [])[:3],  # Top 3 files
                "reviewers": mr.get("reviewers", []),
                "review_comments_count": len(mr.get("review_comments", [])),
                "commit_log": commit_log_summary,
                "E": est.get("E", {}),
                "A": est.get("A", {}),
                "T_review": est.get("T_review", {}),
                "P": est.get("P", {}),
            }
            member_summary.append(mr_summary)

        summary["mrs_by_member"][member] = member_summary

    return json.dumps(summary, ensure_ascii=False, indent=2)


def _call_llm_group_analysis(
    mr_artifacts: List[Dict],
    llm_estimates: List[Dict],
    members: List[str],
    deadline: str,
    system_prompt: str,
    api_key: str
) -> dict:
    """
    Call Anthropic API for group-level pattern detection.

    Falls back to mock report on API error.
    """
    try:
        client = _get_client(api_key)
        logger.info("Calling LLM for group analysis...")

        # Consolidate data for efficient API call
        group_data = _consolidate_group_data(mr_artifacts, llm_estimates, members, deadline)

        user_message = (
            "Analise o relatório do grupo abaixo chamando a ferramenta submit_group_analysis "
            "com os padrões detectados conforme o system prompt.\n\n"
            + group_data
        )

        response = client.messages.create(
            model=config.LLM_MODEL,
            max_tokens=config.LLM_MAX_TOKENS,
            temperature=config.LLM_TEMPERATURE,
            system=system_prompt,
            tools=[GROUP_ANALYSIS_TOOL],
            tool_choice={"type": "tool", "name": "submit_group_analysis"},
            messages=[{"role": "user", "content": user_message}]
        )

        tool_block = next(
            (b for b in response.content if b.type == "tool_use"),
            None
        )

        if tool_block is None:
            logger.warning("No tool_use block in response — using fallback mock report")
            return _mock_group_report(mr_artifacts, llm_estimates, members, deadline)

        parsed = tool_block.input  # already a dict, guaranteed by the schema
        result = {
            **parsed,
            "project": "peer-eval-project",
            "llm_model": config.LLM_MODEL,
            "analyzed_at": datetime.now(datetime.now().astimezone().tzinfo).isoformat(),
            "summary": {
                "total_mrs": len(mr_artifacts),
                "total_persons": len(members),
                "flags_by_level": {
                    level: sum(1 for f in parsed["flags"] if f["suspicion_level"] == level)
                    for level in ("alto", "medio", "baixo")
                }
            }
        }
        logger.info("Group analysis OK")
        return result

    except anthropic.APIStatusError as e:
        logger.error(f"API error ({e.status_code}): {e.message}")
        if e.status_code in (401, 403):
            raise  # Fatal
        return _mock_group_report(mr_artifacts, llm_estimates, members, deadline)

    except anthropic.APIConnectionError as e:
        logger.error(f"Connection error: {e}")
        return _mock_group_report(mr_artifacts, llm_estimates, members, deadline)

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return _mock_group_report(mr_artifacts, llm_estimates, members, deadline)


def detect_patterns(
    mr_artifacts: List[Dict],
    llm_estimates: List[Dict],
    members: List[str],
    deadline: str,
    prompt_path: str = config.PROMPT_FILE,
    api_key: Optional[str] = None,
    dry_run: bool = True,
    output_path: str = "output/group_report.json",
) -> dict:
    """
    Executa Stage 2.1: detecta padrões suspeitos cross-MR.

    Retorna o group_report com campos adicionais:
      context_by_mr  — {mr_id: [flag_type, ...]}  para Stage 2.3
      context_by_sha — {sha:   [flag_type, ...]}  para Stage 2.2

    Args:
        mr_artifacts: Lista de MR artifacts
        llm_estimates: Lista de LLM estimates (usadas para detecção heurística)
        members: Lista de membros do grupo
        deadline: Deadline ISO string
        prompt_path: Caminho para o arquivo de prompts
        api_key: Anthropic API key (obrigatório se dry_run=False)
        dry_run: Se True, usa detecção heurística
        output_path: Onde salvar o report JSON

    Returns:
        Group report dict com flags e context_by_mr / context_by_sha
    """
    logger.info(f"Stage 2.1: {len(mr_artifacts)} MRs (dry_run={dry_run})")

    system_prompt = ""
    if not dry_run:
        try:
            system_prompt = load_prompt("Stage 2.1", prompt_path)
        except (FileNotFoundError, ValueError) as e:
            logger.warning(f"Prompt para Stage 2.1 não encontrado: {e}")

    if dry_run:
        report = _mock_group_report(mr_artifacts, llm_estimates, members, deadline)
    else:
        if not api_key:
            logger.warning("api_key não fornecida — usando detecção heurística")
            report = _mock_group_report(mr_artifacts, llm_estimates, members, deadline)
        else:
            report = _call_llm_group_analysis(
                mr_artifacts, llm_estimates, members, deadline, system_prompt, api_key
            )

    # Garante que context_by_mr e context_by_sha estejam presentes
    if "context_by_mr" not in report:
        report["context_by_mr"], report["context_by_sha"] = extract_context_flags(report)

    from . import loader
    loader.save_json(report, output_path)
    logger.info(f"Stage 2.1 completo → {output_path}")
    return report

