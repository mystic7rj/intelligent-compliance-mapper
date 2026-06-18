# -*- coding: utf-8 -*-
"""Validation tests for Docker and CI/CD configuration files."""

from __future__ import annotations

from pathlib import Path

import yaml


# Verify Dockerfile exists and declares a Python base image.
def test_dockerfile_exists_and_contains_python_base() -> None:
    # Resolve Dockerfile path in repository root.
    dockerfile = Path("Dockerfile")
    # Assert Dockerfile exists before reading content.
    assert dockerfile.exists()
    # Read Dockerfile content for base image validation.
    content = dockerfile.read_text(encoding="utf-8")
    # Assert image declaration contains expected Python base token.
    assert "FROM python" in content


# Verify Dockerfile creates and uses a non-root user.
def test_dockerfile_contains_non_root_user_creation() -> None:
    # Read Dockerfile content for user hardening checks.
    content = Path("Dockerfile").read_text(encoding="utf-8")
    # Assert non-root user creation and runtime user switch are present.
    assert "appuser" in content
    assert "USER appuser" in content


# Verify dockerignore exists and excludes local .env secrets.
def test_dockerignore_exists_and_excludes_env() -> None:
    # Resolve .dockerignore path at repository root.
    dockerignore = Path(".dockerignore")
    # Assert ignore file exists before content check.
    assert dockerignore.exists()
    # Read ignore file and verify secret file exclusion.
    content = dockerignore.read_text(encoding="utf-8")
    assert ".env" in content


# Verify docker-compose file exists and is parseable YAML.
def test_docker_compose_exists_and_is_valid_yaml() -> None:
    # Resolve docker-compose config path.
    compose_file = Path("docker-compose.yml")
    # Assert compose file exists before parsing.
    assert compose_file.exists()
    # Parse YAML to validate syntactic correctness.
    parsed = yaml.safe_load(compose_file.read_text(encoding="utf-8"))
    # Assert parsed compose data contains service definition root.
    assert isinstance(parsed, dict)
    assert "services" in parsed


# Verify CI workflow exists and includes pytest execution command.
def test_ci_workflow_exists_and_contains_pytest_command() -> None:
    # Resolve CI workflow path under GitHub actions directory.
    ci_file = Path(".github/workflows/ci.yml")
    # Assert workflow file exists before reading.
    assert ci_file.exists()
    # Read workflow content for test command validation.
    content = ci_file.read_text(encoding="utf-8")
    # Assert pytest invocation is configured in CI pipeline.
    assert "pytest" in content


# Verify security workflow exists and includes bandit scan command.
def test_security_workflow_exists_and_contains_bandit_command() -> None:
    # Resolve security workflow path under GitHub actions directory.
    security_file = Path(".github/workflows/security.yml")
    # Assert security workflow exists before reading.
    assert security_file.exists()
    # Read workflow content for bandit scan command validation.
    content = security_file.read_text(encoding="utf-8")
    # Assert bandit invocation is configured in security pipeline.
    assert "bandit" in content
