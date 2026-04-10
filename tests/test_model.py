"""
Tests for model.py functions — Contribution Factor Model v4.0.
"""

import pytest
import math
from peer_eval import model
from peer_eval import config


class TestSat:
    """sat() mantida por compatibilidade e uso potencial em extensões."""

    def test_sat_zero(self):
        assert model.sat(0, 100) == 0.0

    def test_sat_tau(self):
        expected = 1 - math.exp(-1)
        assert model.sat(100, 100) == pytest.approx(expected)

    def test_sat_large_x(self):
        assert model.sat(1000, 100) == pytest.approx(1.0, abs=0.01)

    def test_sat_invalid_tau(self):
        with pytest.raises(ValueError):
            model.sat(10, 0)
        with pytest.raises(ValueError):
            model.sat(10, -5)


class TestCalcMessageSyntax:
    """Avaliação determinística de sintaxe de mensagens de commit."""

    def test_full_conventional_commit(self):
        """Prefix + scope + length + description → 1.0."""
        msg = "feat(auth): add JWT expiration validation to prevent stale tokens"
        score = model.calc_message_syntax(msg)
        assert score == pytest.approx(1.0)

    def test_prefix_no_scope_short(self):
        """Prefix sem scope, 20 chars (não > 20) → 0.6 (prefix + description)."""
        msg = "feat: add validation"  # 20 chars exatos → sem bônus de length
        score = model.calc_message_syntax(msg)
        assert score == pytest.approx(0.6, abs=0.05)

    def test_degenerate_message_zero(self):
        """Mensagens degeneradas → 0.0."""
        for msg in ["fix", "wip", "update", "done"]:
            assert model.calc_message_syntax(msg) == 0.0, f"Expected 0.0 for '{msg}'"

    def test_unknown_prefix_no_bonus(self):
        """Prefixo não convencional não recebe bônus de tipo."""
        msg = "updated the payment module with new logic"
        score = model.calc_message_syntax(msg)
        # Sem prefix válido: apenas length (0.2) e description (0.2) se aplicável
        assert score < 0.5

    def test_fix_with_scope_and_description(self):
        """fix(login): correct null check em authentication flow → ~0.8."""
        msg = "fix(login): correct null check in authentication flow"
        score = model.calc_message_syntax(msg)
        assert score >= 0.8

    def test_case_insensitive_prefix(self):
        """Prefixo deve ser case-insensitive."""
        s1 = model.calc_message_syntax("feat(x): do something meaningful")
        s2 = model.calc_message_syntax("FEAT(x): do something meaningful")
        assert s1 == pytest.approx(s2)


class TestCalcXFromCommits:
    """X(k) = média(atomicity × scope_clarity)."""

    def test_empty_commits_returns_neutral(self):
        assert model.calc_x_from_commits([]) == pytest.approx(0.5)

    def test_single_commit(self):
        commits = [{"atomicity": 0.9, "scope_clarity": 0.9}]
        assert model.calc_x_from_commits(commits) == pytest.approx(0.81)

    def test_multiple_commits_average(self):
        commits = [
            {"atomicity": 0.9, "scope_clarity": 0.9},  # 0.81
            {"atomicity": 0.8, "scope_clarity": 0.8},  # 0.64
            {"atomicity": 0.7, "scope_clarity": 0.9},  # 0.63
            {"atomicity": 0.6, "scope_clarity": 0.7},  # 0.42
        ]
        expected = (0.81 + 0.64 + 0.63 + 0.42) / 4
        assert model.calc_x_from_commits(commits) == pytest.approx(expected)

    def test_defaults_when_keys_missing(self):
        """Sem as chaves, usa 0.5 × 0.5 = 0.25 por commit."""
        commits = [{}, {}]
        assert model.calc_x_from_commits(commits) == pytest.approx(0.25)


class TestCalcEFromCommits:
    """E(k) = média(message_quality)."""

    def test_empty_commits_returns_neutral(self):
        assert model.calc_e_from_commits([]) == pytest.approx(0.5)

    def test_single_commit(self):
        commits = [{"message_quality": 0.90}]
        assert model.calc_e_from_commits(commits) == pytest.approx(0.90)

    def test_multiple_commits_average(self):
        commits = [
            {"message_quality": 0.90},
            {"message_quality": 0.75},
            {"message_quality": 0.80},
            {"message_quality": 0.55},
        ]
        expected = (0.90 + 0.75 + 0.80 + 0.55) / 4
        assert model.calc_e_from_commits(commits) == pytest.approx(expected)


class TestCalcS:
    """S(k) — sobrevivência da contribuição."""

    def test_normal_case(self):
        assert model.calc_s() == config.S_NORMAL

    def test_reverted(self):
        assert model.calc_s(reverted=True) == config.S_REVERTED

    def test_overwritten_above_threshold(self):
        assert model.calc_s(overwritten_ratio=0.85) == config.S_OVERWRITTEN

    def test_overwritten_at_threshold_not_penalized(self):
        """exatamente no limiar: não penaliza (threshold é strict >)."""
        assert model.calc_s(overwritten_ratio=config.OVERWRITE_THRESHOLD) == config.S_NORMAL

    def test_reverted_takes_priority(self):
        """Revertido tem prioridade sobre overwritten."""
        assert model.calc_s(reverted=True, overwritten_ratio=0.9) == config.S_REVERTED


