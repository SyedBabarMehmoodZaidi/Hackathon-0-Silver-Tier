#!/usr/bin/env python3
"""
WhatsApp Web Watcher - Playwright based (No GreenAPI required)

Monitors WhatsApp Web for new messages and creates structured .md files
in the /Needs_Action folder for AI processing.

Uses Playwright with persistent session for WhatsApp Web automation.

DEBUG VERSION: Extracts real message preview text from chat rows
"""

import os
import sys
import time
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

# Playwright
try:
    from playwright.sync_api import sync_playwright, Page, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Add parent directory to path for BaseWatcher import
sys.path.insert(0, str(Path(__file__).parent.parent / "Watchers"))
from base_watcher import BaseWatcher


# =============================================================================
# Constants & Configuration
# =============================================================================

WHATSAPP_WEB_URL = "https://web.whatsapp.com"

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
    "deal",
    "important",
    "reply",
    "call",
]

CHECK_INTERVAL_SECONDS = 60  # 1 minute
SESSION_PATH = Path(__file__).parent.parent / "sessions" / "whatsapp_web"
PROCESSED_FILE = SESSION_PATH / "processed_messages.json"

# Chat selectors for WhatsApp Web (updated for current structure)
CHAT_SELECTORS = {
    'chat_row': [
        'div[role="row"]',
        'div[data-testid="chat-item"]',
        'div[class*="chat-item"]',
        'div[class*="conversation"]',
    ],
    'unread_badge': [
        '[aria-label*="unread"]',
        '[data-testid="chat-unread-count"]',
        'span[dir="auto"] + span',
        '[data-testid="unread-count"]',
        '.unread-count',
    ],
    'message_preview': [
        'span[dir="ltr"]',  # Most common for message preview
        'div[title]',  # Title attribute often contains preview
        'span[title]',
        '[data-testid="msg-preview"]',
        '[data-testid="chat-subtitle"]',
        'span[class*="preview"]',
        'div[class*="preview"]',
        'span:last-child',  # Last span often contains preview
    ],
    'sender_name': [
        'span[dir="auto"]',
        '[data-testid="chat-name"]',
        'span[class*="title"]',
    ],
}


# =============================================================================
# WhatsApp Web Authenticator
# =============================================================================

class WhatsAppWebAuth:
    """Handles WhatsApp Web authentication using Playwright."""

    def __init__(self, session_path: str):
        self.session_path = Path(session_path)
        self.session_path.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def start_browser(self) -> bool:
        """Start browser with persistent context."""
        if not PLAYWRIGHT_AVAILABLE:
            print("[ERROR] Playwright not installed.")
            return False

        try:
            self._playwright = sync_playwright().start()

            # Use Chromium with persistent context
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.session_path),
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )

            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()

            print(f"[BROWSER] Browser started with session: {self.session_path}")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to start browser: {e}")
            traceback.print_exc()
            return False

    def is_logged_in(self) -> bool:
        """Check if already logged in to WhatsApp Web."""
        if not self._page:
            return False

        try:
            current_url = self._page.url
            if "web.whatsapp.com" in current_url:
                return self._page.query_selector("#pane-side") is not None
            return False
        except Exception as e:
            print(f"[WARN] Error checking login status: {e}")
            return False

    def navigate_to_whatsapp(self):
        """Navigate to WhatsApp Web."""
        if not self._page:
            return False

        try:
            print("[INFO] Navigating to WhatsApp Web...")
            self._page.goto(WHATSAPP_WEB_URL, timeout=60000)
            self._page.wait_for_load_state("networkidle")
            return True
        except Exception as e:
            print(f"[ERROR] Navigation failed: {e}")
            traceback.print_exc()
            return False

    def wait_for_login(self, timeout_seconds: int = 120) -> bool:
        """Wait for user to scan QR code and login."""
        print("[INFO] Waiting for QR code scan...")
        print("[INFO] Open WhatsApp on your phone → Settings → Linked Devices → Link a Device")

        start_time = time.time()
        check_interval = 5

        while time.time() - start_time < timeout_seconds:
            if self.is_logged_in():
                print("[SUCCESS] WhatsApp Web logged in!")
                return True

            print(f"[WAITING] Still waiting for QR scan... ({int(time.time() - start_time)}/{timeout_seconds}s)")
            time.sleep(check_interval)

        print("[TIMEOUT] QR code scan timeout. Please restart the watcher.")
        return False

    def close(self):
        """Close the browser."""
        if self._context:
            try:
                self._context.close()
            except Exception:
                pass
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass


# =============================================================================
# WhatsApp Message Processor (DEBUG VERSION)
# =============================================================================

class WhatsAppMessageProcessor:
    """Processes WhatsApp messages from WhatsApp Web."""

    def __init__(self, page: Page):
        self.page = page
        self.processed_ids = self._load_processed()

    def _load_processed(self) -> set:
        """Load previously processed message IDs."""
        if PROCESSED_FILE.exists():
            try:
                with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    print(f"[DEBUG] Loaded {len(data)} processed message IDs")
                    return set(data)
            except Exception as e:
                print(f"[WARN] Could not load processed file: {e}")
                return set()
        print("[DEBUG] No processed messages file found")
        return set()

    def _save_processed(self):
        """Save processed message IDs."""
        try:
            PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(PROCESSED_FILE, "w", encoding="utf-8") as f:
                json.dump(list(self.processed_ids), f, indent=2)
            print(f"[DEBUG] Saved {len(self.processed_ids)} processed message IDs")
        except Exception as e:
            print(f"[ERROR] Could not save processed file: {e}")

    def _extract_chat_preview(self, chat_row) -> Optional[str]:
        """
        Extract message preview text from a chat row.
        Tries multiple selectors to find the actual message text.
        """
        # Try each preview selector
        for selector in CHAT_SELECTORS['message_preview']:
            try:
                preview_el = chat_row.query_selector(selector)
                if preview_el:
                    preview_text = preview_el.text_content() or ""
                    if preview_text.strip() and not preview_text.strip().isdigit():
                        # Not just a number (unread count)
                        return preview_text.strip()
            except Exception:
                continue

        # Fallback: try to get title attribute
        try:
            title = chat_row.get_attribute("title")
            if title and not title.strip().isdigit():
                return title.strip()
        except Exception:
            pass

        # Fallback: get all text and filter out numbers
        try:
            all_text = chat_row.text_content() or ""
            lines = [line.strip() for line in all_text.split('\n') if line.strip()]
            # Filter out lines that are just numbers (unread counts)
            text_lines = [line for line in lines if not line.isdigit()]
            if text_lines:
                # Return the longest non-number line (likely the preview)
                return max(text_lines, key=len)
        except Exception:
            pass

        return None

    def _extract_sender_name(self, chat_row) -> str:
        """Extract sender name from chat row."""
        for selector in CHAT_SELECTORS['sender_name']:
            try:
                sender_el = chat_row.query_selector(selector)
                if sender_el:
                    name = sender_el.text_content() or ""
                    if name.strip():
                        return name.strip()
            except Exception:
                continue
        return "Unknown"

    def fetch_unread_chats(self) -> List[Dict[str, Any]]:
        """
        Fetch unread chats from WhatsApp Web sidebar.
        Extracts REAL message preview text (not just unread count).
        """
        chats = []
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"\n{'='*60}")
        print(f"[DEBUG] Checking for new messages at {current_time}")
        print(f"{'='*60}")

        try:
            if not self.page:
                print("[ERROR] Page object is None - restarting browser...")
                return chats

            current_url = self.page.url
            print(f"[DEBUG] Current URL: {current_url}")

            if "web.whatsapp.com" not in current_url:
                print("[WARN] Not on WhatsApp Web, navigating...")
                try:
                    self.page.goto(WHATSAPP_WEB_URL, timeout=30000)
                    time.sleep(3)
                except Exception as e:
                    print(f"[ERROR] Navigation failed: {e}")
                    return chats

            # Wait for chat list to load
            print("[DEBUG] Waiting for chat list...")
            try:
                self.page.wait_for_selector("#pane-side", timeout=10000)
                print("[DEBUG] Chat list found")
            except Exception as e:
                print(f"[WARN] Chat list selector timeout: {e}")
                return chats

            # Find all chat rows first
            print("[DEBUG] Searching for chat rows...")
            chat_rows = []
            for selector in CHAT_SELECTORS['chat_row']:
                try:
                    found = self.page.query_selector_all(selector)
                    if found:
                        print(f"[DEBUG] Found {len(found)} chat rows with selector: {selector}")
                        chat_rows = found
                        break
                except Exception as e:
                    print(f"[DEBUG] Chat row selector {selector} failed: {e}")
                    continue

            if not chat_rows:
                print("[WARN] No chat rows found - page may have changed structure")
                return chats

            # Find unread chats
            print("[DEBUG] Searching for unread chats...")
            unread_chats = []
            
            for selector in CHAT_SELECTORS['unread_badge']:
                try:
                    found = self.page.query_selector_all(selector)
                    if found:
                        print(f"[DEBUG] Found {len(found)} unread badges with selector: {selector}")
                        # Find parent chat rows for each unread badge
                        for badge in found:
                            try:
                                # Navigate up to find the chat row
                                parent = badge
                                for _ in range(5):  # Go up max 5 levels
                                    parent = parent.evaluate('el => el.parentElement')
                                    if not parent:
                                        break
                                    # Check if this parent matches a chat row
                                    for row in chat_rows:
                                        try:
                                            if parent == row.evaluate('el => el'):
                                                if row not in unread_chats:
                                                    unread_chats.append(row)
                                                break
                                        except Exception:
                                            continue
                            except Exception as e:
                                print(f"[DEBUG] Error finding parent for badge: {e}")
                                continue
                        if unread_chats:
                            break
                except Exception as e:
                    print(f"[DEBUG] Unread badge selector {selector} failed: {e}")
                    continue

            # Fallback: check all chat rows for unread indicators
            if not unread_chats:
                print("[DEBUG] No unread badges found, checking all chats for unread indicators...")
                for i, chat_row in enumerate(chat_rows[:30]):
                    try:
                        chat_html = chat_row.inner_html()
                        chat_text = chat_row.text_content() or ""
                        
                        # Check for unread indicators in HTML or text
                        if "unread" in chat_html.lower() or chat_text.strip().isdigit():
                            unread_chats.append(chat_row)
                            print(f"[DEBUG] Chat {i} appears unread (detected by HTML/text)")
                    except Exception as e:
                        print(f"[DEBUG] Error checking chat {i}: {e}")
                        continue

            print(f"[DEBUG] Found {len(unread_chats)} unread chats total")
            print(f"{'='*60}")

            # Extract information from each unread chat
            for i, chat_row in enumerate(unread_chats[:20]):
                try:
                    print(f"\n[DEBUG] --- Processing Chat {i+1}/{len(unread_chats)} ---")
                    
                    # Get sender name
                    sender = self._extract_sender_name(chat_row)
                    print(f"[DEBUG] Sender: {sender}")
                    
                    # Get message preview (REAL TEXT, not just unread count!)
                    preview_text = self._extract_chat_preview(chat_row)
                    
                    if preview_text:
                        print(f"[DEBUG] Preview text: {preview_text[:200]}")
                    else:
                        # Debug: print what we DID find
                        try:
                            all_text = chat_row.text_content() or ""
                            print(f"[DEBUG] All text in row: {all_text[:300]}")
                            print(f"[DEBUG] HTML snippet (first 500 chars):")
                            html_snippet = chat_row.evaluate('el => el.outerHTML')
                            print(f"  {html_snippet[:500]}...")
                        except Exception as e:
                            print(f"[DEBUG] Could not get debug info: {e}")
                        continue  # Skip if no preview text

                    # Check for keywords in preview text
                    text_lower = preview_text.lower().strip()
                    text_clean = text_lower.replace(":", "").replace("  ", " ").strip()
                    
                    print(f"[DEBUG] Checking keywords in: {text_clean[:100]}")
                    
                    found_keywords = []
                    for kw in URGENT_KEYWORDS:
                        if kw in text_clean or kw in text_lower:
                            found_keywords.append(kw)
                            print(f"[DEBUG]   ✓ Keyword match found: {kw}")
                        elif f"{kw}:" in text_lower or f"{kw} " in text_lower:
                            found_keywords.append(kw)
                            print(f"[DEBUG]   ✓ Keyword match (with punctuation): {kw}")

                    if found_keywords:
                        chats.append({
                            "id": f"chat_{i}_{int(time.time())}",
                            "text": preview_text,
                            "sender": sender,
                            "time": datetime.now().strftime("%H:%M"),
                            "has_keywords": True,
                            "keywords": found_keywords,
                        })
                        print(f"[DEBUG]   ✓✓✓ CHAT ADDED - keywords: {found_keywords}")
                    else:
                        print(f"[DEBUG]   ✗ No keywords found in this chat")

                except Exception as e:
                    print(f"[WARN] Error extracting chat {i}: {e}")
                    traceback.print_exc()
                    continue

            print(f"\n{'='*60}")
            print(f"[DEBUG] Total chats with keywords: {len(chats)}")
            print(f"{'='*60}\n")

        except Exception as e:
            print(f"[ERROR] Fetching unread chats failed: {e}")
            traceback.print_exc()

        return chats


