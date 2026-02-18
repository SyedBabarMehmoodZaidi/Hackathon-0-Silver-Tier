# Company Handbook

## Core Principles

### 1. Safety First
- Never execute actions without proper approval
- Always log activities
- Dry-run mode enabled by default
- Human-in-loop for sensitive operations

### 2. Transparency
- All plans documented in markdown
- Clear status tracking (PENDING → APPROVED → IN_PROGRESS → COMPLETED)
- Full audit trail in Logs/

### 3. Reliability
- Promise TASK_COMPLETE for every task
- Handle errors gracefully
- Retry on transient failures

### 4. Efficiency
- Automate repetitive tasks
- Use appropriate tools for each job
- Minimize human intervention for routine tasks

## Task Processing Rules

### Plan Structure (Required)
Every plan MUST have:
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

### Status Flow
```
PENDING → APPROVED → IN_PROGRESS → COMPLETED
                ↓
            REJECTED (with reason)
```

### Priority Levels
| Priority | Response Time | Approval |
|----------|---------------|----------|
| High | Immediate | Expedited |
| Medium | Within 1 hour | Standard |
| Low | Within 24 hours | Batch |

## Communication Guidelines

### Email
- Professional tone
- Clear subject lines
- Include call-to-action
- Sensitivity check required

### LinkedIn
- Professional business content
- Include hashtags (3-7)
- Include call-to-action
- Human approval for sensitive posts

## Security Rules

1. **No credentials in vault** - Use .env for secrets
2. **No sensitive data in logs** - Redact PII
3. **Approval required for:**
   - Financial transactions >$100
   - New external contacts
   - Confidential information
   - Legal/contract matters
   - HR-sensitive content

## Ralph Wiggum Loop Pattern

The agent follows a simple promise-based execution loop:

```
while task_not_complete:
    analyze_task()
    create_plan()
    execute_steps()
    if all_steps_done:
        promise("TASK_COMPLETE")
```

**Key Principle:** Always promise TASK_COMPLETE when work is done.

## File Naming Conventions

| Type | Pattern | Location |
|------|---------|----------|
| Plans | PLAN_YYYYMMDD_HHMMSS.md | Plans/ |
| Pending Approval | [TYPE]_YYYYMMDD_HHMMSS.md | Pending_Approval/ |
| Approved | [TYPE]_YYYYMMDD_HHMMSS.md | Approved/ |
| Completed | [TYPE]_YYYYMMDD_HHMMSS.md | Done/ |
| Logs | activity_YYYYMMDD.jsonl | Logs/ |

## Quality Standards

### Before Marking Complete
- [ ] All checklist items done
- [ ] Output verified
- [ ] Logs updated
- [ ] Files moved to correct location
- [ ] Stakeholders notified (if applicable)

### Documentation Requirements
- Clear, readable markdown
- Frontmatter with metadata
- Status clearly indicated
- Timestamps for all actions

---
*Company Handbook v1.0 | Personal AI Employee*
