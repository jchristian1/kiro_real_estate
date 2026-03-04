"""
Watcher component for Gmail Lead Sync & Response Engine.

This module provides IMAP connection management and email monitoring
functionality for the Gmail Lead Sync system.

Classes:
    IMAPConnection: Manages IMAP connection with retry logic and IDLE support
    GmailWatcher: Orchestrates email discovery and processing
"""

import imaplib
import logging
import time
import socket
import email
from email.header import decode_header
from typing import Optional, Tuple, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from gmail_lead_sync.credentials import CredentialsStore
from gmail_lead_sync.models import Lead, ProcessingLog
from gmail_lead_sync.parser import LeadParser
from gmail_lead_sync.responder import AutoResponder
from gmail_lead_sync.rate_limiter import RateLimiter


logger = logging.getLogger(__name__)


class IMAPConnection:
    """
    IMAP connection manager with retry logic and IDLE support.
    
    Manages connection to Gmail IMAP server with exponential backoff retry,
    connection loss detection, reconnection, and IDLE mode support for
    real-time email notifications.
    
    Features:
        - Exponential backoff retry (2^attempt seconds)
        - Maximum 5 connection attempts
        - Connection loss detection and automatic reconnection
        - IDLE mode support for real-time notifications
        - Authentication failure handling
    
    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
    """
    
    IMAP_SERVER = 'imap.gmail.com'
    IMAP_PORT = 993
    MAX_RETRY_ATTEMPTS = 5
    RECONNECTION_WAIT = 300  # 5 minutes in seconds
    
    def __init__(self, credentials_store: CredentialsStore, agent_id: str):
        """
        Initialize IMAP connection manager.
        
        Args:
            credentials_store: Store for retrieving Gmail credentials
            agent_id: Unique identifier for the agent
        """
        self.credentials_store = credentials_store
        self.agent_id = agent_id
        self.client: Optional[imaplib.IMAP4_SSL] = None
        self._email: Optional[str] = None
        self._app_password: Optional[str] = None
        self._connected = False
    
    def connect_with_retry(self, max_attempts: int = MAX_RETRY_ATTEMPTS) -> bool:
        """
        Connect to IMAP server with exponential backoff retry.
        
        Attempts to establish connection to Gmail IMAP server with retry logic.
        Uses exponential backoff: 1s, 2s, 4s, 8s, 16s between attempts.
        
        Args:
            max_attempts: Maximum number of connection attempts (default: 5)
            
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            ValueError: If credentials cannot be retrieved
            
        Requirements: 1.1, 1.2
        """
        # Retrieve credentials
        try:
            self._email, self._app_password = self.credentials_store.get_credentials(
                self.agent_id
            )
        except ValueError as e:
            logger.error(f"Failed to retrieve credentials for agent {self.agent_id}: {e}")
            raise
        
        # Attempt connection with retry
        for attempt in range(max_attempts):
            try:
                logger.info(
                    f"Attempting IMAP connection to {self.IMAP_SERVER}:{self.IMAP_PORT} "
                    f"(attempt {attempt + 1}/{max_attempts})"
                )
                
                # Create SSL connection
                self.client = imaplib.IMAP4_SSL(self.IMAP_SERVER, self.IMAP_PORT)
                
                # Authenticate
                self.client.login(self._email, self._app_password)
                
                # Select INBOX
                self.client.select('INBOX')
                
                self._connected = True
                logger.info(
                    f"IMAP connection established successfully on attempt {attempt + 1}"
                )
                return True
                
            except imaplib.IMAP4.error as e:
                # Authentication or IMAP protocol error
                error_msg = str(e).lower()
                if 'authentication' in error_msg or 'login' in error_msg:
                    logger.error(
                        f"Authentication failed for {self._email}: {e}. "
                        "Check credentials and ensure 2FA + App Password are configured."
                    )
                    # Don't retry on authentication failures
                    self._connected = False
                    return False
                else:
                    logger.warning(
                        f"IMAP error on attempt {attempt + 1}: {e}"
                    )
                    
            except (socket.error, OSError, ConnectionError) as e:
                # Network or connection error
                logger.warning(
                    f"Connection error on attempt {attempt + 1}: {e}"
                )
                
            except Exception as e:
                # Unexpected error
                logger.error(
                    f"Unexpected error on attempt {attempt + 1}: {e}",
                    exc_info=True
                )
            
            # Close failed connection if exists
            if self.client:
                try:
                    self.client.logout()
                except:
                    pass
                self.client = None
            
            self._connected = False
            
            # Calculate exponential backoff wait time
            if attempt < max_attempts - 1:
                wait_time = 2 ** attempt  # 1, 2, 4, 8, 16 seconds
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        
        # All retry attempts exhausted
        logger.error(
            f"Failed to connect after {max_attempts} attempts. "
            f"Waiting {self.RECONNECTION_WAIT} seconds before next attempt."
        )
        time.sleep(self.RECONNECTION_WAIT)
        return False
    
    def is_connected(self) -> bool:
        """
        Check if IMAP connection is active.
        
        Performs a NOOP command to verify connection is still alive.
        
        Returns:
            True if connected and responsive, False otherwise
            
        Requirements: 1.5
        """
        if not self._connected or not self.client:
            return False
        
        try:
            # Send NOOP to check if connection is alive
            status, _ = self.client.noop()
            return status == 'OK'
        except:
            self._connected = False
            return False
    
    def reconnect(self) -> bool:
        """
        Attempt to reconnect after connection loss.
        
        Closes existing connection (if any) and attempts to establish
        a new connection with retry logic.
        
        Returns:
            True if reconnection successful, False otherwise
            
        Requirements: 1.5
        """
        logger.warning("Connection lost, attempting to reconnect...")
        
        # Close existing connection
        self.disconnect()
        
        # Attempt reconnection
        return self.connect_with_retry()
    
    def disconnect(self) -> None:
        """
        Close IMAP connection gracefully.
        
        Logs out from IMAP server and cleans up connection resources.
        """
        if self.client:
            try:
                self.client.logout()
                logger.info("IMAP connection closed")
            except:
                pass
            finally:
                self.client = None
                self._connected = False
    
    def enable_idle(self) -> bool:
        """
        Enable IDLE mode for real-time email notifications.
        
        IDLE mode allows the server to push notifications when new emails
        arrive, reducing the need for frequent polling.
        
        Returns:
            True if IDLE mode enabled successfully, False otherwise
            
        Requirements: 1.4
        """
        if not self.is_connected():
            logger.error("Cannot enable IDLE: not connected")
            return False
        
        try:
            # Send IDLE command
            tag = self.client._new_tag()
            self.client.send(f'{tag} IDLE\r\n'.encode())
            
            # Wait for continuation response
            response = self.client.readline()
            if b'+ idling' in response.lower() or b'+ waiting' in response.lower():
                logger.info("IDLE mode enabled successfully")
                return True
            else:
                logger.warning(f"Unexpected IDLE response: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to enable IDLE mode: {e}", exc_info=True)
            return False
    
    def disable_idle(self) -> bool:
        """
        Disable IDLE mode and return to normal operation.
        
        Sends DONE command to exit IDLE mode.
        
        Returns:
            True if IDLE mode disabled successfully, False otherwise
            
        Requirements: 1.4
        """
        if not self.is_connected():
            logger.error("Cannot disable IDLE: not connected")
            return False
        
        try:
            # Send DONE to exit IDLE
            self.client.send(b'DONE\r\n')
            
            # Read response
            response = self.client.readline()
            logger.info("IDLE mode disabled")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disable IDLE mode: {e}", exc_info=True)
            return False
    
    def __enter__(self):
        """Context manager entry."""
        self.connect_with_retry()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False


