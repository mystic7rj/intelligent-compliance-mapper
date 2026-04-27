"""CLI tests for compare command group with fully mocked ML dependencies."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from src.api.cli import cli


# Configure shared analyzer return payloads for compare command tests.
def _configure_analyzer_payloads(mock_analyzer: MagicMock) -> None:
    # Mock compare frameworks response with realistic summary fields.
    mock_analyzer.return_value.analyze.return_value = MagicMock(
        source_framework="NIST_CSF",
        target_framework="ISO_27001",
        total_source_controls=10,
        mapped_controls=7,
        unmapped_controls=3,
        mapping_percentage=70.0,
        matches=[],
    )
    # Mock all-pairs response with six pair summaries.
    mock_analyzer.return_value.analyze_all_pairs.return_value = [
        MagicMock(
            source_framework="NIST_CSF",
            target_framework="ISO_27001",
            mapping_percentage=70.0,
            mapped_controls=7,
            total_source_controls=10,
            unmapped_controls=3,
        )
        for _ in range(6)
    ]
    # Mock equivalence map response for source-target mapping table.
    mock_analyzer.return_value.get_equivalence_map.return_value = {
        "ID.AM-1": ["A.8.1.1"],
        "PR.AC-1": ["A.9.2.1"],
    }


# Verify `compare frameworks` exits 0 for a valid source/target pair.
# Mock analyzer class to replace real cross-framework analysis.
@patch("src.api.commands.compare.CrossFrameworkAnalyzer")
# Mock matcher class to replace semantic control matching logic.
@patch("src.api.commands.compare.ControlMatcher")
# Mock similarity calculator to replace real similarity computation.
@patch("src.api.commands.compare.SimilarityCalculator")
# Mock similarity config symbol to replace real similarity configuration.
@patch("src.api.commands.compare.SimilarityConfig", create=True)
# Mock embedding generator to replace real embedding model loading.
@patch("src.api.commands.compare.EmbeddingGenerator")
# Mock embedding config to replace real embedding configuration objects.
@patch("src.api.commands.compare.EmbeddingConfig")
# Mock framework registry to replace real registry initialization.
@patch("src.api.commands.compare.FrameworkRegistry")
# Mock control repository symbol to replace any repository usage path.
@patch("src.api.commands.compare.ControlRepository", create=True)
# Mock session context manager to replace real database sessions.
@patch("src.api.commands.compare.get_session")
def test_compare_frameworks_valid_source_target_exit_zero(
    mock_session: MagicMock,
    mock_repo: MagicMock,
    mock_registry: MagicMock,
    mock_emb_config: MagicMock,
    mock_emb_gen: MagicMock,
    mock_sim_config: MagicMock,
    mock_sim_calc: MagicMock,
    mock_matcher: MagicMock,
    mock_analyzer: MagicMock,
) -> None:
    # Mark non-essential mocks as used while keeping full chain patched.
    _ = (mock_repo, mock_registry, mock_emb_config, mock_emb_gen, mock_sim_config, mock_sim_calc, mock_matcher)
    # Configure deterministic fake payloads on analyzer mock.
    _configure_analyzer_payloads(mock_analyzer)
    # Configure session context manager for command pipeline.
    mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_session.return_value.__exit__ = MagicMock(return_value=False)
    # Invoke frameworks comparison command.
    result = CliRunner().invoke(
        cli,
        ["compare", "frameworks", "--source", "nist_csf", "--target", "iso_27001"],
    )
    # Assert command succeeds and summary text is present.
    assert result.exit_code == 0
    assert "NIST_CSF" in result.output


# Verify invalid source framework value is rejected by Click with exit code 2.
def test_compare_frameworks_invalid_source_shows_error_panel() -> None:
    # Invoke command with invalid source choice.
    result = CliRunner().invoke(
        cli,
        ["compare", "frameworks", "--source", "invalid_fw", "--target", "iso_27001"],
    )
    # Assert click returns usage error for invalid option.
    assert result.exit_code == 2
    assert "Invalid value for '--source'" in result.output


# Verify `compare all-pairs` exits 0 when analyzer returns pair results.
# Mock analyzer class to replace real cross-framework analysis.
@patch("src.api.commands.compare.CrossFrameworkAnalyzer")
# Mock matcher class to replace semantic control matching logic.
@patch("src.api.commands.compare.ControlMatcher")
# Mock similarity calculator to replace real similarity computation.
@patch("src.api.commands.compare.SimilarityCalculator")
# Mock similarity config symbol to replace real similarity configuration.
@patch("src.api.commands.compare.SimilarityConfig", create=True)
# Mock embedding generator to replace real embedding model loading.
@patch("src.api.commands.compare.EmbeddingGenerator")
# Mock embedding config to replace real embedding configuration objects.
@patch("src.api.commands.compare.EmbeddingConfig")
# Mock framework registry to replace real registry initialization.
@patch("src.api.commands.compare.FrameworkRegistry")
# Mock control repository symbol to replace any repository usage path.
@patch("src.api.commands.compare.ControlRepository", create=True)
# Mock session context manager to replace real database sessions.
@patch("src.api.commands.compare.get_session")
def test_compare_all_pairs_exit_zero(
    mock_session: MagicMock,
    mock_repo: MagicMock,
    mock_registry: MagicMock,
    mock_emb_config: MagicMock,
    mock_emb_gen: MagicMock,
    mock_sim_config: MagicMock,
    mock_sim_calc: MagicMock,
    mock_matcher: MagicMock,
    mock_analyzer: MagicMock,
) -> None:
    # Mark non-essential mocks as used while keeping full chain patched.
    _ = (mock_repo, mock_registry, mock_emb_config, mock_emb_gen, mock_sim_config, mock_sim_calc, mock_matcher)
    # Configure deterministic fake payloads on analyzer mock.
    _configure_analyzer_payloads(mock_analyzer)
    # Configure session context manager for command execution.
    mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_session.return_value.__exit__ = MagicMock(return_value=False)
    # Invoke all-pairs command.
    result = CliRunner().invoke(cli, ["compare", "all-pairs"])
    # Assert command succeeds and summary title is present.
    assert result.exit_code == 0
    assert "Cross-Framework Mapping Summary" in result.output


# Verify `compare equivalence` renders source and target mapping columns.
# Mock analyzer class to replace real cross-framework analysis.
@patch("src.api.commands.compare.CrossFrameworkAnalyzer")
# Mock matcher class to replace semantic control matching logic.
@patch("src.api.commands.compare.ControlMatcher")
# Mock similarity calculator to replace real similarity computation.
@patch("src.api.commands.compare.SimilarityCalculator")
# Mock similarity config symbol to replace real similarity configuration.
@patch("src.api.commands.compare.SimilarityConfig", create=True)
# Mock embedding generator to replace real embedding model loading.
@patch("src.api.commands.compare.EmbeddingGenerator")
# Mock embedding config to replace real embedding configuration objects.
@patch("src.api.commands.compare.EmbeddingConfig")
# Mock framework registry to replace real registry initialization.
@patch("src.api.commands.compare.FrameworkRegistry")
# Mock control repository symbol to replace any repository usage path.
@patch("src.api.commands.compare.ControlRepository", create=True)
# Mock session context manager to replace real database sessions.
@patch("src.api.commands.compare.get_session")
def test_compare_equivalence_returns_source_target_columns(
    mock_session: MagicMock,
    mock_repo: MagicMock,
    mock_registry: MagicMock,
    mock_emb_config: MagicMock,
    mock_emb_gen: MagicMock,
    mock_sim_config: MagicMock,
    mock_sim_calc: MagicMock,
    mock_matcher: MagicMock,
    mock_analyzer: MagicMock,
) -> None:
    # Mark non-essential mocks as used while keeping full chain patched.
    _ = (mock_repo, mock_registry, mock_emb_config, mock_emb_gen, mock_sim_config, mock_sim_calc, mock_matcher)
    # Configure deterministic fake payloads on analyzer mock.
    _configure_analyzer_payloads(mock_analyzer)
    # Configure session context manager for command execution.
    mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
    mock_session.return_value.__exit__ = MagicMock(return_value=False)
    # Invoke equivalence command for valid framework pair.
    result = CliRunner().invoke(
        cli,
        ["compare", "equivalence", "--source", "nist_csf", "--target", "iso_27001"],
    )
    # Assert command succeeds and table columns are rendered.
    assert result.exit_code == 0
    assert "Source Control" in result.output
    assert "Matched Target Controls" in result.output
