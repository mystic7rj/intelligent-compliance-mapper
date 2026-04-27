"""Tests for the database layer — repositories, session management, and schema.

All tests use in-memory SQLite (``sqlite:///:memory:``) and never touch
a real database.  Each test gets its own session wrapped in a transaction
that is rolled back after the test completes.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.data.database import DatabaseConfigError, get_engine, get_session
from src.data.repositories.control_repository import (
    ControlRepository,
    ControlRepositoryError,
)
from src.data.repositories.framework_repository import (
    FrameworkRepository,
    FrameworkRepositoryError,
)
from src.data.schema import Base, ControlFamilyTable, ControlTable, FrameworkTable

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine():
    """Create an in-memory SQLite engine with all tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db_session(db_engine):
    """Yield a session that rolls back after each test."""
    with Session(bind=db_engine) as session:
        yield session
        session.rollback()


@pytest.fixture()
def framework_repo(db_session: Session) -> FrameworkRepository:
    """Return a FrameworkRepository bound to the test session."""
    return FrameworkRepository(db_session)


@pytest.fixture()
def control_repo(db_session: Session) -> ControlRepository:
    """Return a ControlRepository bound to the test session."""
    return ControlRepository(db_session)


@pytest.fixture()
def sample_framework() -> FrameworkTable:
    """Return a valid FrameworkTable instance."""
    return FrameworkTable(
        name="NIST CSF",
        version="2.0",
        description="Cybersecurity framework",
    )


@pytest.fixture()
def saved_framework(
    framework_repo: FrameworkRepository,
    sample_framework: FrameworkTable,
) -> FrameworkTable:
    """Save and return a framework so other tests can use it."""
    return framework_repo.save(sample_framework)


@pytest.fixture()
def sample_family(saved_framework: FrameworkTable) -> ControlFamilyTable:
    """Return a ControlFamilyTable linked to the saved framework."""
    return ControlFamilyTable(
        framework_id=saved_framework.id,
        function_name="Identify",
        function_id="ID",
        description="Identify function",
    )


@pytest.fixture()
def saved_family(
    db_session: Session,
    sample_family: ControlFamilyTable,
) -> ControlFamilyTable:
    """Persist and return a control family."""
    db_session.add(sample_family)
    db_session.flush()
    return sample_family


# ---------------------------------------------------------------------------
# FrameworkRepository tests
# ---------------------------------------------------------------------------


class TestFrameworkRepository:
    """CRUD tests for FrameworkRepository."""

    def test_save_framework(
        self, framework_repo: FrameworkRepository, sample_framework: FrameworkTable
    ) -> None:
        result = framework_repo.save(sample_framework)
        assert result.id is not None
        assert result.name == "NIST CSF"

    def test_get_by_name(
        self, framework_repo: FrameworkRepository, saved_framework: FrameworkTable
    ) -> None:
        result = framework_repo.get_by_name("NIST CSF")
        assert result is not None
        assert result.name == "NIST CSF"
        assert result.version == "2.0"

    def test_get_by_name_not_found(
        self, framework_repo: FrameworkRepository
    ) -> None:
        result = framework_repo.get_by_name("Nonexistent")
        assert result is None

    def test_get_all_empty(self, framework_repo: FrameworkRepository) -> None:
        result = framework_repo.get_all()
        assert result == []

    def test_get_all_with_data(
        self, framework_repo: FrameworkRepository, saved_framework: FrameworkTable
    ) -> None:
        result = framework_repo.get_all()
        assert len(result) == 1
        assert result[0].name == "NIST CSF"

    def test_delete_existing(
        self, framework_repo: FrameworkRepository, saved_framework: FrameworkTable
    ) -> None:
        deleted = framework_repo.delete(saved_framework.id)
        assert deleted is True
        assert framework_repo.get_by_name("NIST CSF") is None

    def test_delete_nonexistent(
        self, framework_repo: FrameworkRepository
    ) -> None:
        deleted = framework_repo.delete(uuid.uuid4())
        assert deleted is False

    def test_save_duplicate_name_version_raises(
        self,
        framework_repo: FrameworkRepository,
        saved_framework: FrameworkTable,
        db_session: Session,
    ) -> None:
        duplicate = FrameworkTable(
            name="NIST CSF",
            version="2.0",
            description="Duplicate",
        )
        with pytest.raises(IntegrityError):
            framework_repo.save(duplicate)
            db_session.flush()

    def test_save_empty_name_raises(
        self, framework_repo: FrameworkRepository
    ) -> None:
        bad = FrameworkTable(name="", version="1.0")
        with pytest.raises(FrameworkRepositoryError, match="name cannot be empty"):
            framework_repo.save(bad)

    def test_save_empty_version_raises(
        self, framework_repo: FrameworkRepository
    ) -> None:
        bad = FrameworkTable(name="ISO 27001", version="")
        with pytest.raises(FrameworkRepositoryError, match="version cannot be empty"):
            framework_repo.save(bad)

    def test_get_by_name_empty_raises(
        self, framework_repo: FrameworkRepository
    ) -> None:
        with pytest.raises(FrameworkRepositoryError, match="name cannot be empty"):
            framework_repo.get_by_name("")

    def test_get_by_name_whitespace_raises(
        self, framework_repo: FrameworkRepository
    ) -> None:
        with pytest.raises(FrameworkRepositoryError, match="name cannot be empty"):
            framework_repo.get_by_name("   ")


