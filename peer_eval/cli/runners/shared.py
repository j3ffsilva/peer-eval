"""
Pipeline de avaliação compartilhado (Stages 1-4).

Reutilizado por todos os subcomandos CLI (gitlab, github, fixture).
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Optional, Literal

from ... import loader
from ... import llm_stage2a
from ... import llm_stage2b
from ... import llm_stage2_commits
from ... import scorer
from ... import report

logger = logging.getLogger(__name__)

_PROMPT_PATH = str(
    Path(__file__).parent.parent.parent / "prompts" / "avaliacao_llm.md"
)


def _extract_members_from_artifacts(mr_artifacts: List[Dict]) -> List[str]:
    """Extrai usernames únicos de autores e revisores dos artefatos."""
    members = set()
    for mr in mr_artifacts:
        if mr.get("author"):
            members.add(mr["author"])
        for reviewer in mr.get("reviewers", []):
            members.add(reviewer)
        for comment in mr.get("review_comments", []):
            if comment.get("author"):
                members.add(comment["author"])
    return sorted(members)


def run_evaluation(
    artifacts: List[Dict],
    deadline: str,
    llm_mode: Literal["live", "dry-run", "skip"] = "dry-run",
    anthropic_key: Optional[str] = None,
    members: Optional[List[str]] = None,
    output_dir: str = "output",
    overrides: Optional[str] = None,
    skip_stage2b: bool = False,
    direct_committers: Optional[List[str]] = None,
) -> Dict:
    """
    Executa o pipeline completo de avaliação (Stages 1–4).

    Pipeline:
      Stage 1    — verifica métricas quantitativas
      Stage 2.1  — detecção de padrões suspeitos cross-MR
      Stage 2.2  — avaliação LLM por commit (atomicity, message_quality, scope_clarity)
      Stage 2.3  — avaliação LLM por MR (A, T_review)
      Stage 3    — fator de contribuição por membro
      Stage 4    — relatórios

    Args:
        artifacts: Lista de MR artifacts
        deadline: Deadline do projeto (ISO 8601)
        llm_mode: "live" (API Anthropic), "dry-run" (mock), "skip" (nenhum LLM)
        anthropic_key: Anthropic API key (obrigatório se llm_mode="live")
        members: Lista de usernames (auto-extraída se None)
        output_dir: Diretório de saída
        overrides: Caminho para JSON de overrides do professor (opcional)
        skip_stage2b: Pula Stage 2.1 (detecção de padrões)
        direct_committers: Membros com commits diretos (penalidade W×0.40)

    Returns:
        Dict com scores finais por membro
    """

    # ===== STAGE 1: Métricas quantitativas =====
    logger.info("=" * 60)
    logger.info("Stage 1: Métricas quantitativas")
    logger.info("=" * 60)

    for mr in artifacts:
        if "quantitative" not in mr:
            logger.warning(
                f"{mr.get('mr_id', 'UNKNOWN')}: sem quantitative — usando defaults"
            )
            mr["quantitative"] = {"X": 0.0, "S": 1.0, "Q": 1.0}

    logger.info("Métricas quantitativas verificadas")

    if not members:
        members = _extract_members_from_artifacts(artifacts)
        logger.info(f"Auto-extraídos {len(members)} membros: {', '.join(members)}")
    else:
        logger.info(f"Membros fornecidos ({len(members)}): {', '.join(members)}")

    # Validação antecipada
    if llm_mode == "live" and not anthropic_key:
        raise ValueError(
            "llm_mode='live' mas anthropic_key não fornecida. "
            "Defina ANTHROPIC_API_KEY ou passe --anthropic-key."
        )

    dry_run  = (llm_mode == "dry-run")
    skip_llm = (llm_mode == "skip")
    api_key  = anthropic_key if llm_mode == "live" else None
    cache_dir = os.path.join(output_dir, "cache")

    # ===== STAGE 2.1: Detecção de padrões suspeitos =====
    group_report  = None
    context_flags = {}

    if not skip_stage2b:
        logger.info("=" * 60)
        logger.info("Stage 2.1: Detecção de padrões suspeitos cross-MR")
        logger.info("=" * 60)

        group_report = llm_stage2b.detect_patterns(
            artifacts,
            [],          # estimativas LLM ainda não existem neste ponto
            members,
            deadline,
            prompt_path=_PROMPT_PATH,
            api_key=api_key,
            dry_run=dry_run,
            output_path=os.path.join(output_dir, "group_report.json"),
        )
        context_flags = {
            **group_report.get("context_by_mr",  {}),
            **group_report.get("context_by_sha", {}),
        }
    else:
        logger.info("Stage 2.1 ignorado (--skip-stage2b)")

    # ===== STAGE 2.2: Avaliação LLM por commit =====
    commit_estimates = []

    if not skip_llm:
        logger.info("=" * 60)
        logger.info("Stage 2.2: Avaliação de commits (atomicity, message_quality, scope_clarity)")
        logger.info("=" * 60)

        commit_estimates = llm_stage2_commits.run_stage2_commits(
            artifacts,
            api_key=api_key,
            prompt_path=_PROMPT_PATH,
            dry_run=dry_run,
            cache_dir=cache_dir,
            output_path=os.path.join(output_dir, "commit_estimates.json"),
            context_flags=group_report.get("context_by_sha", {}) if group_report else {},
        )
    else:
        logger.info("Stage 2.2 ignorado (--llm skip)")

    # ===== STAGE 2.3: Avaliação LLM por MR (A + T_review) =====
    llm_estimates = []

    if not skip_llm:
        logger.info("=" * 60)
        logger.info("Stage 2.3: Avaliação de MRs pelo LLM (A, T_review)")
        logger.info("=" * 60)

        llm_estimates = llm_stage2a.run_stage2_mr(
            artifacts,
            api_key=api_key,
            prompt_path=_PROMPT_PATH,
            dry_run=dry_run,
            cache_dir=cache_dir,
            output_path=os.path.join(output_dir, "mr_llm_estimates.json"),
            context_flags=group_report.get("context_by_mr", {}) if group_report else {},
        )
    else:
        logger.info("Stage 2.3 ignorado (--llm skip)")

    # ===== Overrides do professor =====
    overrides_dict = None
    if overrides:
        try:
            overrides_dict = loader.load_overrides(overrides)
            if overrides_dict:
                logger.info(f"Overrides carregados para {len(overrides_dict)} MRs")
        except Exception as e:
            logger.warning(f"Falha ao carregar overrides: {e}")

    # ===== STAGE 3: Fator de contribuição =====
    logger.info("=" * 60)
    logger.info("Stage 3: Fator de contribuição por membro")
    logger.info("=" * 60)

    scores = scorer.compute_scores(
        artifacts,
        llm_estimates,
        overrides_dict,
        members,
        direct_committers=direct_committers,
        commit_estimates=commit_estimates if commit_estimates else None,
    )

    logger.info(f"Scores calculados para {len(scores)} membros")

    # ===== STAGE 4: Relatórios =====
    logger.info("=" * 60)
    logger.info("Stage 4: Relatórios")
    logger.info("=" * 60)

    os.makedirs(output_dir, exist_ok=True)
    report.print_summary(scores, group_report)

    report.export_full_report(
        artifacts,
        llm_estimates,
        scores,
        group_report,
        output_path=os.path.join(output_dir, "full_report.json"),
    )

    if llm_mode == "live" and anthropic_key:
        logger.info("Gerando relatório narrativo...")
        report.generate_narrative_report(
            artifacts,
            llm_estimates if llm_estimates else [],
            scores,
            group_report,
            api_key=anthropic_key,
            output_path=os.path.join(output_dir, "narrative_report.txt"),
        )

    logger.info("=" * 60)
    logger.info("Pipeline concluído com sucesso")
    logger.info(f"Relatórios em {output_dir}/")
    logger.info("=" * 60)

    return scores
