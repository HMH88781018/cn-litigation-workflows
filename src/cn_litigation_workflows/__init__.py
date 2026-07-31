"""Validation and release helpers for CN Litigation Workflows."""

from .validator import PROJECT_VERSION, ValidationIssue, validate_project

__all__ = ["PROJECT_VERSION", "ValidationIssue", "validate_project"]
__version__ = PROJECT_VERSION
