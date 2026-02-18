#!/usr/bin/env python3
"""
Personal AI Employee - Gmail Watcher

Monitors Gmail for unread important emails and creates structured .md files
in the /Needs_Action folder for AI processing.

Agent Skill Style: Modular, composable, and testable.
"""

import os
import base64
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from email.utils import parsedate_to_datetime

# Gmail API dependencies
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

# Add parent directory to path for BaseWatcher import
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "Watchers"))
from base_watcher import BaseWatcher


# =============================================================================
# Constants & Configuration
# =============================================================================

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
          "https://www.googleapis.com/auth/gmail.modify"]
PROCESSED_LABEL = "AI_PROCESSED"
IMPORTANT_LABEL = "IMPORTANT"
CHECK_INTERVAL_SECONDS = 120  # 2 minutes
MAX_RESULTS = 10


# =============================================================================
# Authentication Module
# =============================================================================

class GmailAuthenticator:
    """Handles Gmail API authentication using OAuth2."""

    def __init__(self, credentials_path: str, token_path: str):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.creds: Optional[Credentials] = None

    def authenticate(self) -> Optional[Credentials]:
        """
        Authenticate with Gmail API.
        Returns Credentials object if successful, None otherwise.
        """
        if not GMAIL_AVAILABLE:
            print("[ERROR] Gmail API libraries not installed. Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
            return None

        # Load existing token if available
        if self.token_path.exists():
            self.creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        # Refresh or obtain new credentials
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired:
                try:
                    self.creds.refresh(Request())
                    self._save_token()
                    print("[AUTH] Token refreshed successfully")
                except Exception as e:
                    print(f"[AUTH] Token refresh failed: {e}")
                    self.creds = None

            if not self.creds or not self.creds.valid:
                self.creds = self._flow_authentication()

        return self.creds

    def _flow_authentication(self) -> Optional[Credentials]:
        """Run OAuth2 flow to obtain new credentials."""
        if not self.credentials_path.exists():
            print(f"[ERROR] Credentials file not found: {self.credentials_path}")
            print("[HINT] Download credentials.json from Google Cloud Console")
            return None

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_path, SCOPES
            )
            creds = flow.run_local_server(port=0)
            self.creds = creds
            self._save_token()
            print("[AUTH] Authentication successful")
            return creds
        except Exception as e:
            print(f"[AUTH] Authentication failed: {e}")
            return None

    def _save_token(self):
        """Save credentials to token file."""
        if self.creds:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, "w") as token:
                token.write(self.creds.to_json())
            print(f"[AUTH] Token saved to: {self.token_path}")


# =============================================================================
# Email Processing Module
# =============================================================================

