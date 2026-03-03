"""
Unit tests for Web UI database models.

Tests the web UI models' ability to:
- Create model instances with proper constraints
- Maintain relationships between models
- Handle foreign key constraints
- Support migration rollback functionality
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from gmail_lead_sync.models import Base, Template, LeadSource
from api.models.web_ui_models import (
    User, Session, AuditLog, TemplateVersion, 
    RegexProfileVersion, Setting
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:')
    
    # Enable foreign key constraints for SQLite
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing."""
    user = User(
        username='testuser',
        password_hash='$2b$12$hashed_password_here',
        role='admin'
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_template(db_session):
    """Create a sample template for testing."""
    template = Template(
        name='Test Template',
        subject='Test Subject',
        body='Test Body'
    )
    db_session.add(template)
    db_session.commit()
    return template


@pytest.fixture
def sample_lead_source(db_session):
    """Create a sample lead source for testing."""
    lead_source = LeadSource(
        sender_email='test@example.com',
        identifier_snippet='Test Snippet',
        name_regex=r'Name:\s*(.+)',
        phone_regex=r'Phone:\s*([\d-]+)',
        auto_respond_enabled=False
    )
    db_session.add(lead_source)
    db_session.commit()
    return lead_source


class TestUserModel:
    """Tests for User model."""
    
    def test_create_user(self, db_session):
        """Test creating a user with all required fields."""
        user = User(
            username='newuser',
            password_hash='hashed_password',
            role='admin'
        )
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert user.username == 'newuser'
        assert user.password_hash == 'hashed_password'
        assert user.role == 'admin'
        assert user.created_at is not None
    
    def test_user_unique_username_constraint(self, db_session, sample_user):
        """Test that username must be unique."""
        duplicate_user = User(
            username='testuser',  # Same as sample_user
            password_hash='different_hash',
            role='admin'
        )
        db_session.add(duplicate_user)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_user_default_role(self, db_session):
        """Test that user role defaults to 'admin'."""
        user = User(
            username='defaultrole',
            password_hash='hashed_password'
        )
        db_session.add(user)
        db_session.commit()
        
        # Query fresh from database to get server default
        db_session.expire(user)
        db_session.refresh(user)
        assert user.role == 'admin'
    
    def test_user_relationships(self, db_session, sample_user):
        """Test user relationships with sessions and audit logs."""
        # Create a session
        session = Session(
            id='test_session_token',
            user_id=sample_user.id,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db_session.add(session)
        
        # Create an audit log
        audit_log = AuditLog(
            user_id=sample_user.id,
            action='test_action',
            resource_type='test_resource',
            resource_id=1
        )
        db_session.add(audit_log)
        db_session.commit()
        
        # Verify relationships
        assert len(sample_user.sessions) == 1
        assert sample_user.sessions[0].id == 'test_session_token'
        assert len(sample_user.audit_logs) == 1
        assert sample_user.audit_logs[0].action == 'test_action'


class TestSessionModel:
    """Tests for Session model."""
    
    def test_create_session(self, db_session, sample_user):
        """Test creating a session with all required fields."""
        expires_at = datetime.utcnow() + timedelta(hours=24)
        session = Session(
            id='secure_random_token_12345',
            user_id=sample_user.id,
            expires_at=expires_at
        )
        db_session.add(session)
        db_session.commit()
        
        assert session.id == 'secure_random_token_12345'
        assert session.user_id == sample_user.id
        assert session.expires_at == expires_at
        assert session.created_at is not None
        assert session.last_accessed is not None
    
    def test_session_user_relationship(self, db_session, sample_user):
        """Test session relationship with user."""
        session = Session(
            id='test_token',
            user_id=sample_user.id,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db_session.add(session)
        db_session.commit()
        
        assert session.user.id == sample_user.id
        assert session.user.username == 'testuser'
    
    def test_session_cascade_delete(self, db_session, sample_user):
        """Test that sessions are deleted when user is deleted."""
        session = Session(
            id='cascade_test_token',
            user_id=sample_user.id,
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db_session.add(session)
        db_session.commit()
        
        session_id = session.id
        
        # Delete the user
        db_session.delete(sample_user)
        db_session.commit()
        
        # Verify session was also deleted
        deleted_session = db_session.query(Session).filter_by(id=session_id).first()
        assert deleted_session is None
    
    def test_session_foreign_key_constraint(self, db_session):
        """Test that session requires valid user_id."""
        session = Session(
            id='invalid_user_token',
            user_id=99999,  # Non-existent user
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db_session.add(session)
        
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestAuditLogModel:
    """Tests for AuditLog model."""
    
    def test_create_audit_log(self, db_session, sample_user):
        """Test creating an audit log with all fields."""
        audit_log = AuditLog(
            user_id=sample_user.id,
            action='agent_created',
            resource_type='agent',
            resource_id=1,
            details='Created agent with ID 1'
        )
        db_session.add(audit_log)
        db_session.commit()
        
        assert audit_log.id is not None
        assert audit_log.user_id == sample_user.id
        assert audit_log.action == 'agent_created'
        assert audit_log.resource_type == 'agent'
        assert audit_log.resource_id == 1
        assert audit_log.details == 'Created agent with ID 1'
        assert audit_log.timestamp is not None
    
    def test_audit_log_without_resource_id(self, db_session, sample_user):
        """Test creating audit log without resource_id (nullable)."""
        audit_log = AuditLog(
            user_id=sample_user.id,
            action='system_startup',
            resource_type='system',
            resource_id=None
        )
        db_session.add(audit_log)
        db_session.commit()
        
        assert audit_log.id is not None
        assert audit_log.resource_id is None
    
    def test_audit_log_user_relationship(self, db_session, sample_user):
        """Test audit log relationship with user."""
        audit_log = AuditLog(
            user_id=sample_user.id,
            action='test_action',
            resource_type='test',
            resource_id=1
        )
        db_session.add(audit_log)
        db_session.commit()
        
        assert audit_log.user.id == sample_user.id
        assert audit_log.user.username == 'testuser'
    
    def test_audit_log_cascade_delete(self, db_session, sample_user):
        """Test that audit logs are deleted when user is deleted."""
        audit_log = AuditLog(
            user_id=sample_user.id,
            action='test_action',
            resource_type='test',
            resource_id=1
        )
        db_session.add(audit_log)
        db_session.commit()
        
        audit_log_id = audit_log.id
        
        # Delete the user
        db_session.delete(sample_user)
        db_session.commit()
        
        # Verify audit log was also deleted
        deleted_log = db_session.query(AuditLog).filter_by(id=audit_log_id).first()
        assert deleted_log is None


class TestTemplateVersionModel:
    """Tests for TemplateVersion model."""
    
    def test_create_template_version(self, db_session, sample_user, sample_template):
        """Test creating a template version."""
        version = TemplateVersion(
            template_id=sample_template.id,
            version=1,
            name='Test Template',
            subject='Version 1 Subject',
            body='Version 1 Body',
            created_by=sample_user.id
        )
        db_session.add(version)
        db_session.commit()
        
        assert version.id is not None
        assert version.template_id == sample_template.id
        assert version.version == 1
        assert version.name == 'Test Template'
        assert version.subject == 'Version 1 Subject'
        assert version.body == 'Version 1 Body'
        assert version.created_by == sample_user.id
        assert version.created_at is not None
    
    def test_template_version_unique_constraint(self, db_session, sample_user, sample_template):
        """Test that template_id + version must be unique."""
        version1 = TemplateVersion(
            template_id=sample_template.id,
            version=1,
            name='Test Template',
            subject='Subject',
            body='Body',
            created_by=sample_user.id
        )
        db_session.add(version1)
        db_session.commit()
        
        # Try to create duplicate version
        version2 = TemplateVersion(
            template_id=sample_template.id,
            version=1,  # Same version
            name='Test Template',
            subject='Different Subject',
            body='Different Body',
            created_by=sample_user.id
        )
        db_session.add(version2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_template_version_cascade_delete(self, db_session, sample_user, sample_template):
        """Test that template versions are deleted when template is deleted."""
        version = TemplateVersion(
            template_id=sample_template.id,
            version=1,
            name='Test Template',
            subject='Subject',
            body='Body',
            created_by=sample_user.id
        )
        db_session.add(version)
        db_session.commit()
        
        version_id = version.id
        
        # Delete the template
        db_session.delete(sample_template)
        db_session.commit()
        
        # Verify version was also deleted
        deleted_version = db_session.query(TemplateVersion).filter_by(id=version_id).first()
        assert deleted_version is None
    
    def test_template_version_user_relationship(self, db_session, sample_user, sample_template):
        """Test template version relationship with user."""
        version = TemplateVersion(
            template_id=sample_template.id,
            version=1,
            name='Test Template',
            subject='Subject',
            body='Body',
            created_by=sample_user.id
        )
        db_session.add(version)
        db_session.commit()
        
        assert version.created_by_user.id == sample_user.id
        assert version.created_by_user.username == 'testuser'


class TestRegexProfileVersionModel:
    """Tests for RegexProfileVersion model."""
    
    def test_create_regex_profile_version(self, db_session, sample_user, sample_lead_source):
        """Test creating a regex profile version."""
        version = RegexProfileVersion(
            lead_source_id=sample_lead_source.id,
            version=1,
            name_regex=r'Name:\s*(.+)',
            phone_regex=r'Phone:\s*([\d-]+)',
            identifier_snippet='Test Snippet',
            created_by=sample_user.id
        )
        db_session.add(version)
        db_session.commit()
        
        assert version.id is not None
        assert version.lead_source_id == sample_lead_source.id
        assert version.version == 1
        assert version.name_regex == r'Name:\s*(.+)'
        assert version.phone_regex == r'Phone:\s*([\d-]+)'
        assert version.identifier_snippet == 'Test Snippet'
        assert version.created_by == sample_user.id
        assert version.created_at is not None
    
    def test_regex_profile_version_unique_constraint(self, db_session, sample_user, sample_lead_source):
        """Test that lead_source_id + version must be unique."""
        version1 = RegexProfileVersion(
            lead_source_id=sample_lead_source.id,
            version=1,
            name_regex=r'Name:\s*(.+)',
            phone_regex=r'Phone:\s*([\d-]+)',
            identifier_snippet='Snippet',
            created_by=sample_user.id
        )
        db_session.add(version1)
        db_session.commit()
        
        # Try to create duplicate version
        version2 = RegexProfileVersion(
            lead_source_id=sample_lead_source.id,
            version=1,  # Same version
            name_regex=r'Different:\s*(.+)',
            phone_regex=r'Different:\s*([\d-]+)',
            identifier_snippet='Different Snippet',
            created_by=sample_user.id
        )
        db_session.add(version2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
    
    def test_regex_profile_version_cascade_delete(self, db_session, sample_user, sample_lead_source):
        """Test that regex profile versions are deleted when lead source is deleted."""
        version = RegexProfileVersion(
            lead_source_id=sample_lead_source.id,
            version=1,
            name_regex=r'Name:\s*(.+)',
            phone_regex=r'Phone:\s*([\d-]+)',
            identifier_snippet='Snippet',
            created_by=sample_user.id
        )
        db_session.add(version)
        db_session.commit()
        
        version_id = version.id
        
        # Delete the lead source
        db_session.delete(sample_lead_source)
        db_session.commit()
        
        # Verify version was also deleted
        deleted_version = db_session.query(RegexProfileVersion).filter_by(id=version_id).first()
        assert deleted_version is None
    
    def test_regex_profile_version_user_relationship(self, db_session, sample_user, sample_lead_source):
        """Test regex profile version relationship with user."""
        version = RegexProfileVersion(
            lead_source_id=sample_lead_source.id,
            version=1,
            name_regex=r'Name:\s*(.+)',
            phone_regex=r'Phone:\s*([\d-]+)',
            identifier_snippet='Snippet',
            created_by=sample_user.id
        )
        db_session.add(version)
        db_session.commit()
        
        assert version.created_by_user.id == sample_user.id
        assert version.created_by_user.username == 'testuser'


class TestSettingModel:
    """Tests for Setting model."""
    
    def test_create_setting(self, db_session, sample_user):
        """Test creating a setting."""
        setting = Setting(
            key='sync_interval_seconds',
            value='300',
            updated_by=sample_user.id
        )
        db_session.add(setting)
        db_session.commit()
        
        assert setting.key == 'sync_interval_seconds'
        assert setting.value == '300'
        assert setting.updated_by == sample_user.id
        assert setting.updated_at is not None
    
    def test_setting_unique_key_constraint(self, db_session, sample_user):
        """Test that setting key must be unique."""
        setting1 = Setting(
            key='test_setting',
            value='value1',
            updated_by=sample_user.id
        )
        db_session.add(setting1)
        db_session.commit()
        
        # Try to create duplicate key
        setting2 = Setting(
            key='test_setting',  # Same key
            value='value2',
            updated_by=sample_user.id
        )
        db_session.add(setting2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()  # Clean up after the error
    
    def test_setting_nullable_updated_by(self, db_session):
        """Test that updated_by can be null."""
        setting = Setting(
            key='system_setting',
            value='default_value',
            updated_by=None
        )
        db_session.add(setting)
        db_session.commit()
        
        assert setting.key == 'system_setting'
        assert setting.updated_by is None
    
    def test_setting_user_relationship(self, db_session, sample_user):
        """Test setting relationship with user."""
        setting = Setting(
            key='user_setting',
            value='test_value',
            updated_by=sample_user.id
        )
        db_session.add(setting)
        db_session.commit()
        
        assert setting.updated_by_user.id == sample_user.id
        assert setting.updated_by_user.username == 'testuser'


class TestMigrationRollback:
    """Tests for migration rollback functionality."""
    
    def test_all_tables_exist(self, db_session):
        """Test that all web UI tables are created."""
        inspector = inspect(db_session.bind)
        tables = inspector.get_table_names()
        
        expected_tables = [
            'users',
            'sessions',
            'audit_logs',
            'template_versions',
            'regex_profile_versions',
            'settings'
        ]
        
        for table in expected_tables:
            assert table in tables, f"Table {table} not found in database"
    
    def test_indexes_exist(self, db_session):
        """Test that all required indexes are created."""
        inspector = inspect(db_session.bind)
        
        # Check users indexes
        users_indexes = inspector.get_indexes('users')
        users_index_names = [idx['name'] for idx in users_indexes]
        assert 'ix_users_username' in users_index_names
        
        # Check sessions indexes
        sessions_indexes = inspector.get_indexes('sessions')
        sessions_index_names = [idx['name'] for idx in sessions_indexes]
        assert 'ix_sessions_expires_at' in sessions_index_names
        assert 'ix_sessions_user_id' in sessions_index_names
        
        # Check audit_logs indexes
        audit_logs_indexes = inspector.get_indexes('audit_logs')
        audit_logs_index_names = [idx['name'] for idx in audit_logs_indexes]
        assert 'ix_audit_logs_timestamp' in audit_logs_index_names
        assert 'ix_audit_logs_user_id' in audit_logs_index_names
        assert 'ix_audit_logs_action' in audit_logs_index_names
        assert 'ix_audit_logs_resource' in audit_logs_index_names
    
    def test_foreign_key_constraints(self, db_session):
        """Test that foreign key constraints are properly defined."""
        inspector = inspect(db_session.bind)
        
        # Check sessions foreign keys
        sessions_fks = inspector.get_foreign_keys('sessions')
        assert len(sessions_fks) == 1
        assert sessions_fks[0]['referred_table'] == 'users'
        assert sessions_fks[0]['constrained_columns'] == ['user_id']
        
        # Check audit_logs foreign keys
        audit_logs_fks = inspector.get_foreign_keys('audit_logs')
        assert len(audit_logs_fks) == 1
        assert audit_logs_fks[0]['referred_table'] == 'users'
        
        # Check template_versions foreign keys
        template_versions_fks = inspector.get_foreign_keys('template_versions')
        assert len(template_versions_fks) == 2
        fk_tables = [fk['referred_table'] for fk in template_versions_fks]
        assert 'templates' in fk_tables
        assert 'users' in fk_tables
