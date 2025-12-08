"""Core test fixtures for RPG game tests."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from src.database.models.base import Base
from src.database.models.enums import EntityType
from src.database.models.entities import Entity
from src.database.models.session import GameSession


@pytest.fixture(scope="session")
def engine():
    """Create SQLite in-memory engine for fast tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Enable foreign key constraints in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Import all models to ensure they're registered with Base
    from src.database.models import (  # noqa: F401
        character_state,
        entities,
        injuries,
        items,
        mental_state,
        navigation,
        relationships,
        session,
        tasks,
        vital_state,
        world,
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture(scope="function")
def db_session(engine) -> Session:
    """Create a fresh database session for each test.

    Uses a transaction that rolls back after each test for isolation.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def game_session(db_session: Session) -> GameSession:
    """Create a basic GameSession fixture."""
    session = GameSession(
        session_name="Test Session",
        setting="fantasy",
        status="active",
        total_turns=1,
        llm_provider="anthropic",
        gm_model="claude-sonnet-4-20250514",
    )
    db_session.add(session)
    db_session.flush()
    return session


@pytest.fixture
def game_session_2(db_session: Session) -> GameSession:
    """Create a second GameSession fixture for testing session isolation."""
    session = GameSession(
        session_name="Test Session 2",
        setting="fantasy",
        status="active",
        total_turns=1,
        llm_provider="anthropic",
        gm_model="claude-sonnet-4-20250514",
    )
    db_session.add(session)
    db_session.flush()
    return session


@pytest.fixture
def player_entity(db_session: Session, game_session: GameSession) -> Entity:
    """Create a player Entity fixture."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="player_hero",
        display_name="The Hero",
        entity_type=EntityType.PLAYER,
        is_alive=True,
        is_active=True,
    )
    db_session.add(entity)
    db_session.flush()
    return entity


@pytest.fixture
def npc_entity(db_session: Session, game_session: GameSession) -> Entity:
    """Create an NPC Entity fixture."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="bartender_joe",
        display_name="Joe the Bartender",
        entity_type=EntityType.NPC,
        is_alive=True,
        is_active=True,
    )
    db_session.add(entity)
    db_session.flush()
    return entity


@pytest.fixture
def monster_entity(db_session: Session, game_session: GameSession) -> Entity:
    """Create a monster Entity fixture."""
    entity = Entity(
        session_id=game_session.id,
        entity_key="goblin_scout",
        display_name="Goblin Scout",
        entity_type=EntityType.MONSTER,
        is_alive=True,
        is_active=True,
    )
    db_session.add(entity)
    db_session.flush()
    return entity
