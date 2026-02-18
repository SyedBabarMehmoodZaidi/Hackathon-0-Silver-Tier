#!/usr/bin/env python3
"""
Personal AI Employee - WhatsApp Watcher

Monitors WhatsApp messages for urgent keywords and creates structured .md files
in the /Needs_Action folder for AI processing.

Agent Skill Style: Modular, composable, and testable.
"""

import os
import json
import time
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Set
import re

# WhatsApp API dependencies
try:
    from whatsapp_api_client_python.API import GreenAPI
    WHATSAPP_AVAILABLE = True
except ImportError:
    try:
        from greenapi import GreenAPI
        WHATSAPP_AVAILABLE = True
    except ImportError:
        WHATSAPP_AVAILABLE = False

# Add parent directory to path for BaseWatcher import
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "Watchers"))
from base_watcher import BaseWatcher


# =============================================================================
# Constants & Configuration
# =============================================================================

# Keywords that indicate urgent/important messages
URGENT_KEYWORDS = [
    "urgent",
    "invoice",
    "payment",
    "meeting",
    "price",
    "quote",
    "order",
    "asap",
    "emergency",
    "deadline",
    "contract",
    "deal"
]

CHECK_INTERVAL_SECONDS = 30  # 30 seconds
MAX_MESSAGES_PER_CHECK = 20
SESSION_PATH = Path(__file__).parent.parent / "sessions" / "whatsapp"
PROCESSED_MARK_FILE = "processed_messages.json"


# =============================================================================
# Session Management Module
# =============================================================================

class SessionManager:
    """Manages persistent session state for WhatsApp watcher."""

    def __init__(self, session_path: Path = SESSION_PATH):
        self.session_path = Path(session_path)
        self.session_path.mkdir(parents=True, exist_ok=True)
        self.processed_file = self.session_path / PROCESSED_MARK_FILE
        self._processed_ids: Set[str] = set()
        self._load_processed()

    def _load_processed(self):
        """Load previously processed message IDs from disk."""
        try:
            if self.processed_file.exists():
                with open(self.processed_file, "r") as f:
                    data = json.load(f)
                    self._processed_ids = set(data.get("processed_ids", []))
                print(f"[SESSION] Loaded {len(self._processed_ids)} processed message IDs")
        except Exception as e:
            print(f"[SESSION] Failed to load processed IDs: {e}")
            self._processed_ids = set()

    def _save_processed(self):
        """Save processed message IDs to disk."""
        try:
            data = {"processed_ids": list(self._processed_ids)}
            with open(self.processed_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[SESSION] Failed to save processed IDs: {e}")

    def mark_processed(self, message_id: str):
        """Mark a message as processed."""
        self._processed_ids.add(message_id)
        self._save_processed()

    def is_processed(self, message_id: str) -> bool:
        """Check if a message was already processed."""
        return message_id in self._processed_ids

    def clear_old_processed(self, max_age_days: int = 7):
        """Clear processed IDs older than specified days to prevent unbounded growth."""
        # For simplicity, just limit to last N entries
        max_entries = 10000
        if len(self._processed_ids) > max_entries:
            # Keep only the most recent entries
            self._processed_ids = set(list(self._processed_ids)[-max_entries:])
            self._save_processed()
            print(f"[SESSION] Cleaned up processed IDs to {max_entries} entries")


# =============================================================================
# Keyword Detection Module
# =============================================================================

class KeywordDetector:
    """Detects urgent/important keywords in messages."""

    def __init__(self, keywords: List[str] = None):
        self.keywords = keywords or URGENT_KEYWORDS
        # Compile regex patterns for case-insensitive matching
        self.patterns = {
            kw: re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE)
            for kw in self.keywords
        }

    def detect(self, text: str) -> List[str]:
        """
        Detect keywords in text.
        Returns list of matched keywords.
        """
        if not text:
            return []

        matches = []
        for keyword, pattern in self.patterns.items():
            if pattern.search(text):
                matches.append(keyword)

        return matches

    def is_urgent(self, text: str) -> bool:
        """Check if text contains any urgent keywords."""
        return len(self.detect(text)) > 0

    def get_urgency_score(self, text: str) -> int:
        """
        Calculate urgency score based on keyword matches.
        Higher score = more urgent.
        """
        matches = self.detect(text)
        score = 0

        # Base score from number of matches
        score += len(matches) * 10

        # Bonus for multiple urgent indicators
        if "urgent" in matches or "asap" in matches or "emergency" in matches:
            score += 50

        if "deadline" in matches:
            score += 30

        if any(kw in matches for kw in ["invoice", "payment", "price", "quote", "order"]):
            score += 20

        if "meeting" in matches:
            score += 15

        return score