class EmailProcessor:
    """Processes Gmail messages and extracts relevant information."""

    def __init__(self, service):
        self.service = service

    def fetch_unread_important(self, max_results: int = MAX_RESULTS) -> List[Dict[str, Any]]:
        """
        Fetch unread important emails from Gmail.
        Returns list of message dictionaries.
        """
        messages = []

        try:
            # Query: unread AND important
            query = "is:unread is:important"
            results = self.service.users().messages().list(
                userId="me",
                q=query,
                maxResults=max_results
            ).execute()

            message_list = results.get("messages", [])

            for msg in message_list:
                message_data = self._fetch_message_details(msg["id"])
                if message_data:
                    messages.append(message_data)

        except HttpError as error:
            print(f"[ERROR] Fetching messages failed: {error}")

        return messages

    def _fetch_message_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full message details by ID."""
        try:
            message = self.service.users().messages().get(
                userId="me",
                id=message_id,
                format="full"
            ).execute()

            return self._parse_message(message)

        except HttpError as error:
            print(f"[ERROR] Fetching message {message_id} failed: {error}")
            return None

    def _parse_message(self, message: Dict) -> Dict[str, Any]:
        """Parse raw Gmail message into structured data."""
        headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}

        # Extract body/snippet
        snippet = message.get("snippet", "")
        body = self._extract_body(message["payload"])

        # Parse date
        date_str = headers.get("Date", "")
        try:
            parsed_date = parsedate_to_datetime(date_str).isoformat() if date_str else datetime.now().isoformat()
        except Exception:
            parsed_date = datetime.now().isoformat()

        return {
            "id": message["id"],
            "thread_id": message["threadId"],
            "from": headers.get("From", "Unknown"),
            "to": headers.get("To", ""),
            "subject": headers.get("Subject", "No Subject"),
            "date": parsed_date,
            "snippet": snippet,
            "body": body,
            "labels": message.get("labelIds", [])
        }

    def _extract_body(self, payload: Dict) -> str:
        """Extract plain text body from message payload."""
        body = ""

        # Multipart message
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    body = self._decode_part(part)
                    break
            # Fallback to HTML if no plain text
            if not body:
                for part in payload["parts"]:
                    if part["mimeType"] == "text/html":
                        body = self._decode_part(part)
                        break
        # Simple message
        elif payload["mimeType"] == "text/plain" and "body" in payload:
            body = self._decode_part(payload)

        return body[:500] if body else ""  # Limit body preview

    def _decode_part(self, part: Dict) -> str:
        """Decode base64 encoded message part."""
        try:
            data = part["body"].get("data", "")
            if data:
                decoded = base64.urlsafe_b64decode(data).decode("utf-8")
                return decoded
        except Exception:
            pass
        return ""


# =============================================================================
# Action File Generator Module
# =============================================================================

class ActionFileGenerator:
    """Generates structured markdown action files for Needs_Action folder."""

    def __init__(self, needs_action_path: str):
        self.needs_action_path = Path(needs_action_path)
        self.needs_action_path.mkdir(parents=True, exist_ok=True)

    def generate(self, email_data: Dict[str, Any]) -> Path:
        """
        Generate a markdown action file from email data.
        Returns the path to the created file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"EMAIL_{timestamp}.md"
        filepath = self.needs_action_path / filename

        content = self._build_markdown_content(email_data)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"[ACTION] Created: {filepath}")
        return filepath

    def _build_markdown_content(self, email: Dict[str, Any]) -> str:
        """Build structured markdown content with frontmatter."""
        # Escape pipe characters in fields for markdown tables
        safe_from = email["from"].replace("|", "\\|")
        safe_subject = email["subject"].replace("|", "\\|")

        content = f"""---
type: email_action
priority: high
source: gmail
email_id: {email['id']}
thread_id: {email['thread_id']}
from: "{safe_from}"
subject: "{safe_subject}"
received: {email['date']}
status: pending
created: {datetime.now().isoformat()}
tags:
  - email
  - unread
  - important
---

# 📧 Email Action Required

## Message Details

| Field | Value |
|-------|-------|
| **From** | {safe_from} |
| **Subject** | {safe_subject} |
| **Received** | {email['date']} |
| **Email ID** | `{email['id']}` |

---

## Preview / Snippet

{email['snippet'] if email['snippet'] else '*No snippet available*'}

---

## Full Message Body

{email['body'] if email['body'] else '*No body content available*'}

---

## ✅ Suggested Actions

- [ ] **Reply** - Draft and send a response to this email
- [ ] **Forward** - Forward to appropriate team member
- [ ] **Archive** - Archive after reading (no action needed)
- [ ] **Delegate** - Assign task to someone else
- [ ] **Schedule** - Add related event/task to calendar
- [ ] **Research** - Look up more information before responding
- [ ] **Custom** - Add custom action below:
    - [ ] _Describe custom action_

---

## 📝 Notes

_Add any additional context or notes here_

---

## 🔗 Quick Links

- [Open in Gmail](https://mail.google.com/mail/u/0/#inbox/{email['id']})
- [View Thread](https://mail.google.com/mail/u/0/#inbox/{email['thread_id']})

---
*Generated by Gmail Watcher | Personal AI Employee*
"""
        return content


# =============================================================================
# Label Management Module
# =============================================================================

class LabelManager:
    """Manages Gmail labels for tracking processed emails."""

    def __init__(self, service):
        self.service = service
        self._processed_label_id: Optional[str] = None

    def ensure_processed_label(self) -> Optional[str]:
        """Ensure AI_PROCESSED label exists, create if needed."""
        if self._processed_label_id:
            return self._processed_label_id

        try:
            # Try to find existing label
            labels = self.service.users().labels().list(userId="me").execute()
            for label in labels.get("labels", []):
                if label["name"] == PROCESSED_LABEL:
                    self._processed_label_id = label["id"]
                    return self._processed_label_id

            # Create new label
            label_data = {
                "name": PROCESSED_LABEL,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show"
            }
            new_label = self.service.users().labels().create(
                userId="me",
                body=label_data
            ).execute()
            self._processed_label_id = new_label["id"]
            print(f"[LABEL] Created label: {PROCESSED_LABEL}")
            return self._processed_label_id

        except HttpError as error:
            print(f"[ERROR] Label management failed: {error}")
            return None

    def mark_as_processed(self, message_id: str) -> bool:
        """Mark a message as processed by adding label and removing UNREAD."""
        try:
            label_id = self.ensure_processed_label()
            if not label_id:
                return False

            # Remove UNREAD label, add PROCESSED label
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={
                    "removeLabelIds": ["UNREAD"],
                    "addLabelIds": [label_id]
                }
            ).execute()

            print(f"[LABEL] Marked message {message_id} as processed")
            return True

        except HttpError as error:
            print(f"[ERROR] Marking message as processed failed: {error}")
            return False


# =============================================================================
# Main Gmail Watcher Class
# =============================================================================

