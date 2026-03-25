"""
Auto Responder component for Gmail Lead Sync Engine.

Provides SMTP email sending used by the pipeline engine to deliver
templated emails to leads. All email sending goes through the pipeline —
there is no legacy auto-acknowledgment path.
"""

import smtplib
import time
import logging
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


class AutoResponder:
    """
    SMTP email sender used by the pipeline engine.

    Instantiated via object.__new__(AutoResponder) by the pipeline engine
    so that only send_email() is used — no credentials store or DB session
    needed at construction time.

    Features:
    - SMTP connection to smtp.gmail.com:587 with TLS/STARTTLS
    - Exponential backoff retry logic (max 3 attempts)
    """

    def send_email(
        self,
        to_address: str,
        subject: str,
        body: str,
        from_address: str,
        app_password: str,
        max_attempts: int = 3,
    ) -> bool:
        """Send email via Gmail SMTP with retry logic.

        Args:
            to_address: Recipient email address
            subject: Email subject line
            body: Email body content (plain text)
            from_address: Sender Gmail address
            app_password: Gmail app-specific password
            max_attempts: Maximum send attempts (default: 3)

        Returns:
            True if sent successfully, False if all attempts failed.
        """
        for attempt in range(max_attempts):
            try:
                with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
                    server.starttls()
                    server.login(from_address, app_password)
                    msg = MIMEText(body, "plain", "utf-8")
                    msg["Subject"] = subject
                    msg["From"] = from_address
                    msg["To"] = to_address
                    server.send_message(msg)
                    logger.info("Email sent to %s (attempt %d)", to_address, attempt + 1)
                    return True

            except smtplib.SMTPException as exc:
                logger.warning(
                    "SMTP send attempt %d/%d failed: %s", attempt + 1, max_attempts, exc
                )
                if attempt < max_attempts - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(
                        "Failed to send email to %s after %d attempts: %s",
                        to_address, max_attempts, exc,
                    )
                    return False

            except Exception as exc:
                logger.error(
                    "Unexpected error sending email (attempt %d): %s",
                    attempt + 1, exc, exc_info=True,
                )
                if attempt < max_attempts - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(
                        "Failed to send email to %s after %d attempts",
                        to_address, max_attempts,
                    )
                    return False

        return False
