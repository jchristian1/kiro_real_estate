"""
SQLAlchemy models for Web UI tables.

This module defines the database schema for web UI functionality including:
- User: Admin users for authentication
- Session: User session management
- AuditLog: Audit trail of administrative actions
- TemplateVersion: Version history for templates
- RegexProfileVersion: Version history for lead source regex profiles
- Setting: System configuration settings
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from gmail_lead_sync.models import Base


class User(Base):
    """
    Admin users for authentication and authorization.
    
    Stores user credentials with bcrypt password hashing.
    Supports role-based access control for future multi-tenant expansion.
    """
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, server_default='admin')
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    template_versions = relationship("TemplateVersion", back_populates="created_by_user")
    regex_profile_versions = relationship("RegexProfileVersion", back_populates="created_by_user")
    settings = relationship("Setting", back_populates="updated_by_user")


class Session(Base):
    """
    User session management for authentication.
    
    Stores session tokens with expiration tracking.
    Sessions expire after 24 hours by default.
    """
    __tablename__ = 'sessions'
    
    id = Column(String(64), primary_key=True)  # Secure random token
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    last_accessed = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="sessions")


class AuditLog(Base):
    """
    Audit trail of administrative actions.
    
    Records all system changes and operations for compliance and debugging.
    Append-only with no deletion capability.
    """
    __tablename__ = 'audit_logs'
    __table_args__ = (
        Index('ix_audit_logs_resource', 'resource_type', 'resource_id'),
    )
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")


class TemplateVersion(Base):
    """
    Version history for email templates.
    
    Maintains complete history of template changes for rollback capability.
    Each update creates a new version record.
    """
    __tablename__ = 'template_versions'
    __table_args__ = (
        UniqueConstraint('template_id', 'version', name='uq_template_version'),
        Index('ix_template_versions_template_id', 'template_id'),
    )
    
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey('templates.id', ondelete='CASCADE'), nullable=False)
    version = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Relationships
    created_by_user = relationship("User", back_populates="template_versions")


class RegexProfileVersion(Base):
    """
    Version history for lead source regex profiles.
    
    Maintains complete history of regex pattern changes for rollback capability.
    Each update creates a new version record.
    """
    __tablename__ = 'regex_profile_versions'
    __table_args__ = (
        UniqueConstraint('lead_source_id', 'version', name='uq_lead_source_version'),
        Index('ix_regex_profile_versions_lead_source_id', 'lead_source_id'),
    )
    
    id = Column(Integer, primary_key=True)
    lead_source_id = Column(Integer, ForeignKey('lead_sources.id', ondelete='CASCADE'), nullable=False)
    version = Column(Integer, nullable=False)
    name_regex = Column(String(500), nullable=False)
    phone_regex = Column(String(500), nullable=False)
    identifier_snippet = Column(String(500), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Relationships
    created_by_user = relationship("User", back_populates="regex_profile_versions")


class Setting(Base):
    """
    System configuration settings.
    
    Stores configurable system parameters with update tracking.
    Supports settings like sync intervals, timeouts, and feature flags.
    """
    __tablename__ = 'settings'
    
    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Relationships
    updated_by_user = relationship("User", back_populates="settings")
