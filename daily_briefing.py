#!/usr/bin/env python3
"""
Daily Briefing Generator

Runs Claude to generate a daily briefing (e.g., Monday Morning CEO Briefing)
using Business_Goals.md and recent Done files.

Usage:
    python daily_briefing.py [--day monday|tuesday|...] [--output PATH]
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Try to import Anthropic for Claude
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# =============================================================================
# Configuration
# =============================================================================

PROJECT_ROOT = Path(__file__).parent
BUSINESS_GOALS_PATH = PROJECT_ROOT / "Business_Goals.md"
DONE_PATH = PROJECT_ROOT / "Done"
LOGS_PATH = PROJECT_ROOT / "Logs"
OUTPUT_PATH = PROJECT_ROOT / "Briefings"

# Ensure output directory exists
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

# Days of week for briefing types
BRIEFING_TYPES = {
    "monday": "Monday Morning CEO Briefing",
    "tuesday": "Tuesday Progress Update",
    "wednesday": "Wednesday Mid-Week Check-in",
    "thursday": "Thursday Strategy Review",
    "friday": "Friday Wrap-up & Week Review",
    "saturday": "Saturday Quiet Day Summary",
    "sunday": "Sunday Week Preview",
}


# =============================================================================
# Data Collectors
# =============================================================================

class DataCollector:
    """Collects data for briefing generation."""

    def __init__(self, project_root: Path = PROJECT_ROOT):
        self.project_root = project_root
        self.done_path = project_root / "Done"
        self.logs_path = project_root / "Logs"
        self.business_goals_path = project_root / "Business_Goals.md"

    def get_business_goals(self) -> str:
        """Read business goals file."""
        if not self.business_goals_path.exists():
            return "# Business Goals\n\n*No business goals file found.*"

        with open(self.business_goals_path, "r", encoding="utf-8") as f:
            return f.read()

    def get_recent_done_files(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent completed tasks from Done/ folder."""
        if not self.done_path.exists():
            return []

        done_files = []
        cutoff_date = datetime.now() - timedelta(days=days)

        for file_path in self.done_path.glob("*.md"):
            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime >= cutoff_date:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Extract key info
                    done_files.append({
                        "filename": file_path.name,
                        "completed_at": mtime.isoformat(),
                        "content": content[:2000],  # Limit content
                    })
            except Exception as e:
                print(f"Error reading {file_path.name}: {e}")

        # Sort by completion time (newest first)
        done_files.sort(key=lambda x: x["completed_at"], reverse=True)
        return done_files

    def get_activity_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get activity summary from logs."""
        summary = {
            "total_actions": 0,
            "executions": 0,
            "errors": 0,
            "approvals": 0,
        }

        if not self.logs_path.exists():
            return summary

        cutoff_date = datetime.now() - timedelta(days=days)

        for log_file in self.logs_path.glob("*.jsonl"):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            timestamp = entry.get("timestamp", "")
                            if timestamp:
                                entry_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                                if entry_date.replace(tzinfo=None) >= cutoff_date:
                                    summary["total_actions"] += 1

                                    activity_type = entry.get("activity_type", "")
                                    if "executed" in activity_type:
                                        summary["executions"] += 1
                                    elif "error" in activity_type:
                                        summary["errors"] += 1
                                    elif "approval" in activity_type:
                                        summary["approvals"] += 1
                        except (json.JSONDecodeError, ValueError):
                            continue
            except Exception as e:
                print(f"Error reading log {log_file.name}: {e}")

        return summary

    def get_pending_items(self) -> List[str]:
        """Get list of pending items from Pending_Approval/."""
        pending_path = self.project_root / "Pending_Approval"
        if not pending_path.exists():
            return []

        return [f.name for f in pending_path.glob("*.md")]

    def get_needs_action_items(self) -> List[str]:
        """Get list of items needing action."""
        needs_action_path = self.project_root / "Needs_Action"
        if not needs_action_path.exists():
            return []

        return [f.name for f in needs_action_path.glob("*.md")]


# =============================================================================
# Briefing Generator
# =============================================================================

class BriefingGenerator:
    """Generates daily briefings using Claude."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.collector = DataCollector()

        if ANTHROPIC_AVAILABLE and self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None

    def generate_briefing(
        self,
        day: str = "monday",
        include_goals: bool = True,
        include_done: bool = True,
        include_activity: bool = True,
        days_lookback: int = 7,
    ) -> str:
        """
        Generate a daily briefing.

        Args:
            day: Day of week for briefing type
            include_goals: Include business goals context
            include_done: Include recent completed tasks
            include_activity: Include activity summary
            days_lookback: Days of history to include

        Returns:
            Generated briefing text
        """
        # Collect data
        business_goals = self.collector.get_business_goals() if include_goals else ""
        done_files = self.collector.get_recent_done_files(days_lookback) if include_done else []
        activity_summary = self.collector.get_activity_summary(days_lookback) if include_activity else {}
        pending_items = self.collector.get_pending_items()
        needs_action = self.collector.get_needs_action_items()

        # Build prompt
        briefing_type = BRIEFING_TYPES.get(day.lower(), "Daily Briefing")
        prompt = self._build_prompt(
            briefing_type=briefing_type,
            business_goals=business_goals,
            done_files=done_files,
            activity_summary=activity_summary,
            pending_items=pending_items,
            needs_action=needs_action,
        )

        # Generate with Claude
        if self.client:
            briefing = self._generate_with_claude(prompt)
        else:
            briefing = self._generate_fallback(
                briefing_type, business_goals, done_files, activity_summary, pending_items, needs_action
            )

        return briefing

    def _build_prompt(
        self,
        briefing_type: str,
        business_goals: str,
        done_files: List[Dict],
        activity_summary: Dict,
        pending_items: List[str],
        needs_action: List[str],
    ) -> str:
        """Build the Claude prompt."""
        # Format done files
        done_section = ""
        if done_files:
            done_items = []
            for f in done_files[:10]:  # Limit to 10 most recent
                done_items.append(f"- **{f['filename']}** (completed: {f['completed_at'][:10]})")
            done_section = "\n".join(done_items)
        else:
            done_section = "*No completed tasks in the lookback period.*"

        # Format activity summary
        activity_section = f"""
- Total Actions: {activity_summary.get('total_actions', 0)}
- Executions: {activity_summary.get('executions', 0)}
- Errors: {activity_summary.get('errors', 0)}
- Approvals: {activity_summary.get('approvals', 0)}
"""

        # Format pending items
        pending_section = "\n".join([f"- {item}" for item in pending_items]) if pending_items else "*None*"

        # Format needs action
        needs_action_section = "\n".join([f"- {item}" for item in needs_action]) if needs_action else "*None*"

        prompt = f"""You are an executive assistant generating a {briefing_type} for the CEO.

## Context

Today is {datetime.now().strftime("%A, %B %d, %Y")}.

## Business Goals

{business_goals}

## Recently Completed (Done/)

{done_section}

## Activity Summary (Last 7 Days)

{activity_section}

## Pending Approval

{pending_section}

## Needs Action

{needs_action_section}

---

## Task

Generate a professional {briefing_type} that includes:

1. **Executive Summary** - 2-3 sentence overview of key highlights
2. **Accomplishments This Week** - Bullet list of completed work
3. **Business Goals Progress** - How recent work aligns with Q1/Q2 goals
4. **Pending Decisions** - Items requiring CEO attention
5. **Metrics & KPIs** - Key numbers from activity
6. **Priorities for Today** - Recommended focus areas
7. **Risks & Blockers** - Any concerns to address

Format as a professional markdown briefing document with clear sections.
Be concise but comprehensive. Use emoji sparingly for visual organization.
"""
        return prompt

    def _generate_with_claude(self, prompt: str) -> str:
        """Generate briefing using Claude API."""
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            return response.content[0].text
        except Exception as e:
            print(f"Claude API error: {e}")
            return self._generate_fallback_prompt(prompt)

    def _generate_fallback(self, briefing_type: str, business_goals: str,
                          done_files: List, activity_summary: Dict,
                          pending_items: List, needs_action: List) -> str:
        """Generate a basic briefing without Claude."""
        today = datetime.now().strftime("%A, %B %d, %Y")

        return f"""# {briefing_type}

**Generated:** {today}
**Note:** Claude API unavailable - basic briefing generated

---

## Executive Summary

This is a basic briefing generated without AI assistance. {len(done_files)} tasks were completed in the lookback period with {activity_summary.get('executions', 0)} executions recorded.

---

## Accomplishments This Week

""" + "\n".join([f"- {f['filename']}" for f in done_files[:10]]) + f"""

---

## Business Goals Alignment

Refer to Business_Goals.md for current objectives.

---

## Pending Decisions

""" + ("\n".join([f"- {item}" for item in pending_items]) if pending_items else "*None*") + f"""

---

## Metrics

- Actions: {activity_summary.get('total_actions', 0)}
- Executions: {activity_summary.get('executions', 0)}
- Errors: {activity_summary.get('errors', 0)}

---

## Needs Action

""" + ("\n".join([f"- {item}" for item in needs_action]) if needs_action else "*None*") + """

---

*Install anthropic package and set ANTHROPIC_API_KEY for AI-generated briefings.*
"""

    def _generate_fallback_prompt(self, prompt: str) -> str:
        """Fallback when Claude fails."""
        return f"""# Briefing Generation Error

The Claude API call failed. Please check:
1. ANTHROPIC_API_KEY environment variable is set
2. anthropic package is installed: `pip install anthropic`
3. Network connectivity

Prompt prepared with {len(prompt)} characters.
"""


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Daily Briefing Generator")
    parser.add_argument(
        "--day", "-d",
        default="monday",
        choices=list(BRIEFING_TYPES.keys()),
        help="Day of week for briefing type"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: Briefings/BRIEFING_YYYYMMDD.md)"
    )
    parser.add_argument(
        "--lookback", "-l",
        type=int,
        default=7,
        help="Days of history to include"
    )
    parser.add_argument(
        "--no-goals",
        action="store_true",
        help="Exclude business goals from briefing"
    )
    parser.add_argument(
        "--no-done",
        action="store_true",
        help="Exclude completed tasks from briefing"
    )
    parser.add_argument(
        "--print", "-p",
        action="store_true",
        help="Print briefing to stdout"
    )

    args = parser.parse_args()

    # Get API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[WARN] ANTHROPIC_API_KEY not set. Using fallback briefing.")

    # Generate briefing
    print(f"[BRIEFING] Generating {BRIEFING_TYPES[args.day]}...")

    generator = BriefingGenerator(api_key=api_key)
    briefing = generator.generate_briefing(
        day=args.day,
        include_goals=not args.no_goals,
        include_done=not args.no_done,
        days_lookback=args.lookback,
    )

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d")
        day = args.day.lower()
        output_path = OUTPUT_PATH / f"BRIEFING_{day}_{timestamp}.md"

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(briefing)

    print(f"[BRIEFING] Briefing saved to: {output_path}")

    # Print if requested
    if args.print:
        print("\n" + "=" * 60)
        print(briefing)
        print("=" * 60)

    return str(output_path)


if __name__ == "__main__":
    main()
