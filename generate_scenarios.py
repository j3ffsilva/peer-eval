#!/usr/bin/env python3
"""
Helper script to generate all 12 scenario fixtures.
This validates fixture generation logic before writing to disk.
"""

import json
import math
from pathlib import Path
import config

def sat(x: float, tau: float) -> float:
    """Saturation function."""
    return 1.0 - math.exp(-x / tau)

def calc_x(lines: int, files: int, n_modules: int) -> float:
    """Calculate quantitative X(k)."""
    sat_lines = sat(lines, config.TAU_LINES)
    sat_files = sat(files, config.TAU_FILES)
    sat_modules = sat(n_modules, config.TAU_MODULES)
    return 0.5 * sat_lines + 0.3 * sat_files + 0.2 * sat_modules

def calc_q(ci_green: bool, has_ci: bool) -> float:
    """Calculate quality Q based on CI status."""
    if ci_green:
        return 1.0
    elif has_ci:
        return 0.0
    else:
        return 0.5

def create_mr(
    mr_id: str,
    author: str,
    reviewers: list,
    lines: int,
    files: int,
    modules: list,
    type_declared: str,
    ci_green: bool,
    has_ci: bool = True,
    closes_issue: bool = False,
    survival: float = 1.0
) -> dict:
    """Create an MR artifact with calculated quantitative values."""

    # Calculate X and Q
    x_value = calc_x(lines, files, len(modules))
    q_value = calc_q(ci_green, has_ci)
    s_value = survival

    # Create diff_summary from modules
    diff_summary = []
    for i, module in enumerate(modules):
        diff_summary.append({
            "file": f"{module}/code_{i}.py",
            "additions": lines // len(modules) + (1 if i < lines % len(modules) else 0),
            "deletions": 0,
            "content_excerpt": f"# {module} code"
        })

    return {
        "mr_id": mr_id,
        "author": author,
        "title": f"{type_declared}: {mr_id.lower()} implementation",
        "description": f"Implementation for {mr_id}",
        "type_declared": type_declared,
        "opened_at": "2024-11-20T10:00:00Z",
        "merged_at": "2024-11-20T14:00:00Z",
        "deadline": "2024-11-29T23:59:00Z",
        "linked_issues": [{"id": 1, "title": "Issue"}] if closes_issue else [],
        "diff_summary": diff_summary,
        "review_comments": [],
        "reviewers": reviewers,
        "quantitative": {
            "X": round(x_value, 3),
            "S": round(s_value, 2),
            "Q": round(q_value, 2)
        }
    }

def save_scenario(name: str, mrs: list):
    """Save scenario to JSON file."""
    output_path = Path("fixtures/scenarios") / f"{name}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(mrs, f, indent=2)

    print(f"✓ Created {output_path}")
    return output_path

# ─── SET 1 ────────────────────────────────────────────────────────────────────

def set1_s1_so_review():
    """S1 — Só faz review: Ana nunca autora, só revisa."""
    mrs = [
        create_mr("MR-1", "Bruno", ["Ana"], 80, 4, ["api", "domain", "tests"], "feat", True),
        create_mr("MR-2", "Carla", ["Ana", "Diego"], 60, 3, ["core", "tests"], "fix", True, closes_issue=True, survival=0.9),
        create_mr("MR-3", "Diego", ["Ana"], 50, 2, ["services"], "feat", False, has_ci=True, survival=0.8),
        create_mr("MR-4", "Bruno", ["Carla"], 90, 5, ["core", "api", "domain"], "refactor", True),
    ]
    return save_scenario("set1_s1_so_review", mrs)

def set1_s2_mrs_pequenos_vs_grande():
    """S2 — MRs pequenos vs. MR grande: fragmentação paga."""
    mrs = [
        create_mr("MR-1", "Bruno", ["Ana"], 300, 15, ["core", "api", "domain", "services", "tests"], "feat", True, closes_issue=True),
        create_mr("MR-2", "Carla", ["Diego"], 75, 4, ["api", "domain"], "feat", True),
        create_mr("MR-3", "Carla", ["Diego"], 75, 4, ["core", "tests"], "feat", True),
        create_mr("MR-4", "Carla", ["Ana"], 75, 4, ["services"], "feat", True),
        create_mr("MR-5", "Carla", ["Ana"], 75, 3, ["domain"], "feat", True, closes_issue=True),
        create_mr("MR-6", "Ana", ["Bruno"], 80, 4, ["api", "domain", "tests"], "feat", True, survival=0.9),
        create_mr("MR-7", "Diego", ["Carla"], 60, 3, ["tests", "config"], "test", True),
    ]
    return save_scenario("set1_s2_mrs_pequenos_vs_grande", mrs)

