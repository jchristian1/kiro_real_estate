"""
Auto Responder component for Gmail Lead Sync Engine.

This module provides functionality for sending automated acknowledgment emails
to leads via SMTP and rendering email templates with placeholder replacement.
"""

import re
import smtplib
import time
import logging
from typing import Dict, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.orm import Session

from gmail_lead_sync.models import Template, Lead, LeadSource
from gmail_lead_sync.credentials import CredentialsStore

logger = logging.getLogger(__name__)


class TemplateRenderer:
    """
    Template rendering engine with placeholder replacement.
    
    Replaces placeholders in email templates with actual lead and agent information.
    Supported placeholders:
    - {lead_name}: Extracted lead name
    - {agent_name}: Agent's name from configuration
    - {agent_phone}: Agent's phone number
    - {agent_email}: Agent's email address
    """
    
    def render_template(self, template: Template, lead: Lead, agent_info: Dict[str, str]) -> tuple:
        """
        Render email template by replacing placeholders with actual values.
        
        Returns:
            Tuple of (rendered_subject, rendered_body)
        """
        import os
        base_url = os.environ.get("PUBLIC_BASE_URL", "http://localhost:5173").rstrip("/")
        form_link = agent_info.get('form_link', f"{base_url}/public/buyer-qualification")

        replacements = {
            '{lead_name}': lead.name or '',
            '{agent_name}': agent_info.get('agent_name', ''),
            '{agent_phone}': agent_info.get('agent_phone', ''),
            '{agent_email}': agent_info.get('agent_email', ''),
            '{form_link}': form_link,
        }

        rendered_subject = template.subject
        rendered_body = template.body

        for placeholder, value in replacements.items():
            rendered_subject = rendered_subject.replace(placeholder, value)
            rendered_body = rendered_body.replace(placeholder, value)

        # Validate no unreplaced placeholders remain in body
        remaining = re.findall(r'\{[^}]+\}', rendered_body)
        if remaining:
            raise ValueError(
                f'Template rendering incomplete. Unreplaced placeholders: {remaining}'
            )

        return rendered_subject, rendered_body


