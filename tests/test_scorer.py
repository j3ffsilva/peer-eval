"""
Tests for scorer.py — Contribution Factor Model v4.0.
"""

import pytest
from typing import Optional, List
from peer_eval import scorer
from peer_eval import config


class TestComputeScores:
    """Testes de cálculo do fator de contribuição."""

    def create_minimal_mr(self, mr_id: str, author: str, reviewers: Optional[List[str]] = None):
        """Fábrica de MR mínimo válido para testes."""
        if reviewers is None:
            reviewers = []
        return {
            "mr_id": mr_id,
            "author": author,
            "title": "test",
            "type_declared": "feat",
            "diff_summary": [{"file": "core/test.py"}],
            "quantitative": {"X": 0.5, "S": 1.0, "Q": 1.0},
            "linked_issues": [],
            "review_comments": [],
            "reviewers": reviewers,
        }

    def test_author_contribution(self):
        """Autor recebe T_AUTHOR × W(k)."""
        mrs = [self.create_minimal_mr("MR-1", "alice")]
        scores = scorer.compute_scores(mrs, None, None, ["alice", "bob"])

        assert "alice" in scores
        contrib = scores["alice"]["mr_contributions"][0]
        assert contrib["role"] == "author"
        assert contrib["T"] == config.T_AUTHOR

    def test_reviewer_contribution(self):
        """Revisor recebe (T_review / n_revisores) × W(k)."""
        mrs = [self.create_minimal_mr("MR-1", "alice", reviewers=["bob"])]
        scores = scorer.compute_scores(mrs, None, None, ["alice", "bob"])

        contrib = scores["bob"]["mr_contributions"][0]
        assert contrib["role"] == "reviewer"

    def test_multiple_reviewers_share_weight(self):
        """Múltiplos revisores dividem T_review igualmente."""
        mrs = [self.create_minimal_mr("MR-1", "alice", reviewers=["bob", "carol"])]
        scores = scorer.compute_scores(mrs, None, None, ["alice", "bob", "carol"])

        bob_t   = scores["bob"]["mr_contributions"][0]["T"]
        carol_t = scores["carol"]["mr_contributions"][0]["T"]
        assert bob_t == carol_t
        assert bob_t < config.T_REVIEWER_MAX

    def test_member_without_contribution(self):
        """Membro sem MRs: S=0, Abs=0, Rel=0, fc=0."""
        mrs = [self.create_minimal_mr("MR-1", "alice")]
        scores = scorer.compute_scores(mrs, None, None, ["alice", "bob"])

        assert scores["bob"]["S"]   == 0.0
        assert scores["bob"]["Abs"] == 0.0
        assert scores["bob"]["Rel"] == 0.0
        assert scores["bob"]["fc"]  == 0.0

    def test_abs_capped_at_one(self):
        """Abs nunca excede 1.0."""
        mrs = [
            self.create_minimal_mr("MR-1", "alice"),
            self.create_minimal_mr("MR-2", "alice"),
            self.create_minimal_mr("MR-3", "alice"),
        ]
        scores = scorer.compute_scores(mrs, None, None, ["alice"])
        assert scores["alice"]["Abs"] <= 1.0

    def test_rel_between_zero_and_one(self):
        """Rel ∈ [0, 1] para todos os membros."""
        mrs = [
            self.create_minimal_mr("MR-1", "alice"),
            self.create_minimal_mr("MR-2", "bob"),
        ]
        scores = scorer.compute_scores(mrs, None, None, ["alice", "bob"])
        for member in ["alice", "bob"]:
            assert 0 <= scores[member]["Rel"] <= 1

    def test_direct_committer_gets_penalty_not_zero(self):
        """
        Direct committers recebem penalidade de W×0.40,
        não nota zero automática.
        """
        mrs = [self.create_minimal_mr("MR-1", "alice")]
        members = ["alice"]

        # Sem penalidade
        scores_normal = scorer.compute_scores(mrs, None, None, members)
        # Com penalidade
        scores_penalty = scorer.compute_scores(
            mrs, None, None, members, direct_committers=["alice"]
        )

        # fc existe e é positivo (não zero)
        assert scores_penalty["alice"]["fc"] > 0.0
        # fc com penalidade < fc sem penalidade
        assert scores_penalty["alice"]["fc"] < scores_normal["alice"]["fc"]

    def test_direct_committer_contribution_reduced_by_factor(self):
        """W efetivo = W × DIRECT_COMMIT_PENALTY_MULTIPLIER (0.40)."""
        mrs = [self.create_minimal_mr("MR-1", "alice")]
        members = ["alice"]

        scores_normal  = scorer.compute_scores(mrs, None, None, members)
        scores_penalty = scorer.compute_scores(
            mrs, None, None, members, direct_committers=["alice"]
        )

        ratio = scores_penalty["alice"]["S"] / scores_normal["alice"]["S"]
        assert ratio == pytest.approx(config.DIRECT_COMMIT_PENALTY_MULTIPLIER, abs=0.01)

    def test_fc_formula(self):
        """fc = ALPHA × Abs + BETA × Rel."""
        mrs = [self.create_minimal_mr("MR-1", "alice")]
        scores = scorer.compute_scores(mrs, None, None, ["alice"])

        alice = scores["alice"]
        expected_fc = config.ALPHA * alice["Abs"] + config.BETA * alice["Rel"]
        assert alice["fc"] == pytest.approx(expected_fc)

    def test_nota_is_alias_for_fc(self):
        """nota deve ser igual a fc (alias de compatibilidade)."""
        mrs = [self.create_minimal_mr("MR-1", "alice")]
        scores = scorer.compute_scores(mrs, None, None, ["alice"])
        assert scores["alice"]["nota"] == scores["alice"]["fc"]

    def test_accumulates_multiple_contributions(self):
        """Membro com múltiplos papéis acumula contribuições."""
        mrs = [
            self.create_minimal_mr("MR-1", "alice", reviewers=["bob"]),
            self.create_minimal_mr("MR-2", "bob",   reviewers=["alice"]),
        ]
        scores = scorer.compute_scores(mrs, None, None, ["alice", "bob"])

        assert len(scores["alice"]["mr_contributions"]) == 2
        assert len(scores["bob"]["mr_contributions"])   == 2
        assert scores["alice"]["S"] > 0
        assert scores["bob"]["S"]   > 0

    def test_commit_estimates_flow_into_x_and_e(self):
        """commit_estimates alimentam X e E via model.resolve_components."""
        mrs = [self.create_minimal_mr("MR-1", "alice")]
        commit_estimates = [
            {
                "mr_id": "MR-1", "is_filtered": False,
                "atomicity": 0.9, "scope_clarity": 0.9, "message_quality": 0.9,
            }
        ]
        scores = scorer.compute_scores(
            mrs, None, None, ["alice"], commit_estimates=commit_estimates
        )
        # Apenas verifica que não explode e produz score positivo
        assert scores["alice"]["S"] > 0
        assert scores["alice"]["fc"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