class TestCalcQ:
    """Q(k) — qualidade CI."""

    def test_no_ci_configured(self):
        assert model.calc_q(ci_configured=False) == config.Q_NO_CI

    def test_green_first_attempt(self):
        assert model.calc_q(ci_configured=True, ci_passed=True, ci_attempts=1) == config.Q_GREEN_FIRST

    def test_green_after_fix(self):
        assert model.calc_q(ci_configured=True, ci_passed=True, ci_attempts=3) == config.Q_GREEN_AFTER_FIX

    def test_failed_merged(self):
        assert model.calc_q(ci_configured=True, ci_passed=False) == config.Q_FAILED_MERGED


class TestCalcV:
    """V(k) = 0.35·X + 0.35·A + 0.30·E."""

    def test_formula(self):
        v = model.calc_v(0.625, 0.75, 0.750)
        expected = 0.35 * 0.625 + 0.35 * 0.75 + 0.30 * 0.750
        assert v == pytest.approx(expected)

    def test_all_ones(self):
        assert model.calc_v(1.0, 1.0, 1.0) == pytest.approx(1.0)

    def test_all_zeros(self):
        assert model.calc_v(0.0, 0.0, 0.0) == 0.0


class TestCalcR:
    """R(k) = 0.60·S + 0.40·Q (P removido)."""

    def test_formula(self):
        r = model.calc_r(1.0, 1.0)
        assert r == pytest.approx(0.60 + 0.40)

    def test_all_ones(self):
        assert model.calc_r(1.0, 1.0) == pytest.approx(1.0)

    def test_all_zeros(self):
        assert model.calc_r(0.0, 0.0) == 0.0

    def test_partial(self):
        r = model.calc_r(S=1.0, Q=0.7)
        expected = 0.60 * 1.0 + 0.40 * 0.7
        assert r == pytest.approx(expected)


class TestCalcW:
    """W(k) com gating por trivialidade."""

    def test_no_gating(self):
        w = model.calc_w(V=0.5, R=0.8, A=0.4, X=0.25)
        assert w == pytest.approx(0.5 * 0.8)

    def test_gating_both_conditions(self):
        w = model.calc_w(V=0.5, R=0.8, A=0.2, X=0.1)
        assert w == pytest.approx(0.5 * 0.8 * config.GATE_PENALTY)

    def test_gating_only_a_low(self):
        w = model.calc_w(V=0.5, R=0.8, A=0.2, X=0.25)
        assert w == pytest.approx(0.5 * 0.8)

    def test_gating_only_x_low(self):
        w = model.calc_w(V=0.5, R=0.8, A=0.4, X=0.1)
        assert w == pytest.approx(0.5 * 0.8)

    def test_gating_boundary_a(self):
        """A = 0.3 exato: NÃO dispara gating (threshold é strict <)."""
        w = model.calc_w(V=0.5, R=0.8, A=0.3, X=0.1)
        assert w == pytest.approx(0.5 * 0.8)

    def test_gating_boundary_x(self):
        """X = 0.2 exato: NÃO dispara gating."""
        w = model.calc_w(V=0.5, R=0.8, A=0.2, X=0.2)
        assert w == pytest.approx(0.5 * 0.8)


class TestReferenceCase:
    """Caso de referência do modelo v4.0 (do paper)."""

    def test_reference_mr_v4(self):
        """
        MR com 4 commits:
          c1: atom=0.9, scope=0.9, mq=0.90
          c2: atom=0.8, scope=0.8, mq=0.75
          c3: atom=0.7, scope=0.9, mq=0.80
          c4: atom=0.6, scope=0.7, mq=0.55
        A(k) = 0.75, S(k) = 1.0, Q(k) = 1.0
        """
        commits = [
            {"atomicity": 0.9, "scope_clarity": 0.9, "message_quality": 0.90},
            {"atomicity": 0.8, "scope_clarity": 0.8, "message_quality": 0.75},
            {"atomicity": 0.7, "scope_clarity": 0.9, "message_quality": 0.80},
            {"atomicity": 0.6, "scope_clarity": 0.7, "message_quality": 0.55},
        ]
        X = model.calc_x_from_commits(commits)
        E = model.calc_e_from_commits(commits)
        A = 0.75

        assert X == pytest.approx(0.625, abs=0.001)
        assert E == pytest.approx(0.750, abs=0.001)

        V = model.calc_v(X, A, E)
        R = model.calc_r(S=1.0, Q=1.0)
        W = model.calc_w(V, R, A, X)

        assert V == pytest.approx(0.35 * 0.625 + 0.35 * 0.75 + 0.30 * 0.750, abs=0.001)
        assert R == pytest.approx(1.0)
        assert W == pytest.approx(V * R)


