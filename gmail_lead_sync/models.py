"""
SQLAlchemy models for Gmail Lead Sync & Response Engine.

This module defines the database schema including:
- Lead: Extracted lead records from emails
- LeadSource: Configuration for parsing emails from specific senders
- ProcessingLog: Audit trail of email processing attempts
- Template: Email response templates with placeholders
- Credentials: Encrypted storage for Gmail credentials
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class Lead(Base):
    """
    Lead records extracted from emails.
    
    Each lead represents a potential customer with contact information
    extracted from an email using configured parsing rules.
    """
    __tablename__ = 'leads'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=False)
    source_email = Column(String(255), nullable=False, index=True)
    lead_source_id = Column(Integer, ForeignKey('lead_sources.id'), nullable=False)
    gmail_uid = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    response_sent = Column(Boolean, default=False)
    response_status = Column(String(50))
    
    # Relationships
    lead_source = relationship("LeadSource", back_populates="leads")
    processing_logs = relationship("ProcessingLog", back_populates="lead")


class LeadSource(Base):
    """
    Configuration for parsing emails from specific senders.
    
    Defines regex patterns and identifiers for extracting lead information
    from emails sent by a particular sender address.
    """
    __tablename__ = 'lead_sources'
    
    id = Column(Integer, primary_key=True)
    sender_email = Column(String(255), unique=True, nullable=False, index=True)
    identifier_snippet = Column(String(500), nullable=False)
    name_regex = Column(String(500), nullable=False)
    phone_regex = Column(String(500), nullable=False)
    template_id = Column(Integer, ForeignKey('templates.id'), nullable=True)
    auto_respond_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    leads = relationship("Lead", back_populates="lead_source")
    template = relationship("Template", back_populates="lead_sources")


class ProcessingLog(Base):
    """
    Audit trail of email processing attempts.
    
    Records every attempt to process an email, including success and failure
    details for debugging and verification.
    """
    __tablename__ = 'processing_logs'
    
    id = Column(Integer, primary_key=True)
    gmail_uid = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    sender_email = Column(String(255), nullable=False, index=True)
    status = Column(String(50), nullable=False, index=True)
    error_details = Column(Text)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    lead = relationship("Lead", back_populates="processing_logs")


class Template(Base):
    """
    Email response templates with placeholders.
    
    Defines customizable email templates for automated responses to leads.
    Supports placeholders: {lead_name}, {agent_name}, {agent_phone}, {agent_email}
    """
    __tablename__ = 'templates'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    lead_sources = relationship("LeadSource", back_populates="template")


class Credentials(Base):
    """
    Encrypted storage for Gmail credentials.
    
    Stores agent Gmail credentials with AES-256 encryption for secure
    IMAP/SMTP authentication.
    """
    __tablename__ = 'credentials'
    
    id = Column(Integer, primary_key=True)
    agent_id = Column(String(255), unique=True, nullable=False)
    email_encrypted = Column(Text, nullable=False)
    app_password_encrypted = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Composite index for efficient ProcessingLog queries
Index(
    'idx_processing_log_query',
    ProcessingLog.timestamp,
    ProcessingLog.sender_email,
    ProcessingLog.status
)
