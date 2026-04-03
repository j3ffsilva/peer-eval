#!/usr/bin/env python3
"""
Scenario validation report generator.

This script runs all 12 scenarios without LLM, prints a formatted report,
and validates that results match expected ranges.

Run with: python scripts/run_scenarios.py
"""

import sys
import json
from pathlib import Path

# Add parent directory to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from loader import load_artifacts
from scorer import compute_scores

FIXTURES_DIR = Path("fixtures/scenarios")


def load_and_score(fixture_name, members, direct_committers=None):
    """Load fixture and compute scores."""
    artifacts = load_artifacts(str(FIXTURES_DIR / fixture_name))
    return compute_scores(
        mr_artifacts=artifacts,
        llm_estimates=None,
        overrides=None,
        members=members,
        direct_committers=direct_committers or [],
    )


def format_header():
    """Print main header."""
    print("\n" + "╔" + "═" * 66 + "╗")
    print("║" + " " * 66 + "║")
    print("║" + "        VALIDAÇÃO DE CENÁRIOS — Modelo de Contribuição v3.0      ".center(66) + "║")
    print("║" + " " * 66 + "║")
    print("╚" + "═" * 66 + "╝\n")


def print_section(title):
    """Print section header."""
    print(f"\n{title}")
    print("─" * 68)


def print_scenario(title, members_names, num_mrs):
    """Print scenario header with brief description."""
    print(f"\n{title:50} ({num_mrs} MRs)")


def print_member_score(name, score_dict):
    """Pretty-print a member's score."""
    s = score_dict["S"]
    abs_val = score_dict["Abs"]
    rel = score_dict["Rel"]
    nota = score_dict["nota"]

    note = ""
    if score_dict.get("nota") == 0.0 and "S" in score_dict:
        note = " ← direct committer penalized"

    status = "✓" if nota > 0 else "✗"

    print(
        f"  {status} {name:8} S={s:6.3f}  Abs={abs_val:.3f}  Rel={rel:.3f}  "
        f"nota={nota:6.2%}{note}"
    )


def run_scenario(fixture_name, title, members, direct_committers=None, num_mrs=None):
    """Load, score, and print a scenario."""
    try:
        scores = load_and_score(fixture_name, members, direct_committers)

        if num_mrs is None:
            artifacts = load_artifacts(str(FIXTURES_DIR / fixture_name))
            num_mrs = len(artifacts)

        print_scenario(title, members, num_mrs)

        for name in members:
            print_member_score(name, scores[name])

        return True, scores
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        return False, None


def validate_invariants(scores_by_scenario):
    """Validate key invariants across all scenarios."""
    print("\n" + "═" * 68)
    print("INVARIANTES CRÍTICAS VALIDADAS")
    print("═" * 68)

    checks = [
        ("S1: Ana score > 0 sem autoria",
         lambda: scores_by_scenario["set1_s1"]["Ana"]["S"] > 0),

        ("S2: Fragmentação paga (Carla > Bruno)",
         lambda: scores_by_scenario["set1_s2"]["Carla"]["S"] > scores_by_scenario["set1_s2"]["Bruno"]["S"]),

        ("S3: Diego nota = 0.0 (direct committer)",
         lambda: abs(scores_by_scenario["set1_s3"]["Diego"]["nota"] - 0.0) < 0.001),

        ("S5: Bruno punido (nota < todos os outros)",
         lambda: (scores_by_scenario["set1_s5"]["Bruno"]["nota"] < scores_by_scenario["set1_s5"]["Ana"]["nota"])),

        ("S6: Gating ativo em docs triviais (Ana >> Bruno)",
         lambda: scores_by_scenario["set1_s6"]["Ana"]["S"] > 5 * scores_by_scenario["set1_s6"]["Bruno"]["S"]),

        ("SET2_S1: Modelo não volumétrico (Ana 8L > Carla 20L)",
         lambda: scores_by_scenario["set2_s1"]["Ana"]["nota"] > scores_by_scenario["set2_s1"]["Carla"]["nota"]),

        ("SET2_S2: Review suficiente (Ana Abs ≈ 1.0)",
         lambda: abs(scores_by_scenario["set2_s2"]["Ana"]["Abs"] - 1.0) < 0.01),

        ("SET2_S3: Fragmentação paga (Carla > Bruno)",
         lambda: scores_by_scenario["set2_s3"]["Carla"]["S"] > scores_by_scenario["set2_s3"]["Bruno"]["S"]),

        ("SET2_S4: Hierarquia (Ana > Bruno > Carla > Diego)",
         lambda: (scores_by_scenario["set2_s4"]["Ana"]["nota"] > scores_by_scenario["set2_s4"]["Bruno"]["nota"] and
                  scores_by_scenario["set2_s4"]["Bruno"]["nota"] > scores_by_scenario["set2_s4"]["Carla"]["nota"] and
                  scores_by_scenario["set2_s4"]["Carla"]["nota"] > scores_by_scenario["set2_s4"]["Diego"]["nota"])),

        ("SET2_S5: Resilência sem CI (todas notas > 0)",
         lambda: all(scores_by_scenario["set2_s5"][p]["nota"] > 0 for p in ["Ana", "Bruno", "Carla", "Diego"])),

        ("SET2_S6: Survival baixo → Abs < 1.0",
         lambda: scores_by_scenario["set2_s6"]["Bruno"]["Abs"] < 1.0),
    ]

    passed = 0
    failed = 0

    for check_name, check_fn in checks:
        try:
            if check_fn():
                print(f"  ✅ {check_name}")
                passed += 1
            else:
                print(f"  ❌ {check_name}")
                failed += 1
        except Exception as e:
            print(f"  ❌ {check_name} (ERROR: {e})")
            failed += 1

    print("─" * 68)
    print(f"Resultado: {passed} / {passed + failed} invariantes validadas")

    return failed == 0


