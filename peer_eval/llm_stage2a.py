"""
Stage 2.3 — Avaliação qualitativa por MR.

Avalia apenas:
  A(k)       — importância arquitetural (LLM)
  T_review   — qualidade do review (LLM)

X(k) e E(k) são calculados a partir dos commits (Stage 2.2).
P(k) foi removido; S(k) e Q(k) são determinísticos.
"""

import anthropic
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict

from . import config
from . import model

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Tool Schema — enforces structured output without text parsing
# ═══════════════════════════════════════════════════════════════════════════

MR_EVALUATION_TOOL: dict = {
    "name": "submit_mr_evaluation",
    "description": (
        "Submit the structured qualitative evaluation for a Merge Request. "
        "Evaluate only A (architectural importance) and T_review (review quality). "
        "X and E are computed from commits (Stage 2.2) — do NOT estimate them here."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "A": {
                "type": "object",
                "description": (
                    "Architectural importance — is this MR structurally central to the project? "
                    "Consider: position in system (core vs. peripheral), observable practical effect, "
                    "relevance to project goals. Base evaluation on concrete evidence from the diff."
                ),
                "properties": {
                    "value":      {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "reasoning":  {"type": "string"}
                },
                "required": ["value", "confidence", "reasoning"]
            },
            "T_review": {
                "type": "object",
                "description": (
                    "Review quality — depth of feedback provided by reviewers. "
                    "0.20–0.30: substantial review with technical comments, changes requested, "
                    "evidence MR was altered after review. "
                    "0.10–0.20: superficial review, simple approval. "
                    "0.00–0.10: absent or irrelevant review."
                ),
                "properties": {
                    "value":      {"type": "number", "minimum": 0.0, "maximum": 0.30},
                    "level":      {"type": "string", "enum": ["absent", "superficial", "substantive"]},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                    "reasoning":  {"type": "string"}
                },
                "required": ["value", "level", "confidence", "reasoning"]
            }
        },
        "required": ["A", "T_review"]
    }
}


# ═══════════════════════════════════════════════════════════════════════════
# Prompt Loading
# ═══════════════════════════════════════════════════════════════════════════


def load_prompt(section: str, prompt_path: str = config.PROMPT_FILE) -> str:
    """
    Load and extract system prompt from markdown file.

    Searches for a heading matching '#### System Prompt — {section}'
    and extracts the code block immediately following it.

    Args:
        section: Section name (e.g., "Stage 2a")
        prompt_path: Path to prompts markdown file

    Returns:
        System prompt content

    Raises:
        FileNotFoundError: If prompt file not found
        ValueError: If section not found
    """
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    # Search for the section heading
    pattern = rf"#### System Prompt — {section}\s*\n\s*```\s*\n(.*?)\n```"
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        raise ValueError(f"Section 'System Prompt — {section}' not found in {prompt_path}")

    return match.group(1).strip()


# ═══════════════════════════════════════════════════════════════════════════
# LLM Client
# ═══════════════════════════════════════════════════════════════════════════


def _get_client(api_key: str) -> anthropic.Anthropic:
    """Create and return Anthropic client."""
    return anthropic.Anthropic(api_key=api_key)


# ═══════════════════════════════════════════════════════════════════════════
# Fallback Heuristics
# ═══════════════════════════════════════════════════════════════════════════


def _fallback_estimate(mr_artifact: dict, reason: str = "fallback") -> dict:
    """
    Estimativa heurística quando o LLM falha.
    Retorna apenas A e T_review (X e E vêm dos commits).
    """
    files = [f["file"] for f in mr_artifact.get("diff_summary", [])]
    has_reviewers = len(mr_artifact.get("reviewers", [])) > 0
    a_value = model.calc_a_heuristic(files)

    return {
        "mr_id": mr_artifact["mr_id"],
        "author": mr_artifact["author"],
        "A": {
            "value": a_value,
            "confidence": "low",
            "reasoning": f"Heuristic fallback ({reason})"
        },
        "T_review": {
            "value": config.T_REVIEWER_MAX if has_reviewers else 0.0,
            "level": "absent" if not has_reviewers else "superficial",
            "confidence": "low",
            "reasoning": f"Heuristic fallback ({reason})"
        },
        "llm_model": "heuristic",
        "estimated_at": datetime.now(timezone.utc).isoformat() + "Z"
    }


# ═══════════════════════════════════════════════════════════════════════════
# Mock Estimate (for dry_run)
# ═══════════════════════════════════════════════════════════════════════════


