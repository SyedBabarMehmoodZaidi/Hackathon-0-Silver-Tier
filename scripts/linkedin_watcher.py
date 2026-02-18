#!/usr/bin/env python3
"""
LinkedIn Watcher - Playwright based

Monitors LinkedIn for notifications and messages containing keywords:
"opportunity", "lead", "interest", "hire"

Creates structured .md files in the /Needs_Action folder for AI processing.

Uses Playwright with persistent context for session persistence.

IMPROVED v2: Smart timeout handling, optional notifications, feed monitoring
"""

import os
import sys
import time
import re
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

# Playwright
try:
    from playwright.sync_api import sync_playwright, Page, BrowserContext, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# Add parent directory to path for BaseWatcher import
sys.path.insert(0, str(Path(__file__).parent.parent / "Watchers"))
from base_watcher import BaseWatcher


# =============================================================================
# Constants & Configuration
# =============================================================================

LINKEDIN_URL = "https://www.linkedin.com"
LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"
LINKEDIN_FEED_URL = "https://www.linkedin.com/feed"
LINKEDIN_NOTIFICATIONS_URL = "https://www.linkedin.com/notifications"
LINKEDIN_MESSAGING_URL = "https://www.linkedin.com/messaging"

# Keywords to watch for
WATCH_KEYWORDS = ["opportunity", "lead", "interest", "hire"]

# Session storage path
SESSION_PATH = Path(__file__).parent.parent / "sessions" / "linkedin"

# Timeouts (increased for stability)
PAGE_LOAD_TIMEOUT = 120000  # 120 seconds
NAVIGATION_TIMEOUT = 120000  # 120 seconds
WAIT_FOR_ELEMENTS = 30000  # 30 seconds
DEFAULT_TIMEOUT = 120000  # 120 seconds
LOAD_STATE_TIMEOUT = 60000  # 60 seconds

# Check interval
CHECK_INTERVAL_SECONDS = 180  # 3 minutes

# Retry settings with exponential backoff
MAX_RETRIES = 5
RETRY_DELAYS = [5, 10, 15, 30, 60]  # seconds for each retry

# Skip threshold - after this many failures, skip section
SKIP_THRESHOLD = 3

# Markdown file prefix
MD_FILE_PREFIX = "LINKEDIN"

# Real browser User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


# =============================================================================
# LinkedIn Authenticator
# =============================================================================

class LinkedInAuthenticator:
    """Handles LinkedIn authentication using Playwright persistent context."""

    def __init__(self, session_path: str):
        self.session_path = Path(session_path)
        self.session_path.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def start_browser(self) -> Optional[BrowserContext]:
        """Start browser with persistent context."""
        if not PLAYWRIGHT_AVAILABLE:
            print("[ERROR] Playwright not installed.")
            return None

        try:
            self._playwright = sync_playwright().start()
            
            # Use Chromium with persistent context and stability args
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.session_path),
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
                ignore_default_args=["--enable-automation"],
            )
            
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
            
            # Set default timeout
            self._page.set_default_timeout(DEFAULT_TIMEOUT)
            
            # Set real browser User-Agent
            self._page.set_extra_http_headers({"User-Agent": USER_AGENT})
            
            print(f"[BROWSER] Browser started with session: {self.session_path}")
            return self._context

        except Exception as e:
            print(f"[ERROR] Failed to start browser: {e}")
            traceback.print_exc()
            return None

    def is_logged_in(self) -> bool:
        """Check if already logged in."""
        if not self._context or not self._page:
            return False

        try:
            # Check auth cookies
            cookies = self._context.cookies()
            auth_cookies = [c for c in cookies if c.get("name") in ["li_at", "JSESSIONID"]]
            
            if not auth_cookies:
                return False
            
            # Check URL
            current_url = self._page.url
            if "login" in current_url.lower():
                return False
            
            # Check for feed elements
            try:
                feed_selector = self._page.query_selector('.feed-identity-module__actor-meta, .global-nav, nav[aria-label="Primary navigation"]')
                if feed_selector:
                    return True
            except Exception:
                pass
            
            # Check if on LinkedIn main page
            if "linkedin.com/" in current_url and "login" not in current_url:
                return True
            
            return False

        except Exception as e:
            print(f"[ERROR] Checking login status: {e}")
            return False

    def navigate_to_linkedin(self) -> bool:
        """Navigate to LinkedIn feed page."""
        if not self._page:
            return False

        try:
            print("[INFO] Navigating to LinkedIn feed...")
            self._page.goto(LINKEDIN_FEED_URL, timeout=NAVIGATION_TIMEOUT, wait_until="networkidle")
            self._page.wait_for_load_state("networkidle", timeout=LOAD_STATE_TIMEOUT)
            print(f"[DEBUG] Current URL: {self._page.url}")
            return True
        except Exception as e:
            print(f"[ERROR] Navigation failed: {e}")
            traceback.print_exc()
            return False

    def login(self, email: str, password: str) -> bool:
        """Perform LinkedIn login."""
        if not self._page:
            return False

        try:
            print("[INFO] Navigating to login page...")
            self._page.goto(LINKEDIN_LOGIN_URL, timeout=NAVIGATION_TIMEOUT, wait_until="networkidle")
            
            if self.is_logged_in():
                print("[AUTH] Already logged in")
                return True

            print("[INFO] Entering credentials...")
            self._page.wait_for_selector("#username", timeout=WAIT_FOR_ELEMENTS)
            self._page.fill("#username", email)
            self._page.fill("#password", password)
            self._page.click('button[type="submit"]')
            self._page.wait_for_load_state("networkidle", timeout=NAVIGATION_TIMEOUT)
            
            if self.is_logged_in():
                print("[AUTH] Login successful")
                return True
            
            print("[AUTH] Login verification failed")
            return False

        except Exception as e:
            print(f"[ERROR] Login failed: {e}")
            traceback.print_exc()
            return False

    def wait_for_manual_login(self, timeout_seconds: int = 120) -> bool:
        """Wait for user to manually login."""
        print("[INFO] Please login to LinkedIn in the browser window")
        
        start_time = time.time()
        check_interval = 5
        
        while time.time() - start_time < timeout_seconds:
            if self.is_logged_in():
                print("[SUCCESS] Login detected!")
                return True
            
            elapsed = int(time.time() - start_time)
            print(f"[WAITING] Waiting for login... ({elapsed}/{timeout_seconds}s)")
            time.sleep(check_interval)
        
        print("[TIMEOUT] Login timeout")
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
# LinkedIn Data Processor
# =============================================================================

class LinkedInDataProcessor:
    """Processes LinkedIn notifications and messages."""

    def __init__(self, context: BrowserContext):
        self.context = context
        self.keywords_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(k) for k in WATCH_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
        self._notification_failures = 0
        self._message_failures = 0

    def _get_page(self) -> Optional[Page]:
        """Get or create a page."""
        try:
            return self.context.pages[0] if self.context.pages else self.context.new_page()
        except Exception as e:
            print(f"[ERROR] Could not get page: {e}")
            return None

    def _take_screenshot(self, page: Page, name: str):
        """Take a debug screenshot."""
        try:
            screenshot_path = f"debug_linkedin_{name}.png"
            page.screenshot(path=screenshot_path)
            print(f"[DEBUG] Screenshot saved: {screenshot_path}")
        except Exception as e:
            print(f"[WARN] Could not take screenshot: {e}")

    def _retry_operation(self, operation, operation_name: str) -> Optional[Any]:
        """Retry an operation with exponential backoff."""
        for attempt in range(MAX_RETRIES):
            try:
                print(f"[DEBUG] {operation_name} (attempt {attempt+1}/{MAX_RETRIES})")
                return operation()
            except PlaywrightTimeout as e:
                print(f"[WARN] {operation_name} timeout on attempt {attempt+1}: {e}")
                
                # Take screenshot on failures
                page = self._get_page()
                if page:
                    self._take_screenshot(page, f"{operation_name.lower().replace(' ', '_')}_attempt_{attempt+1}")
                
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS)-1)]
                    print(f"[DEBUG] Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print(f"[ERROR] {operation_name} failed after {MAX_RETRIES} attempts")
                    raise
            except Exception as e:
                print(f"[ERROR] {operation_name} failed: {e}")
                traceback.print_exc()
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS)-1)]
                    time.sleep(delay)
                else:
                    raise
        return None

    def _safe_navigate(self, url: str, operation_name: str) -> bool:
        """Navigate safely with retry and reload logic."""
        page = self._get_page()
        if not page:
            return False

        for attempt in range(3):
            try:
                print(f"[DEBUG] Navigating to {url} (attempt {attempt+1}/3)")
                page.goto(url, timeout=NAVIGATION_TIMEOUT, wait_until="networkidle")
                page.wait_for_load_state("networkidle", timeout=LOAD_STATE_TIMEOUT)
                print(f"[DEBUG] Navigation successful, current URL: {page.url}")
                return True
            except PlaywrightTimeout as e:
                print(f"[WARN] Navigation timeout on attempt {attempt+1}: {e}")
                
                # Take screenshot
                self._take_screenshot(page, f"nav_timeout_{operation_name}_attempt_{attempt+1}")
                
                # Try reload on second attempt
                if attempt == 1:
                    print("[DEBUG] Attempting page reload...")
                    try:
                        page.reload(timeout=NAVIGATION_TIMEOUT, wait_until="networkidle")
                        page.wait_for_load_state("networkidle", timeout=LOAD_STATE_TIMEOUT)
                        return True
                    except Exception:
                        pass
                
                if attempt < 2:
                    time.sleep(RETRY_DELAYS[attempt])
                
            except Exception as e:
                print(f"[ERROR] Navigation failed: {e}")
                if attempt < 2:
                    time.sleep(RETRY_DELAYS[attempt])
        
        return False

    def fetch_notifications(self) -> List[Dict[str, Any]]:
        """Fetch notifications with smart skip logic."""
        # Skip if too many consecutive failures
        if self._notification_failures >= SKIP_THRESHOLD:
            print(f"[SKIP] Skipping notifications (failed {self._notification_failures} times)")
            return []

        notifications = []

        def _fetch():
            page = self._get_page()
            if not page:
                return notifications

            # Navigate to notifications page
            if not self._safe_navigate(LINKEDIN_NOTIFICATIONS_URL, "notifications"):
                raise PlaywrightTimeout("Navigation failed after retries")

            # Wait for notifications with multiple selectors
            notification_selectors = [
                '.notification-card',
                '[data-id]',
                'article.notification',
                '.mn-notification-card',
            ]
            
            found_selector = None
            for selector in notification_selectors:
                try:
                    page.wait_for_selector(selector, timeout=WAIT_FOR_ELEMENTS, state="attached")
                    found_selector = selector
                    print(f"[DEBUG] Found notifications with: {selector}")
                    break
                except PlaywrightTimeout:
                    continue
            
            if not found_selector:
                print("[WARN] No notification selectors matched")
                # Take screenshot for debugging
                self._take_screenshot(page, "notifications_no_content")
                # Check page content for keywords
                content = page.content()
                if any(kw.lower() in content.lower() for kw in WATCH_KEYWORDS):
                    notifications.append({
                        "type": "notification",
                        "subtype": "general",
                        "sender": "LinkedIn",
                        "content": "Keywords detected in notifications page",
                        "timestamp": datetime.now().isoformat(),
                        "has_keyword": True,
                        "matched_keywords": WATCH_KEYWORDS,
                        "url": LINKEDIN_NOTIFICATIONS_URL,
                    })
                return notifications
            
            # Extract notifications
            notification_cards = page.query_selector_all(found_selector)
            print(f"[DEBUG] Found {len(notification_cards)} notification cards")
            
            for card in notification_cards[:20]:
                try:
                    notification_data = self._parse_notification_card(card, page)
                    if notification_data:
                        notifications.append(notification_data)
                except Exception as e:
                    print(f"[WARN] Failed to parse notification: {e}")
                    continue

            return notifications

        try:
            result = self._retry_operation(lambda: _fetch(), "Fetch notifications")
            self._notification_failures = 0  # Reset on success
            return result or []
        except Exception as e:
            self._notification_failures += 1
            print(f"[ERROR] Fetching notifications failed (failure {self._notification_failures}/{SKIP_THRESHOLD}): {e}")
            if self._notification_failures >= SKIP_THRESHOLD:
                print(f"[SKIP] Skipping notifications for this cycle")
            return []

    def _parse_notification_card(self, card, page: Page) -> Optional[Dict[str, Any]]:
        """Parse a notification card."""
        try:
            text_content = card.text_content() or ""
            
            sender = ""
            sender_elem = card.query_selector(".actor-name, .notification-actor-name, .feed-identity-module__actor-meta")
            if sender_elem:
                sender = sender_elem.text_content() or ""
            
            timestamp = datetime.now().isoformat()
            time_elem = card.query_selector("time, .notification-time")
            if time_elem:
                time_text = time_elem.text_content() or ""
                if time_text:
                    timestamp = self._parse_relative_time(time_text)
            
            # Check for keywords (flexible matching)
            text_lower = text_content.lower()
            has_keyword = bool(self.keywords_pattern.search(text_content))
            
            if not has_keyword:
                for kw in WATCH_KEYWORDS:
                    if kw in text_lower:
                        has_keyword = True
                        break
            
            return {
                "type": "notification",
                "subtype": self._detect_notification_type(text_content),
                "sender": sender.strip() if sender else "Unknown",
                "content": text_content.strip()[:500],
                "timestamp": timestamp,
                "has_keyword": has_keyword,
                "matched_keywords": self._get_matched_keywords(text_content),
                "url": LINKEDIN_NOTIFICATIONS_URL,
            }
        except Exception as e:
            return None

    def fetch_messages(self) -> List[Dict[str, Any]]:
        """Fetch messages with smart skip logic."""
        # Skip if too many consecutive failures
        if self._message_failures >= SKIP_THRESHOLD:
            print(f"[SKIP] Skipping messages (failed {self._message_failures} times)")
            return []

        messages = []

        def _fetch():
            page = self._get_page()
            if not page:
                return messages

            # Navigate to messaging page
            if not self._safe_navigate(LINKEDIN_MESSAGING_URL, "messages"):
                raise PlaywrightTimeout("Navigation failed after retries")

            # Wait for conversation list
            message_selectors = [
                '.conversation-card',
                '[data-conversation-id]',
                '.msg-conversation-card',
            ]
            
            found_selector = None
            for selector in message_selectors:
                try:
                    page.wait_for_selector(selector, timeout=WAIT_FOR_ELEMENTS, state="attached")
                    found_selector = selector
                    print(f"[DEBUG] Found messages with: {selector}")
                    break
                except PlaywrightTimeout:
                    continue
            
            if not found_selector:
                print("[WARN] No message selectors matched")
                self._take_screenshot(page, "messages_no_content")
                content = page.content()
                if any(kw.lower() in content.lower() for kw in WATCH_KEYWORDS):
                    messages.append({
                        "type": "message",
                        "sender": "LinkedIn Messages",
                        "content": "Keywords detected in messages page",
                        "timestamp": datetime.now().isoformat(),
                        "has_keyword": True,
                        "matched_keywords": WATCH_KEYWORDS,
                        "url": LINKEDIN_MESSAGING_URL,
                    })
                return messages
            
            conversation_cards = page.query_selector_all(found_selector)
            print(f"[DEBUG] Found {len(conversation_cards)} conversation cards")
            
            for card in conversation_cards[:15]:
                try:
                    message_data = self._parse_message_card(card, page)
                    if message_data:
                        messages.append(message_data)
                except Exception as e:
                    print(f"[WARN] Failed to parse message: {e}")
                    continue

            return messages

        try:
            result = self._retry_operation(lambda: _fetch(), "Fetch messages")
            self._message_failures = 0  # Reset on success
            return result or []
        except Exception as e:
            self._message_failures += 1
            print(f"[ERROR] Fetching messages failed (failure {self._message_failures}/{SKIP_THRESHOLD}): {e}")
            if self._message_failures >= SKIP_THRESHOLD:
                print(f"[SKIP] Skipping messages for this cycle")
            return []

    def _parse_message_card(self, card, page: Page) -> Optional[Dict[str, Any]]:
        """Parse a message card."""
        try:
            text_content = card.text_content() or ""
            
            sender = ""
            sender_elem = card.query_selector(".artdeco-entity-title, .msg-conversation-card__name")
            if sender_elem:
                sender = sender_elem.text_content() or ""
            
            preview = ""
            preview_elem = card.query_selector(".message-preview, .msg-conversation-card__message-preview")
            if preview_elem:
                preview = preview_elem.text_content() or ""
            
            timestamp = datetime.now().isoformat()
            
            full_content = f"{sender} {text_content} {preview}"
            text_lower = full_content.lower()
            has_keyword = bool(self.keywords_pattern.search(full_content))
            
            if not has_keyword:
                for kw in WATCH_KEYWORDS:
                    if kw in text_lower:
                        has_keyword = True
                        break
            
            return {
                "type": "message",
                "sender": sender.strip() if sender else "Unknown",
                "preview": preview.strip()[:300] if preview else "",
                "content": full_content.strip()[:500],
                "timestamp": timestamp,
                "has_keyword": has_keyword,
                "matched_keywords": self._get_matched_keywords(full_content),
                "url": LINKEDIN_MESSAGING_URL,
            }
        except Exception as e:
            return None

    def fetch_feed_content(self) -> List[Dict[str, Any]]:
        """
        Fetch and scan feed content for keywords.
        This is more reliable than notifications/messages.
        """
        items = []

        try:
            page = self._get_page()
            if not page:
                return items

            # Navigate to feed
            print("[DEBUG] Navigating to feed...")
            page.goto(LINKEDIN_FEED_URL, timeout=NAVIGATION_TIMEOUT, wait_until="networkidle")
            page.wait_for_load_state("networkidle", timeout=LOAD_STATE_TIMEOUT)
            
            # Wait for feed posts
            feed_selectors = [
                '.feed-shared-update-v2',
                '[data-id="urn:li:activity:"]',
                'article.ember-view',
                '.update-v2',
            ]
            
            found_selector = None
            for selector in feed_selectors:
                try:
                    page.wait_for_selector(selector, timeout=WAIT_FOR_ELEMENTS, state="attached")
                    found_selector = selector
                    print(f"[DEBUG] Found feed posts with: {selector}")
                    break
                except PlaywrightTimeout:
                    continue
            
            if not found_selector:
                print("[WARN] No feed selectors matched")
                return items
            
            # Extract feed posts
            feed_posts = page.query_selector_all(found_selector)
            print(f"[DEBUG] Found {len(feed_posts)} feed posts")
            
            for post in feed_posts[:30]:  # Check first 30 posts
                try:
                    text_content = post.text_content() or ""
                    text_lower = text_content.lower()
                    
                    # Check for keywords
                    has_keyword = bool(self.keywords_pattern.search(text_content))
                    if not has_keyword:
                        for kw in WATCH_KEYWORDS:
                            if kw in text_lower:
                                has_keyword = True
                                break
                    
                    if has_keyword:
                        # Extract author
                        author = "Unknown"
                        author_elem = post.query_selector(".feed-identity-module__actor-meta, .update-v2__actor-name")
                        if author_elem:
                            author = author_elem.text_content() or "Unknown"
                        
                        items.append({
                            "type": "feed_post",
                            "sender": author.strip(),
                            "content": text_content.strip()[:500],
                            "timestamp": datetime.now().isoformat(),
                            "has_keyword": True,
                            "matched_keywords": self._get_matched_keywords(text_content),
                            "url": LINKEDIN_FEED_URL,
                        })
                        print(f"[DEBUG] Found keyword in feed post by {author}")
                        
                except Exception as e:
                    print(f"[WARN] Failed to parse feed post: {e}")
                    continue

        except Exception as e:
            print(f"[ERROR] Fetching feed content failed: {e}")

        return items

    def _detect_notification_type(self, text: str) -> str:
        """Detect notification type."""
        text_lower = text.lower()
        
        if "connection" in text_lower or "connect" in text_lower:
            return "connection"
        elif "message" in text_lower or "inbox" in text_lower:
            return "message"
        elif "job" in text_lower or "hiring" in text_lower or "hire" in text_lower:
            return "job_opportunity"
        elif "profile" in text_lower or "view" in text_lower:
            return "profile_view"
        elif "post" in text_lower or "comment" in text_lower or "like" in text_lower:
            return "engagement"
        elif "recommendation" in text_lower or "endorse" in text_lower:
            return "recommendation"
        return "general"

    def _get_matched_keywords(self, text: str) -> List[str]:
        """Get matched keywords."""
        text_lower = text.lower()
        return [kw for kw in WATCH_KEYWORDS if kw in text_lower]

    def _parse_relative_time(self, time_text: str) -> str:
        """Parse relative time."""
        try:
            time_text = time_text.strip().lower()
            if "just now" in time_text:
                return datetime.now().isoformat()
            return datetime.now().isoformat()
        except Exception:
            return datetime.now().isoformat()


# =============================================================================
# Action File Generator
# =============================================================================

class ActionFileGenerator:
    """Generates structured markdown action files."""

    def __init__(self, needs_action_path: str):
        self.needs_action_path = Path(needs_action_path).resolve()
        self.needs_action_path.mkdir(parents=True, exist_ok=True)

    def generate(self, item_data: Dict[str, Any]) -> Path:
        """Generate markdown action file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        item_type = item_data.get("type", "item")
        
        if item_data.get("matched_keywords"):
            keyword_slug = "_".join(item_data["matched_keywords"][:2])
        else:
            keyword_slug = "review"
        
        filename = f"{MD_FILE_PREFIX}_{item_type.upper()}_{keyword_slug}_{timestamp}.md"
        filepath = self.needs_action_path / filename

        content = self._build_markdown_content(item_data)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"[ACTION] Created: {filepath}")
        return filepath

    def _build_markdown_content(self, item: Dict[str, Any]) -> str:
        """Build markdown content."""
        item_type = item.get("type", "unknown")
        subtype = item.get("subtype", "")
        sender = item.get("sender", "Unknown").replace("|", "\\|")
        content = item.get("content", "").replace("|", "\\|")
        preview = item.get("preview", "").replace("|", "\\|")
        timestamp = item.get("timestamp", datetime.now().isoformat())
        matched_keywords = item.get("matched_keywords", [])
        has_keyword = item.get("has_keyword", False)
        url = item.get("url", LINKEDIN_URL)

        priority = "high" if has_keyword else "medium"
        
        tags = ["linkedin", item_type]
        if has_keyword:
            tags.extend(matched_keywords)
        if subtype:
            tags.append(subtype)

        tags_yaml = "\n".join([f"  - {tag}" for tag in tags])
        emoji = "[Business]" if item_type in ["notification", "feed_post"] else "[Message]"
        item_label = "Notification" if item_type == "notification" else ("Feed Post" if item_type == "feed_post" else "Message")

        return f"""---
type: linkedin_{item_type}_action
priority: {priority}
source: linkedin
sender: "{sender}"
received: {timestamp}
status: pending
created: {datetime.now().isoformat()}
has_keywords: {str(has_keyword).lower()}
matched_keywords: {matched_keywords if matched_keywords else '[]'}
tags:
{tags_yaml}
---

# {emoji} LinkedIn {item_label} Action Required

## Item Details

| Field | Value |
|-------|-------|
| **Type** | {item_type.title()}{' - ' + subtype.title() if subtype else ''} |
| **From** | {sender if sender else '*Unknown*'} |
| **Received** | {timestamp} |
| **Keywords Matched** | {', '.join(matched_keywords) if matched_keywords else 'None'} |

---

## Content

{content if content else (preview if preview else '*No content available*')}

---

## Suggested Actions

- [ ] **Review** - Read and assess the content
- [ ] **Engage** - Like, comment, or respond
- [ ] **Connect** - Send connection request if relevant
- [ ] **Share** - Share with your network
- [ ] **Save** - Save for later reference
- [ ] **Ignore** - No action needed

---

## Notes

_Add any additional context or notes here_

---

## Quick Links

- [Open in LinkedIn]({url})

---
## Keyword Alert

**This item contains:** {', '.join(matched_keywords) if matched_keywords else 'No specific keywords'}

---
*Generated by LinkedIn Watcher | Personal AI Employee*
"""


# =============================================================================
# Main LinkedIn Watcher Class
# =============================================================================

class LinkedInWatcher(BaseWatcher):
    """
    LinkedIn Watcher with improved stability.
    """

    def __init__(
        self,
        needs_action_path: str,
        session_path: str = str(SESSION_PATH),
        check_interval: int = CHECK_INTERVAL_SECONDS,
        email: Optional[str] = None,
        password: Optional[str] = None
    ):
        super().__init__("LinkedIn", needs_action_path)
        self.session_path = session_path
        self._check_interval = check_interval
        self._email = email or os.getenv("LINKEDIN_EMAIL")
        self._password = password or os.getenv("LINKEDIN_PASSWORD")
        self._consecutive_errors = 0
        self._max_errors_before_restart = 5

        self._authenticator: Optional[LinkedInAuthenticator] = None
        self._context: Optional[BrowserContext] = None
        self._processor: Optional[LinkedInDataProcessor] = None
        self._action_generator: Optional[ActionFileGenerator] = None

    def _initialize_components(self) -> bool:
        """Initialize components."""
        if self._context and self._authenticator and self._authenticator.is_logged_in():
            return True

        if not PLAYWRIGHT_AVAILABLE:
            print("[ERROR] Playwright not installed")
            return False

        self._authenticator = LinkedInAuthenticator(self.session_path)
        self._context = self._authenticator.start_browser()
        
        if not self._context:
            return False

        self._authenticator.navigate_to_linkedin()

        if not self._authenticator.is_logged_in():
            if self._email and self._password:
                print("[AUTH] Attempting auto-login...")
                if not self._authenticator.login(self._email, self._password):
                    print("[ERROR] Auto-login failed")
                    return False
            else:
                print("[AUTH] Please login manually")
                if not self._authenticator.wait_for_manual_login(120):
                    return False

        self._processor = LinkedInDataProcessor(self._context)
        self._action_generator = ActionFileGenerator(self.needs_action_path)
        
        print("[INIT] LinkedIn Watcher initialized")
        return True

    def check_for_events(self) -> List[Dict[str, Any]]:
        """Check for LinkedIn content with keywords."""
        try:
            if not self._initialize_components():
                self._consecutive_errors += 1
                if self._consecutive_errors >= self._max_errors_before_restart:
                    self._restart_browser()
                return []

            self._consecutive_errors = 0

            print(f"\n[CHECK] Scanning LinkedIn for: {WATCH_KEYWORDS}")
            
            all_items = []

            # Try notifications (may skip if failing)
            print("[CHECK] Fetching notifications...")
            notifications = self._processor.fetch_notifications()
            keyword_notifications = [n for n in notifications if n.get("has_keyword")]
            if keyword_notifications:
                print(f"[CHECK] Found {len(keyword_notifications)} notifications with keywords")
                all_items.extend(keyword_notifications)

            # Try messages (may skip if failing)
            print("[CHECK] Fetching messages...")
            messages = self._processor.fetch_messages()
            keyword_messages = [m for m in messages if n.get("has_keyword")]
            if keyword_messages:
                print(f"[CHECK] Found {len(keyword_messages)} messages with keywords")
                all_items.extend(keyword_messages)

            # Feed content (more reliable)
            print("[CHECK] Scanning feed content...")
            feed_items = self._processor.fetch_feed_content()
            if feed_items:
                print(f"[CHECK] Found {len(feed_items)} feed posts with keywords")
                all_items.extend(feed_items)

            if not all_items:
                print("[CHECK] No items with keywords found")

            return all_items

        except Exception as e:
            print(f"[ERROR] check_for_events failed: {e}")
            traceback.print_exc()
            self._consecutive_errors += 1
            return []

    def _restart_browser(self):
        """Restart browser on errors."""
        print("[INFO] Restarting browser...")
        try:
            if self._authenticator:
                self._authenticator.close()
                self._authenticator = None
                self._context = None
                self._processor = None
            
            time.sleep(2)
            
            if self._initialize_components():
                print("[SUCCESS] Browser restarted")
            else:
                print("[ERROR] Failed to restart")
        except Exception as e:
            print(f"[ERROR] Browser restart failed: {e}")
            traceback.print_exc()

    def generate_markdown_content(self, event_data: Dict[str, Any]) -> str:
        """Generate markdown content."""
        if not self._action_generator:
            self._action_generator = ActionFileGenerator(self.needs_action_path)
        return self._action_generator._build_markdown_content(event_data)

    def process_item(self, item_data: Dict[str, Any]) -> Optional[Path]:
        """Process item: create action file."""
        if not self._action_generator:
            self._action_generator = ActionFileGenerator(self.needs_action_path)
        return self._action_generator.generate(item_data)

    def check_for_events_and_process(self) -> List[Path]:
        """Check and process items."""
        items = self.check_for_events()
        action_files = []

        for item in items:
            action_file = self.process_item(item)
            if action_file:
                action_files.append(action_file)

        return action_files

    def get_check_interval(self) -> int:
        """Return check interval."""
        return self._check_interval

    def stop_monitoring(self):
        """Stop monitoring."""
        self.running = False
        if self._authenticator:
            self._authenticator.close()
        print(f"[STOP] {self.name} watcher stopped")


# =============================================================================
# CLI Entry Point
# =============================================================================

def run_watcher(
    needs_action_path: str = "./Needs_Action",
    session_path: str = str(SESSION_PATH),
    interval: int = CHECK_INTERVAL_SECONDS,
    email: Optional[str] = None,
    password: Optional[str] = None,
    single_run: bool = False
):
    """Run the LinkedIn Watcher."""
    watcher = LinkedInWatcher(
        needs_action_path=needs_action_path,
        session_path=session_path,
        check_interval=interval,
        email=email,
        password=password
    )

    if single_run:
        print("[MODE] Single run mode")
        action_files = watcher.check_for_events_and_process()
        print(f"[COMPLETE] Processed {len(action_files)} item(s)")
        watcher.stop_monitoring()
        return action_files

    print(f"[START] LinkedIn Watcher starting (interval: {interval}s)")
    print(f"[KEYWORDS] Watching for: {WATCH_KEYWORDS}")
    try:
        watcher.start_monitoring()
    finally:
        watcher.stop_monitoring()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="LinkedIn Watcher")
    parser.add_argument("--needs-action", default="./Needs_Action")
    parser.add_argument("--session", default=str(SESSION_PATH))
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL_SECONDS)
    parser.add_argument("--email", default=os.getenv("LINKEDIN_EMAIL"))
    parser.add_argument("--password", default=os.getenv("LINKEDIN_PASSWORD"))
    parser.add_argument("--single-run", action="store_true")

    args = parser.parse_args()

    run_watcher(
        needs_action_path=args.needs_action,
        session_path=args.session,
        interval=args.interval,
        email=args.email,
        password=args.password,
        single_run=args.single_run
    )


if __name__ == "__main__":
    main()
