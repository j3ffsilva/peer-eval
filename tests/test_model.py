"""
Tests for model.py functions.
"""

import pytest
import math
from peer_eval import model
from peer_eval import config


class TestSat:
    """Test saturation function."""

    def test_sat_zero(self):
        """sat(0, τ) should return 0."""
        assert model.sat(0, 100) == 0.0

    def test_sat_tau(self):
        """sat(τ, τ) should return 1 - exp(-1)."""
        expected = 1 - math.exp(-1)
        assert model.sat(100, 100) == pytest.approx(expected)

    def test_sat_large_x(self):
        """sat(x, τ) approaches 1 as x → ∞."""
        assert model.sat(1000, 100) == pytest.approx(1.0, abs=0.01)

    def test_sat_invalid_tau(self):
        """sat should raise if tau <= 0."""
        with pytest.raises(ValueError):
            model.sat(10, 0)

        with pytest.raises(ValueError):
            model.sat(10, -5)


class TestCalcX:
    """Test quantitative component calculation."""

    def test_calc_x_zero(self):
        """X with zero lines, files, modules should be 0."""
        x = model.calc_x(0, 0, 0)
        assert x == 0.0

    def test_calc_x_saturated(self):
        """X with very large values should approach 1."""
        x = model.calc_x(1000, 100, 50)
        assert x == pytest.approx(1.0, abs=0.01)

    def test_calc_x_reference(self):
        """
        Reference case: 80 lines, 4 files, 3 modules.
        X = 0.5·sat(80,100) + 0.3·sat(4,10) + 0.2·sat(3,5)
        """
        x = model.calc_x(80, 4, 3)
        sat_lines = model.sat(80, 100)
        sat_files = model.sat(4, 10)
        sat_modules = model.sat(3, 5)
        expected = 0.5 * sat_lines + 0.3 * sat_files + 0.2 * sat_modules
        assert x == pytest.approx(expected)


class TestCalcAHeuristic:
    """Test architectural weight heuristic."""

    def test_calc_a_empty(self):
        """Empty module list should return 0.5."""
        a = model.calc_a_heuristic([])
        assert a == 0.5

    def test_calc_a_single_known_module(self):
        """Single known module should return its weight."""
        a = model.calc_a_heuristic(["core/something.py"])
        assert a == 1.0  # "core" → 1.0

    def test_calc_a_single_unknown_module(self):
        """Single unknown module should return 0.5."""
        a = model.calc_a_heuristic(["unknown/file.py"])
        assert a == 0.5

    def test_calc_a_multiple_modules(self):
        """Multiple modules should return their average weight."""
        # "core" = 1.0, "api" = 0.8, "tests" = 0.7
        a = model.calc_a_heuristic(["core/file.py", "api/routes.py", "tests/test.py"])
        expected = (1.0 + 0.8 + 0.7) / 3
        assert a == pytest.approx(expected)

    def test_calc_a_duplicate_modules(self):
        """Duplicate modules still count independently."""
        a = model.calc_a_heuristic(["core/a.py", "core/b.py"])
        expected = (1.0 + 1.0) / 2
        assert a == pytest.approx(expected)


class TestCalcEHeuristic:
    """Test effort/authenticity heuristic."""

    def test_calc_e_feat_no_ci_no_issue(self):
        """feat type alone: 0.3."""
        e = model.calc_e_heuristic("feat", False, False)
        assert e == 0.3

    def test_calc_e_feat_with_ci(self):
        """feat + CI green: 0.3 + 0.2 = 0.5."""
        e = model.calc_e_heuristic("feat", True, False)
        assert e == pytest.approx(0.5)

    def test_calc_e_feat_with_issue(self):
        """feat + closes issue: 0.3 + 0.4 = 0.7."""
        e = model.calc_e_heuristic("feat", False, True)
        assert e == pytest.approx(0.7)

    def test_calc_e_feat_with_ci_and_issue(self):
        """feat + CI + issue: 0.3 + 0.2 + 0.4 = 0.9."""
        e = model.calc_e_heuristic("feat", True, True)
        assert e == pytest.approx(0.9)

    def test_calc_e_clamped(self):
        """E should be clamped to 1.0 max."""
        e = model.calc_e_heuristic("feat", True, True)
        assert e <= 1.0

    def test_calc_e_case_insensitive(self):
        """Type should be case-insensitive."""
        e1 = model.calc_e_heuristic("FEAT", False, False)
        e2 = model.calc_e_heuristic("feat", False, False)
        assert e1 == e2

    def test_calc_e_unknown_type(self):
        """Unknown type should default to 0.2."""
        e = model.calc_e_heuristic("unknown", False, False)
        assert e == 0.2