def _mock_estimate(mr_artifact: dict) -> dict:
    """
    Estimativa mock para dry_run.
    Retorna apenas A e T_review (Stage 2.3).
    X e E são calculados a partir dos commits (Stage 2.2).
    """
    mr_id    = mr_artifact.get("mr_id", "UNKNOWN")
    author   = mr_artifact.get("author", "unknown")
    reviewers     = mr_artifact.get("reviewers", [])
    review_comments = mr_artifact.get("review_comments", [])
    diff_summary  = mr_artifact.get("diff_summary", [])

    # A(k) — heurístico por módulos
    module_paths = [f["file"] for f in diff_summary]
    A_value = model.calc_a_heuristic(module_paths)

    # T_review — heurístico por comentários
    T_review_value = 0.0
    T_review_level = "absent"

    if reviewers and review_comments:
        substantive = sum(
            1 for c in review_comments
            if len(c.get("body", "")) > 30
            and any(w in c.get("body", "").lower() for w in ["add", "remove", "fix", "improve", "refactor"])
        )
        if substantive > 0:
            T_review_value = 0.26
            T_review_level = "substantive"
        else:
            T_review_value = 0.12
            T_review_level = "superficial"
    elif reviewers:
        T_review_value = 0.15
        T_review_level = "superficial"

    return {
        "mr_id":  mr_id,
        "author": author,
        "A": {
            "value":      min(1.0, max(0.0, A_value)),
            "confidence": "medium",
            "reasoning":  "mock"
        },
        "T_review": {
            "value":      min(0.30, max(0.0, T_review_value)),
            "level":      T_review_level,
            "confidence": "medium",
            "reasoning":  "mock"
        },
        "llm_model":    "dry_run",
        "estimated_at": datetime.now(timezone.utc).isoformat() + "Z",
    }


# ═══════════════════════════════════════════════════════════════════════════
# Caching
# ═══════════════════════════════════════════════════════════════════════════


def _cache_path(mr_id: str, cache_dir: str = "output/cache") -> Path:
    """Return Path to cached estimate file."""
    return Path(cache_dir) / f"{mr_id}.json"


def _load_from_cache(mr_id: str, cache_dir: str = "output/cache") -> Optional[dict]:
    """Load estimate from cache, return None if not found or invalid."""
    path = _cache_path(mr_id, cache_dir)
    if path.exists():
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            logger.debug(f"[{mr_id}] Loaded from cache")
            return result
        except Exception as e:
            logger.warning(f"[{mr_id}] Cache load error: {e}")
    return None


