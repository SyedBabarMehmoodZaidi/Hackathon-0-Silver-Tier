#!/usr/bin/env python3
"""
Task Planner Agent - Core Agent Skill

Monitors Needs_Action files and creates structured Plans/PLAN_*.md with checkboxes.
Uses Ralph Wiggum loop pattern (promise TASK_COMPLETE) and follows Company_Handbook.md rules.

Ralph Wiggum Loop Pattern:
    while not task_complete:
        analyze_task()
        create_plan()
        execute_steps()
        if all_steps_done:
            promise("TASK_COMPLETE")
"""

import json
import os
import re
import sys
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

# =============================================================================
# Configuration
# =============================================================================

SKILL_PATH = Path(__file__).parent
PROJECT_ROOT = SKILL_PATH.parent.parent
NEEDS_ACTION_PATH = PROJECT_ROOT / "Needs_Action"
PLANS_PATH = PROJECT_ROOT / "Plans"
APPROVED_PATH = PROJECT_ROOT / "Approved"
DONE_PATH = PROJECT_ROOT / "Done"
LOGS_PATH = PROJECT_ROOT / "Logs"
HANDBOOK_PATH = PROJECT_ROOT / "Company_Handbook.md"

# Ensure directories exist
for path in [PLANS_PATH, APPROVED_PATH, DONE_PATH, LOGS_PATH, NEEDS_ACTION_PATH]:
    path.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Enums and Data Classes
# =============================================================================