class TestCalcV:
    """Test value component calculation."""

    def test_calc_v_formula(self):
        """V = 0.35·X + 0.35·A + 0.30·E."""
        v = model.calc_v(0.8, 0.6, 0.5)
        expected = 0.35 * 0.8 + 0.35 * 0.6 + 0.30 * 0.5
        assert v == pytest.approx(expected)

    def test_calc_v_all_ones(self):
        """V(1, 1, 1) = 0.35 + 0.35 + 0.30 = 1.0."""
        v = model.calc_v(1.0, 1.0, 1.0)
        assert v == pytest.approx(1.0)

    def test_calc_v_all_zeros(self):
        """V(0, 0, 0) = 0."""
        v = model.calc_v(0.0, 0.0, 0.0)
        assert v == 0.0


class TestCalcR:
    """Test review/risk component calculation."""

    def test_calc_r_formula(self):
        """R = 0.50·S + 0.30·P + 0.20·Q."""
        r = model.calc_r(1.0, 0.5, 1.0)
        expected = 0.50 * 1.0 + 0.30 * 0.5 + 0.20 * 1.0
        assert r == pytest.approx(expected)

    def test_calc_r_all_ones(self):
        """R(1, 1, 1) = 0.50 + 0.30 + 0.20 = 1.0."""
        r = model.calc_r(1.0, 1.0, 1.0)
        assert r == pytest.approx(1.0)

    def test_calc_r_all_zeros(self):
        """R(0, 0, 0) = 0."""
        r = model.calc_r(0.0, 0.0, 0.0)
        assert r == 0.0


class TestCalcW:
    """Test MR weight calculation with gating."""

    def test_calc_w_no_gating(self):
        """W = V × R when gating not triggered."""
        w = model.calc_w(V=0.5, R=0.8, A=0.4, X=0.25)
        expected = 0.5 * 0.8
        assert w == pytest.approx(expected)

    def test_calc_w_gating_both_conditions(self):
        """Gating: A < 0.3 AND X < 0.2 → W *= 0.1."""
        w = model.calc_w(V=0.5, R=0.8, A=0.2, X=0.1)
        expected = 0.5 * 0.8 * 0.1
        assert w == pytest.approx(expected)

    def test_calc_w_gating_only_a_low(self):
        """Only A low, X high → no gating."""
        w = model.calc_w(V=0.5, R=0.8, A=0.2, X=0.25)
        expected = 0.5 * 0.8
        assert w == pytest.approx(expected)

    def test_calc_w_gating_only_x_low(self):
        """Only X low, A high → no gating."""
        w = model.calc_w(V=0.5, R=0.8, A=0.4, X=0.1)
        expected = 0.5 * 0.8
        assert w == pytest.approx(expected)

    def test_calc_w_gating_boundary_a(self):
        """A exactly at threshold (0.3): not triggered."""
        w = model.calc_w(V=0.5, R=0.8, A=0.3, X=0.1)
        expected = 0.5 * 0.8  # A=0.3 is NOT < 0.3
        assert w == pytest.approx(expected)

    def test_calc_w_gating_boundary_x(self):
        """X exactly at threshold (0.2): not triggered."""
        w = model.calc_w(V=0.5, R=0.8, A=0.2, X=0.2)
        expected = 0.5 * 0.8  # X=0.2 is NOT < 0.2
        assert w == pytest.approx(expected)


class TestReferenceCase:
    """Test against the reference case from specification."""

    def test_reference_mr(self):
        """
        Reference PR: 80 lines, 4 files, 3 modules
        A = (core=1.0 + api=0.8 + tests=0.7) / 3 ≈ 0.833
        E = feat (0.3) + CI (0.2) = 0.5
        → W ≈ 0.514 and 0.7 × W ≈ 0.360
        """
        X = model.calc_x(80, 4, 3)
        A = (1.0 + 0.8 + 0.7) / 3  # approximate from modules
        E = 0.5  # feat + CI

        V = model.calc_v(X, A, E)
        R = model.calc_r(S=1.0, P=0.5, Q=1.0)
        W = model.calc_w(V, R, A, X)

        # Should be approximately 0.514
        assert W == pytest.approx(0.514, abs=0.02)

        # 0.7 × W should be approximately 0.360
        assert 0.7 * W == pytest.approx(0.360, abs=0.01)