# =============================================================================
# Action File Generator
# =============================================================================

class ActionFileGenerator:
    """Generates structured markdown action files."""

    def __init__(self, needs_action_path: str):
        self.needs_action_path = Path(needs_action_path).resolve()
        self.needs_action_path.mkdir(parents=True, exist_ok=True)
        print(f"[DEBUG] Action files will be saved to: {self.needs_action_path}")

    def generate(self, message_data: Dict[str, Any]) -> Path:
        """Generate markdown action file from WhatsApp message."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"WHATSAPP_{timestamp}.md"
        filepath = self.needs_action_path / filename

        print(f"\n[DEBUG] Creating action file for: {filepath}")
        print(f"[DEBUG]   Sender: {message_data.get('sender', 'Unknown')}")
        print(f"[DEBUG]   Keywords: {message_data.get('keywords', [])}")
        print(f"[DEBUG]   Preview: {message_data.get('text', '')[:100]}")

        try:
            content = self._build_markdown_content(message_data)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            print(f"[ACTION] Created: {filepath}")
            print(f"[DEBUG]   Absolute path: {filepath.resolve()}")
            print(f"[DEBUG]   File exists: {filepath.exists()}")
            return filepath

        except Exception as e:
            print(f"[ERROR] Failed to create action file: {e}")
            traceback.print_exc()
            raise

    def _build_markdown_content(self, msg: Dict[str, Any]) -> str:
        """Build markdown content with preview in frontmatter."""
        keywords = msg.get("keywords", [])
        preview = msg.get("text", "")

        content = f"""---
type: whatsapp_message
priority: high
source: whatsapp_web
sender: "{msg.get('sender', 'Unknown')}"
received: {msg.get('time', 'Unknown')}
status: pending
created: {datetime.now().isoformat()}
keywords: {keywords}
preview: "{preview[:200]}"
tags:
  - whatsapp
  - message
  - {' '.join(keywords)}
---

# 📱 WhatsApp Message - Action Required

## Message Details

| Field | Value |
|-------|-------|
| **From** | {msg.get('sender', 'Unknown')} |
| **Time** | {msg.get('time', 'Unknown')} |
| **Keywords** | {', '.join(keywords) if keywords else 'None'} |

---

## Message Preview

{preview if preview else '*No preview available*'}

---

## ✅ Suggested Actions

- [ ] **Reply** - Send a response to this message
- [ ] **Call** - Call the sender if urgent
- [ ] **Forward** - Forward to appropriate team member
- [ ] **Schedule** - Add related task to calendar
- [ ] **Archive** - Archive after handling

---

## 📝 Notes

_Add any additional context or notes here_

---
*Generated by WhatsApp Web Watcher | Personal AI Employee*
"""
        return content


# =============================================================================
# Main WhatsApp Watcher Class
# =============================================================================

class WhatsAppWebWatcher(BaseWatcher):
    """
    WhatsApp Web Watcher - Monitors WhatsApp Web for messages.
    DEBUG VERSION with message preview extraction
    """

    def __init__(
        self,
        needs_action_path: str,
        session_path: str = str(SESSION_PATH),
        check_interval: int = CHECK_INTERVAL_SECONDS
    ):
        super().__init__("WhatsAppWeb", needs_action_path)
        self.session_path = Path(session_path).resolve()
        self._check_interval = check_interval
        self._consecutive_errors = 0
        self._max_errors_before_restart = 5

        self._auth: Optional[WhatsAppWebAuth] = None
        self._processor: Optional[WhatsAppMessageProcessor] = None
        self._action_generator: Optional[ActionFileGenerator] = None

    def _initialize_components(self) -> bool:
        """Initialize WhatsApp Web components."""
        if self._auth and self._auth.is_logged_in():
            # Check if page is still responsive
            try:
                if self._auth._page:
                    self._auth._page.evaluate("1")  # Simple check
                    return True
            except Exception:
                print("[WARN] Page seems unresponsive, reinitializing...")
                self._auth = None

        self._auth = WhatsAppWebAuth(str(self.session_path))

        # Start browser
        if not self._auth.start_browser():
            return False

        # Navigate to WhatsApp Web
        self._auth.navigate_to_whatsapp()

        # Check if already logged in
        if not self._auth.is_logged_in():
            print("[INFO] Not logged in. Waiting for QR code scan...")
            if not self._auth.wait_for_login(timeout_seconds=120):
                return False

        self._processor = WhatsAppMessageProcessor(self._auth._page)
        self._action_generator = ActionFileGenerator(self.needs_action_path)

        print("[INIT] WhatsApp Web Watcher initialized")
        return True

    def check_for_events(self) -> List[Dict[str, Any]]:
        """Check for new WhatsApp messages with keywords."""
        try:
            if not self._initialize_components():
                self._consecutive_errors += 1
                print(f"[WARN] Initialization failed (error {self._consecutive_errors}/{self._max_errors_before_restart})")
                
                if self._consecutive_errors >= self._max_errors_before_restart:
                    print("[ERROR] Too many errors, attempting browser restart...")
                    self._restart_browser()
                
                return []

            self._consecutive_errors = 0  # Reset error counter

            print(f"\n[CHECK] Scanning WhatsApp Web for keywords: {URGENT_KEYWORDS}")
            print(f"[CHECK] Session path: {self.session_path}")
            print(f"[CHECK] Needs_Action path: {self.needs_action_path}")

            messages = self._processor.fetch_unread_chats()

            if messages:
                print(f"[CHECK] Found {len(messages)} unread chat(s) with keywords")
            else:
                print("[CHECK] No unread chats with keywords")

            return messages

        except Exception as e:
            print(f"[ERROR] check_for_events failed: {e}")
            traceback.print_exc()
            self._consecutive_errors += 1
            return []

    def _restart_browser(self):
        """Restart the browser if too many errors occur."""
        print("[INFO] Attempting browser restart...")
        try:
            if self._auth:
                self._auth.close()
                self._auth = None
            
            time.sleep(2)
            
            if self._initialize_components():
                print("[SUCCESS] Browser restarted successfully")
            else:
                print("[ERROR] Failed to restart browser")
        except Exception as e:
            print(f"[ERROR] Browser restart failed: {e}")
            traceback.print_exc()

    def generate_markdown_content(self, event_data: Dict[str, Any]) -> str:
        """Generate markdown content from message data."""
        return self._action_generator._build_markdown_content(event_data)

    def process_message(self, message_data: Dict[str, Any]) -> Optional[Path]:
        """Process a single message: create action file."""
        return self._action_generator.generate(message_data)

    def check_for_events_and_process(self) -> List[Path]:
        """Check for messages and process them."""
        messages = self.check_for_events()
        action_files = []

        for msg in messages:
            try:
                action_file = self.process_message(msg)
                if action_file:
                    action_files.append(action_file)
            except Exception as e:
                print(f"[ERROR] Failed to process message: {e}")
                traceback.print_exc()
                continue

        return action_files

    def get_check_interval(self) -> int:
        """Return check interval in seconds."""
        return self._check_interval

    def stop_monitoring(self):
        """Stop monitoring and close browser."""
        self.running = False
        if self._auth:
            self._auth.close()
        print(f"[STOP] {self.name} watcher stopped")


# =============================================================================
# CLI Entry Point
# =============================================================================

def run_watcher(
    needs_action_path: str = "./Needs_Action",
    session_path: str = str(SESSION_PATH),
    interval: int = CHECK_INTERVAL_SECONDS,
    single_run: bool = False
):
    """Run the WhatsApp Web Watcher."""
    watcher = WhatsAppWebWatcher(
        needs_action_path=needs_action_path,
        session_path=session_path,
        check_interval=interval
    )

    if single_run:
        print("[MODE] Single run mode")
        action_files = watcher.check_for_events_and_process()
        print(f"[COMPLETE] Processed {len(action_files)} message(s)")
        watcher.stop_monitoring()
        return action_files

    print(f"[START] WhatsApp Web Watcher starting (interval: {interval}s)")
    print(f"[KEYWORDS] Watching for: {URGENT_KEYWORDS}")
    try:
        watcher.start_monitoring()
    finally:
        watcher.stop_monitoring()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="WhatsApp Web Watcher - Monitor WhatsApp without GreenAPI (DEBUG VERSION)"
    )
    parser.add_argument(
        "--needs-action",
        default="./Needs_Action",
        help="Path to Needs_Action folder"
    )
    parser.add_argument(
        "--session",
        default=str(SESSION_PATH),
        help="Path to session storage directory"
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
        session_path=args.session,
        interval=args.interval,
        single_run=args.single_run
    )


if __name__ == "__main__":
    main()
