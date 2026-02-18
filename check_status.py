#!/usr/bin/env python3
"""
System Status Checker

Checks the status of all watchers, APIs, and dependencies.
"""

import sys
import os
from pathlib import Path


def check(title: str, condition: bool, hint: str = ""):
    """Print check result."""
    status = "[OK]" if condition else "[  ]"
    print(f"  {status} {title}")
    if not condition and hint:
        print(f"       Hint: {hint}")
    return condition


def main():
    print("\n" + "=" * 60)
    print("Personal AI Employee - System Status")
    print("=" * 60 + "\n")

    project_root = Path(__file__).parent
    passed = 0
    total = 0

    # =============================================================================
    # Python Version
    # =============================================================================
    print("Python Environment")
    total += 1
    if check(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
             sys.version_info >= (3, 8)):
        passed += 1
    print()

    # =============================================================================
    # Core Dependencies
    # =============================================================================
    print("\nCore Dependencies")

    total += 1
    if check("watchdog", condition=True, hint="pip install watchdog"):
        try:
            import watchdog
            passed += 1
        except ImportError:
            check("watchdog", False, "pip install watchdog")

    total += 1
    try:
        import anthropic
        check("anthropic (Claude API)", True)
        passed += 1
    except ImportError:
        check("anthropic (Claude API)", False, "pip install anthropic")

    total += 1
    try:
        import playwright
        check("playwright", True)
        passed += 1
    except ImportError:
        check("playwright", False, "pip install playwright && playwright install")

    total += 1
    try:
        from google.oauth2 import credentials
        check("google-auth (Gmail API)", True)
        passed += 1
    except ImportError:
        check("google-auth (Gmail API)", False, "pip install google-auth google-auth-oauthlib")

    total += 1
    try:
        from whatsapp_api_client_python import API
        check("whatsapp-api-client (GreenAPI)", True)
        passed += 1
    except ImportError:
        check("whatsapp-api-client (GreenAPI)", False, "pip install whatsapp-api-client-python")

    print()

    # =============================================================================
    # Credentials Files
    # =============================================================================
    print("\nCredentials Files")

    total += 1
    if check("credentials.json (Google)",
             (project_root / "credentials.json").exists(),
             "Copy your Google OAuth credentials.json to project root"):
        passed += 1

    total += 1
    if check("token.json (Google OAuth)",
             (project_root / "token.json").exists(),
             "Run gmail_watcher.py to generate token.json"):
        passed += 1

    total += 1
    if check(".env file",
             (project_root / ".env").exists(),
             "Copy .env.example to .env and fill in credentials"):
        passed += 1

    print()

    # =============================================================================
    # Environment Variables
    # =============================================================================
    print("\nEnvironment Variables")

    total += 1
    if check("CLAUDE_API_KEY",
             os.getenv("CLAUDE_API_KEY") is not None,
             "Set CLAUDE_API_KEY in .env or environment"):
        passed += 1

    total += 1
    if check("WHATSAPP_ID_INSTANCE",
             os.getenv("WHATSAPP_ID_INSTANCE") is not None,
             "Set WHATSAPP_ID_INSTANCE in .env or environment"):
        passed += 1

    total += 1
    if check("WHATSAPP_API_TOKEN_INSTANCE",
             os.getenv("WHATSAPP_API_TOKEN_INSTANCE") is not None,
             "Set WHATSAPP_API_TOKEN_INSTANCE in .env or environment"):
        passed += 1

    total += 1
    if check("LINKEDIN_EMAIL",
             os.getenv("LINKEDIN_EMAIL") is not None,
             "Optional: Set for LinkedIn auto-login"):
        passed += 1

    print()

    # =============================================================================
    # Directory Structure
    # =============================================================================
    print("\nDirectory Structure")

    dirs = [
        "Needs_Action",
        "Approved",
        "Done",
        "Logs",
        "Plans",
        "Pending_Approval",
        "Incoming_Files",
        "Briefings",
    ]

    for dir_name in dirs:
        total += 1
        if check(dir_name, (project_root / dir_name).exists()):
            passed += 1

    print()

    # =============================================================================
    # Summary
    # =============================================================================
    print("=" * 60)
    percentage = (passed / total * 100) if total > 0 else 0

    if percentage >= 80:
        message = "Excellent! System is ready."
    elif percentage >= 50:
        message = "Partial setup. Some features unavailable."
    else:
        message = "Setup required. Many features unavailable."

    print(f"Status: {passed}/{total} checks passed ({percentage:.0f}%)")
    print(f"{message}")
    print("=" * 60 + "\n")

    return 0 if percentage >= 80 else 1


if __name__ == "__main__":
    sys.exit(main())
