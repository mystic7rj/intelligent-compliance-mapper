"""Shared pytest fixtures for security and CLI test modules."""

from __future__ import annotations

import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from src.core.gap_analyzer import Control as GapControl
from src.core.gap_analyzer import GapAnalysisResult
from src.core.models import Control, ControlFamily, Framework, Priority
from src.core.risk_scorer import RiskFinding, RiskReport
from src.data.schema import Base


# Provide an isolated in-memory database session with explicit cleanup.
@pytest.fixture()
def db_session() -> Session:
    # Create an in-memory engine for each test to avoid cross-test state.
    engine = create_engine(
        "sqlite:///:memory:",
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    # Build all ORM tables for repository-backed operations.
    Base.metadata.create_all(engine)
    # Build a scoped session factory to isolate thread-local test sessions.
    session_factory = scoped_session(sessionmaker(bind=engine))
    # Open a scoped session instance for the current test function.
    session = session_factory()
    try:
        # Yield the active session to the test.
        yield session
    finally:
        # Explicitly close active session resources before removing scoped state.
        session.close()
        # Remove scoped session registry to avoid leaked thread-local sessions.
        session_factory.remove()
        # Dispose the engine pool to release all connections.
        engine.dispose()


# Provide a realistic gap analysis result with five missing controls.
@pytest.fixture()
def mock_gap_result() -> GapAnalysisResult:
    # Build a deterministic gap result object used by CLI tests.
    yield GapAnalysisResult(
        framework_name="NIST_CSF",
        total_controls=20,
        implemented_count=15,
        missing_controls=[
            GapControl(
                control_id="PR.AC-1",
                title="Identity management",
                description="Manage identities and credentials.",
                priority="critical",
            ),
            GapControl(
                control_id="DE.CM-1",
                title="Continuous monitoring",
                description="Monitor networks for anomalies.",
                priority="high",
            ),
            GapControl(
                control_id="RS.RP-1",
                title="Incident response plan",
                description="Define response process and roles.",
                priority="high",
            ),
            GapControl(
                control_id="RC.CO-1",
                title="Recovery communications",
                description="Coordinate recovery communications.",
                priority="medium",
            ),
            GapControl(
                control_id="ID.AM-2",
                title="Software inventory",
                description="Track software assets and owners.",
                priority="medium",
            ),
        ],
        compliance_percentage=75.0,
        analyzed_at=datetime.now(tz=UTC),
    )


# Provide a realistic CRITICAL-level risk report for pipeline tests.
@pytest.fixture()
def mock_risk_report() -> RiskReport:
    # Build a deterministic risk report object used by CLI tests.
    yield RiskReport(
        overall_risk_level="CRITICAL",
        risk_score=82.4,
        findings=[
            RiskFinding(
                control_id="PR.AC-1",
                control_name="Identity management",
                severity="CRITICAL",
                likelihood=0.95,
                impact=0.95,
                risk_score=90.25,
            ),
            RiskFinding(
                control_id="DE.CM-1",
                control_name="Continuous monitoring",
                severity="HIGH",
                likelihood=0.8,
                impact=0.8,
                risk_score=64.0,
            ),
            RiskFinding(
                control_id="RS.RP-1",
                control_name="Incident response plan",
                severity="HIGH",
                likelihood=0.8,
                impact=0.75,
                risk_score=60.0,
            ),
        ],
        recommendations=[
            "1. Prioritise implementation of PR.AC-1.",
            "2. Establish continuous monitoring coverage.",
        ],
        scored_at=datetime.now(tz=UTC),
    )


# Provide a realistic framework model for load/show command tests.
@pytest.fixture()
def mock_framework() -> Framework:
    # Build one framework with families and controls for CLI serialization paths.
    yield Framework(
        name="NIST_CSF",
        version="2.0",
        description="NIST Cybersecurity Framework",
        families=[
            ControlFamily(
                function_name="Protect",
                function_id="PR",
                description="Protective safeguards",
                controls=[
                    Control(
                        id="PR.AC-1",
                        title="Identity Management",
                        description="Manage identities and credentials.",
                        priority=Priority.HIGH,
                    ),
                    Control(
                        id="PR.DS-1",
                        title="Data-at-Rest Protection",
                        description="Protect stored data.",
                        priority=Priority.CRITICAL,
                    ),
                ],
            ),
        ],
    )


# Provide a temporary output directory that is cleaned up after each test.
@pytest.fixture()
def tmp_output_dir() -> Path:
    # Create a unique temporary directory for report output assertions.
    output_dir = Path(tempfile.mkdtemp(prefix="compliance_mapper_test_output_"))
    try:
        # Yield the directory path to tests.
        yield output_dir
    finally:
        # Recursively remove the temporary directory during teardown.
        shutil.rmtree(output_dir, ignore_errors=True)


# Automatically clean up database transactions after each test function.
@pytest.fixture(autouse=True, scope="function")
def auto_cleanup_db(request: pytest.FixtureRequest) -> None:
    # Check whether the current test requested the shared db_session fixture.
    if "db_session" not in request.fixturenames:
        # Skip cleanup when no database session fixture is involved.
        yield
        return
    # Resolve the shared db_session fixture instance for this test.
    session: Session = request.getfixturevalue("db_session")
    try:
        # Yield to execute the test before cleanup occurs.
        yield
    finally:
        # Roll back any open transaction state to keep DB interactions isolated.
        session.rollback()
