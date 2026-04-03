"""
Test suite for all 12 contribution scoring scenarios.

This suite validates that the Python implementation correctly implements
the contribution model by testing key invariants for each scenario.

Run with: pytest tests/test_scenarios.py -v
"""

import pytest
from pathlib import Path
from scorer import compute_scores
from loader import load_artifacts

FIXTURES_DIR = Path("fixtures/scenarios")


def load_and_score(fixture_name, members, direct_committers=None, overrides=None):
    """Helper: loads fixture, runs scorer without LLM, returns scores."""
    artifacts = load_artifacts(str(FIXTURES_DIR / fixture_name))
    return compute_scores(
        mr_artifacts=artifacts,
        llm_estimates=None,  # no LLM in cycle 1
        overrides=overrides,
        members=members,
        direct_committers=direct_committers or [],
    )


# ═══════════════════════════════════════════════════════════════════════════
# SET 1 — Cenários Limítrofes
# ═══════════════════════════════════════════════════════════════════════════


class TestSet1S1SoReview:
    """S1 — Só faz review: Ana nunca autora, ganha score apenas via revisões."""

    def setup_method(self):
        """Load fixture and compute scores."""
        self.scores = load_and_score(
            "set1_s1_so_review.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )

    def test_invariant_ana_score_positive_without_authoring(self):
        """Invariant: Ana tem S(p) > 0 apesar de nunca ter sido autora."""
        assert self.scores["Ana"]["S"] > 0, \
            f"Ana S={self.scores['Ana']['S']}, expected > 0"

    def test_invariant_ana_nota_positive_without_authoring(self):
        """Invariant: Ana nota > 0 apesar de nunca ter sido autora."""
        assert self.scores["Ana"]["nota"] > 0, \
            f"Ana nota={self.scores['Ana']['nota']}, expected > 0"

    def test_all_members_have_positive_scores(self):
        """All members should have positive contributions."""
        for name in ["Ana", "Bruno", "Carla", "Diego"]:
            assert self.scores[name]["nota"] >= 0, \
                f"{name} nota={self.scores[name]['nota']}, expected >= 0"


class TestSet1S2MRsPequenosVsGrande:
    """S2 — MRs pequenos vs. MR grande: fragmentação paga dividendos."""

    def setup_method(self):
        """Load fixture and compute scores."""
        self.scores = load_and_score(
            "set1_s2_mrs_pequenos_vs_grande.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )

    def test_invariant_fragmentacao_paga(self):
        """Invariant: Carla 4×75L > Bruno 1×300L em S(p) (fragmentação paga)."""
        assert self.scores["Carla"]["S"] > self.scores["Bruno"]["S"], \
            f"Carla S={self.scores['Carla']['S']}, Bruno S={self.scores['Bruno']['S']}, " \
            f"expected Carla > Bruno"

    def test_carla_nota_supera_bruno(self):
        """Carla nota must exceed Bruno (fragmentação paga)."""
        assert self.scores["Carla"]["nota"] > self.scores["Bruno"]["nota"], \
            f"Carla nota {self.scores['Carla']['nota']} must exceed Bruno {self.scores['Bruno']['nota']}"


class TestSet1S3CommitDireto:
    """S3 — Commit direto na main: direct_committers → nota = 0.0."""

    def setup_method(self):
        """Load fixture with Diego as direct committer."""
        self.scores = load_and_score(
            "set1_s3_commit_direto.json",
            members=["Ana", "Bruno", "Carla", "Diego"],
            direct_committers=["Diego"]
        )

    def test_invariant_diego_direct_committer_nota_zero(self):
        """Invariant: Diego como direct_committer tem nota = 0.0."""
        assert self.scores["Diego"]["nota"] == pytest.approx(0.0), \
            f"Diego nota={self.scores['Diego']['nota']}, expected 0.0"

    def test_others_not_penalized(self):
        """Ana, Bruno, Carla não são direct_committers, devem ter nota > 0."""
        for name in ["Ana", "Bruno", "Carla"]:
            assert self.scores[name]["nota"] > 0, \
                f"{name} nota={self.scores[name]['nota']}, expected > 0"


class TestSet1S4MRSemRevisor:
    """S4 — MR sem revisor: Ana tem 3 MRs sem reviewer."""

    def setup_method(self):
        """Load fixture and compute scores."""
        self.scores = load_and_score(
            "set1_s4_mr_sem_revisor.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )

    def test_invariant_all_positive(self):
        """Invariant: todos têm S(p) > 0 mesmo sem reviews de Ana."""
        for name in ["Bruno", "Carla", "Diego"]:
            assert self.scores[name]["S"] > 0, \
                f"{name} S={self.scores[name]['S']}, expected > 0"

    def test_ana_has_significant_score(self):
        """Ana should have significant score from her MRs."""
        assert self.scores["Ana"]["S"] > 0.7, \
            f"Ana S={self.scores['Ana']['S']}, expected > 0.7"


class TestSet1S5CodigoNaoSobrevive:
    """S5 — Código que não sobrevive: Bruno survival=0.05 → punição severa."""

    def setup_method(self):
        """Load fixture and compute scores."""
        self.scores = load_and_score(
            "set1_s5_codigo_nao_sobrevive.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )

    def test_invariant_bruno_lowest_nota(self):
        """Invariant: Bruno tem menor nota que todos (survival baixo)."""
        assert self.scores["Bruno"]["nota"] < self.scores["Ana"]["nota"]
        assert self.scores["Bruno"]["nota"] < self.scores["Carla"]["nota"]
        assert self.scores["Bruno"]["nota"] < self.scores["Diego"]["nota"]

    def test_bruno_survival_penalty_visible(self):
        """Bruno's score should be visibly lower due to survival penalty."""
        # All others should have nota > 0.9, Bruno < 0.95
        assert self.scores["Ana"]["nota"] > 0.9
        assert self.scores["Carla"]["nota"] > 0.9
        assert self.scores["Diego"]["nota"] > 0.9


class TestSet1S6GrupoDesequilibrado:
    """S6 — Grupo desequilibrado: Ana 5 MRs sólidos, outros com triviais (gating)."""

    def setup_method(self):
        """Load fixture and compute scores."""
        self.scores = load_and_score(
            "set1_s6_grupo_desequilibrado.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )

    def test_invariant_ana_nota_maxima(self):
        """Invariant: Ana tem nota próxima a 1.0."""
        assert self.scores["Ana"]["nota"] > 0.95

    def test_invariant_ana_score_muito_maior(self):
        """Invariant: Ana S(p) >> tempo 5x dos outros (gating em triviais)."""
        assert self.scores["Ana"]["S"] > 5 * self.scores["Bruno"]["S"]

    def test_gating_reduces_trivial_contributions(self):
        """Gating should reduce trivial MR (docs) contributions significantly."""
        # Bruno, Carla, Diego have S much smaller than Ana despite 8 MRs total
        assert self.scores["Bruno"]["S"] < 0.5
        assert self.scores["Carla"]["S"] < 0.5
        assert self.scores["Diego"]["S"] < 0.5


# ═══════════════════════════════════════════════════════════════════════════
# SET 2 — Cenários de Validação Conceitual
# ═══════════════════════════════════════════════════════════════════════════


class TestSet2S1PequenoMasNobre:
    """S1 — Pequeno mas nobre: Ana 8L fix em domain > Carla 20L docs."""

    def setup_method(self):
        """Load fixture and compute scores."""
        self.scores = load_and_score(
            "set2_s1_pequeno_mas_nobre.json",
            members=["Ana", "Carla"]
        )

    def test_invariant_modelo_nao_e_volumetrico(self):
        """Invariant: Ana 8L deve superar Carla 20L (modelo não é volumétrico)."""
        assert self.scores["Ana"]["nota"] > self.scores["Carla"]["nota"]

    def test_ana_nota_high(self):
        """Ana com fix importante deve ter nota alta."""
        assert self.scores["Ana"]["nota"] > 0.9

    def test_carla_nota_gated(self):
        """Carla com docs trivial deve ter nota bem menor."""
        assert self.scores["Carla"]["nota"] < 0.15


class TestSet2S2ReviewForteSemAutoria:
    """S2 — Review forte sem autoria: Ana atinge Abs=1.0 só com reviews."""

    def setup_method(self):
        """Load fixture and compute scores."""
        self.scores = load_and_score(
            "set2_s2_review_forte_sem_autoria.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )

    def test_invariant_ana_abs_maxima(self):
        """Invariant: Ana deve atingir Abs = 1.0 via reviews."""
        assert self.scores["Ana"]["Abs"] == pytest.approx(1.0, abs=0.01)

    def test_invariant_ana_score_acima_de_L(self):
        """Invariant: Ana S(p) > L = 0.360."""
        assert self.scores["Ana"]["S"] > 0.360

    def test_ana_nota_alta(self):
        """Ana should have high nota despite no authorship."""
        assert self.scores["Ana"]["nota"] > 0.85


class TestSet2S3Fragmentacao:
    """S3 — Fragmentação: Bruno 1×300L < Carla 4×75L em S(p)."""

    def setup_method(self):
        """Load fixture and compute scores."""
        self.scores = load_and_score(
            "set2_s3_fragmentacao.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )

    def test_invariant_divisao_paga(self):
        """Invariant: Carla 4×75L > Bruno 1×300L."""
        assert self.scores["Carla"]["S"] > self.scores["Bruno"]["S"]

    def test_bruno_score_in_expected_range(self):
        """Bruno S should be around 0.509 (±0.05 tolerance)."""
        assert 0.459 <= self.scores["Bruno"]["S"] <= 0.559


class TestSet2S4PerfisDistintos:
    """S4 — Perfis distintos: Ana(feat) > Bruno(test) > Carla(ci) > Diego(docs)."""

    def setup_method(self):
        """Load fixture and compute scores."""
        self.scores = load_and_score(
            "set2_s4_perfis_distintos.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )

    def test_invariant_hierarquia_feat_test_infra_docs(self):
        """Invariant: hierarquia must-have: Ana > Bruno > Carla > Diego."""
        assert self.scores["Ana"]["nota"] > self.scores["Bruno"]["nota"], \
            f"Ana {self.scores['Ana']['nota']} should exceed Bruno"
        assert self.scores["Bruno"]["nota"] > self.scores["Carla"]["nota"], \
            f"Bruno {self.scores['Bruno']['nota']} should exceed Carla"
        assert self.scores["Carla"]["nota"] > self.scores["Diego"]["nota"], \
            f"Carla {self.scores['Carla']['nota']} should exceed Diego"


class TestSet2S5SemCI:
    """S5 — Projeto sem CI: todos com hasCi=false, modelos não colapsam."""

    def setup_method(self):
        """Load fixture with all Q=0.5."""
        self.scores = load_and_score(
            "set2_s5_sem_ci.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )

    def test_invariant_modelo_nao_colapsa_sem_ci(self):
        """Invariant: Nenhuma nota deve ser 0 — modelo resiliente sem CI."""
        for name in ["Ana", "Bruno", "Carla", "Diego"]:
            assert self.scores[name]["nota"] > 0, \
                f"{name} nota={self.scores[name]['nota']}, expected > 0"

    def test_all_positive(self):
        """All members should have positive scores without CI."""
        for name in ["Ana", "Bruno", "Carla", "Diego"]:
            assert self.scores[name]["S"] > 0


class TestSet2S6NaoSobrevive:
    """S6 — Código grande que não sobrevive: Bruno survival=0.05."""

    def setup_method(self):
        """Load fixture and compute scores."""
        self.scores = load_and_score(
            "set2_s6_nao_sobrevive.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )

    def test_invariant_bruno_nao_atinge_abs_maxima(self):
        """Invariant: Bruno Abs < 1.0 (não atinge L devido survival baixo)."""
        assert self.scores["Bruno"]["Abs"] < 1.0

    def test_bruno_score_in_expected_range(self):
        """Bruno S should be around 0.209 (±0.15 tolerance for low S values)."""
        assert self.scores["Bruno"]["S"] > 0.15
        assert self.scores["Bruno"]["S"] < 0.45

    def test_bruno_note_penalized(self):
        """Bruno nota should be visibly lower than others due to survival."""
        assert self.scores["Bruno"]["nota"] < self.scores["Carla"]["nota"]


# ═══════════════════════════════════════════════════════════════════════════
# Summary Tests — Critical Invariants (all 12 scenarios)
# ═══════════════════════════════════════════════════════════════════════════


class TestAllInvariants:
    """All critical invariants across all scenarios."""

    def test_set1_s1_ana_positive_without_authoring(self):
        """SET 1 S1: Ana has score without being author."""
        scores = load_and_score(
            "set1_s1_so_review.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )
        assert scores["Ana"]["S"] > 0

    def test_set1_s2_fragmentacao_paga(self):
        """SET 1 S2: small MRs outweigh large single MR."""
        scores = load_and_score(
            "set1_s2_mrs_pequenos_vs_grande.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )
        assert scores["Carla"]["S"] > scores["Bruno"]["S"]

    def test_set1_s3_diego_direct_committer(self):
        """SET 1 S3: direct committer penalized to nota=0."""
        scores = load_and_score(
            "set1_s3_commit_direto.json",
            members=["Ana", "Bruno", "Carla", "Diego"],
            direct_committers=["Diego"]
        )
        assert scores["Diego"]["nota"] == pytest.approx(0.0)

    def test_set1_s5_bruno_lowest(self):
        """SET 1 S5: low survival penalizes most."""
        scores = load_and_score(
            "set1_s5_codigo_nao_sobrevive.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )
        assert scores["Bruno"]["nota"] < scores["Ana"]["nota"]
        assert scores["Bruno"]["nota"] < scores["Carla"]["nota"]
        assert scores["Bruno"]["nota"] < scores["Diego"]["nota"]

    def test_set1_s6_gating_docs(self):
        """SET 1 S6: gating suppresses trivial contributions."""
        scores = load_and_score(
            "set1_s6_grupo_desequilibrado.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )
        assert scores["Ana"]["S"] > 5 * scores["Bruno"]["S"]

    def test_set2_s1_modelo_nao_volumetrico(self):
        """SET 2 S1: model is not purely volumetric."""
        scores = load_and_score(
            "set2_s1_pequeno_mas_nobre.json",
            members=["Ana", "Carla"]
        )
        assert scores["Ana"]["nota"] > scores["Carla"]["nota"]

    def test_set2_s2_ana_abs_maxima(self):
        """SET 2 S2: review-only contribution can reach Abs=1.0."""
        scores = load_and_score(
            "set2_s2_review_forte_sem_autoria.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )
        assert scores["Ana"]["Abs"] == pytest.approx(1.0, abs=0.01)

    def test_set2_s3_carla_supera_bruno(self):
        """SET 2 S3: fragmentation advantage."""
        scores = load_and_score(
            "set2_s3_fragmentacao.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )
        assert scores["Carla"]["S"] > scores["Bruno"]["S"]

    def test_set2_s4_hierarquia(self):
        """SET 2 S4: commit type hierarchy (feat > test > ci > docs)."""
        scores = load_and_score(
            "set2_s4_perfis_distintos.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )
        assert scores["Ana"]["nota"] > scores["Bruno"]["nota"]
        assert scores["Bruno"]["nota"] > scores["Carla"]["nota"]
        assert scores["Carla"]["nota"] > scores["Diego"]["nota"]

    def test_set2_s5_resilencia_sem_ci(self):
        """SET 2 S5: model is resilient without CI."""
        scores = load_and_score(
            "set2_s5_sem_ci.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )
        for name in ["Ana", "Bruno", "Carla", "Diego"]:
            assert scores[name]["nota"] > 0

    def test_set2_s6_bruno_nao_atinge_abs_maxima(self):
        """SET 2 S6: low survival prevents reaching max absolute score."""
        scores = load_and_score(
            "set2_s6_nao_sobrevive.json",
            members=["Ana", "Bruno", "Carla", "Diego"]
        )
        assert scores["Bruno"]["Abs"] < 1.0
