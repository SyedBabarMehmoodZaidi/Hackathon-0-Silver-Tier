#!/usr/bin/env python3
"""
Test script to demonstrate the Personal AI Employee system
"""

import os
import time
from pathlib import Path
import shutil

def create_test_scenario():
    """Create a test scenario to demonstrate the system"""
    print("[TEST] Creating test scenario...")

    # Create a sample action file in Incoming_Files
    incoming_dir = Path("Incoming_Files")
    needs_action_dir = Path("Needs_Action")

    # Sample action request
    test_content = """# Urgent Task Request

## Priority
High

## Task Description
Please research the latest trends in AI development and prepare a summary document.

## Deadline
End of week

## Resources Needed
- Access to internet for research
- Word processing capabilities
- Email to send summary

## Expected Output
A 2-page summary document sent to boss@company.com
"""

    test_file = incoming_dir / "urgent_research_task.md"
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_content)

    print(f"[FILE] Created test file: {test_file}")
    print("[INFO] The system should detect this and create a plan...")

    # Wait a bit to allow the system to process
    time.sleep(2)

    # Show what files exist now
    print("\n[DIRS] Current files in system:")
    for dir_name in ["Needs_Action", "Vault/Daily", "Approved", "Done", "Logs"]:
        dir_path = Path(dir_name)
        if dir_path.exists():
            files = list(dir_path.glob("*.md")) + list(dir_path.glob("*.json*"))
            print(f"  {dir_name}: {len(files)} files")


def demonstrate_system_flow():
    """Demonstrate the complete system flow"""
    print("\n[FLOW] Demonstrating System Flow:")
    print("1. [IN] External Input (created test file)")
    print("2. [WATCH] Watcher (would detect the file)")
    print("3. [MOVE] Moved to Needs_Action (simulated)")
    print("4. [CLAUDE] Claude (would analyze and create plan)")
    print("5. [APPROVE] Approval (would be requested)")
    print("6. [MCP] MCP (would execute actions)")
    print("7. [DONE] Done (would move to done folder)")
    print("8. [LOG] Logs (would record all activities)")


if __name__ == "__main__":
    print("[START] Personal AI Employee - Test Scenario")
    print("=" * 50)

    create_test_scenario()
    demonstrate_system_flow()

    print("\n[TIP] To run the full system:")
    print("   python main.py --mode full")
    print("\n[INFO] Drop .md files into Incoming_Files to trigger the workflow")