def set1_s3_commit_direto():
    """S3 — Commit direto na main: Diego em direct_committers."""
    mrs = [
        create_mr("MR-1", "Ana", ["Bruno"], 80, 4, ["api", "domain", "tests"], "feat", True, closes_issue=True),
        create_mr("MR-2", "Bruno", ["Ana", "Carla"], 70, 3, ["core", "tests"], "fix", True, survival=0.9),
        create_mr("MR-3", "Carla", ["Ana"], 60, 2, ["services", "infra"], "refactor", True),
    ]
    return save_scenario("set1_s3_commit_direto", mrs)

def set1_s4_mr_sem_revisor():
    """S4 — MR sem revisor: Ana tem 3 MRs sem reviewer."""
    mrs = [
        create_mr("MR-1", "Ana", [], 80, 4, ["api", "domain", "tests"], "feat", True, closes_issue=True),
        create_mr("MR-2", "Ana", [], 70, 3, ["core", "services"], "fix", True, survival=0.9),
        create_mr("MR-3", "Ana", [], 60, 3, ["domain", "tests"], "refactor", False, has_ci=True),
        create_mr("MR-4", "Bruno", ["Carla"], 80, 4, ["api", "domain", "tests"], "feat", True),
        create_mr("MR-5", "Carla", ["Bruno", "Diego"], 70, 3, ["core", "tests"], "fix", True, closes_issue=True, survival=0.9),
        create_mr("MR-6", "Diego", ["Bruno"], 65, 3, ["services", "infra"], "feat", True),
    ]
    return save_scenario("set1_s4_mr_sem_revisor", mrs)

def set1_s5_codigo_nao_sobrevive():
    """S5 — Código que não sobrevive: Bruno com survival baixo."""
    mrs = [
        create_mr("MR-1", "Bruno", ["Ana"], 120, 6, ["core", "api", "domain"], "feat", True, closes_issue=True, survival=0.05),
        create_mr("MR-2", "Bruno", ["Diego"], 90, 4, ["services", "tests"], "refactor", True, survival=0.08),
        create_mr("MR-3", "Ana", ["Carla"], 80, 4, ["api", "domain", "tests"], "feat", True, closes_issue=True),
        create_mr("MR-4", "Carla", ["Ana", "Diego"], 70, 3, ["core", "tests"], "fix", True, survival=0.95),
        create_mr("MR-5", "Diego", ["Ana"], 65, 3, ["services", "infra"], "refactor", True),
    ]
    return save_scenario("set1_s5_codigo_nao_sobrevive", mrs)

def set1_s6_grupo_desequilibrado():
    """S6 — Grupo desequilibrado: Ana com 5 MRs sólidos, outros com triviais."""
    mrs = [
        create_mr("MR-1", "Ana", ["Bruno"], 100, 5, ["core", "api", "domain", "tests"], "feat", True, closes_issue=True),
        create_mr("MR-2", "Ana", ["Carla"], 90, 4, ["core", "services", "tests"], "fix", True, closes_issue=True, survival=0.95),
        create_mr("MR-3", "Ana", ["Diego"], 80, 4, ["api", "domain"], "refactor", True),
        create_mr("MR-4", "Ana", ["Bruno"], 70, 3, ["auth", "tests"], "feat", True, closes_issue=True, survival=0.9),
        create_mr("MR-5", "Ana", ["Carla"], 60, 3, ["core", "infra"], "ci", True),
        create_mr("MR-6", "Bruno", ["Ana"], 15, 1, ["docs"], "docs", True),
        create_mr("MR-7", "Carla", ["Ana"], 10, 1, ["config"], "docs", False, has_ci=True, survival=0.5),
        create_mr("MR-8", "Diego", ["Ana"], 12, 1, ["docs"], "docs", True, survival=0.8),
    ]
    return save_scenario("set1_s6_grupo_desequilibrado", mrs)

# ─── SET 2 ────────────────────────────────────────────────────────────────────

def set2_s1_pequeno_mas_nobre():
    """S2_S1 — Pequeno mas nobre: Ana com fix em domain pequeno mas impactante."""
    mrs = [
        create_mr("MR-Ana", "Ana", [], 8, 1, ["domain"], "fix", True, closes_issue=True),
        create_mr("MR-Carla", "Carla", [], 20, 1, ["docs"], "docs", True),
    ]
    return save_scenario("set2_s1_pequeno_mas_nobre", mrs)