class TestResolveComponents:
    """Resolução de componentes com fallback gracioso."""

    def _base_artifact(self, **kwargs):
        base = {
            "mr_id": "MR-1",
            "author": "test",
            "type_declared": "feat",
            "diff_summary": [{"file": "core/test.py"}],
            "quantitative": {"X": 0.5, "S": 1.0, "Q": 1.0},
            "linked_issues": [],
            "review_comments": [],
            "reviewers": [],
        }
        base.update(kwargs)
        return base

    def test_x_from_commits_when_provided(self):
        """X vem de commits quando commit_estimates é fornecido."""
        artifact = self._base_artifact()
        commits = [
            {"mr_id": "MR-1", "is_filtered": False, "atomicity": 0.8, "scope_clarity": 0.8,
             "message_quality": 0.9},
        ]
        result = model.resolve_components(artifact, commit_estimates=commits)
        assert result["X_source"] == "commits"
        assert result["X"] == pytest.approx(0.64)

    def test_x_legacy_when_no_commits(self):
        """X vem de quantitative quando sem commits (compatibilidade legada)."""
        artifact = self._base_artifact()
        result = model.resolve_components(artifact)
        assert result["X_source"] == "legacy"
        assert result["X"] == pytest.approx(0.5)

    def test_e_from_commits_when_provided(self):
        """E vem de commits quando commit_estimates é fornecido."""
        artifact = self._base_artifact()
        commits = [
            {"mr_id": "MR-1", "is_filtered": False, "atomicity": 0.8, "scope_clarity": 0.8,
             "message_quality": 0.8},
        ]
        result = model.resolve_components(artifact, commit_estimates=commits)
        assert result["E_source"] == "commits"
        assert result["E"] == pytest.approx(0.8)

    def test_e_professor_override_takes_priority(self):
        """Professor override tem prioridade máxima sobre E."""
        artifact = self._base_artifact()
        commits = [{"mr_id": "MR-1", "is_filtered": False, "atomicity": 0.9,
                    "scope_clarity": 0.9, "message_quality": 0.9}]
        result = model.resolve_components(artifact, overrides={"E": 0.3},
                                          commit_estimates=commits)
        assert result["E"] == pytest.approx(0.3)
        assert result["E_source"] == "professor"

    def test_s_from_artifact_fields(self):
        """S vem dos campos reverted/overwritten_ratio quando presentes."""
        artifact = self._base_artifact(reverted=False, overwritten_ratio=0.0)
        result = model.resolve_components(artifact)
        assert result["S_source"] == "script"
        assert result["S"] == config.S_NORMAL

    def test_s_legacy_when_fields_absent(self):
        """S vem de quantitative quando campos novos ausentes."""
        artifact = self._base_artifact()  # sem reverted/overwritten_ratio
        result = model.resolve_components(artifact)
        assert result["S_source"] == "legacy"
        assert result["S"] == pytest.approx(1.0)

    def test_q_from_artifact_fields(self):
        """Q vem de ci_passed/ci_attempts quando presentes."""
        artifact = self._base_artifact(ci_configured=True, ci_passed=True, ci_attempts=1)
        result = model.resolve_components(artifact)
        assert result["Q_source"] == "script"
        assert result["Q"] == config.Q_GREEN_FIRST

    def test_a_llm_estimate(self):
        """A vem de LLM se confidence != low."""
        artifact = self._base_artifact()
        llm_est = {"A": {"value": 0.85, "confidence": "high"}}
        result = model.resolve_components(artifact, llm_estimate=llm_est)
        assert result["A"] == pytest.approx(0.85)
        assert result["A_source"] == "llm"

    def test_a_heuristic_fallback(self):
        """A usa heurística quando sem LLM."""
        artifact = self._base_artifact()
        result = model.resolve_components(artifact)
        assert result["A_source"] == "heuristic"
        assert result["A"] == pytest.approx(1.0)  # "core" → 1.0

    def test_t_review_llm(self):
        """T_review vem de LLM se confidence != low."""
        artifact = self._base_artifact(reviewers=["bob"])
        llm_est = {"T_review": {"value": 0.25, "level": "substantive", "confidence": "high"}}
        result = model.resolve_components(artifact, llm_estimate=llm_est)
        assert result["T_review"] == pytest.approx(0.25)
        assert result["T_review_source"] == "llm"

    def test_computes_v_r_w(self):
        """Resultado inclui V, R, W calculados."""
        artifact = self._base_artifact()
        result = model.resolve_components(artifact)
        assert "V" in result and "R" in result and "W" in result
        assert result["V"] > 0
        assert result["R"] > 0
        assert result["W"] > 0

    def test_filtered_commits_excluded_from_x_e(self):
        """Commits filtrados (is_filtered=True) não entram em X e E."""
        artifact = self._base_artifact()
        commits = [
            {"mr_id": "MR-1", "is_filtered": True, "atomicity": 0.0,
             "scope_clarity": 0.0, "message_quality": 0.0},
            {"mr_id": "MR-1", "is_filtered": False, "atomicity": 0.8,
             "scope_clarity": 0.8, "message_quality": 0.8},
        ]
        result = model.resolve_components(artifact, commit_estimates=commits)
        # Só o commit não filtrado deve contar
        assert result["X"] == pytest.approx(0.64)
        assert result["E"] == pytest.approx(0.8)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