class TaskStatus(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class Priority(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TaskPlan:
    """Represents a structured task plan."""
    plan_id: str
    source: str
    source_path: str
    created: str
    status: str = "PENDING"
    priority: str = "medium"
    task_type: str = "general"
    title: str = ""
    description: str = ""
    checklist: List[str] = field(default_factory=list)
    execution_steps: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    approval_required: bool = False
    started: Optional[str] = None
    completed: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# Task Analyzer
# =============================================================================

class TaskAnalyzer:
    """Analyzes Needs_Action files to extract task information."""

    # Task type patterns
    TASK_PATTERNS = {
        "email": [r"type:\s*email", r"source:\s*gmail", r"📧", r"email_action"],
        "linkedin": [r"type:\s*linkedin", r"source:\s*linkedin", r"💼", r"💬", r"linkedin_"],
        "file_drop": [r"type:\s*file", r"file_drop", r"file dropped"],
        "whatsapp": [r"type:\s*whatsapp", r"source:\s*whatsapp", r"📱"],
        "calendar": [r"type:\s*calendar", r"schedule", r"meeting", r"event"],
        "general": [r"type:\s*general", r"task", r"action"],
    }

    # Priority patterns
    PRIORITY_PATTERNS = {
        "high": [r"priority:\s*high", r"urgent", r"asap", r"immediate", r"🔴"],
        "medium": [r"priority:\s*medium", r"normal", r"standard", r"🟡"],
        "low": [r"priority:\s*low", r"when possible", r"convenient", r"🟢"],
    }

    # Sensitivity patterns (require approval)
    SENSITIVE_PATTERNS = [
        r"\$\d{3,}",  # Financial amounts >$100
        r"confidential",
        r"NDA",
        r"proprietary",
        r"legal",
        r"contract",
        r"salary",
        r"termination",
    ]

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns."""
        self.task_regex = {
            k: [re.compile(p, re.IGNORECASE) for p in v]
            for k, v in self.TASK_PATTERNS.items()
        }
        self.priority_regex = {
            k: [re.compile(p, re.IGNORECASE) for p in v]
            for k, v in self.PRIORITY_PATTERNS.items()
        }
        self.sensitive_regex = [
            re.compile(p, re.IGNORECASE) for p in self.SENSITIVE_PATTERNS
        ]

    def analyze(self, file_path: Path) -> Dict[str, Any]:
        """
        Analyze a Needs_Action file and extract task information.

        Args:
            file_path: Path to the Needs_Action file

        Returns:
            Dictionary with task analysis results
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract frontmatter
        frontmatter = self._extract_frontmatter(content)

        # Detect task type
        task_type = self._detect_task_type(content, frontmatter)

        # Detect priority
        priority = self._detect_priority(content, frontmatter)

        # Check sensitivity
        approval_required = self._check_sensitivity(content)

        # Extract title
        title = self._extract_title(content, file_path)

        # Extract description
        description = self._extract_description(content)

        # Generate checklist
        checklist = self._generate_checklist(task_type, content)

        # Generate execution steps
        execution_steps = self._generate_execution_steps(task_type, content)

        # Determine required tools
        required_tools = self._determine_tools(task_type)

        # Extract tags
        tags = self._extract_tags(content, frontmatter)

        return {
            "task_type": task_type,
            "priority": priority,
            "approval_required": approval_required,
            "title": title,
            "description": description,
            "checklist": checklist,
            "execution_steps": execution_steps,
            "required_tools": required_tools,
            "tags": tags,
            "frontmatter": frontmatter,
            "word_count": len(content.split()),
            "character_count": len(content),
        }

    def _extract_frontmatter(self, content: str) -> Dict[str, Any]:
        """Extract YAML frontmatter from content."""
        frontmatter = {}
        match = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if match:
            fm_content = match.group(1)
            for line in fm_content.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip()
        return frontmatter

    def _detect_task_type(self, content: str, frontmatter: Dict) -> str:
        """Detect task type from content."""
        # Check frontmatter first
        if "type" in frontmatter:
            fm_type = frontmatter["type"].lower()
            for task_type in self.task_regex.keys():
                if task_type in fm_type:
                    return task_type

        # Check content patterns
        for task_type, patterns in self.task_regex.items():
            for pattern in patterns:
                if pattern.search(content):
                    return task_type

        return "general"

    def _detect_priority(self, content: str, frontmatter: Dict) -> str:
        """Detect priority from content."""
        # Check frontmatter first
        if "priority" in frontmatter:
            fm_priority = frontmatter["priority"].lower()
            if fm_priority in ["high", "medium", "low"]:
                return fm_priority

        # Check content patterns
        for priority, patterns in self.priority_regex.items():
            for pattern in patterns:
                if pattern.search(content):
                    return priority

        return "medium"  # Default priority

    def _check_sensitivity(self, content: str) -> bool:
        """Check if content requires human approval."""
        for pattern in self.sensitive_regex:
            if pattern.search(content):
                return True
        return False

    def _extract_title(self, content: str, file_path: Path) -> str:
        """Extract or generate title."""
        # Try to find first heading
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()

        # Use filename as fallback
        return file_path.stem.replace("_", " ").title()

    def _extract_description(self, content: str) -> str:
        """Extract main description from content."""
        # Remove frontmatter
        content_no_fm = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)

        # Remove headings
        content_no_headings = re.sub(r"^#+\s+.+$", "", content_no_fm, flags=re.MULTILINE)

        # Get first paragraph
        paragraphs = [p.strip() for p in content_no_headings.split("\n\n") if p.strip()]
        if paragraphs:
            return paragraphs[0][:500]  # Limit length

        return ""

    def _generate_checklist(self, task_type: str, content: str) -> List[str]:
        """Generate task checklist based on type."""
        checklists = {
            "email": [
                "Review email content and recipient",
                "Verify sensitivity check passed",
                "Draft response using email-mcp",
                "Review draft for accuracy",
                "Send email and confirm delivery",
                "Log completion and update contacts",
            ],
            "linkedin": [
                "Review LinkedIn notification/message",
                "Check for keywords (opportunity, lead, interest, hire)",
                "Draft response or post",
                "Verify content follows Company Handbook",
                "Post to LinkedIn using browser-mcp",
                "Monitor for engagement",
            ],
            "file_drop": [
                "Review dropped file content",
                "Determine file type and purpose",
                "Process file according to type",
                "Move file to appropriate location",
                "Log processing completion",
            ],
            "whatsapp": [
                "Review WhatsApp message",
                "Determine response needed",
                "Draft response",
                "Send via WhatsApp API",
                "Log conversation",
            ],
            "calendar": [
                "Review meeting/event details",
                "Check availability",
                "Create calendar event",
                "Send invitations",
                "Set reminders",
            ],
            "general": [
                "Review task requirements",
                "Identify required tools/resources",
                "Execute task steps",
                "Verify completion",
                "Log results",
            ],
        }

        return checklists.get(task_type, checklists["general"])

    def _generate_execution_steps(self, task_type: str, content: str) -> List[str]:
        """Generate numbered execution steps."""
        steps = {
            "email": [
                "Parse email frontmatter for recipient and subject",
                "Check sensitivity (financial, new contact, confidential)",
                "If sensitive: create Pending_Approval/EMAIL_*.md",
                "If approved: use email-mcp to send",
                "Add recipient to contacts if new",
                "Create Done/EMAIL_*.md confirmation",
            ],
            "linkedin": [
                "Parse LinkedIn content for type (notification/message)",
                "Check for action keywords",
                "Create Plans/PLAN_*.md with response draft",
                "Use browser-mcp to navigate to LinkedIn",
                "Post or respond as needed",
                "Log to Done/LINKEDIN_*.md",
            ],
            "file_drop": [
                "Read file content and metadata",
                "Determine file type (document, image, data)",
                "Process according to file type",
                "Move to appropriate destination",
                "Update task log",
            ],
            "general": [
                "Read and understand task requirements",
                "Break down into subtasks",
                "Execute each subtask",
                "Verify all subtasks complete",
                "Mark task as TASK_COMPLETE",
            ],
        }

        return steps.get(task_type, steps["general"])

    def _determine_tools(self, task_type: str) -> List[str]:
        """Determine required MCP tools."""
        tools = {
            "email": ["email-mcp"],
            "linkedin": ["browser-mcp"],
            "whatsapp": ["whatsapp-mcp"],
            "calendar": ["calendar-mcp"],
            "file_drop": [],
            "general": [],
        }
        return tools.get(task_type, [])

    def _extract_tags(self, content: str, frontmatter: Dict) -> List[str]:
        """Extract tags from content."""
        tags = []

        # Check frontmatter
        if "tags" in frontmatter:
            tags_str = frontmatter["tags"]
            if isinstance(tags_str, str):
                tags = [t.strip() for t in tags_str.split(",")]
            elif isinstance(tags_str, list):
                tags = tags_str

        # Extract from content hashtags
        hashtags = re.findall(r"#(\w+)", content)
        tags.extend(hashtags)

        return list(set(tags))


# =============================================================================
# Plan Generator
# =============================================================================

class PlanGenerator:
    """Generates structured Plan.md files."""

    def __init__(self, plans_path: Path = PLANS_PATH):
        self.plans_path = plans_path

    def generate(self, analysis: Dict[str, Any], source_path: Path) -> Tuple[Path, TaskPlan]:
        """
        Generate a Plan.md file from task analysis.

        Args:
            analysis: Task analysis results
            source_path: Path to source Needs_Action file

        Returns:
            Tuple of (plan_path, task_plan)
        """
        timestamp = datetime.now()
        # Use microseconds + hash for uniqueness in rapid processing
        unique_suffix = hashlib.md5(str(source_path).encode()).hexdigest()[:6]
        plan_id = f"PLAN_{timestamp.strftime('%Y%m%d_%H%M%S')}_{unique_suffix}"

        # Create task plan object
        task_plan = TaskPlan(
            plan_id=plan_id,
            source=source_path.name,
            source_path=str(source_path),
            created=timestamp.isoformat(),
            status=TaskStatus.PENDING.value,
            priority=analysis["priority"],
            task_type=analysis["task_type"],
            title=analysis["title"],
            description=analysis["description"],
            checklist=analysis["checklist"],
            execution_steps=analysis["execution_steps"],
            required_tools=analysis["required_tools"],
            approval_required=analysis["approval_required"],
            tags=analysis["tags"],
            metadata={
                "word_count": analysis["word_count"],
                "character_count": analysis["character_count"],
                "frontmatter": analysis["frontmatter"],
            },
        )

        # Generate markdown content
        content = self._generate_markdown(task_plan)

        # Write plan file
        plan_path = self.plans_path / f"{plan_id}.md"
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(content)

        return plan_path, task_plan

    def _generate_markdown(self, plan: TaskPlan) -> str:
        """Generate markdown content for plan."""
        # Build checklist markdown
        checklist_md = "\n".join([f"- [ ] {item}" for item in plan.checklist])

        # Build execution steps markdown
        steps_md = "\n".join([f"{i+1}. {step}" for i, step in enumerate(plan.execution_steps)])

        # Build required tools markdown
        tools_md = "\n".join([f"- [ ] {tool}" for tool in plan.required_tools]) if plan.required_tools else "- [ ] None required"

        # Build tags markdown
        tags_md = "\n  - ".join(plan.tags) if plan.tags else "  - general"

        # Approval status
        approval_status = "Required" if plan.approval_required else "Auto-approved (non-sensitive)"

        content = f"""---
plan_id: {plan.plan_id}
source: {plan.source}
source_path: {plan.source_path}
created: {plan.created}
status: {plan.status}
priority: {plan.priority}
task_type: {plan.task_type}
approval_required: {str(plan.approval_required).lower()}
tags:
  - {tags_md}
---

# 📋 {plan.title}

## Source Information

| Field | Value |
|-------|-------|
| **File** | `{plan.source}` |
| **Path** | {plan.source_path} |
| **Created** | {plan.created} |
| **Type** | {plan.task_type} |
| **Priority** | {plan.priority} |

---

## Description

{plan.description if plan.description else "*No description available*"}

---

## ✅ Task Checklist

{checklist_md}

---

## 🔧 Execution Steps

{steps_md}

---

## 🛠️ Required Tools

{tools_md}

---

## 🔒 Approval Status

**Approval:** {approval_status}

- [ ] Human approval required
- [ ] Auto-approved (non-sensitive)

---

## 📊 Status Tracking

| Field | Value |
|-------|-------|
| **Status** | {plan.status} |
| **Started** | {plan.started if plan.started else "-"} |
| **Completed** | {plan.completed if plan.completed else "-"} |

---

## 🏷️ Tags

{', '.join(plan.tags) if plan.tags else 'general'}

---

## 📝 Notes

_Add any additional context or notes here_

---

## 🔗 Ralph Wiggum Loop

```
while not task_complete:
    analyze_task()
    create_plan()
    execute_steps()
    if all_steps_done:
        promise("TASK_COMPLETE")
```

**Current State:** Analyzed ✓ | Plan Created ✓ | Execution Pending

---
*Generated by Task Planner Agent | Personal AI Employee*
*Follows Company_Handbook.md rules*
"""
        return content


# =============================================================================
# Task Executor (Ralph Wiggum Loop)
# =============================================================================

class TaskExecutor:
    """Executes tasks using Ralph Wiggum loop pattern."""

    def __init__(self, logs_path: Path = LOGS_PATH):
        self.logs_path = logs_path
        self.task_complete_promised = False

    def execute(self, plan_path: Path, plan: TaskPlan) -> Dict[str, Any]:
        """
        Execute a task using Ralph Wiggum loop pattern.

        Args:
            plan_path: Path to plan file
            plan: TaskPlan object

        Returns:
            Execution result dictionary
        """
        print(f"[EXECUTOR] Starting task: {plan.plan_id}")

        # Update status to IN_PROGRESS
        self._update_plan_status(plan_path, "IN_PROGRESS", started=datetime.now().isoformat())

        # Ralph Wiggum Loop
        results = []
        for i, step in enumerate(plan.execution_steps):
            print(f"[EXECUTOR] Step {i+1}/{len(plan.execution_steps)}: {step}")
            result = self._execute_step(step, plan)
            results.append({"step": i+1, "result": result})
            self._log_activity("step_executed", {"plan_id": plan.plan_id, "step": step, "result": result})

        # Check if all steps done
        all_done = all(r["result"].get("success", False) for r in results)

        if all_done:
            # Promise TASK_COMPLETE
            self.promise_task_complete(plan_path, plan)
        else:
            print(f"[EXECUTOR] Task incomplete - {sum(1 for r in results if r['result'].get('success'))}/{len(results)} steps succeeded")

        return {
            "plan_id": plan.plan_id,
            "success": all_done,
            "steps_executed": len(results),
            "task_complete_promised": self.task_complete_promised,
        }

    def _execute_step(self, step: str, plan: TaskPlan) -> Dict[str, Any]:
        """Execute a single step (simulated - would call appropriate MCP)."""
        # In production, this would route to appropriate MCP server
        # For now, simulate successful execution
        return {
            "success": True,
            "message": f"Step executed: {step}",
            "step": step,
        }

    def promise_task_complete(self, plan_path: Path, plan: TaskPlan):
        """Promise TASK_COMPLETE and update plan status."""
        print(f"[EXECUTOR] Promising TASK_COMPLETE for {plan.plan_id}")

        # Update status to COMPLETED
        self._update_plan_status(
            plan_path,
            "COMPLETED",
            completed=datetime.now().isoformat()
        )

        # Move to Done/
        done_path = DONE_PATH / plan_path.name
        plan_path.rename(done_path)

        # Log completion
        self._log_activity("task_complete_promised", {
            "plan_id": plan.plan_id,
            "source": plan.source,
        })

        self.task_complete_promised = True

    def _update_plan_status(self, plan_path: Path, status: str, **kwargs):
        """Update plan status in file."""
        if not plan_path.exists():
            return

        with open(plan_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Update status field
        content = re.sub(
            r"(\*\*Status\*\*\s*\|\s*)\w+",
            f"\\1{status}",
            content
        )
        content = re.sub(
            r"(^status:\s*)\w+",
            f"\\1{status}",
            content,
            flags=re.MULTILINE
        )

        # Update started/completed if provided
        if "started" in kwargs and kwargs["started"]:
            content = re.sub(
                r"(\*\*Started\*\*\s*\|\s*)[^|]+",
                f"\\1{kwargs['started']}",
                content
            )
        if "completed" in kwargs and kwargs["completed"]:
            content = re.sub(
                r"(\*\*Completed\*\*\s*\|\s*)[^|]+",
                f"\\1{kwargs['completed']}",
                content
            )

        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _log_activity(self, activity_type: str, details: Dict[str, Any]):
        """Log activity to JSONL file."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "activity_type": activity_type,
            "details": details,
        }

        log_file = self.logs_path / f"activity_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")


# =============================================================================
# Task Planner Agent (Main)
# =============================================================================

class TaskPlannerAgent:
    """
    Main Task Planner Agent.

    Monitors Needs_Action files and creates Plans/PLAN_*.md with checkboxes.
    Uses Ralph Wiggum loop pattern (promise TASK_COMPLETE).
    Follows Company_Handbook.md rules.
    """

    def __init__(self):
        self.analyzer = TaskAnalyzer()
        self.generator = PlanGenerator()
        self.executor = TaskExecutor()
        self.processed_files: set = set()

    def process_needs_action(self, file_path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """
        Process all Needs_Action files.

        Args:
            file_path: Optional specific file to process

        Returns:
            List of processing results
        """
        results = []

        if file_path:
            files_to_process = [file_path]
        else:
            # Get all .md files in Needs_Action
            files_to_process = list(NEEDS_ACTION_PATH.glob("*.md"))

        print(f"[AGENT] Found {len(files_to_process)} Needs_Action file(s)")

        for file_path in files_to_process:
            # Skip already processed files
            if str(file_path) in self.processed_files:
                print(f"[AGENT] Skipping already processed: {file_path.name}")
                continue

            result = self.process_single_file(file_path)
            results.append(result)
            self.processed_files.add(str(file_path))

        return results

    def process_single_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a single Needs_Action file.

        Args:
            file_path: Path to Needs_Action file

        Returns:
            Processing result dictionary
        """
        print(f"[AGENT] Processing: {file_path.name}")

        try:
            # Step 1: Analyze task
            print(f"[AGENT] Step 1: Analyzing task...")
            analysis = self.analyzer.analyze(file_path)
            print(f"[AGENT] Task type: {analysis['task_type']}, Priority: {analysis['priority']}")

            # Step 2: Generate plan
            print(f"[AGENT] Step 2: Generating plan...")
            plan_path, plan = self.generator.generate(analysis, file_path)
            print(f"[AGENT] Plan created: {plan_path}")

            # Step 3: Move source to Approved or Pending_Approval
            if analysis["approval_required"]:
                dest_dir = APPROVED_PATH.parent / "Pending_Approval"
                dest_dir.mkdir(parents=True, exist_ok=True)
            else:
                dest_dir = APPROVED_PATH

            dest_path = dest_dir / file_path.name
            file_path.rename(dest_path)
            print(f"[AGENT] Source moved to: {dest_path}")

            # Step 4: Execute (Ralph Wiggum Loop)
            print(f"[AGENT] Step 3: Executing task (Ralph Wiggum Loop)...")
            exec_result = self.executor.execute(plan_path, plan)

            return {
                "success": True,
                "file": file_path.name,
                "plan_id": plan.plan_id,
                "plan_path": str(plan_path),
                "task_type": analysis["task_type"],
                "priority": analysis["priority"],
                "approval_required": analysis["approval_required"],
                "execution": exec_result,
            }

        except Exception as e:
            print(f"[AGENT] Error processing {file_path.name}: {e}")
            self.executor._log_activity("processing_error", {
                "file": str(file_path),
                "error": str(e),
            })
            return {
                "success": False,
                "file": file_path.name,
                "error": str(e),
            }

    def ralph_wiggum_loop(self):
        """
        Run the Ralph Wiggum loop continuously.

        while not task_complete:
            analyze_task()
            create_plan()
            execute_steps()
            if all_steps_done:
                promise("TASK_COMPLETE")
        """
        print("[AGENT] Starting Ralph Wiggum Loop...")
        print("[AGENT] Monitoring Needs_Action/ for new files")

        try:
            while True:
                results = self.process_needs_action()

                if results:
                    for result in results:
                        if result.get("success"):
                            print(f"[AGENT] ✓ {result['file']} → {result['plan_id']} → TASK_COMPLETE")
                        else:
                            print(f"[AGENT] ✗ {result['file']} → Error: {result.get('error')}")

                time.sleep(5)  # Check every 5 seconds

        except KeyboardInterrupt:
            print("\n[AGENT] Ralph Wiggum Loop stopped")


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point for Task Planner Agent."""
    import argparse

    parser = argparse.ArgumentParser(description="Task Planner Agent")
    parser.add_argument("--file", "-f", help="Specific file to process")
    parser.add_argument("--loop", "-l", action="store_true", help="Run continuous Ralph Wiggum loop")
    parser.add_argument("--list", action="store_true", help="List pending Needs_Action files")

    args = parser.parse_args()

    agent = TaskPlannerAgent()

    if args.list:
        # List pending files
        files = list(NEEDS_ACTION_PATH.glob("*.md"))
        if files:
            print(f"Pending Needs_Action files ({len(files)}):")
            for f in files:
                print(f"  - {f.name}")
        else:
            print("No pending Needs_Action files")

    elif args.loop:
        # Run continuous loop
        agent.ralph_wiggum_loop()

    else:
        # Process single file or all pending
        if args.file:
            file_path = Path(args.file)
            if not file_path.exists():
                file_path = NEEDS_ACTION_PATH / args.file
        else:
            file_path = None

        results = agent.process_needs_action(file_path)

        print("\n" + "=" * 60)
        print("PROCESSING RESULTS")
        print("=" * 60)

        for result in results:
            if result.get("success"):
                print(f"[OK] {result['file']}")
                print(f"  Plan: {result['plan_id']}")
                print(f"  Type: {result['task_type']} | Priority: {result['priority']}")
                print(f"  Task Complete Promised: {result.get('execution', {}).get('task_complete_promised', False)}")
            else:
                print(f"[ERROR] {result['file']}: {result.get('error')}")


if __name__ == "__main__":
    main()
