"""
Stage 2.2 — Avaliação qualitativa por commit.

Para cada commit (após filtragem):
  - message_syntax:   determinístico (sem LLM)
  - atomicity:        LLM
  - message_semantic: LLM
  - scope_clarity:    LLM

Uma única chamada LLM por commit retorna atomicity + message_semantic + scope_clarity.
Cache por sha (estável — nunca muda).

message_quality(c) = 0.50·message_syntax(c) + 0.50·message_semantic(c)
"""

import anthropic
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict

from . import config
from . import model

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Tool Schema
# ═══════════════════════════════════════════════════════════════════════════

COMMIT_EVALUATION_TOOL: dict = {
    "name": "submit_commit_evaluation",
    "description": (
        "Submit the structured qualitative evaluation for a single commit. "
        "Evaluate atomicity, message semantics, and scope clarity based on "
        "the commit message, files touched, and diff provided."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "atomicity": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": (
                    "Does the commit do exactly one thing with a clear purpose? "
                    "High: surgical change in 1–2 files, single purpose. "
                    "Low: mixed concerns, unrelated files changed together."
                )
            },
            "message_semantic": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": (
                    "Does the message describe WHY, not just WHAT? "
                    "High: explains motivation/impact. "
                    "Low: only restates what the diff shows."
                )
            },
            "scope_clarity": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": (
                    "Are the files touched coherent with the declared purpose? "
                    "High: all files obviously relate to the stated change. "
                    "Low: files appear out of scope or unrelated."
                )
            },
            "scope_clarity_reason": {
                "type": "string",
                "description": (
                    "Brief explanation only when scope_clarity < 0.7. "
                    "Name the suspicious file(s) and why they seem out of scope."
                )
            }
        },
        "required": ["atomicity", "message_semantic", "scope_clarity", "scope_clarity_reason"]
    }
}


# ═══════════════════════════════════════════════════════════════════════════
# Filtro de commits
# ═══════════════════════════════════════════════════════════════════════════

_MERGE_RE = re.compile(config.MERGE_COMMIT_PATTERN, re.IGNORECASE)


def _is_merge_commit(commit: dict) -> bool:
    """True se o commit é um merge automático."""
    return bool(_MERGE_RE.match(commit.get("message", "")))


def _is_bot_commit(commit: dict) -> bool:
    """True se o autor do commit é um bot conhecido."""
    author = commit.get("author", "").lower().strip()
    return author in {a.lower() for a in config.BOT_AUTHORS}


def filter_commits(commits: List[Dict]) -> List[Dict]:
    """
    Filtra commits que não devem ser avaliados.

    EXCLUIR: merges automáticos, bots.
    MANTER: fixup, wip, mensagens genéricas — o modelo penaliza via message_quality.

    Args:
        commits: Lista de commits do commit_log do MR

    Returns:
        Lista com campo "is_filtered" e "filter_reason" adicionados a cada commit
    """
    result = []
    for commit in commits:
        if _is_merge_commit(commit):
            result.append({**commit, "is_filtered": True, "filter_reason": "merge_commit"})
        elif _is_bot_commit(commit):
            result.append({**commit, "is_filtered": True, "filter_reason": "bot_author"})
        else:
            result.append({**commit, "is_filtered": False, "filter_reason": None})
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Cache por sha
# ═══════════════════════════════════════════════════════════════════════════


def _cache_path(sha: str, cache_dir: str) -> Path:
    return Path(cache_dir) / "commits" / f"{sha}.json"


def _load_from_cache(sha: str, cache_dir: str) -> Optional[dict]:
    path = _cache_path(sha, cache_dir)
    if path.exists():
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            logger.debug(f"[commit:{sha[:8]}] Loaded from cache")
            return result
        except Exception as e:
            logger.warning(f"[commit:{sha[:8]}] Cache load error: {e}")
    return None


