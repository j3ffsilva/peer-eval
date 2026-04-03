"""
Custom exceptions for the Contribution Factor Model.
"""


class FixtureNotFoundError(Exception):
    """Raised when a required fixture file is not found."""
    pass


class LLMParseError(Exception):
    """Raised when LLM output cannot be parsed as valid JSON."""
    pass


class MissingFieldError(Exception):
    """Raised when a required field is missing from an artifact or estimate."""
    pass
