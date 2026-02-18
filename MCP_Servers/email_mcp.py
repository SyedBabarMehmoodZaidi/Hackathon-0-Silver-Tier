#!/usr/bin/env python3
"""
Email MCP Server - Gmail API with browser fallback

Provides capabilities for:
- Sending emails
- Reading emails
- Searching emails
- Managing labels

Uses Gmail API as primary, browser-mcp as fallback if API unavailable.
"""

import asyncio
import base64
import json
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime

# Gmail API imports
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False


# =============================================================================
# Gmail API Client
# =============================================================================

class GmailAPIClient:
    """Gmail API client for sending and reading emails."""

    SCOPES = [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify"
    ]

    def __init__(self, credentials_path: str = "./credentials.json", token_path: str = "./token.json"):
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self._service = None
        self._creds: Optional[Credentials] = None

    def authenticate(self) -> bool:
        """Authenticate with Gmail API."""
        if not GMAIL_AVAILABLE:
            return False

        try:
            # Load existing token
            if self.token_path.exists():
                self._creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)

            # Refresh or obtain new credentials
            if not self._creds or not self._creds.valid:
                if self._creds and self._creds.expired:
                    try:
                        self._creds.refresh(Request())
                        self._save_token()
                    except Exception:
                        self._creds = None

                if not self._creds or not self._creds.valid:
                    if not self.credentials_path.exists():
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.SCOPES
                    )
                    self._creds = flow.run_local_server(port=0)
                    self._save_token()

            self._service = build("gmail", "v1", credentials=self._creds)
            return True

        except Exception as e:
            print(f"[GMAIL] Authentication failed: {e}")
            return False

    def _save_token(self):
        """Save credentials to token file."""
        if self._creds:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_path, "w") as token:
                token.write(self._creds.to_json())

    def send_email(self, to: str, subject: str, body: str, html: bool = False, 
                   cc: Optional[str] = None, bcc: Optional[str] = None) -> Dict[str, Any]:
        """Send an email."""
        if not self._service:
            if not self.authenticate():
                return {"success": False, "error": "Gmail API authentication failed"}

        try:
            message = MIMEMultipart("alternative")
            message["to"] = to
            message["subject"] = subject
            
            if cc:
                message["cc"] = cc
            if bcc:
                message["bcc"] = bcc

            # Add body
            if html:
                message.attach(MIMEText(body, "html"))
            else:
                message.attach(MIMEText(body, "plain"))

            # Encode and send
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            sent_message = self._service.users().messages().send(
                userId="me",
                body={"raw": raw_message}
            ).execute()

            return {
                "success": True,
                "message_id": sent_message["id"],
                "thread_id": sent_message["threadId"]
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_emails(self, query: str = "is:unread", max_results: int = 10) -> Dict[str, Any]:
        """Read emails matching query."""
        if not self._service:
            if not self.authenticate():
                return {"success": False, "error": "Gmail API authentication failed"}

        try:
            results = self._service.users().messages().list(
                userId="me",
                q=query,
                maxResults=max_results
            ).execute()

            messages = results.get("messages", [])
            email_list = []

            for msg in messages:
                details = self._service.users().messages().get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["From", "To", "Subject", "Date"]
                ).execute()
                
                headers = {h["name"]: h["value"] for h in details["payload"]["headers"]}
                email_list.append({
                    "id": details["id"],
                    "thread_id": details["threadId"],
                    "from": headers.get("From", ""),
                    "to": headers.get("To", ""),
                    "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""),
                    "snippet": details.get("snippet", "")
                })

            return {"success": True, "emails": email_list}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_emails(self, query: str, max_results: int = 20) -> Dict[str, Any]:
        """Search emails by query."""
        return self.read_emails(query=query, max_results=max_results)

    def mark_as_read(self, message_id: str) -> Dict[str, Any]:
        """Mark an email as read."""
        if not self._service:
            if not self.authenticate():
                return {"success": False, "error": "Gmail API authentication failed"}

        try:
            self._service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return {"success": True, "message_id": message_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_label(self, label_name: str) -> Dict[str, Any]:
        """Create a Gmail label."""
        if not self._service:
            if not self.authenticate():
                return {"success": False, "error": "Gmail API authentication failed"}

        try:
            label = self._service.users().labels().create(
                userId="me",
                body={"name": label_name}
            ).execute()
            return {"success": True, "label_id": label["id"], "label_name": label["name"]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_label(self, message_id: str, label_name: str) -> Dict[str, Any]:
        """Add a label to a message."""
        if not self._service:
            if not self.authenticate():
                return {"success": False, "error": "Gmail API authentication failed"}

        try:
            # Find or create label
            labels = self._service.users().labels().list(userId="me").execute()
            label_id = None
            for label in labels.get("labels", []):
                if label["name"] == label_name:
                    label_id = label["id"]
                    break
            
            if not label_id:
                new_label = self.create_label(label_name)
                if new_label["success"]:
                    label_id = new_label["label_id"]
                else:
                    return new_label

            self._service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": [label_id]}
            ).execute()
            return {"success": True, "message_id": message_id, "label": label_name}
        except Exception as e:
            return {"success": False, "error": str(e)}


# =============================================================================
# Email MCP Server
# =============================================================================

class EmailMCPServer:
    """
    Email MCP Server with Gmail API primary and browser fallback.
    
    Capabilities:
    - email/send: Send an email
    - email/read: Read emails
    - email/search: Search emails
    - email/mark_read: Mark email as read
    - email/create_label: Create a label
    - email/add_label: Add label to email
    """

    def __init__(self, credentials_path: str = "./credentials.json", 
                 token_path: str = "./token.json",
                 use_browser_fallback: bool = True):
        self.gmail_client = GmailAPIClient(credentials_path, token_path)
        self.use_browser_fallback = use_browser_fallback
        self._browser_server = None
        self._api_available = None

    def _check_api_available(self) -> bool:
        """Check if Gmail API is available."""
        if self._api_available is not None:
            return self._api_available
        
        self._api_available = GMAIL_AVAILABLE and self.gmail_client.authenticate()
        return self._api_available

    async def email_send(self, to: str, subject: str, body: str, 
                         html: bool = False, cc: Optional[str] = None,
                         bcc: Optional[str] = None) -> Dict[str, Any]:
        """Send an email using Gmail API or browser fallback."""
        if self._check_api_available():
            return self.gmail_client.send_email(to, subject, body, html, cc, bcc)
        
        # Browser fallback would use browser-mcp
        if self.use_browser_fallback:
            return {
                "success": False,
                "error": "Gmail API unavailable. Browser fallback requires browser-mcp integration.",
                "fallback_needed": True,
                "draft": {"to": to, "subject": subject, "body": body}
            }
        
        return {"success": False, "error": "Gmail API unavailable and browser fallback disabled"}

    async def email_read(self, query: str = "is:unread", max_results: int = 10) -> Dict[str, Any]:
        """Read emails."""
        if self._check_api_available():
            return self.gmail_client.read_emails(query, max_results)
        return {"success": False, "error": "Gmail API unavailable"}

    async def email_search(self, query: str, max_results: int = 20) -> Dict[str, Any]:
        """Search emails."""
        if self._check_api_available():
            return self.gmail_client.search_emails(query, max_results)
        return {"success": False, "error": "Gmail API unavailable"}

    async def email_mark_read(self, message_id: str) -> Dict[str, Any]:
        """Mark email as read."""
        if self._check_api_available():
            return self.gmail_client.mark_as_read(message_id)
        return {"success": False, "error": "Gmail API unavailable"}

    async def email_create_label(self, label_name: str) -> Dict[str, Any]:
        """Create a Gmail label."""
        if self._check_api_available():
            return self.gmail_client.create_label(label_name)
        return {"success": False, "error": "Gmail API unavailable"}

    async def email_add_label(self, message_id: str, label_name: str) -> Dict[str, Any]:
        """Add label to email."""
        if self._check_api_available():
            return self.gmail_client.add_label(message_id, label_name)
        return {"success": False, "error": "Gmail API unavailable"}

    async def email_draft(self, to: str, subject: str, body: str,
                          html: bool = False) -> Dict[str, Any]:
        """Create a draft email (for browser fallback)."""
        return {
            "success": True,
            "draft": {
                "to": to,
                "subject": subject,
                "body": body,
                "html": html,
                "created": datetime.now().isoformat()
            },
            "message": "Draft created. Use browser-mcp to send via Gmail web interface."
        }


# =============================================================================
# MCP Server Entry Point
# =============================================================================

async def handle_request(server: EmailMCPServer, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP protocol requests."""
    
    handlers = {
        "email/send": lambda: server.email_send(
            params.get("to", ""),
            params.get("subject", ""),
            params.get("body", ""),
            params.get("html", False),
            params.get("cc"),
            params.get("bcc")
        ),
        "email/read": lambda: server.email_read(
            params.get("query", "is:unread"),
            params.get("max_results", 10)
        ),
        "email/search": lambda: server.email_search(
            params.get("query", ""),
            params.get("max_results", 20)
        ),
        "email/mark_read": lambda: server.email_mark_read(params.get("message_id", "")),
        "email/create_label": lambda: server.email_create_label(params.get("label_name", "")),
        "email/add_label": lambda: server.email_add_label(
            params.get("message_id", ""),
            params.get("label_name", "")
        ),
        "email/draft": lambda: server.email_draft(
            params.get("to", ""),
            params.get("subject", ""),
            params.get("body", ""),
            params.get("html", False)
        ),
    }
    
    if method not in handlers:
        return {"success": False, "error": f"Unknown method: {method}"}
    
    return await handlers[method]()


async def run_stdio_server():
    """Run MCP server using stdio transport."""
    server = EmailMCPServer(
        credentials_path="./credentials.json",
        token_path="./token.json",
        use_browser_fallback=True
    )
    
    try:
        for line in sys.stdin:
            try:
                request = json.loads(line.strip())
                method = request.get("method", "")
                params = request.get("params", {})
                request_id = request.get("id")
                
                result = await handle_request(server, method, params)
                
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }
                print(json.dumps(response), flush=True)
                
            except json.JSONDecodeError:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"}
                }
                print(json.dumps(error_response), flush=True)
                
    except KeyboardInterrupt:
        pass


def main():
    """Entry point for email MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Email MCP Server")
    parser.add_argument("--credentials", default="./credentials.json", help="Path to Gmail credentials.json")
    parser.add_argument("--token", default="./token.json", help="Path to token.json")
    parser.add_argument("--no-browser-fallback", action="store_true", help="Disable browser fallback")
    
    args = parser.parse_args()
    
    server = EmailMCPServer(
        credentials_path=args.credentials,
        token_path=args.token,
        use_browser_fallback=not args.no_browser_fallback
    )
    
    asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()