def _save_to_cache(estimate: dict, cache_dir: str) -> None:
    path = _cache_path(estimate["sha"], cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(estimate, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    logger.debug(f"[commit:{estimate['sha'][:8]}] Saved to cache")


# ═══════════════════════════════════════════════════════════════════════════
# Mock e fallback
# ═══════════════════════════════════════════════════════════════════════════


def _mock_commit_estimate(commit: dict) -> dict:
    """
    Gera estimativa mock para dry_run, baseada em heurísticas simples.
    """
    message   = commit.get("message", "")
    files     = commit.get("files_touched", [])
    n_files   = len(files)

    syntax = model.calc_message_syntax(message)

    # Atomicity heurística: menos arquivos e propósito aparente → maior atomicidade
    atomicity = max(0.1, min(1.0, 1.0 - (n_files - 1) * 0.15)) if n_files > 0 else 0.5

    # message_semantic: proxy via qualidade sintática (sem conteúdo real a analisar)
    message_semantic = min(1.0, syntax * 0.9 + 0.1)

    # scope_clarity: proxy via número de arquivos
    scope_clarity = max(0.2, 1.0 - (n_files - 1) * 0.10) if n_files > 0 else 0.5

    message_quality = 0.5 * syntax + 0.5 * message_semantic

    return {
        "sha":              commit.get("sha", "unknown"),
        "mr_id":            commit.get("mr_id", "unknown"),
        "author":           commit.get("author", "unknown"),
        "message_syntax":   round(syntax, 3),
        "atomicity":        round(atomicity, 3),
        "message_semantic": round(message_semantic, 3),
        "scope_clarity":    round(scope_clarity, 3),
        "scope_clarity_reason": "",
        "message_quality":  round(message_quality, 3),
        "is_filtered":      commit.get("is_filtered", False),
        "filter_reason":    commit.get("filter_reason"),
        "llm_model":        "dry_run",
        "estimated_at":     datetime.now(timezone.utc).isoformat() + "Z",
    }


def _fallback_commit_estimate(commit: dict, reason: str) -> dict:
    """Fallback com valores neutros quando a API falha."""
    syntax = model.calc_message_syntax(commit.get("message", ""))
    message_quality = 0.5 * syntax + 0.5 * 0.5  # sem semantic, usa 0.5 neutro

    return {
        "sha":              commit.get("sha", "unknown"),
        "mr_id":            commit.get("mr_id", "unknown"),
        "author":           commit.get("author", "unknown"),
        "message_syntax":   round(syntax, 3),
        "atomicity":        0.5,
        "message_semantic": 0.5,
        "scope_clarity":    0.5,
        "scope_clarity_reason": f"Fallback: {reason}",
        "message_quality":  round(message_quality, 3),
        "is_filtered":      commit.get("is_filtered", False),
        "filter_reason":    commit.get("filter_reason"),
        "llm_model":        "heuristic",
        "estimated_at":     datetime.now(timezone.utc).isoformat() + "Z",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Avaliação individual de commit
# ═══════════════════════════════════════════════════════════════════════════


def _build_commit_user_message(commit: dict, context_flags: List[str]) -> str:
    """Monta a mensagem de usuário para avaliação do commit."""
    parts = ["Avalie o commit abaixo chamando a ferramenta submit_commit_evaluation.\n"]

    if context_flags:
        parts.append(
            "[CONTEXTO — Stage 2.1]\n"
            f"Padrões suspeitos detectados: {', '.join(context_flags)}\n"
            "Considere esses sinais ao avaliar atomicity e scope_clarity.\n"
        )

    commit_data = {
        "sha":          commit.get("sha", ""),
        "message":      commit.get("message", ""),
        "files_touched": commit.get("files_touched", []),
        "diff":         (commit.get("diff", "") or "")[:config.COMMIT_DIFF_MAX_CHARS],
    }
    parts.append(json.dumps(commit_data, ensure_ascii=False, indent=2))
    return "\n".join(parts)


def evaluate_commit(
    commit: dict,
    system_prompt: str = "",
    api_key: Optional[str] = None,
    dry_run: bool = True,
    cache_dir: str = "output/cache",
    context_flags: Optional[List[str]] = None,
) -> dict:
    """
    Avalia um único commit (não filtrado).

    Args:
        commit: Dict de commit com sha, message, files_touched, diff
        system_prompt: System prompt para a API
        api_key: Anthropic API key (obrigatório se dry_run=False)
        dry_run: Se True, retorna estimativa mock
        cache_dir: Diretório para cache (chave = sha)
        context_flags: Flags de padrão do Stage 2.1 para este commit

    Returns:
        Estimativa com atomicity, message_semantic, scope_clarity, message_quality
    """
    sha = commit.get("sha", "unknown")

    if dry_run:
        return _mock_commit_estimate(commit)

    if not api_key:
        raise ValueError("api_key required when dry_run=False")

    cached = _load_from_cache(sha, cache_dir)
    if cached:
        return cached

    user_message = _build_commit_user_message(commit, context_flags or [])

    try:
        client = anthropic.Anthropic(api_key=api_key)
        logger.debug(f"[commit:{sha[:8]}] Calling LLM...")

        response = client.messages.create(
            model=config.LLM_MODEL,
            max_tokens=config.LLM_MAX_TOKENS_COMMIT,
            temperature=config.LLM_TEMPERATURE,
            system=system_prompt,
            tools=[COMMIT_EVALUATION_TOOL],
            tool_choice={"type": "tool", "name": "submit_commit_evaluation"},
            messages=[{"role": "user", "content": user_message}],
        )

        tool_block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )

        if tool_block is None:
            logger.warning(f"[commit:{sha[:8]}] No tool_use block — fallback")
            result = _fallback_commit_estimate(commit, "no tool call")
        else:
            parsed = tool_block.input
            syntax = model.calc_message_syntax(commit.get("message", ""))
            message_quality = 0.5 * syntax + 0.5 * parsed["message_semantic"]
            result = {
                "sha":              sha,
                "mr_id":            commit.get("mr_id", "unknown"),
                "author":           commit.get("author", "unknown"),
                "message_syntax":   round(syntax, 3),
                "atomicity":        round(parsed["atomicity"], 3),
                "message_semantic": round(parsed["message_semantic"], 3),
                "scope_clarity":    round(parsed["scope_clarity"], 3),
                "scope_clarity_reason": parsed.get("scope_clarity_reason", ""),
                "message_quality":  round(message_quality, 3),
                "is_filtered":      commit.get("is_filtered", False),
                "filter_reason":    commit.get("filter_reason"),
                "llm_model":        config.LLM_MODEL,
                "estimated_at":     datetime.now(timezone.utc).isoformat() + "Z",
            }
            logger.debug(
                f"[commit:{sha[:8]}] OK — "
                f"atom={result['atomicity']:.2f} "
                f"msg_q={result['message_quality']:.2f} "
                f"scope={result['scope_clarity']:.2f}"
            )

    except anthropic.APIStatusError as e:
        logger.error(f"[commit:{sha[:8]}] API error ({e.status_code}): {e.message}")
        if e.status_code in (401, 403):
            raise
        result = _fallback_commit_estimate(commit, f"API error {e.status_code}")

    except anthropic.APIConnectionError as e:
        logger.error(f"[commit:{sha[:8]}] Connection error: {e}")
        result = _fallback_commit_estimate(commit, "connection error")

    except Exception as e:
        logger.error(f"[commit:{sha[:8]}] Unexpected error: {e}")
        result = _fallback_commit_estimate(commit, f"unexpected: {type(e).__name__}")

    _save_to_cache(result, cache_dir)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Orquestração — Stage 2.2
# ═══════════════════════════════════════════════════════════════════════════


def run_stage2_commits(
    mr_artifacts: List[Dict],
    api_key: Optional[str] = None,
    prompt_path: str = config.PROMPT_FILE,
    dry_run: bool = True,
    cache_dir: str = "output/cache",
    output_path: str = "output/commit_estimates.json",
    context_flags: Optional[Dict] = None,
) -> List[Dict]:
    """
    Executa Stage 2.2: avalia todos os commits de todos os MRs.

    Commits filtrados (merge, bot) recebem estimativa com is_filtered=True
    e não são passados ao LLM.

    Args:
        mr_artifacts: Lista de MR artifacts (devem ter commit_log)
        api_key: Anthropic API key (obrigatório se dry_run=False)
        prompt_path: Caminho para o arquivo de prompts
        dry_run: Se True, usa estimativas mock
        cache_dir: Diretório de cache (chave por sha)
        output_path: Onde salvar as estimativas em JSON
        context_flags: Dict {sha: [flags]} e {mr_id: [flags]} do Stage 2.1

    Returns:
        Lista de estimativas de commits (todos, incluindo filtrados)
    """
    context_flags = context_flags or {}

    # Conta total de commits avaliáveis
    total_commits = sum(len(mr.get("commit_log", [])) for mr in mr_artifacts)
    logger.info(
        f"Stage 2.2: {len(mr_artifacts)} MRs, "
        f"{total_commits} commits (dry_run={dry_run})"
    )

    # Carrega system prompt
    system_prompt = ""
    if not dry_run:
        try:
            from .llm_stage2a import load_prompt
            system_prompt = load_prompt("Stage 2.2", prompt_path)
        except (FileNotFoundError, ValueError) as e:
            logger.warning(f"Prompt para Stage 2.2 não encontrado: {e} — usando prompt vazio")

    all_estimates: List[Dict] = []
    evaluated = 0

    for mr in mr_artifacts:
        mr_id    = mr.get("mr_id", "unknown")
        raw_commits = mr.get("commit_log", [])

        if not raw_commits:
            logger.debug(f"[{mr_id}] Sem commit_log — pulando Stage 2.2")
            continue

        # Anota mr_id em cada commit (necessário para lookup no scorer)
        annotated = [{**c, "mr_id": mr_id} for c in raw_commits]
        filtered  = filter_commits(annotated)

        for commit in filtered:
            sha = commit.get("sha", "unknown")

            if commit.get("is_filtered"):
                # Registra o commit filtrado sem chamar o LLM
                all_estimates.append({
                    "sha":              sha,
                    "mr_id":            mr_id,
                    "author":           commit.get("author", "unknown"),
                    "is_filtered":      True,
                    "filter_reason":    commit.get("filter_reason"),
                    "message_syntax":   0.0,
                    "atomicity":        0.0,
                    "message_semantic": 0.0,
                    "scope_clarity":    0.0,
                    "scope_clarity_reason": "",
                    "message_quality":  0.0,
                    "llm_model":        "filtered",
                    "estimated_at":     datetime.now(timezone.utc).isoformat() + "Z",
                })
                logger.debug(
                    f"[{mr_id}] commit {sha[:8]} filtrado "
                    f"({commit.get('filter_reason')})"
                )
                continue

            # Flags de contexto para este commit
            flags = list(set(
                context_flags.get(sha, []) + context_flags.get(mr_id, [])
            ))

            evaluated += 1
            logger.info(
                f"Stage 2.2 [{evaluated}] {mr_id}/{sha[:8]} — "
                f"{commit.get('message', '')[:50]}"
            )

            estimate = evaluate_commit(
                commit=commit,
                system_prompt=system_prompt,
                api_key=api_key,
                dry_run=dry_run,
                cache_dir=cache_dir,
                context_flags=flags,
            )
            all_estimates.append(estimate)

    # Salva em disco
    from . import loader
    loader.save_json(all_estimates, output_path)

    n_evaluated = sum(1 for e in all_estimates if not e.get("is_filtered"))
    n_filtered  = sum(1 for e in all_estimates if e.get("is_filtered"))
    logger.info(
        f"Stage 2.2 completo: {n_evaluated} avaliados, "
        f"{n_filtered} filtrados → {output_path}"
    )
    return all_estimates