def set2_s2_review_forte_sem_autoria():
    """S2_S2 — Review forte sem autoria: Ana não tem MRs mas revisa 3."""
    mrs = [
        create_mr("MR-1", "Bruno", ["Ana"], 80, 4, ["api", "domain", "tests"], "feat", True),
        create_mr("MR-2", "Carla", ["Ana"], 70, 3, ["core", "tests"], "fix", True, closes_issue=True, survival=0.95),
        create_mr("MR-3", "Diego", ["Ana"], 65, 3, ["services", "infra"], "refactor", True),
    ]
    return save_scenario("set2_s2_review_forte_sem_autoria", mrs)

def set2_s3_fragmentacao():
    """S2_S3 — Fragmentação: Bruno 1×300L vs Carla 4×75L."""
    mrs = [
        create_mr("MR-1", "Bruno", ["Ana"], 300, 15, ["core", "api", "domain", "services", "tests"], "feat", True, closes_issue=True),
        create_mr("MR-2", "Carla", ["Diego"], 75, 4, ["api", "domain"], "feat", True),
        create_mr("MR-3", "Carla", ["Diego"], 75, 4, ["core", "tests"], "feat", True),
        create_mr("MR-4", "Carla", ["Ana"], 75, 4, ["services"], "feat", True),
        create_mr("MR-5", "Carla", ["Ana"], 75, 3, ["domain"], "feat", True, closes_issue=True),
    ]
    return save_scenario("set2_s3_fragmentacao", mrs)

def set2_s4_perfis_distintos():
    """S2_S4 — Perfis distintos: Ana(feat) > Bruno(test) > Carla(ci) > Diego(docs)."""
    mrs = [
        create_mr("MR-Ana", "Ana", [], 75, 4, ["domain", "api"], "feat", True, closes_issue=True),
        create_mr("MR-Bruno", "Bruno", [], 70, 4, ["tests"], "test", True),
        create_mr("MR-Carla", "Carla", [], 65, 3, ["infra", "config"], "ci", True),
        create_mr("MR-Diego", "Diego", [], 5, 1, ["docs"], "docs", True),
    ]
    return save_scenario("set2_s4_perfis_distintos", mrs)

def set2_s5_sem_ci():
    """S2_S5 — Projeto sem CI: todos com hasCi=false."""
    mrs = [
        create_mr("MR-1", "Ana", ["Bruno"], 80, 4, ["api", "domain", "tests"], "feat", False, has_ci=False),
        create_mr("MR-2", "Bruno", ["Ana"], 75, 4, ["core", "tests"], "fix", False, has_ci=False, survival=0.9),
        create_mr("MR-3", "Carla", ["Diego"], 65, 3, ["services"], "feat", False, has_ci=False),
        create_mr("MR-4", "Diego", ["Carla"], 60, 2, ["api", "domain"], "refactor", False, has_ci=False, survival=0.95),
    ]
    return save_scenario("set2_s5_sem_ci", mrs)

def set2_s6_nao_sobrevive():
    """S2_S6 — Código grande que não sobrevive: Bruno survival=0.05."""
    mrs = [
        create_mr("MR-Bruno", "Bruno", ["Ana"], 120, 6, ["core", "api", "domain"], "feat", True, closes_issue=True, survival=0.05),
        create_mr("MR-Ana", "Ana", ["Carla"], 80, 4, ["api", "domain", "tests"], "feat", True, closes_issue=True),
        create_mr("MR-Carla", "Carla", ["Diego"], 70, 3, ["core", "tests"], "fix", True, survival=0.95),
        create_mr("MR-Diego", "Diego", ["Bruno"], 65, 3, ["services", "infra"], "refactor", True),
    ]
    return save_scenario("set2_s6_nao_sobrevive", mrs)

if __name__ == "__main__":
    print("Generating scenario fixtures...\n")

    print("SET 1 — Cenários Limítrofes")
    set1_s1_so_review()
    set1_s2_mrs_pequenos_vs_grande()
    set1_s3_commit_direto()
    set1_s4_mr_sem_revisor()
    set1_s5_codigo_nao_sobrevive()
    set1_s6_grupo_desequilibrado()

    print("\nSET 2 — Cenários de Validação Conceitual")
    set2_s1_pequeno_mas_nobre()
    set2_s2_review_forte_sem_autoria()
    set2_s3_fragmentacao()
    set2_s4_perfis_distintos()
    set2_s5_sem_ci()
    set2_s6_nao_sobrevive()

    print("\n✅ All 12 scenarios generated!")