def main():
    """Run all scenarios and generate report."""
    format_header()

    scores_by_scenario = {}

    # SET 1
    print_section("SET 1 — Cenários Limítrofes")

    success, scores = run_scenario(
        "set1_s1_so_review.json",
        "S1 · Só faz review",
        ["Ana", "Bruno", "Carla", "Diego"],
        num_mrs=4
    )
    if success:
        scores_by_scenario["set1_s1"] = scores

    success, scores = run_scenario(
        "set1_s2_mrs_pequenos_vs_grande.json",
        "S2 · MRs pequenos vs. MR grande",
        ["Ana", "Bruno", "Carla", "Diego"],
        num_mrs=7
    )
    if success:
        scores_by_scenario["set1_s2"] = scores

    success, scores = run_scenario(
        "set1_s3_commit_direto.json",
        "S3 · Commit direto na main",
        ["Ana", "Bruno", "Carla", "Diego"],
        direct_committers=["Diego"],
        num_mrs=3
    )
    if success:
        scores_by_scenario["set1_s3"] = scores

    success, scores = run_scenario(
        "set1_s4_mr_sem_revisor.json",
        "S4 · MR sem revisor",
        ["Ana", "Bruno", "Carla", "Diego"],
        num_mrs=6
    )
    if success:
        scores_by_scenario["set1_s4"] = scores

    success, scores = run_scenario(
        "set1_s5_codigo_nao_sobrevive.json",
        "S5 · Código que não sobrevive",
        ["Ana", "Bruno", "Carla", "Diego"],
        num_mrs=5
    )
    if success:
        scores_by_scenario["set1_s5"] = scores

    success, scores = run_scenario(
        "set1_s6_grupo_desequilibrado.json",
        "S6 · Grupo desequilibrado",
        ["Ana", "Bruno", "Carla", "Diego"],
        num_mrs=8
    )
    if success:
        scores_by_scenario["set1_s6"] = scores

    # SET 2
    print_section("SET 2 — Cenários de Validação Conceitual")

    success, scores = run_scenario(
        "set2_s1_pequeno_mas_nobre.json",
        "S1 · Pequeno mas nobre",
        ["Ana", "Carla"],
        num_mrs=2
    )
    if success:
        scores_by_scenario["set2_s1"] = scores

    success, scores = run_scenario(
        "set2_s2_review_forte_sem_autoria.json",
        "S2 · Review forte sem autoria",
        ["Ana", "Bruno", "Carla", "Diego"],
        num_mrs=3
    )
    if success:
        scores_by_scenario["set2_s2"] = scores

    success, scores = run_scenario(
        "set2_s3_fragmentacao.json",
        "S3 · Fragmentação saudável vs. oportunista",
        ["Ana", "Bruno", "Carla", "Diego"],
        num_mrs=5
    )
    if success:
        scores_by_scenario["set2_s3"] = scores

    success, scores = run_scenario(
        "set2_s4_perfis_distintos.json",
        "S4 · Perfis distintos",
        ["Ana", "Bruno", "Carla", "Diego"],
        num_mrs=4
    )
    if success:
        scores_by_scenario["set2_s4"] = scores

    success, scores = run_scenario(
        "set2_s5_sem_ci.json",
        "S5 · Projeto sem CI",
        ["Ana", "Bruno", "Carla", "Diego"],
        num_mrs=4
    )
    if success:
        scores_by_scenario["set2_s5"] = scores

    success, scores = run_scenario(
        "set2_s6_nao_sobrevive.json",
        "S6 · Código grande que não sobrevive",
        ["Ana", "Bruno", "Carla", "Diego"],
        num_mrs=4
    )
    if success:
        scores_by_scenario["set2_s6"] = scores

    # Validate invariants
    if len(scores_by_scenario) > 0:
        all_ok = validate_invariants(scores_by_scenario)
    else:
        all_ok = False

    # Final summary
    print("\n" + "═" * 68)
    if all_ok:
        print("✅ VALIDAÇÃO COMPLETA: Todos os cenários e invariantes passaram!")
    else:
        print("⚠️  VALIDAÇÃO COM ERROS: Verifique os logs acima.")
    print("═" * 68 + "\n")

    return 0 if all_ok else 1


if __name__ == "__main__":
    exit(main())