# =============================================================================
# WhatsApp Client Module
# =============================================================================

class WhatsAppClient:
    """Client for interacting with WhatsApp via GreenAPI."""

    def __init__(self, id_instance: str, api_token: str):
        self.id_instance = id_instance
        self.api_token = api_token
        self._api = None

    def connect(self) -> bool:
        """Establish connection to WhatsApp API."""
        try:
            if not WHATSAPP_AVAILABLE:
                print("[ERROR] WhatsApp API library not installed.")
                print("[HINT] Run: pip install whatsapp-api-client-python OR pip install greenapi")
                return False

            if not self.id_instance or not self.api_token:
                print("[ERROR] Missing idInstance or apiTokenInstance")
                print("[HINT] Get credentials from https://green-api.com/")
                return False

            self._api = GreenAPI(self.id_instance, self.api_token)

            # Test connection
            if self._api.whatsapp.checkWhatsapp(self.id_instance):
                print("[CONNECT] WhatsApp API connected successfully")
                return True
            else:
                print("[WARN] WhatsApp instance may not be ready")
                return True  # Still allow, might be initializing

        except Exception as e:
            print(f"[ERROR] WhatsApp connection failed: {e}")
            return False

    def receive_messages(self, count: int = MAX_MESSAGES_PER_CHECK) -> List[Dict[str, Any]]:
        """
        Receive incoming messages from WhatsApp.
        Returns list of message dictionaries.
        """
        messages = []

        try:
            if not self._api:
                return messages

            # Fetch messages in a loop up to count
            for _ in range(count):
                try:
                    notification = self._api.service.receiveNotification()

                    if notification and isinstance(notification, dict):
                        receipt_id = notification.get("receiptId")

                        if receipt_id:
                            # Mark notification as read
                            try:
                                self._api.service.deleteNotification(receipt_id)
                            except Exception:
                                pass  # Ignore delete errors

                            message_data = notification.get("body", {})
                            if message_data:
                                messages.append(message_data)
                        else:
                            break  # No more messages
                    else:
                        break  # No more notifications

                except Exception as e:
                    print(f"[WARN] Error fetching notification: {e}")
                    break

        except Exception as e:
            print(f"[ERROR] Failed to receive messages: {e}")

        return messages

    def get_contact_name(self, chat_id: str) -> str:
        """Get contact name for a chat ID."""
        try:
            if not self._api:
                return chat_id

            contact = self._api.contacts.getContact(chat_id)
            if contact and isinstance(contact, dict):
                return contact.get("name", contact.get("pushName", chat_id))
            return chat_id

        except Exception:
            return chat_id


# =============================================================================
# Message Processing Module
# =============================================================================

class MessageProcessor:
    """Processes WhatsApp messages and extracts relevant information."""

    def __init__(self, client: WhatsAppClient, keyword_detector: KeywordDetector):
        self.client = client
        self.keyword_detector = keyword_detector

    def process_messages(self, raw_messages: List[Dict]) -> List[Dict[str, Any]]:
        """
        Process raw messages and filter for important ones.
        Returns list of processed message dictionaries.
        """
        processed = []

        for raw_msg in raw_messages:
            try:
                msg = self._parse_message(raw_msg)
                if msg:
                    processed.append(msg)
            except Exception as e:
                print(f"[WARN] Failed to parse message: {e}")

        return processed

    def _parse_message(self, raw_msg: Dict) -> Optional[Dict[str, Any]]:
        """Parse raw WhatsApp message into structured data."""
        try:
            # Extract basic fields
            chat_id = raw_msg.get("chatId", "unknown")
            sender = raw_msg.get("senderName", raw_msg.get("pushName", chat_id))
            message_type = raw_msg.get("type", "textMessage")

            # Extract message text based on type
            text = self._extract_message_text(raw_msg)

            # Detect keywords
            keywords = self.keyword_detector.detect(text)
            urgency_score = self.keyword_detector.get_urgency_score(text)

            # Parse timestamp
            timestamp = raw_msg.get("timestamp", int(time.time()))
            try:
                parsed_time = datetime.fromtimestamp(timestamp).isoformat()
            except Exception:
                parsed_time = datetime.now().isoformat()

            return {
                "id": raw_msg.get("id", f"msg_{timestamp}"),
                "chat_id": chat_id,
                "sender": sender,
                "sender_phone": self._extract_phone(chat_id),
                "text": text,
                "message_type": message_type,
                "timestamp": parsed_time,
                "timestamp_unix": timestamp,
                "keywords": keywords,
                "urgency_score": urgency_score,
                "is_urgent": len(keywords) > 0,
                "raw": raw_msg  # Keep raw for debugging
            }

        except Exception as e:
            print(f"[ERROR] Message parsing failed: {e}")
            return None

    def _extract_message_text(self, raw_msg: Dict) -> str:
        """Extract text content from message."""
        # Try different message types
        if "textMessage" in raw_msg:
            return raw_msg["textMessage"].get("textMessage", "")

        if "extendedTextMessage" in raw_msg:
            return raw_msg["extendedTextMessage"].get("text", "")

        if "message" in raw_msg:
            msg_body = raw_msg["message"]
            if isinstance(msg_body, dict):
                return msg_body.get("textMessage", msg_body.get("text", ""))

        # Fallback: check for any text field
        for key in ["text", "message", "body", "content"]:
            if key in raw_msg and isinstance(raw_msg[key], str):
                return raw_msg[key]

        return ""

    def _extract_phone(self, chat_id: str) -> str:
        """Extract phone number from chat ID."""
        # Chat ID format is usually: phoneNumber@c.us or phoneNumber@g.us
        if "@" in chat_id:
            return chat_id.split("@")[0]
        return chat_id


# =============================================================================
# Action File Generator Module
# =============================================================================

class ActionFileGenerator:
    """Generates structured markdown action files for Needs_Action folder."""

    def __init__(self, needs_action_path: str):
        self.needs_action_path = Path(needs_action_path)
        self.needs_action_path.mkdir(parents=True, exist_ok=True)

    def generate(self, message_data: Dict[str, Any]) -> Path:
        """
        Generate a markdown action file from WhatsApp message data.
        Returns the path to the created file.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"WHATSAPP_{timestamp}.md"
        filepath = self.needs_action_path / filename

        content = self._build_markdown_content(message_data)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"[ACTION] Created: {filepath}")
        return filepath

    def _build_markdown_content(self, msg: Dict[str, Any]) -> str:
        """Build structured markdown content with frontmatter."""
        # Escape special characters for markdown
        safe_sender = str(msg["sender"]).replace("|", "\\|").replace("#", "\\#")
        safe_text = msg["text"].replace("|", "\\|")

        # Build urgency badge
        urgency_badge = "🔴 HIGH" if msg["urgency_score"] >= 50 else "🟡 MEDIUM" if msg["urgency_score"] >= 20 else "🟢 LOW"

        # Build keywords section
        keywords_str = ", ".join(f"`{kw}`" for kw in msg["keywords"]) if msg["keywords"] else "None detected"

        content = f"""---
type: whatsapp_action
priority: {"high" if msg["is_urgent"] else "normal"}
source: whatsapp
message_id: {msg['id']}
chat_id: {msg['chat_id']}
sender: "{safe_sender}"
sender_phone: {msg['sender_phone']}
received: {msg['timestamp']}
urgency_score: {msg['urgency_score']}
keywords: {json.dumps(msg['keywords'])}
status: pending
created: {datetime.now().isoformat()}
tags:
  - whatsapp
  - {"urgent" if msg["is_urgent"] else "message"}
  - {"priority" if msg["urgency_score"] >= 30 else "normal"}
---

# 📱 WhatsApp Message Action Required

## Message Details

| Field | Value |
|-------|-------|
| **Sender** | {safe_sender} |
| **Phone** | `{msg['sender_phone']}` |
| **Chat ID** | `{msg['chat_id']}` |
| **Received** | {msg['timestamp']} |
| **Message ID** | `{msg['id']}` |
| **Urgency** | {urgency_badge} (Score: {msg['urgency_score']}) |
| **Keywords** | {keywords_str} |

---

## 📄 Full Message

{safe_text if safe_text else '*No text content (may be media/other type)*'}

---

## ✅ Suggested Actions

- [ ] **Reply** - Send a response to this message
- [ ] **Urgent Response** - Immediate action required (high priority)
- [ ] **Forward** - Forward to appropriate team member
- [ ] **Schedule** - Add related event/task to calendar
- [ ] **Payment/Invoice** - Process financial matter
    - [ ] Verify invoice details
    - [ ] Process payment
    - [ ] Send confirmation
- [ ] **Meeting** - Schedule or confirm meeting
    - [ ] Check availability
    - [ ] Send calendar invite
- [ ] **Order/Quote** - Process order or provide quote
    - [ ] Review requirements
    - [ ] Prepare quote/response
- [ ] **Archive** - Mark as handled (no action needed)
- [ ] **Custom** - Add custom action below:
    - [ ] _Describe custom action_

---

## 📝 Notes

_Add any additional context or notes here_

---

## 🔗 Quick Actions

- [Reply on WhatsApp Web](https://web.whatsapp.com/)
- Open WhatsApp Desktop

---
*Generated by WhatsApp Watcher | Personal AI Employee*
"""
        return content


# =============================================================================
# Main WhatsApp Watcher Class
# =============================================================================

class WhatsAppWatcher(BaseWatcher):
    """
    WhatsApp Watcher - Monitors WhatsApp messages for urgent keywords.

    Features:
    - Persistent session in /sessions/whatsapp
    - Checks every 30 seconds for new messages
    - Keyword detection: urgent, invoice, payment, meeting, price, quote, order
    - Creates structured .md files in /Needs_Action/
    - Robust error handling with try/except
    """

    def __init__(
        self,
        needs_action_path: str,
        id_instance: str = None,
        api_token: str = None,
        check_interval: int = CHECK_INTERVAL_SECONDS,
        session_path: Path = SESSION_PATH
    ):
        super().__init__("WhatsApp", needs_action_path)
        self.id_instance = id_instance or os.getenv("WHATSAPP_ID_INSTANCE", "")
        self.api_token = api_token or os.getenv("WHATSAPP_API_TOKEN", "")
        self._check_interval = check_interval
        self._session_path = Path(session_path)

        # Components (lazy initialization)
        self._client: Optional[WhatsAppClient] = None
        self._processor: Optional[MessageProcessor] = None
        self._action_generator: Optional[ActionFileGenerator] = None
        self._session_manager: Optional[SessionManager] = None
        self._keyword_detector: Optional[KeywordDetector] = None

    def _initialize_components(self) -> bool:
        """Initialize all WhatsApp components with robust error handling."""
        if self._client:
            return True  # Already initialized

        try:
            # Initialize session manager
            self._session_manager = SessionManager(self._session_path)

            # Initialize keyword detector
            self._keyword_detector = KeywordDetector()

            # Initialize WhatsApp client
            self._client = WhatsAppClient(self.id_instance, self.api_token)

            if not self._client.connect():
                print("[WARN] WhatsApp client not connected, will retry on next check")
                return False

            # Initialize processor
            self._processor = MessageProcessor(self._client, self._keyword_detector)

            # Initialize action file generator
            self._action_generator = ActionFileGenerator(self.needs_action_path)

            print("[INIT] WhatsApp Watcher components initialized")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to initialize WhatsApp components: {e}")
            return False

    def check_for_events(self) -> List[Dict[str, Any]]:
        """Check for new urgent WhatsApp messages."""
        try:
            if not self._initialize_components():
                return []

            print(f"[CHECK] Scanning for new WhatsApp messages...")

            # Fetch raw messages
            raw_messages = self._client.receive_messages(count=MAX_MESSAGES_PER_CHECK)

            if not raw_messages:
                print("[CHECK] No new WhatsApp messages")
                return []

            # Process messages
            processed_messages = self._processor.process_messages(raw_messages)

            # Filter: only keep unprocessed and urgent/relevant messages
            urgent_messages = []
            for msg in processed_messages:
                try:
                    # Skip if already processed
                    if self._session_manager.is_processed(msg["id"]):
                        continue

                    # Keep if urgent or has significant content
                    if msg["is_urgent"] or (msg["text"] and len(msg["text"]) > 10):
                        urgent_messages.append(msg)
                        # Mark as processed
                        self._session_manager.mark_processed(msg["id"])

                except Exception as e:
                    print(f"[WARN] Error filtering message: {e}")

            if urgent_messages:
                print(f"[CHECK] Found {len(urgent_messages)} new relevant message(s)")
            else:
                print("[CHECK] No new relevant messages")

            return urgent_messages

        except Exception as e:
            print(f"[ERROR] check_for_events failed: {e}")
            return []

    def generate_markdown_content(self, event_data: Dict[str, Any]) -> str:
        """
        Generate markdown content from message data.
        Note: ActionFileGenerator handles file creation directly,
        this method is for BaseWatcher compatibility.
        """
        generator = ActionFileGenerator(self.needs_action_path)
        return generator._build_markdown_content(event_data)

    def process_message(self, message_data: Dict[str, Any]) -> Optional[Path]:
        """
        Process a single message: create action file.
        Returns the path to the created action file.
        """
        try:
            if not self._action_generator:
                return None

            action_file = self._action_generator.generate(message_data)
            return action_file

        except Exception as e:
            print(f"[ERROR] Failed to process message: {e}")
            return None

    def check_for_events_and_process(self) -> List[Path]:
        """
        Check for messages and process them immediately.
        Returns list of created action file paths.
        """
        messages = self.check_for_events()
        action_files = []

        for msg in messages:
            try:
                action_file = self.process_message(msg)
                if action_file:
                    action_files.append(action_file)
            except Exception as e:
                print(f"[ERROR] Failed to process message {msg.get('id', 'unknown')}: {e}")

        return action_files

    def get_check_interval(self) -> int:
        """Return check interval in seconds (default: 30)."""
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
    id_instance: str = None,
    api_token: str = None,
    interval: int = CHECK_INTERVAL_SECONDS,
    single_run: bool = False
):
    """
    Run the WhatsApp Watcher.

    Args:
        needs_action_path: Path to Needs_Action folder
        id_instance: WhatsApp GreenAPI instance ID
        api_token: WhatsApp GreenAPI token
        interval: Check interval in seconds
        single_run: If True, run once and exit
    """
    watcher = WhatsAppWatcher(
        needs_action_path=needs_action_path,
        id_instance=id_instance,
        api_token=api_token,
        check_interval=interval
    )

    if single_run:
        print("[MODE] Single run mode - checking once then exiting")
        action_files = watcher.check_for_events_and_process()
        print(f"[COMPLETE] Processed {len(action_files)} message(s)")
        return action_files

    print(f"[START] WhatsApp Watcher starting (interval: {interval}s)")
    watcher.start_monitoring()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="WhatsApp Watcher - Monitor WhatsApp for urgent messages"
    )
    parser.add_argument(
        "--needs-action",
        default="./Needs_Action",
        help="Path to Needs_Action folder"
    )
    parser.add_argument(
        "--id-instance",
        default=None,
        help="WhatsApp GreenAPI Instance ID (or set WHATSAPP_ID_INSTANCE env var)"
    )
    parser.add_argument(
        "--api-token",
        default=None,
        help="WhatsApp GreenAPI Token (or set WHATSAPP_API_TOKEN env var)"
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
        id_instance=args.id_instance,
        api_token=args.api_token,
        interval=args.interval,
        single_run=args.single_run
    )


if __name__ == "__main__":
    main()