class TestResolveComponents:
    """Test component resolution with priority: professor > llm > heuristic."""

    def test_resolve_components_from_artifact(self):
        """Extract X, S, Q from artifact quantitative."""
        artifact = {
            "mr_id": "MR-1",
            "author": "test",
            "type_declared": "feat",
            "diff_summary": [{"file": "core/test.py"}],
            "quantitative": {"X": 0.5, "S": 1.0, "Q": 1.0},
            "linked_issues": [],
            "review_comments": [],
            "reviewers": []
        }
        result = model.resolve_components(artifact)

        assert result["X"] == 0.5
        assert result["X_source"] == "script"
        assert result["S"] == 1.0
        assert result["Q"] == 1.0

    def test_resolve_e_professor_override(self):
        """Professor override has highest priority for E."""
        artifact = {
            "mr_id": "MR-1",
            "author": "test",
            "type_declared": "feat",
            "diff_summary": [],
            "quantitative": {"X": 0.5, "S": 1.0, "Q": 1.0},
            "linked_issues": [],
            "review_comments": [],
            "reviewers": []
        }
        llm_est = {
            "E": {"value": 0.8, "confidence": "high"}
        }
        override = {"E": 0.5}

        result = model.resolve_components(artifact, llm_est, override)
        assert result["E"] == 0.5
        assert result["E_source"] == "professor"

    def test_resolve_e_llm_estimate(self):
        """LLM estimate used if no professor override and confidence != low."""
        artifact = {
            "mr_id": "MR-1",
            "author": "test",
            "type_declared": "feat",
            "diff_summary": [],
            "quantitative": {"X": 0.5, "S": 1.0, "Q": 1.0},
            "linked_issues": [],
            "review_comments": [],
            "reviewers": []
        }
        llm_est = {
            "E": {"value": 0.8, "confidence": "high"}
        }

        result = model.resolve_components(artifact, llm_est)
        assert result["E"] == 0.8
        assert result["E_source"] == "llm"

    def test_resolve_e_llm_low_confidence_ignored(self):
        """LLM estimate with low confidence is ignored."""
        artifact = {
            "mr_id": "MR-1",
            "author": "test",
            "type_declared": "feat",
            "diff_summary": [],
            "quantitative": {"X": 0.5, "S": 1.0, "Q": 1.0},
            "linked_issues": [],
            "review_comments": [],
            "reviewers": []
        }
        llm_est = {
            "E": {"value": 0.8, "confidence": "low"}
        }

        result = model.resolve_components(artifact, llm_est)
        assert result["E"] != 0.8
        assert result["E_source"] == "heuristic"

    def test_resolve_e_heuristic_fallback(self):
        """Heuristic E calculated if no override or LLM."""
        artifact = {
            "mr_id": "MR-1",
            "author": "test",
            "type_declared": "feat",
            "diff_summary": [],
            "quantitative": {"X": 0.5, "S": 1.0, "Q": 1.0},
            "linked_issues": [{"id": 1}],  # closes issue
            "review_comments": [],
            "reviewers": []
        }

        result = model.resolve_components(artifact)
        # feat (0.3) + CI (0.2 for Q=1.0) + issue (0.4) = 0.9
        assert result["E"] == pytest.approx(0.9)
        assert result["E_source"] == "heuristic"

    def test_resolve_t_review_with_reviewers(self):
        """T_review defaults to T_REVIEWER_MAX if reviewers exist."""
        artifact = {
            "mr_id": "MR-1",
            "author": "test",
            "type_declared": "feat",
            "diff_summary": [],
            "quantitative": {"X": 0.5, "S": 1.0, "Q": 1.0},
            "linked_issues": [],
            "review_comments": [],
            "reviewers": ["reviewer1"]
        }

        result = model.resolve_components(artifact)
        assert result["T_review"] == config.T_REVIEWER_MAX
        assert result["T_review_source"] == "heuristic"

    def test_resolve_t_review_without_reviewers(self):
        """T_review is 0.0 if no reviewers."""
        artifact = {
            "mr_id": "MR-1",
            "author": "test",
            "type_declared": "feat",
            "diff_summary": [],
            "quantitative": {"X": 0.5, "S": 1.0, "Q": 1.0},
            "linked_issues": [],
            "review_comments": [],
            "reviewers": []
        }

        result = model.resolve_components(artifact)
        assert result["T_review"] == 0.0
        assert result["T_review_source"] == "heuristic"

    def test_resolve_computes_v_r_w(self):
        """Result includes computed V, R, W values."""
        artifact = {
            "mr_id": "MR-1",
            "author": "test",
            "type_declared": "feat",
            "diff_summary": [{"file": "core/test.py"}],
            "quantitative": {"X": 0.5, "S": 1.0, "Q": 1.0},
            "linked_issues": [],
            "review_comments": [],
            "reviewers": []
        }

        result = model.resolve_components(artifact)
        assert "V" in result
        assert "R" in result
        assert "W" in result
        assert result["V"] > 0
        assert result["R"] > 0
        assert result["W"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
