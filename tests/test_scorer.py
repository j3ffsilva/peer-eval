"""
Tests for scorer.py functions.
"""

import pytest
from typing import Optional, List
import scorer
import config


class TestComputeScores:
    """Test score computation."""

    def create_minimal_mr(self, mr_id: str, author: str, reviewers: Optional[List[str]] = None):
        """Factory function to create minimal valid MR for testing."""
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
            "reviewers": reviewers
        }

    def test_author_contribution(self):
        """Author should receive T_AUTHOR × W(k)."""
        mrs = [self.create_minimal_mr("MR-1", "alice")]
        members = ["alice", "bob"]

        scores = scorer.compute_scores(mrs, None, None, members)

        assert "alice" in scores
        assert len(scores["alice"]["mr_contributions"]) == 1
        contrib = scores["alice"]["mr_contributions"][0]
        assert contrib["role"] == "author"
        assert contrib["T"] == config.T_AUTHOR

    def test_reviewer_contribution(self):
        """Reviewer should receive (T_review / n_reviewers) × W(k)."""
        mrs = [self.create_minimal_mr("MR-1", "alice", reviewers=["bob"])]
        members = ["alice", "bob"]

        scores = scorer.compute_scores(mrs, None, None, members)

        assert len(scores["bob"]["mr_contributions"]) == 1
        contrib = scores["bob"]["mr_contributions"][0]
        assert contrib["role"] == "reviewer"

    def test_multiple_reviewers_share_weight(self):
        """Multiple reviewers share T_review weight equally."""
        mrs = [self.create_minimal_mr("MR-1", "alice", reviewers=["bob", "carol"])]
        members = ["alice", "bob", "carol"]

        scores = scorer.compute_scores(mrs, None, None, members)

        bob_contrib = scores["bob"]["mr_contributions"][0]
        carol_contrib = scores["carol"]["mr_contributions"][0]

        # Both should receive equal weight
        assert bob_contrib["T"] == carol_contrib["T"]
        assert bob_contrib["T"] < config.T_REVIEWER_MAX  # should be half

    def test_member_without_contribution(self):
        """Member with no MRs should have S=0, Abs=0, Rel=0, nota=0."""
        mrs = [self.create_minimal_mr("MR-1", "alice")]
        members = ["alice", "bob"]

        scores = scorer.compute_scores(mrs, None, None, members)

        assert scores["bob"]["S"] == 0.0
        assert scores["bob"]["Abs"] == 0.0
        assert scores["bob"]["Rel"] == 0.0
        assert scores["bob"]["nota"] == 0.0

    def test_abs_capped_at_one(self):
        """Abs should never exceed 1.0."""
        # Create MRs with very high contribution
        mrs = [
            self.create_minimal_mr("MR-1", "alice"),
            self.create_minimal_mr("MR-2", "alice"),
            self.create_minimal_mr("MR-3", "alice"),
        ]
        members = ["alice"]

        scores = scorer.compute_scores(mrs, None, None, members)

        assert scores["alice"]["Abs"] <= 1.0

    def test_rel_between_zero_and_one(self):
        """Rel should be between 0 and 1 for all members."""
        mrs = [
            self.create_minimal_mr("MR-1", "alice"),
            self.create_minimal_mr("MR-2", "bob"),
        ]
        members = ["alice", "bob"]

        scores = scorer.compute_scores(mrs, None, None, members)

        for member in members:
            rel = scores[member]["Rel"]
            assert 0 <= rel <= 1

    def test_direct_committer_zero_score(self):
        """Direct committers should have nota = 0.0."""
        mrs = [self.create_minimal_mr("MR-1", "alice")]
        members = ["alice", "bob"]
        direct_committers = ["alice"]

        scores = scorer.compute_scores(mrs, None, None, members, direct_committers)

        assert scores["alice"]["nota"] == 0.0

    def test_grade_formula(self):
        """nota = ALPHA × Abs + BETA × Rel."""
        mrs = [self.create_minimal_mr("MR-1", "alice")]
        members = ["alice"]

        scores = scorer.compute_scores(mrs, None, None, members)

        alice = scores["alice"]
        expected_nota = config.ALPHA * alice["Abs"] + config.BETA * alice["Rel"]
        assert alice["nota"] == pytest.approx(expected_nota)

    def test_accumulates_multiple_contributions(self):
        """Member with multiple contribution roles should sum them."""
        mrs = [
            self.create_minimal_mr("MR-1", "alice", reviewers=["bob"]),
            self.create_minimal_mr("MR-2", "bob", reviewers=["alice"]),
        ]
        members = ["alice", "bob"]

        scores = scorer.compute_scores(mrs, None, None, members)

        # Both alice and bob should have 2 contributions
        assert len(scores["alice"]["mr_contributions"]) == 2
        assert len(scores["bob"]["mr_contributions"]) == 2

        # S should be sum of both
        assert scores["alice"]["S"] > 0
        assert scores["bob"]["S"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
