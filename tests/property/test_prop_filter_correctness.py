"""
Property-based tests for filter correctness.

Feature: agent-app

**Property 16: Filter Correctness** — for any query with active filters, every
returned lead satisfies all active filter conditions simultaneously.

**Validates: Requirements 11.2, 11.3**
"""

import secrets
import uuid
from datetime import datetime, timedelta

import bcrypt
import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from api.main import app, get_db
from gmail_lead_sync.agent_models import AgentPreferences, AgentSession, AgentUser
from gmail_lead_sync.models import Base, Lead, LeadSource


# ---------------------------------------------------------------------------
# DB isolation fixture — named in-memory SQLite per test run
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_db():
    db_name = f"test_{uuid.uuid4().hex}"
    engine = create_engine(
        f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSessionLocal, engine
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_BUCKETS = ["HOT", "WARM", "NURTURE"]
ALL_STATUSES = ["NEW", "CONTACTED", "APPOINTMENT_SET", "LOST", "CLOSED"]


def _create_agent(db) -> AgentUser:
    uid = uuid.uuid4().hex[:8]
    password_hash = bcrypt.hashpw(b"password", bcrypt.gensalt()).decode()
    agent = AgentUser(
        email=f"agent_{uid}@example.com",
        password_hash=password_hash,
        full_name=f"Agent {uid}",
        onboarding_step=1,
        onboarding_completed=True,
        created_at=datetime.utcnow(),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    prefs = AgentPreferences(
        agent_user_id=agent.id,
        hot_threshold=80,
        warm_threshold=50,
        sla_minutes_hot=5,
        watcher_enabled=True,
        created_at=datetime.utcnow(),
    )
    db.add(prefs)
    db.commit()
    return agent


def _create_session(db, agent_user_id: int) -> str:
    token = secrets.token_hex(64)
    now = datetime.utcnow()
    session = AgentSession(
        id=token,
        agent_user_id=agent_user_id,
        created_at=now,
        expires_at=now + timedelta(days=1),
        last_accessed=now,
    )
    db.add(session)
    db.commit()
    return token


def _ensure_lead_source(db) -> int:
    source = db.query(LeadSource).first()
    if source is None:
        source = LeadSource(
            sender_email="test@leadsource.com",
            identifier_snippet="test",
            name_regex=r"Name: (.+)",
            phone_regex=r"Phone: (.+)",
        )
        db.add(source)
        db.commit()
        db.refresh(source)
    return source.id


def _create_lead(
    db,
    agent_user_id: int,
    *,
    bucket: str = "HOT",
    status: str = "NEW",
    name: str = "Test Lead",
    index: int = 0,
) -> Lead:
    source_id = _ensure_lead_source(db)
    score_map = {"HOT": 85, "WARM": 65, "NURTURE": 30}
    lead = Lead(
        name=name,
        phone="555-0000",
        source_email="source@example.com",
        lead_source_id=source_id,
        gmail_uid=f"uid_{agent_user_id}_{bucket}_{status}_{index}_{uuid.uuid4().hex}",
        agent_user_id=agent_user_id,
        score_bucket=bucket,
        score=score_map.get(bucket, 50),
        agent_current_state=status,
        created_at=datetime.utcnow(),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


# ---------------------------------------------------------------------------
# Property 16a: Bucket filter correctness
# ---------------------------------------------------------------------------


class TestProperty16BucketFilter:
    """
    Property 16: Filter Correctness — bucket filter
    **Validates: Requirements 11.2**

    For any bucket filter, every returned lead has score_bucket == bucket.
    """

    @given(
        bucket=st.sampled_from(["HOT", "WARM", "NURTURE"]),
        n_matching=st.integers(1, 4),
        n_other=st.integers(0, 4),
    )
    @settings(
        max_examples=30,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_bucket_filter_returns_only_matching_bucket(
        self, setup_db, bucket: str, n_matching: int, n_other: int
    ):
        """
        Property 16: Bucket Filter Correctness
        **Validates: Requirements 11.2**

        Every lead returned when filtering by bucket must have
        score_bucket == bucket.
        """
        TestingSessionLocal, engine = setup_db

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)

        other_buckets = [b for b in ALL_BUCKETS if b != bucket]

        db = TestingSessionLocal()
        try:
            agent = _create_agent(db)

            # Create n_matching leads with the target bucket
            for i in range(n_matching):
                _create_lead(db, agent.id, bucket=bucket, index=i)

            # Create n_other leads with other buckets (cycling through them)
            for i in range(n_other):
                other_bucket = other_buckets[i % len(other_buckets)]
                _create_lead(db, agent.id, bucket=other_bucket, index=1000 + i)

            token = _create_session(db, agent.id)
        finally:
            db.close()

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(
                "/api/v1/agent/leads",
                params={"bucket": bucket},
                cookies={"agent_session": token},
            )

        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        leads = data["leads"]

        # Every returned lead must have the requested bucket
        for lead in leads:
            assert lead["score_bucket"] == bucket, (
                f"Lead id={lead['id']} has score_bucket={lead['score_bucket']!r}, "
                f"expected {bucket!r}"
            )

        # The count must equal n_matching
        assert len(leads) == n_matching, (
            f"Expected {n_matching} leads with bucket={bucket!r}, got {len(leads)}"
        )


# ---------------------------------------------------------------------------
# Property 16b: Status filter correctness
# ---------------------------------------------------------------------------


class TestProperty16StatusFilter:
    """
    Property 16: Filter Correctness — status filter
    **Validates: Requirements 11.2**

    For any status filter, every returned lead has current_state == status.
    """

    @given(
        status=st.sampled_from(["NEW", "CONTACTED", "APPOINTMENT_SET", "LOST", "CLOSED"]),
        n_matching=st.integers(1, 4),
        n_other=st.integers(0, 4),
    )
    @settings(
        max_examples=30,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_status_filter_returns_only_matching_status(
        self, setup_db, status: str, n_matching: int, n_other: int
    ):
        """
        Property 16: Status Filter Correctness
        **Validates: Requirements 11.2**

        Every lead returned when filtering by status must have
        current_state == status.
        """
        TestingSessionLocal, engine = setup_db

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)

        other_statuses = [s for s in ALL_STATUSES if s != status]

        db = TestingSessionLocal()
        try:
            agent = _create_agent(db)

            # Create n_matching leads with the target status
            for i in range(n_matching):
                _create_lead(db, agent.id, status=status, index=i)

            # Create n_other leads with other statuses
            for i in range(n_other):
                other_status = other_statuses[i % len(other_statuses)]
                _create_lead(db, agent.id, status=other_status, index=1000 + i)

            token = _create_session(db, agent.id)
        finally:
            db.close()

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(
                "/api/v1/agent/leads",
                params={"status": status},
                cookies={"agent_session": token},
            )

        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        leads = data["leads"]

        # Every returned lead must have the requested status
        for lead in leads:
            assert lead["current_state"] == status, (
                f"Lead id={lead['id']} has current_state={lead['current_state']!r}, "
                f"expected {status!r}"
            )

        # The count must equal n_matching
        assert len(leads) == n_matching, (
            f"Expected {n_matching} leads with status={status!r}, got {len(leads)}"
        )


# ---------------------------------------------------------------------------
# Property 16c: Search filter correctness
# ---------------------------------------------------------------------------


class TestProperty16SearchFilter:
    """
    Property 16: Filter Correctness — search filter
    **Validates: Requirements 11.3**

    For any search term, every returned lead's name contains the search term
    (case-insensitive).
    """

    @given(
        search_term=st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu")),
            min_size=3,
            max_size=8,
        ),
        n_matching=st.integers(1, 3),
        n_other=st.integers(0, 3),
    )
    @settings(
        max_examples=30,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_search_filter_returns_only_matching_names(
        self, setup_db, search_term: str, n_matching: int, n_other: int
    ):
        """
        Property 16: Search Filter Correctness
        **Validates: Requirements 11.3**

        Every lead returned when filtering by search term must have a name
        that contains the search term (case-insensitive).
        """
        TestingSessionLocal, engine = setup_db

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)

        db = TestingSessionLocal()
        try:
            agent = _create_agent(db)

            # Create n_matching leads whose name contains the search_term
            for i in range(n_matching):
                matching_name = f"Prefix {search_term} Suffix {i}"
                _create_lead(db, agent.id, name=matching_name, index=i)

            # Create n_other leads with names that do NOT contain the search_term.
            # Use a UUID-based name to guarantee no accidental match.
            for i in range(n_other):
                unrelated_name = f"Unrelated {uuid.uuid4().hex}"
                _create_lead(db, agent.id, name=unrelated_name, index=1000 + i)

            token = _create_session(db, agent.id)
        finally:
            db.close()

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(
                "/api/v1/agent/leads",
                params={"search": search_term},
                cookies={"agent_session": token},
            )

        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        leads = data["leads"]

        # Every returned lead must have a name containing the search term
        for lead in leads:
            assert search_term.lower() in lead["name"].lower(), (
                f"Lead id={lead['id']} name={lead['name']!r} does not contain "
                f"search_term={search_term!r}"
            )

        # The count must equal n_matching
        assert len(leads) == n_matching, (
            f"Expected {n_matching} leads matching search={search_term!r}, "
            f"got {len(leads)}"
        )