class GmailWatcher:
    """
    Gmail watcher for monitoring and processing emails.
    
    Orchestrates the email discovery and processing workflow:
    1. Connect to Gmail via IMAP
    2. Search for UNSEEN emails from configured senders
    3. Check if email already processed (UID exists)
    4. Parse email to extract lead information
    5. Store lead and mark email as processed
    6. Send automated response if configured
    
    Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4
    """
    
    def __init__(self, credentials_store: CredentialsStore, db_session: Session, 
                 agent_id: str = 'default'):
        """
        Initialize Gmail watcher.
        
        Args:
            credentials_store: Store for retrieving Gmail credentials
            db_session: SQLAlchemy database session
            agent_id: Unique identifier for the agent (default: 'default')
        """
        self.credentials_store = credentials_store
        self.db_session = db_session
        self.agent_id = agent_id
        self.connection = IMAPConnection(credentials_store, agent_id)
        self.parser = LeadParser(db_session)
        self.responder = AutoResponder(credentials_store, db_session, agent_id)
        # Initialize rate limiter: 100 requests per minute
        self.rate_limiter = RateLimiter(max_requests=100, time_window=60)
    
    def connect(self) -> bool:
        """
        Establish IMAP connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        return self.connection.connect_with_retry()
    
    def is_connected(self) -> bool:
        """
        Check if watcher is connected to IMAP server.
        
        Returns:
            True if connected, False otherwise
        """
        return self.connection.is_connected()
    
    def disconnect(self) -> None:
        """
        Close IMAP connection.
        """
        self.connection.disconnect()
    
    def is_email_processed(self, gmail_uid: str) -> bool:
        """
        Check if email has already been processed.
        
        Queries the database to determine if a Lead record with the given
        Gmail UID already exists, indicating the email has been processed.
        
        Args:
            gmail_uid: Unique Gmail identifier for the email
            
        Returns:
            True if email already processed, False otherwise
            
        Requirements: 3.1
        """
        try:
            # Check if any Lead exists with this gmail_uid
            existing_lead = self.db_session.query(Lead)\
                .filter(Lead.gmail_uid == gmail_uid)\
                .first()
            
            if existing_lead:
                logger.debug(f"Email {gmail_uid} already processed (Lead ID {existing_lead.id})")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking if email {gmail_uid} is processed: {e}", exc_info=True)
            # On error, assume not processed to avoid skipping emails
            return False
    
    def mark_as_processed(self, gmail_uid: str, lead_id: Optional[int]) -> None:
        """
        Mark email as processed by storing UID atomically with lead.
        
        This method is called after a Lead is successfully created to ensure
        the Gmail UID is stored atomically with the Lead record. The actual
        storage happens in the parser's validate_and_create_lead method within
        a transaction.
        
        Note: In the current implementation, the UID is stored as part of the
        Lead record itself (Lead.gmail_uid), so this method primarily serves
        as a verification step and for logging purposes.
        
        Args:
            gmail_uid: Unique Gmail identifier for the email
            lead_id: ID of the created Lead record (None if processing failed)
            
        Requirements: 3.3, 3.4
        """
        if lead_id:
            logger.info(f"Email {gmail_uid} marked as processed (Lead ID {lead_id})")
        else:
            logger.info(f"Email {gmail_uid} processing completed without lead creation")
    
    def process_unseen_emails(self, sender_list: List[str]) -> None:
        """
        Process all UNSEEN emails from configured senders.
        
        Searches for UNSEEN emails from senders in the provided list, retrieves
        email data (UID, sender, body), checks if already processed, parses to
        extract leads, sends automated responses if configured, and creates
        Processing_Log records for all attempts.
        
        Implements error isolation: if processing one email fails, continues
        with remaining emails.
        
        Args:
            sender_list: List of email addresses to search for UNSEEN emails
            
        Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 8.1, 8.2, 8.3, 8.4, 11.2
        """
        if not self.is_connected():
            logger.error("Cannot process emails: not connected to IMAP server")
            return
        
        try:
            # Build search criteria for UNSEEN emails from sender list
            # IMAP search format: (OR FROM "sender1" FROM "sender2" ...) UNSEEN
            if not sender_list:
                logger.warning("No senders in sender_list, skipping email processing")
                return
            
            # Search for UNSEEN emails from each sender
            all_email_data = []
            
            for sender in sender_list:
                try:
                    # Search for UNSEEN emails from this sender
                    search_criteria = f'(FROM "{sender}" UNSEEN)'
                    logger.info(f"Searching for UNSEEN emails from {sender}")
                    
                    status, message_numbers = self.connection.client.search(None, search_criteria)
                    
                    if status != 'OK':
                        logger.warning(f"Search failed for sender {sender}: {status}")
                        continue
                    
                    # Parse message numbers
                    if not message_numbers[0]:
                        logger.debug(f"No UNSEEN emails found from {sender}")
                        continue
                    
                    uids = message_numbers[0].split()
                    logger.info(f"Found {len(uids)} UNSEEN email(s) from {sender}")
                    
                    # Fetch email data for each UID
                    for uid in uids:
                        try:
                            email_data = self._fetch_email_data(uid.decode())
                            if email_data:
                                all_email_data.append(email_data)
                        except Exception as e:
                            logger.error(
                                f"Error fetching email data for UID {uid.decode()}: {e}",
                                exc_info=True
                            )
                            # Continue with next email (error isolation)
                            continue
                    
                except Exception as e:
                    logger.error(
                        f"Error searching emails from sender {sender}: {e}",
                        exc_info=True
                    )
                    # Continue with next sender (error isolation)
                    continue
            
            if not all_email_data:
                logger.info("No UNSEEN emails to process")
                return
            
            # Sort emails by received date (chronological order)
            all_email_data.sort(key=lambda x: x['date'])
            logger.info(f"Processing {len(all_email_data)} email(s) in chronological order")
            
            # Process each email
            for email_data in all_email_data:
                try:
                    self._process_single_email(
                        gmail_uid=email_data['uid'],
                        sender=email_data['sender'],
                        body=email_data['body'],
                        date=email_data['date']
                    )
                except Exception as e:
                    logger.error(
                        f"Error processing email {email_data['uid']}: {e}",
                        exc_info=True
                    )
                    # Continue with next email (error isolation)
                    continue
            
            logger.info(f"Completed processing {len(all_email_data)} email(s)")
            
        except Exception as e:
            logger.error(f"Unexpected error in process_unseen_emails: {e}", exc_info=True)
    
    def _fetch_email_data(self, uid: str) -> Optional[dict]:
        """
        Fetch email data (UID, sender, body, date) for a given UID.
        
        Applies rate limiting to prevent excessive IMAP requests.
        
        Args:
            uid: Email UID to fetch
            
        Returns:
            Dictionary with keys: uid, sender, body, date
            None if fetch fails
            
        Requirements: 2.2, 2.3, 2.4, 11.1
        """
        try:
            # Apply rate limiting before fetch
            self.rate_limiter.wait_if_needed()
            
            # Fetch email data
            status, msg_data = self.connection.client.fetch(uid, '(RFC822)')
            
            if status != 'OK':
                logger.warning(f"Failed to fetch email {uid}: {status}")
                return None
            
            # Parse email message — msg_data is a list of tuples like [(b'... RFC822 ...', b'<raw bytes>'), b')']
            # Find the first tuple element that contains bytes
            raw_email = None
            for part in msg_data:
                if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], bytes):
                    raw_email = part[1]
                    break
            
            if raw_email is None:
                logger.warning(f"Could not extract raw email bytes for UID {uid}, msg_data: {type(msg_data)}")
                return None
            
            email_message = email.message_from_bytes(raw_email)
            
            # Extract sender
            from_header = email_message.get('From', '')
            sender = self._extract_email_address(from_header)
            
            # Extract date
            date_header = email_message.get('Date', '')
            received_date = self._parse_email_date(date_header)
            
            # Extract body
            body = self._extract_email_body(email_message)
            
            logger.debug(
                f"Fetched email {uid}: sender={sender}, "
                f"date={received_date}, body_length={len(body)}"
            )
            
            return {
                'uid': uid,
                'sender': sender,
                'body': body,
                'date': received_date
            }
            
        except Exception as e:
            logger.error(f"Error fetching email data for UID {uid}: {e}", exc_info=True)
            return None
    
    def _extract_email_address(self, from_header: str) -> str:
        """
        Extract email address from From header.
        
        Args:
            from_header: Email From header (e.g., "Name <email@example.com>")
            
        Returns:
            Email address string
        """
        import re
        # Try to extract email from "Name <email@example.com>" format
        # Pattern: <(.+?)> matches text within angle brackets (non-greedy)
        match = re.search(r'<(.+?)>', from_header)
        if match:
            return match.group(1)
        
        # If no angle brackets, assume the whole string is the email
        return from_header.strip()
    
    def _parse_email_date(self, date_header: str) -> datetime:
        """
        Parse email date header to datetime object.
        
        Args:
            date_header: Email Date header string
            
        Returns:
            datetime object (defaults to current time if parsing fails)
        """
        from email.utils import parsedate_to_datetime
        
        try:
            return parsedate_to_datetime(date_header)
        except Exception as e:
            logger.warning(f"Failed to parse date '{date_header}': {e}")
            # Default to current time if parsing fails
            return datetime.utcnow()
    
    def _extract_email_body(self, email_message) -> str:
        """
        Extract plain text body from email message.
        
        Args:
            email_message: Parsed email message object
            
        Returns:
            Email body as plain text string
        """
        body = ""
        
        # Handle multipart messages
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                # Look for text/plain parts that aren't attachments
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body += payload.decode('utf-8', errors='ignore')
                    except Exception as e:
                        logger.warning(f"Error decoding email part: {e}")
        else:
            # Simple non-multipart message
            try:
                payload = email_message.get_payload(decode=True)
                if payload:
                    body = payload.decode('utf-8', errors='ignore')
            except Exception as e:
                logger.warning(f"Error decoding email body: {e}")
        
        return body.strip()
    
    def _process_single_email(self, gmail_uid: str, sender: str, body: str, 
                             date: datetime) -> None:
        """
        Process a single email: check if processed, parse, respond, log.
        """
        logger.info(f"Processing email {gmail_uid} from {sender} (date: {date})")
        
        # Check if already processed (idempotency)
        if self.is_email_processed(gmail_uid):
            logger.info(f"Email {gmail_uid} already processed, skipping")
            return
        
        try:
            # Parse email to extract lead
            lead = self.parser.parse_email(sender, body, gmail_uid)
            
            if lead:
                # Lead successfully created
                logger.info(f"Lead {lead.id} created from email {gmail_uid}")
                
                # Mark as processed
                self.mark_as_processed(gmail_uid, lead.id)
                
                # Send automated response if configured
                try:
                    # Refresh lead_source relationship
                    self.db_session.refresh(lead)
                    lead_source = lead.lead_source
                    
                    if lead_source.auto_respond_enabled:
                        logger.info(f"Sending automated response for lead {lead.id}")
                        self.responder.send_acknowledgment(lead, lead_source)
                    else:
                        logger.debug(f"Auto-response disabled for lead source {lead_source.id}")
                        
                except Exception as e:
                    # Log error but don't fail the entire processing
                    logger.error(
                        f"Error sending automated response for lead {lead.id}: {e}",
                        exc_info=True
                    )
            else:
                # Parsing failed (already logged by parser)
                logger.info(f"Failed to extract lead from email {gmail_uid}")
                self.mark_as_processed(gmail_uid, None)
                
        except IntegrityError as e:
            # Duplicate UID - email was processed by another process
            logger.info(f"Email {gmail_uid} already processed (IntegrityError), skipping")
            self.db_session.rollback()
            
        except Exception as e:
            # Unexpected error
            logger.error(
                f"Unexpected error processing email {gmail_uid}: {e}",
                exc_info=True
            )
            self.db_session.rollback()
    
    def start_monitoring(self) -> None:
        """
        Start IDLE mode monitoring for new emails.
        
        This method enables IDLE mode on the IMAP connection to receive
        real-time notifications when new emails arrive.
        
        Requirements: 1.4
        """
        if not self.is_connected():
            logger.error("Cannot start monitoring: not connected to IMAP server")
            return
        
        success = self.connection.enable_idle()
        if success:
            logger.info("Started monitoring for new emails in IDLE mode")
        else:
            logger.error("Failed to enable IDLE mode")
