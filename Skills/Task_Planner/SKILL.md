---
name: Task_Planner
description: Core agent skill that monitors Needs_Action files and creates structured Plans/PLAN_*.md with checkboxes. Uses Ralph Wiggum loop pattern (promise TASK_COMPLETE) and follows Company_Handbook.md rules.
version: 1.0.0
author: Personal AI Employee
capabilities:
  - task_analysis
  - plan_generation
  - checklist_creation
  - status_tracking
  - ralph_wiggum_loop
tools_required:
  - None (core skill)
when_to_use:
  - Any Needs_Action file appears
  - New task requires planning
  - Task needs structured execution plan
  - Checklist-based workflow needed
when_not_to_use:
  - Immediate actions (no planning needed)
  - Emergency situations (use emergency protocol)
output_format:
  - Plans/PLAN_YYYYMMDD_HHMMSS.md (always)
  - Frontmatter with metadata
  - Checkbox-based task list
  - Status tracking
---

# Task Planner Skill

## Overview

This is the **core agent skill** that transforms Needs_Action files into structured, executable plans. It follows the Ralph Wiggum loop pattern and Company_Handbook.md rules.

## Ralph Wiggum Loop Pattern

```python
while not task_complete:
    analyze_task()
    create_plan()
    execute_steps()
    if all_steps_done:
        promise("TASK_COMPLETE")
```

**Key Principle:** Always promise `TASK_COMPLETE` when work is done.

## Workflow

### Step 1: Monitor Needs_Action

Watch for new `.md` files in `Needs_Action/`:
- Email notifications
- LinkedIn opportunities
- File drops
- User requests

### Step 2: Analyze Task

For each Needs_Action file:
1. Read frontmatter and content
2. Extract task type and priority
3. Identify required tools
4. Determine sensitivity level

### Step 3: Create Plan

Generate `Plans/PLAN_YYYYMMDD_HHMMSS.md` with:
- Frontmatter metadata
- Task checklist with checkboxes
- Execution steps
- Required tools
- Approval status

### Step 4: Track Status

Update plan status through flow:
```
PENDING → APPROVED → IN_PROGRESS → COMPLETED
```

### Step 5: Promise TASK_COMPLETE

When all checklist items are done:
- Mark status as COMPLETED
- Move to Done/
- Log completion
- Promise TASK_COMPLETE

## Plan Structure

```markdown
---
plan_id: PLAN_YYYYMMDD_HHMMSS
source: [source_file.md]
created: ISO_TIMESTAMP
status: PENDING
priority: high|medium|low
---

# Plan Title

## Source
- File: [filename]
- Created: [timestamp]
- Type: [task_type]

## Task Checklist
- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

## Execution Steps
1. Step one
2. Step two
3. Step three

## Required Tools
- [ ] email-mcp
- [ ] browser-mcp

## Approval
- [ ] Human approval required
- [ ] Auto-approved (non-sensitive)

## Status
- Status: PENDING
- Started: -
- Completed: -
```

## Company Handbook Rules

### Safety First
- Never execute without approval
- Always log activities
- Dry-run mode by default

### Transparency
- All plans in markdown
- Clear status tracking
- Full audit trail

### Reliability
- Promise TASK_COMPLETE
- Handle errors gracefully
- Retry on failures

### Efficiency
- Automate repetitive tasks
- Use appropriate tools
- Minimize human intervention

## Priority Levels

| Priority | Response Time | Approval |
|----------|---------------|----------|
| High | Immediate | Expedited |
| Medium | Within 1 hour | Standard |
| Low | Within 24 hours | Batch |

## Status Flow

```
┌─────────┐     ┌──────────┐     ┌────────────┐     ┌───────────┐
│ PENDING │ ──→ │ APPROVED │ ──→ │ IN_PROGRESS│ ──→ │ COMPLETED │
└─────────┘     └──────────┘     └────────────┘     └───────────┘
                    │
                    ↓
               ┌──────────┐
               │ REJECTED │
               └──────────┘
```

## File Naming

| Type | Pattern | Location |
|------|---------|----------|
| Plans | PLAN_YYYYMMDD_HHMMSS.md | Plans/ |
| Pending | [TYPE]_YYYYMMDD_HHMMSS.md | Pending_Approval/ |
| Approved | [TYPE]_YYYYMMDD_HHMMSS.md | Approved/ |
| Completed | [TYPE]_YYYYMMDD_HHMMSS.md | Done/ |
| Logs | activity_YYYYMMDD.jsonl | Logs/ |

## Quality Checklist

Before marking complete:
- [ ] All checklist items done
- [ ] Output verified
- [ ] Logs updated
- [ ] Files moved correctly
- [ ] Stakeholders notified

---

*Task Planner Skill v1.0 | Personal AI Employee*