# ---------------------------------------------------------------------------
# ControlRepository tests
# ---------------------------------------------------------------------------


class TestControlRepository:
    """CRUD tests for ControlRepository."""

    def test_save_bulk(
        self,
        control_repo: ControlRepository,
        saved_family: ControlFamilyTable,
    ) -> None:
        controls = [
            ControlTable(
                family_id=saved_family.id,
                control_id="ID.AM-1",
                title="Asset inventory",
                description="Physical devices inventoried",
                priority="high",
            ),
            ControlTable(
                family_id=saved_family.id,
                control_id="ID.AM-2",
                title="Software inventory",
                description="Software platforms inventoried",
                priority="medium",
            ),
        ]
        result = control_repo.save_bulk(controls)
        assert len(result) == 2
        assert all(c.id is not None for c in result)

    def test_get_by_framework(
        self,
        control_repo: ControlRepository,
        saved_family: ControlFamilyTable,
        saved_framework: FrameworkTable,
    ) -> None:
        controls = [
            ControlTable(
                family_id=saved_family.id,
                control_id="ID.AM-1",
                title="Asset inventory",
            ),
        ]
        control_repo.save_bulk(controls)
        result = control_repo.get_by_framework(saved_framework.id)
        assert len(result) == 1
        assert result[0].control_id == "ID.AM-1"

    def test_get_by_framework_empty(
        self, control_repo: ControlRepository
    ) -> None:
        result = control_repo.get_by_framework(uuid.uuid4())
        assert result == []

    def test_get_by_id(
        self,
        control_repo: ControlRepository,
        saved_family: ControlFamilyTable,
    ) -> None:
        ctrl = ControlTable(
            family_id=saved_family.id,
            control_id="ID.AM-1",
            title="Asset inventory",
        )
        control_repo.save_bulk([ctrl])
        result = control_repo.get_by_id(ctrl.id)
        assert result is not None
        assert result.control_id == "ID.AM-1"

    def test_get_by_id_not_found(
        self, control_repo: ControlRepository
    ) -> None:
        result = control_repo.get_by_id(uuid.uuid4())
        assert result is None

    def test_save_bulk_empty_list_raises(
        self, control_repo: ControlRepository
    ) -> None:
        with pytest.raises(ControlRepositoryError, match="cannot be empty"):
            control_repo.save_bulk([])

    def test_save_bulk_empty_control_id_raises(
        self,
        control_repo: ControlRepository,
        saved_family: ControlFamilyTable,
    ) -> None:
        bad = ControlTable(
            family_id=saved_family.id,
            control_id="",
            title="Test",
        )
        with pytest.raises(ControlRepositoryError, match="control_id cannot be empty"):
            control_repo.save_bulk([bad])

    def test_save_bulk_empty_title_raises(
        self,
        control_repo: ControlRepository,
        saved_family: ControlFamilyTable,
    ) -> None:
        bad = ControlTable(
            family_id=saved_family.id,
            control_id="ID.AM-1",
            title="",
        )
        with pytest.raises(ControlRepositoryError, match="title cannot be empty"):
            control_repo.save_bulk([bad])


# ---------------------------------------------------------------------------
# Transaction rollback tests
# ---------------------------------------------------------------------------


class TestTransactionRollback:
    """Verify that session rollback works correctly on errors."""

    def test_rollback_on_constraint_violation(self, db_engine) -> None:
        """A constraint violation should not corrupt the session."""
        # Use an independent session so the first save actually commits
        with Session(bind=db_engine) as session:
            repo = FrameworkRepository(session)
            repo.save(FrameworkTable(name="ISO 27001", version="2022"))
            session.commit()

        # New session: attempt a duplicate — should fail
        with Session(bind=db_engine) as session:
            repo = FrameworkRepository(session)
            dup = FrameworkTable(name="ISO 27001", version="2022")
            with pytest.raises(IntegrityError):
                repo.save(dup)
                session.flush()

            # Session should still be usable after rollback
            session.rollback()
            result = repo.get_all()
            assert len(result) == 1


# ---------------------------------------------------------------------------
# Database engine / session tests
# ---------------------------------------------------------------------------


class TestDatabaseSetup:
    """Tests for get_engine() and get_session()."""

    def test_get_engine_with_url(self) -> None:
        engine = get_engine("sqlite:///:memory:")
        assert engine is not None
        assert engine.dialect.name == "sqlite"

    def test_get_engine_missing_url_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(DatabaseConfigError, match="DATABASE_URL is not configured"):
            get_engine()

    def test_get_session_commits_on_success(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with get_session(engine) as session:
            fw = FrameworkTable(name="SOC 2", version="2023")
            session.add(fw)

        # After context manager exits, the row should be committed
        with Session(bind=engine) as verify:
            result = verify.query(FrameworkTable).filter_by(name="SOC 2").first()
            assert result is not None

    def test_get_session_rolls_back_on_error(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        with pytest.raises(ValueError, match="deliberate"):
            with get_session(engine) as session:
                fw = FrameworkTable(name="CIS Controls", version="8.0")
                session.add(fw)
                msg = "deliberate error"
                raise ValueError(msg)

        # After rollback, the row should NOT exist
        with Session(bind=engine) as verify:
            result = verify.query(FrameworkTable).filter_by(name="CIS Controls").first()
            assert result is None
