"""
Credentials Store for Gmail Lead Sync & Response Engine.

This module provides secure storage and retrieval of Gmail credentials
with support for environment variables and encrypted database storage.

Classes:
    CredentialsStore: Abstract base class defining the credentials interface
    EnvironmentCredentialsStore: Reads credentials from environment variables
    EncryptedDBCredentialsStore: Stores credentials encrypted in database with AES-256
"""

import os
from abc import ABC, abstractmethod
from typing import Tuple
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session
from gmail_lead_sync.models import Credentials


class CredentialsStore(ABC):
    """
    Abstract base class for credentials storage.
    
    Defines the interface for storing and retrieving Gmail credentials
    securely. Implementations must provide methods to get and store
    credentials for a given agent.
    """
    
    @abstractmethod
    def get_credentials(self, agent_id: str) -> Tuple[str, str]:
        """
        Retrieve credentials for the specified agent.
        
        Args:
            agent_id: Unique identifier for the agent
            
        Returns:
            Tuple of (email, app_password)
            
        Raises:
            ValueError: If credentials not found for the agent
        """
        pass
    
    @abstractmethod
    def store_credentials(self, agent_id: str, email: str, app_password: str) -> None:
        """
        Store credentials for the specified agent.
        
        Args:
            agent_id: Unique identifier for the agent
            email: Gmail email address
            app_password: Gmail app-specific password
            
        Raises:
            ValueError: If credentials cannot be stored
        """
        pass


class EnvironmentCredentialsStore(CredentialsStore):
    """
    Credentials store that reads from environment variables.
    
    Reads credentials from environment variables in the format:
    - GMAIL_EMAIL_{agent_id}: Email address
    - GMAIL_APP_PASSWORD_{agent_id}: App password
    
    This implementation is read-only and does not support storing credentials.
    """
    
    def get_credentials(self, agent_id: str) -> Tuple[str, str]:
        """
        Retrieve credentials from environment variables.
        
        Args:
            agent_id: Unique identifier for the agent
            
        Returns:
            Tuple of (email, app_password)
            
        Raises:
            ValueError: If environment variables are not set
        """
        email_key = f"GMAIL_EMAIL_{agent_id.upper()}"
        password_key = f"GMAIL_APP_PASSWORD_{agent_id.upper()}"
        
        email = os.environ.get(email_key)
        app_password = os.environ.get(password_key)
        
        if not email:
            raise ValueError(
                f"Environment variable {email_key} not set for agent {agent_id}"
            )
        
        if not app_password:
            raise ValueError(
                f"Environment variable {password_key} not set for agent {agent_id}"
            )
        
        return email, app_password
    
    def store_credentials(self, agent_id: str, email: str, app_password: str) -> None:
        """
        Store credentials (not supported for environment store).
        
        Args:
            agent_id: Unique identifier for the agent
            email: Gmail email address
            app_password: Gmail app-specific password
            
        Raises:
            NotImplementedError: This store is read-only
        """
        raise NotImplementedError(
            "EnvironmentCredentialsStore is read-only. "
            "Set environment variables manually."
        )


class EncryptedDBCredentialsStore(CredentialsStore):
    """
    Credentials store with AES-256 encryption in database.
    
    Stores credentials encrypted using Fernet (symmetric encryption) in the
    database. The encryption key must be provided via the ENCRYPTION_KEY
    environment variable.
    
    Security:
        - Uses Fernet encryption (AES-256 in CBC mode with HMAC authentication)
        - Encryption key must be 32 bytes base64-encoded
        - Never logs credentials in plain text
        - Credentials are encrypted before database storage
    """
    
    def __init__(self, db_session: Session, encryption_key: str = None):
        """
        Initialize encrypted credentials store.
        
        Args:
            db_session: SQLAlchemy database session
            encryption_key: Optional encryption key (base64-encoded).
                          If not provided, reads from ENCRYPTION_KEY env var.
                          
        Raises:
            ValueError: If encryption key is not provided or invalid
        """
        self.db_session = db_session
        
        # Load encryption key from parameter or environment
        if encryption_key is None:
            encryption_key = os.environ.get('ENCRYPTION_KEY')
        
        if not encryption_key:
            raise ValueError(
                "Encryption key not provided. Set ENCRYPTION_KEY environment "
                "variable or pass encryption_key parameter. "
                "Generate key with: python -c \"from cryptography.fernet import "
                "Fernet; print(Fernet.generate_key().decode())\""
            )
        
        try:
            # Initialize Fernet cipher with the encryption key
            self.cipher = Fernet(encryption_key.encode())
        except Exception as e:
            raise ValueError(
                f"Invalid encryption key format: {e}. "
                "Key must be 32 bytes base64-encoded."
            )
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext using Fernet (AES-256).
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        encrypted_bytes = self.cipher.encrypt(plaintext.encode())
        return encrypted_bytes.decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt ciphertext using Fernet (AES-256).
        
        Args:
            ciphertext: Base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string
            
        Raises:
            ValueError: If decryption fails (invalid key or corrupted data)
        """
        try:
            decrypted_bytes = self.cipher.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except InvalidToken:
            raise ValueError(
                "Failed to decrypt credentials. "
                "Encryption key may be incorrect or data corrupted."
            )
    
    def get_credentials(self, agent_id: str) -> Tuple[str, str]:
        """
        Retrieve and decrypt credentials from database.
        
        Args:
            agent_id: Unique identifier for the agent
            
        Returns:
            Tuple of (email, app_password)
            
        Raises:
            ValueError: If credentials not found or decryption fails
        """
        creds = self.db_session.query(Credentials)\
            .filter(Credentials.agent_id == agent_id)\
            .first()
        
        if not creds:
            raise ValueError(f"No credentials found for agent {agent_id}")
        
        # Decrypt credentials
        email = self.decrypt(creds.email_encrypted)
        app_password = self.decrypt(creds.app_password_encrypted)
        
        return email, app_password
    
    def store_credentials(self, agent_id: str, email: str, app_password: str) -> None:
        """
        Encrypt and store credentials in database.
        
        If credentials already exist for the agent, they will be updated.
        Otherwise, new credentials will be created.
        
        Args:
            agent_id: Unique identifier for the agent
            email: Gmail email address
            app_password: Gmail app-specific password
            
        Raises:
            ValueError: If encryption or database operation fails
        """
        # Encrypt credentials
        email_encrypted = self.encrypt(email)
        password_encrypted = self.encrypt(app_password)
        
        # Check if credentials already exist
        existing = self.db_session.query(Credentials)\
            .filter(Credentials.agent_id == agent_id)\
            .first()
        
        if existing:
            # Update existing credentials
            existing.email_encrypted = email_encrypted
            existing.app_password_encrypted = password_encrypted
        else:
            # Create new credentials
            creds = Credentials(
                agent_id=agent_id,
                email_encrypted=email_encrypted,
                app_password_encrypted=password_encrypted
            )
            self.db_session.add(creds)
        
        # Commit to database
        self.db_session.commit()