class AutoResponder:
    """
    Automated email responder with SMTP support.
    
    Sends automated acknowledgment emails to leads via Gmail SMTP with
    retry logic and error handling. Updates lead records with response status.
    
    Features:
    - SMTP connection to smtp.gmail.com:587 with TLS/STARTTLS
    - Exponential backoff retry logic (max 3 attempts)
    - Updates Lead.response_sent and Lead.response_status fields
    - Error handling that doesn't block lead processing
    """
    
    def __init__(self, credentials_store: CredentialsStore, db_session: Session, 
                 agent_id: str = 'default'):
        """
        Initialize auto responder with credentials and database session.
        
        Args:
            credentials_store: CredentialsStore instance for retrieving Gmail credentials
            db_session: SQLAlchemy database session
            agent_id: Agent identifier for credential retrieval (default: 'default')
        """
        self.credentials_store = credentials_store
        self.db_session = db_session
        self.agent_id = agent_id
        self.template_renderer = TemplateRenderer()
    
    def send_acknowledgment(self, lead: Lead, lead_source: LeadSource, 
                          agent_info: Optional[Dict[str, str]] = None) -> bool:
        """
        Send automated acknowledgment email to lead if configured.
        
        Checks if auto_respond_enabled is True and template is configured
        for the lead source. If so, renders the template and sends email.
        Updates lead record with response status.
        
        Args:
            lead: Lead object to send acknowledgment to
            lead_source: LeadSource configuration for the lead
            agent_info: Optional dictionary with agent information for template rendering.
                       If not provided, uses credentials email as agent_email.
                       Expected keys: 'agent_name', 'agent_phone', 'agent_email'
        
        Returns:
            True if email sent successfully, False otherwise
        """
        # Check if auto-response is enabled
        if not lead_source.auto_respond_enabled:
            logger.debug(f"Auto-response disabled for lead source {lead_source.id}")
            return False
        
        # Check if template is configured
        if not lead_source.template:
            logger.warning(
                f"Auto-response enabled but no template configured for "
                f"lead source {lead_source.id}"
            )
            lead.response_status = 'no_template'
            self.db_session.commit()
            return False
        
        try:
            # Get credentials for sending email
            email, app_password = self.credentials_store.get_credentials(self.agent_id)
            
            # Prepare agent info for template rendering
            if agent_info is None:
                # Try to fetch display_name and phone from DB
                from gmail_lead_sync.models import Credentials
                creds_record = self.db_session.query(Credentials).filter(
                    Credentials.agent_id == self.agent_id
                ).first()

                # Try to resolve a human name: prefer AgentUser.full_name,
                # then Credentials.display_name, then the email address.
                resolved_name = None
                resolved_phone = ''
                resolved_email = email

                # If agent_id is numeric, look up AgentUser for full_name/phone
                try:
                    numeric_id = int(self.agent_id)
                    from gmail_lead_sync.agent_models import AgentUser
                    agent_user = self.db_session.query(AgentUser).filter(
                        AgentUser.id == numeric_id
                    ).first()
                    if agent_user:
                        resolved_name = agent_user.full_name or None
                        resolved_phone = agent_user.phone or ''
                        resolved_email = agent_user.email or email
                except (ValueError, TypeError):
                    pass  # agent_id is not numeric

                if not resolved_name and creds_record and creds_record.display_name:
                    resolved_name = creds_record.display_name
                if not resolved_name:
                    resolved_name = email  # last resort: use email address

                if not resolved_phone and creds_record and creds_record.phone:
                    resolved_phone = creds_record.phone

                agent_info = {
                    'agent_name': resolved_name,
                    'agent_phone': resolved_phone,
                    'agent_email': resolved_email,
                }
            
            # Render template with lead and agent information
            template = lead_source.template
            rendered_subject, body = self.template_renderer.render_template(template, lead, agent_info)
            
            # Send email via SMTP
            success = self.send_email(
                to_address=lead.source_email,
                subject=rendered_subject,
                body=body,
                from_address=email,
                app_password=app_password
            )
            
            # Update lead record with response status
            if success:
                lead.response_sent = True
                lead.response_status = 'sent'
                logger.info(f"Acknowledgment sent to lead {lead.id} at {lead.source_email}")
            else:
                lead.response_sent = False
                lead.response_status = 'failed'
                logger.error(f"Failed to send acknowledgment to lead {lead.id}")
            
            self.db_session.commit()
            return success
            
        except Exception as e:
            # Log error but don't block lead processing
            logger.error(
                f"Error sending acknowledgment to lead {lead.id}: {e}",
                exc_info=True
            )
            lead.response_sent = False
            lead.response_status = f'error: {str(e)[:100]}'
            self.db_session.commit()
            return False
    
    def send_email(self, to_address: str, subject: str, body: str,
                   from_address: str, app_password: str, max_attempts: int = 3) -> bool:
        """
        Send email via Gmail SMTP with retry logic.
        
        Connects to smtp.gmail.com:587 with TLS/STARTTLS support.
        Implements exponential backoff retry logic on failure.
        
        Args:
            to_address: Recipient email address
            subject: Email subject line
            body: Email body content (plain text)
            from_address: Sender email address (Gmail account)
            app_password: Gmail app-specific password
            max_attempts: Maximum number of send attempts (default: 3)
        
        Returns:
            True if email sent successfully, False if all attempts failed
        """
        for attempt in range(max_attempts):
            try:
                # Create SMTP connection with TLS
                with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as server:
                    # Enable TLS encryption
                    server.starttls()
                    
                    # Login with credentials
                    server.login(from_address, app_password)
                    
                    # Create email message
                    msg = MIMEText(body, 'plain', 'utf-8')
                    msg['Subject'] = subject
                    msg['From'] = from_address
                    msg['To'] = to_address
                    
                    # Send email
                    server.send_message(msg)
                    
                    logger.info(
                        f"Email sent successfully to {to_address} on attempt {attempt + 1}"
                    )
                    return True
                    
            except smtplib.SMTPException as e:
                # SMTP-specific errors (authentication, rate limiting, etc.)
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                logger.warning(
                    f"SMTP send attempt {attempt + 1}/{max_attempts} failed: {e}"
                )
                
                if attempt < max_attempts - 1:
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Failed to send email to {to_address} after "
                        f"{max_attempts} attempts: {e}"
                    )
                    return False
                    
            except Exception as e:
                # Unexpected errors (network issues, etc.)
                logger.error(
                    f"Unexpected error sending email on attempt {attempt + 1}: {e}",
                    exc_info=True
                )
                
                if attempt < max_attempts - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"Failed to send email to {to_address} after "
                        f"{max_attempts} attempts due to unexpected error"
                    )
                    return False
        
        return False
