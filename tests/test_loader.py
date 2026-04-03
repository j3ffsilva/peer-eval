"""
Tests for loader.py functions.
"""

import pytest
import json
import os
import tempfile
import loader
from exceptions import FixtureNotFoundError


class TestLoadArtifacts:
    """Test artifact loading."""

    def test_load_artifacts_valid(self):
        """Load valid fixture."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"mr_id": "MR-1", "author": "test"}], f)
            path = f.name

        try:
            artifacts = loader.load_artifacts(path)
            assert isinstance(artifacts, list)
            assert len(artifacts) == 1
            assert artifacts[0]["mr_id"] == "MR-1"
        finally:
            os.unlink(path)

    def test_load_artifacts_not_found(self):
        """Raise FixtureNotFoundError if file missing."""
        with pytest.raises(FixtureNotFoundError):
            loader.load_artifacts("/nonexistent/path.json")

    def test_load_artifacts_invalid_json(self):
        """Raise JSONDecodeError if invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json")
            path = f.name

        try:
            with pytest.raises(json.JSONDecodeError):
                loader.load_artifacts(path)
        finally:
            os.unlink(path)

    def test_load_artifacts_not_list(self):
        """Raise ValueError if top-level is not a list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"mr_id": "MR-1"}, f)
            path = f.name

        try:
            with pytest.raises(ValueError):
                loader.load_artifacts(path)
        finally:
            os.unlink(path)


class TestLoadLLMEstimates:
    """Test LLM estimates loading."""

    def test_load_llm_estimates_valid(self):
        """Load valid estimates file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"mr_id": "MR-1", "E": {"value": 0.8}}], f)
            path = f.name

        try:
            estimates = loader.load_llm_estimates(path)
            assert isinstance(estimates, list)
            assert len(estimates) == 1
        finally:
            os.unlink(path)

    def test_load_llm_estimates_not_found(self):
        """Return None if file missing."""
        result = loader.load_llm_estimates("/nonexistent/path.json")
        assert result is None

    def test_load_llm_estimates_not_list(self):
        """Raise ValueError if top-level is not a list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"mr_id": "MR-1"}, f)
            path = f.name

        try:
            with pytest.raises(ValueError):
                loader.load_llm_estimates(path)
        finally:
            os.unlink(path)


class TestLoadOverrides:
    """Test override loading."""

    def test_load_overrides_valid(self):
        """Load valid overrides file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"MR-1": {"E": 0.5}, "MR-2": {"A": 0.7}}, f)
            path = f.name

        try:
            overrides = loader.load_overrides(path)
            assert isinstance(overrides, dict)
            assert overrides["MR-1"]["E"] == 0.5
        finally:
            os.unlink(path)

    def test_load_overrides_not_found(self):
        """Return None if file missing."""
        result = loader.load_overrides("/nonexistent/path.json")
        assert result is None

    def test_load_overrides_not_dict(self):
        """Raise ValueError if top-level is not a dict."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(["MR-1"], f)
            path = f.name

        try:
            with pytest.raises(ValueError):
                loader.load_overrides(path)
        finally:
            os.unlink(path)


class TestSaveJson:
    """Test JSON saving."""

    def test_save_json_creates_dir(self):
        """Create directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "subdir", "file.json")
            data = {"test": "value"}
            loader.save_json(data, path)

            assert os.path.exists(path)
            with open(path, "r") as f:
                loaded = json.load(f)
            assert loaded == data

    def test_save_json_formatting(self):
        """Verify JSON formatting (ensure_ascii=False, indent=2)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "file.json")
            data = {"nome": "José", "valor": 123}
            loader.save_json(data, path)

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Should contain proper indentation
            assert "  " in content
            # Should preserve unicode characters
            assert "José" in content
            # Should not escape non-ASCII
            assert "\\u" not in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
