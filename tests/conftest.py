"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    """Configure anyio backend for async tests."""
    return "asyncio"


@pytest.fixture
def sample_tree_text():
    """A sample directory tree for testing."""
    return """\
src/
  auth/
    login.py  (120B)
    session.py  (80B)
  api/
    routes.py  (200B)
tests/
  test_auth.py  (90B)
README.md  (2KB)
"""
