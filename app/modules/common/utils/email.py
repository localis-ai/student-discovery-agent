"""Email service using Gmail API."""

import base64
import os
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from google.oauth2.credentials import Credentials

from app.core.config import settings
from app.modules.common.utils.logging import logger


class GmailClient:
    """Gmail API client with OAuth2"""

    def __init__(self):
        self.gmail_client_id = settings.GMAIL_CLIENT_ID
        self.gmail_client_secret = settings.GMAIL_CLIENT_SECRET
        self.gmail_refresh_token = settings.GMAIL_REFRESH_TOKEN
        # self.proxy_host = settings.PROXY_HOST
        # self.proxy_port = settings.PROXY_PORT
        # self.proxies = {
        #     "http": f"http://{self.proxy_host}:{self.proxy_port}",
        #     "https": f"http://{self.proxy_host}:{self.proxy_port}",
        # }

        if not all([self.gmail_client_id, self.gmail_client_secret, self.gmail_refresh_token]):
            raise RuntimeError("Gmail API credentials not configured")

        self.credentials = Credentials(
            token=None,
            refresh_token=self.gmail_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.gmail_client_id,
            client_secret=self.gmail_client_secret,
            scopes=["https://www.googleapis.com/auth/gmail.send"],
        )

    def _get_access_token(self) -> str:
        """Get access token with proxy support"""
        try:
            if self.credentials.expired or not self.credentials.token:
                data = {
                    "client_id": self.gmail_client_id,
                    "client_secret": self.gmail_client_secret,
                    "refresh_token": self.gmail_refresh_token,
                    "grant_type": "refresh_token",
                }
                resp = requests.post(
                    "https://oauth2.googleapis.com/token",
                    data=data,
                    proxies=self.proxies,
                    timeout=30,
                )
                resp.raise_for_status()
                token = resp.json().get("access_token")
                if not token:
                    raise ValueError("No access_token in response")
                self.credentials.token = token
            return self.credentials.token
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise

    def send_email(self, to: str, subject: str, html_content: str, attachments: list = None) -> bool:
        """Send email via Gmail API"""
        try:
            msg = MIMEMultipart()
            msg["From"] = "Backend API"
            msg["To"] = to
            msg["Subject"] = subject

            msg.attach(MIMEText(html_content, "html", "utf-8"))

            # Add attachments
            if attachments:
                for filepath in attachments:
                    if os.path.exists(filepath):
                        with open(filepath, "rb") as attachment:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(attachment.read())
                            encoders.encode_base64(part)
                        part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(filepath)}")
                        msg.attach(part)

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
            access_token = self._get_access_token()

            resp = requests.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json={"raw": raw},
                proxies=self.proxies,
                timeout=30,
            )
            resp.raise_for_status()
            logger.info(f"Email sent to {to}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise
