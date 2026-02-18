#!/usr/bin/env python3
"""
Browser MCP Server - Playwright-based browser automation

Provides capabilities for:
- Web scraping
- LinkedIn posting and interaction
- Form filling and submission
- Screenshot capture
"""

import asyncio
import json
import sys
from typing import Any, Dict, Optional
from pathlib import Path

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


# =============================================================================
# MCP Protocol Implementation
# =============================================================================

class BrowserMCPServer:
    """
    Browser MCP Server using Playwright for automation.
    
    Capabilities:
    - browser_navigate: Navigate to a URL
    - browser_screenshot: Take a screenshot
    - browser_click: Click an element
    - browser_fill: Fill a form field
    - browser_evaluate: Execute JavaScript
    - browser_scrape: Extract content from page
    - linkedin_post: Create a LinkedIn post
    - linkedin_login: Login to LinkedIn
    """

    def __init__(self, headless: bool = False, session_path: Optional[str] = None):
        self.headless = headless
        self.session_path = Path(session_path) if session_path else None
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def initialize(self):
        """Initialize Playwright and browser."""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install")
        
        self._playwright = await async_playwright().start()
        
        if self.session_path:
            # Persistent context for session persistence
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.session_path),
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        else:
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()

    async def shutdown(self):
        """Clean up resources."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    # ==========================================================================
    # Core Browser Capabilities
    # ==========================================================================

    async def browser_navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to a URL."""
        if not self._page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            await self._page.goto(url, wait_until="networkidle", timeout=30000)
            return {
                "success": True,
                "url": self._page.url,
                "title": await self._page.title()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_screenshot(self, path: str, full_page: bool = False) -> Dict[str, Any]:
        """Take a screenshot."""
        if not self._page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            await self._page.screenshot(path=path, full_page=full_page)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_click(self, selector: str) -> Dict[str, Any]:
        """Click an element."""
        if not self._page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            await self._page.click(selector, timeout=5000)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_fill(self, selector: str, value: str) -> Dict[str, Any]:
        """Fill a form field."""
        if not self._page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            await self._page.fill(selector, value, timeout=5000)
            return {"success": True, "selector": selector, "value": value}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_evaluate(self, script: str) -> Dict[str, Any]:
        """Execute JavaScript on the page."""
        if not self._page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            result = await self._page.evaluate(script)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_scrape(self, selector: str = "body") -> Dict[str, Any]:
        """Extract text content from page."""
        if not self._page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            content = await self._page.text_content(selector)
            return {"success": True, "content": content[:10000] if content else ""}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_hover(self, selector: str) -> Dict[str, Any]:
        """Hover over an element."""
        if not self._page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            await self._page.hover(selector, timeout=5000)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def browser_wait(self, selector: str, timeout: int = 5000) -> Dict[str, Any]:
        """Wait for an element to appear."""
        if not self._page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            await self._page.wait_for_selector(selector, timeout=timeout)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==========================================================================
    # LinkedIn Capabilities
    # ==========================================================================

    async def linkedin_login(self, email: str, password: str) -> Dict[str, Any]:
        """Login to LinkedIn."""
        if not self._page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            await self._page.goto("https://www.linkedin.com/login", wait_until="networkidle")
            
            # Check if already logged in
            if "feed" in self._page.url:
                return {"success": True, "message": "Already logged in", "url": self._page.url}
            
            # Fill credentials
            await self._page.fill("#username", email)
            await self._page.fill("#password", password)
            await self._page.click('button[type="submit"]')
            await self._page.wait_for_load_state("networkidle", timeout=30000)
            
            if "feed" in self._page.url or "linkedin.com" in self._page.url:
                return {"success": True, "message": "Login successful", "url": self._page.url}
            else:
                return {"success": False, "error": "Login failed - check credentials"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def linkedin_post(self, content: str, image_path: Optional[str] = None) -> Dict[str, Any]:
        """Create a LinkedIn post."""
        if not self._page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            # Navigate to LinkedIn homepage
            await self._page.goto("https://www.linkedin.com/feed", wait_until="networkidle")
            
            # Click on the post creation box
            await self._page.wait_for_selector('[data-id="gh-create-a-post"]', timeout=10000)
            await self._page.click('[data-id="gh-create-a-post"]')
            
            # Wait for the post dialog to appear
            await self._page.wait_for_selector('[contenteditable="true"]', timeout=5000)
            
            # Fill the post content
            await self._page.fill('[contenteditable="true"]', content)
            
            # Add image if provided
            if image_path:
                await self._page.click('button[aria-label*="Media"]')
                await self._page.wait_for_selector('input[type="file"]')
                file_input = await self._page.query_selector('input[type="file"]')
                await file_input.set_input_files(image_path)
            
            # Click Post button
            await self._page.click('button[aria-label*="Post"]')
            await self._page.wait_for_load_state("networkidle", timeout=10000)
            
            return {"success": True, "message": "Post published successfully"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def linkedin_check_notifications(self) -> Dict[str, Any]:
        """Check LinkedIn notifications."""
        if not self._page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            await self._page.goto("https://www.linkedin.com/notifications", wait_until="networkidle")
            
            # Extract notifications
            notifications = await self._page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('.notification-card, [data-id]');
                    return Array.from(cards.slice(0, 20)).map(card => ({
                        text: card.textContent.trim().substring(0, 500),
                        time: card.querySelector('time')?.textContent || 'unknown'
                    }));
                }
            """)
            
            return {"success": True, "notifications": notifications}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def linkedin_send_message(self, recipient_name: str, message: str) -> Dict[str, Any]:
        """Send a LinkedIn message."""
        if not self._page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            await self._page.goto("https://www.linkedin.com/messaging", wait_until="networkidle")
            
            # Click new message button
            await self._page.click('button[aria-label*="New message"]')
            
            # Search for recipient
            await self._page.fill('input[aria-label*="To"]', recipient_name)
            await self._page.wait_for_timeout(2000)
            await self._page.keyboard.press("Enter")
            
            # Type message
            await self._page.fill('[contenteditable="true"]', message)
            
            # Send
            await self._page.click('button[aria-label*="Send"]')
            await self._page.wait_for_load_state("networkidle", timeout=5000)
            
            return {"success": True, "message": "Message sent successfully"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}


# =============================================================================
# MCP Server Entry Point
# =============================================================================

async def handle_request(server: BrowserMCPServer, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP protocol requests."""
    
    handlers = {
        # Core browser
        "browser/navigate": lambda: server.browser_navigate(params.get("url", "")),
        "browser/screenshot": lambda: server.browser_screenshot(
            params.get("path", "screenshot.png"),
            params.get("full_page", False)
        ),
        "browser/click": lambda: server.browser_click(params.get("selector", "")),
        "browser/fill": lambda: server.browser_fill(
            params.get("selector", ""),
            params.get("value", "")
        ),
        "browser/evaluate": lambda: server.browser_evaluate(params.get("script", "")),
        "browser/scrape": lambda: server.browser_scrape(params.get("selector", "body")),
        "browser/hover": lambda: server.browser_hover(params.get("selector", "")),
        "browser/wait": lambda: server.browser_wait(
            params.get("selector", ""),
            params.get("timeout", 5000)
        ),
        # LinkedIn
        "linkedin/login": lambda: server.linkedin_login(
            params.get("email", ""),
            params.get("password", "")
        ),
        "linkedin/post": lambda: server.linkedin_post(
            params.get("content", ""),
            params.get("image_path")
        ),
        "linkedin/check_notifications": lambda: server.linkedin_check_notifications(),
        "linkedin/send_message": lambda: server.linkedin_send_message(
            params.get("recipient_name", ""),
            params.get("message", "")
        ),
    }
    
    if method not in handlers:
        return {"success": False, "error": f"Unknown method: {method}"}
    
    return await handlers[method]()


async def run_stdio_server():
    """Run MCP server using stdio transport."""
    server = BrowserMCPServer(
        headless=False,  # Set to False for interactive LinkedIn posting
        session_path="./sessions/browser"
    )
    
    await server.initialize()
    
    try:
        # Read requests from stdin
        for line in sys.stdin:
            try:
                request = json.loads(line.strip())
                method = request.get("method", "")
                params = request.get("params", {})
                request_id = request.get("id")
                
                result = await handle_request(server, method, params)
                
                # Send response to stdout
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
                
    finally:
        await server.shutdown()


def main():
    """Entry point for browser MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Browser MCP Server")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--session-path", default="./sessions/browser", help="Path for persistent session")
    
    args = parser.parse_args()
    
    server = BrowserMCPServer(
        headless=args.headless,
        session_path=args.session_path
    )
    
    asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()