class GmailWatcher(BaseWatcher):
    """
    Gmail Watcher - Monitors Gmail for unread important emails.

    Features:
    - OAuth2 authentication with credentials.json + token.json
    - Checks every 2 minutes for new important unread emails
    - Creates structured .md files in /Needs_Action/
    - Marks processed emails with AI_PROCESSED label
    """

    def __init__(
        self,
        needs_action_path: str,
        credentials_path: str = "./credentials.json",
        token_path: str = "./token.json",
        check_interval: int = CHECK_INTERVAL_SECONDS
    ):
        super().__init__("Gmail", needs_action_path)
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._check_interval = check_interval

        # Components (lazy initialization)
        self._authenticator: Optional[GmailAuthenticator] = None
        self._service = None
        self._email_processor: Optional[EmailProcessor] = None
        self._action_generator: Optional[ActionFileGenerator] = None
        self._label_manager: Optional[LabelManager] = None

    def _initialize_components(self) -> bool:
        """Initialize all Gmail API components."""
        if self._service:
            return True  # Already initialized

        self._authenticator = GmailAuthenticator(
            self.credentials_path,
            self.token_path
        )

        creds = self._authenticator.authenticate()
        if not creds:
            print("[ERROR] Gmail authentication failed")
            return False

        try:
            self._service = build("gmail", "v1", credentials=creds)
            self._email_processor = EmailProcessor(self._service)
            self._action_generator = ActionFileGenerator(self.needs_action_path)
            self._label_manager = LabelManager(self._service)
            print("[INIT] Gmail Watcher components initialized")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to build Gmail service: {e}")
            return False

    def check_for_events(self) -> List[Dict[str, Any]]:
        """Check for new unread important emails."""
        if not self._initialize_components():
            return []

        print(f"[CHECK] Scanning for unread important emails...")
        emails = self._email_processor.fetch_unread_important()

        if emails:
            print(f"[CHECK] Found {len(emails)} unread important email(s)")
        else:
            print("[CHECK] No new unread important emails")

        return emails

    def generate_markdown_content(self, event_data: Dict[str, Any]) -> str:
        """
        Generate markdown content from email data.
        Note: ActionFileGenerator handles file creation directly,
        this method is for BaseWatcher compatibility.
        """
        generator = ActionFileGenerator(self.needs_action_path)
        return generator._build_markdown_content(event_data)

    def process_email(self, email_data: Dict[str, Any]) -> Optional[Path]:
        """
        Process a single email: create action file and mark as processed.
        Returns the path to the created action file.
        """
        # Create action file
        action_file = self._action_generator.generate(email_data)

        # Mark email as processed
        self._label_manager.mark_as_processed(email_data["id"])

        return action_file

    def check_for_events_and_process(self) -> List[Path]:
        """
        Check for emails and process them immediately.
        Returns list of created action file paths.
        """
        emails = self.check_for_events()
        action_files = []

        for email in emails:
            action_file = self.process_email(email)
            if action_file:
                action_files.append(action_file)

        return action_files

    def get_check_interval(self) -> int:
        """Return check interval in seconds (default: 2 minutes)."""
        return self._check_interval

    def stop_monitoring(self):
        """Stop the monitoring loop."""
        self.running = False
        print(f"[STOP] {self.name} watcher stopped")


# =============================================================================
# CLI & Entry Point
# =============================================================================

def run_watcher(
    needs_action_path: str = "./Needs_Action",
    credentials_path: str = "./credentials.json",
    token_path: str = "./token.json",
    interval: int = CHECK_INTERVAL_SECONDS,
    single_run: bool = False
):
    """
    Run the Gmail Watcher.

    Args:
        needs_action_path: Path to Needs_Action folder
        credentials_path: Path to credentials.json
        token_path: Path to token.json
        interval: Check interval in seconds
        single_run: If True, run once and exit
    """
    watcher = GmailWatcher(
        needs_action_path=needs_action_path,
        credentials_path=credentials_path,
        token_path=token_path,
        check_interval=interval
    )

    if single_run:
        print("[MODE] Single run mode - checking once then exiting")
        action_files = watcher.check_for_events_and_process()
        print(f"[COMPLETE] Processed {len(action_files)} email(s)")
        return action_files

    print(f"[START] Gmail Watcher starting (interval: {interval}s)")
    watcher.start_monitoring()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Gmail Watcher - Monitor Gmail for important unread emails"
    )
    parser.add_argument(
        "--needs-action",
        default="./Needs_Action",
        help="Path to Needs_Action folder"
    )
    parser.add_argument(
        "--credentials",
        default="./credentials.json",
        help="Path to credentials.json"
    )
    parser.add_argument(
        "--token",
        default="./token.json",
        help="Path to token.json"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=CHECK_INTERVAL_SECONDS,
        help=f"Check interval in seconds (default: {CHECK_INTERVAL_SECONDS})"
    )
    parser.add_argument(
        "--single-run",
        action="store_true",
        help="Run once and exit (for testing)"
    )

    args = parser.parse_args()

    run_watcher(
        needs_action_path=args.needs_action,
        credentials_path=args.credentials,
        token_path=args.token,
        interval=args.interval,
        single_run=args.single_run
    )


if __name__ == "__main__":
    main()