def _save_to_cache(estimate: dict, cache_dir: str = "output/cache") -> None:
    """Save estimate to cache file."""
    path = _cache_path(estimate["mr_id"], cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(estimate, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    logger.debug(f"[{estimate['mr_id']}] Saved to cache")


# ═══════════════════════════════════════════════════════════════════════════
# Core Estimation Logic
# ═══════════════════════════════════════════════════════════════════════════


def estimate_mr(
    mr_artifact: dict,
    system_prompt: str = "",
    api_key: Optional[str] = None,
    dry_run: bool = True,
    cache_dir: str = "output/cache",
    context_flags: Optional[List[str]] = None,
) -> dict:
    """
    Avalia A(k) e T_review para um único MR (Stage 2.3).

    Args:
        mr_artifact: MR artifact dict
        system_prompt: System prompt para a API
        api_key: Anthropic API key (obrigatório se dry_run=False)
        dry_run: Se True, retorna estimativa mock
        cache_dir: Diretório para cache
        context_flags: Flags de padrão do Stage 2.1 para este MR

    Returns:
        Estimativa com A e T_review

    Raises:
        ValueError: Se dry_run=False e api_key é None
    """
    mr_id = mr_artifact["mr_id"]

    if dry_run:
        return _mock_estimate(mr_artifact)

    if not api_key:
        raise ValueError("api_key required when dry_run=False")

    cached = _load_from_cache(mr_id, cache_dir)
    if cached:
        return cached

    # Monta mensagem com contexto do Stage 2.1
    parts = [
        "Avalie o Merge Request abaixo chamando a ferramenta submit_mr_evaluation "
        "para estimar A(k) e T_review.\n"
    ]
    if context_flags:
        parts.append(
            "[CONTEXTO — Stage 2.1]\n"
            f"Padrões suspeitos detectados: {', '.join(context_flags)}\n"
            "Considere esses sinais ao estimar A(k) e T_review.\n"
        )
    parts.append(json.dumps(mr_artifact, ensure_ascii=False, indent=2))
    user_message = "\n".join(parts)

    try:
        client = _get_client(api_key)
        logger.info(f"[{mr_id}] Calling LLM (Stage 2.3)...")

        response = client.messages.create(
            model=config.LLM_MODEL,
            max_tokens=config.LLM_MAX_TOKENS,
            temperature=config.LLM_TEMPERATURE,
            system=system_prompt,
            tools=[MR_EVALUATION_TOOL],
            tool_choice={"type": "tool", "name": "submit_mr_evaluation"},
            messages=[{"role": "user", "content": user_message}],
        )

        tool_block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )

        if tool_block is None:
            logger.warning(f"[{mr_id}] No tool_use block — fallback heuristic")
            result = _fallback_estimate(mr_artifact, reason="no tool call")
        else:
            parsed = tool_block.input
            result = {
                "mr_id":  mr_id,
                "author": mr_artifact["author"],
                **parsed,
                "llm_model":    config.LLM_MODEL,
                "estimated_at": datetime.now(timezone.utc).isoformat() + "Z",
            }
            logger.info(
                f"[{mr_id}] OK — "
                f"A={result['A']['value']:.2f}({result['A']['confidence']}) "
                f"T={result['T_review']['value']:.2f}({result['T_review']['level']})"
            )

    except anthropic.APIStatusError as e:
        logger.error(f"[{mr_id}] API error ({e.status_code}): {e.message}")
        if e.status_code in (401, 403):
            raise  # Invalid key — stop immediately
        if e.status_code == 429:
            # Rate limited: wait before falling back so the professor can re-run
            # without losing this MR to a heuristic estimate permanently.
            logger.warning(f"[{mr_id}] Rate limited (429), waiting 60s before fallback...")
            time.sleep(60)
        result = _fallback_estimate(mr_artifact, reason=f"API error {e.status_code}")

    except anthropic.APIConnectionError as e:
        logger.error(f"[{mr_id}] Connection error: {e}")
        result = _fallback_estimate(mr_artifact, reason="connection error")

    except Exception as e:
        logger.error(f"[{mr_id}] Unexpected error: {e}")
        result = _fallback_estimate(mr_artifact, reason=f"unexpected error: {type(e).__name__}")

    # Save to cache regardless of source
    _save_to_cache(result, cache_dir)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Stage 2a Orchestration
# ═══════════════════════════════════════════════════════════════════════════


def run_stage2_mr(
    mr_artifacts: List[Dict],
    api_key: Optional[str] = None,
    prompt_path: str = config.PROMPT_FILE,
    dry_run: bool = True,
    cache_dir: str = "output/cache",
    output_path: str = "output/mr_llm_estimates.json",
    context_flags: Optional[Dict] = None,
) -> List[Dict]:
    """
    Executa Stage 2.3: avalia A(k) e T_review para todos os MRs.

    Args:
        mr_artifacts: Lista de MR artifacts
        api_key: Anthropic API key (obrigatório se dry_run=False)
        prompt_path: Caminho para o arquivo de prompts
        dry_run: Se True, usa estimativas mock
        cache_dir: Diretório para cache
        output_path: Onde salvar as estimativas em JSON
        context_flags: Dict {mr_id: [flags]} do Stage 2.1

    Returns:
        Lista de estimativas com A e T_review por MR
    """
    context_flags = context_flags or {}
    logger.info(f"Stage 2.3: {len(mr_artifacts)} MRs (dry_run={dry_run})")

    system_prompt = ""
    if not dry_run:
        try:
            system_prompt = load_prompt("Stage 2.3", prompt_path)
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Could not load prompt: {e}")
            raise

    estimates = []
    for i, mr_artifact in enumerate(mr_artifacts, 1):
        mr_id = mr_artifact["mr_id"]
        logger.info(
            f"Stage 2.3 [{i}/{len(mr_artifacts)}] "
            f"{mr_id} — {mr_artifact.get('title', '')[:60]}"
        )
        flags = context_flags.get(mr_id, [])
        estimate = estimate_mr(
            mr_artifact=mr_artifact,
            system_prompt=system_prompt,
            api_key=api_key,
            dry_run=dry_run,
            cache_dir=cache_dir,
            context_flags=flags,
        )
        estimates.append(estimate)

    from . import loader
    loader.save_json(estimates, output_path)
    logger.info(f"Stage 2.3 completo: {len(estimates)} estimativas → {output_path}")
    return estimates


# Alias de compatibilidade com código legado
def run_stage2a(
    mr_artifacts: List[Dict],
    api_key: Optional[str] = None,
    prompt_path: str = config.PROMPT_FILE,
    dry_run: bool = True,
    cache_dir: str = "output/cache",
    output_path: str = "output/mr_llm_estimates.json",
    context_flags: Optional[Dict] = None,
) -> List[Dict]:
    """Alias para run_stage2_mr (compatibilidade com código existente)."""
    return run_stage2_mr(
        mr_artifacts=mr_artifacts,
        api_key=api_key,
        prompt_path=prompt_path,
        dry_run=dry_run,
        cache_dir=cache_dir,
        output_path=output_path,
        context_flags=context_flags,
    )
