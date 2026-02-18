---
name: Email_Sender
description: Sends professional emails via Gmail using email-mcp. Includes human-in-loop approval for sensitive emails (financial mentions >$100, new contacts, confidential content).
version: 1.0.0
author: Personal AI Employee
capabilities:
  - email_sending
  - email_drafting
  - contact_management
  - sensitivity_detection
  - human_approval_workflow
tools_required:
  - email-mcp (Gmail API)
  - browser-mcp (fallback for Gmail web)
when_to_use:
  - User wants to send professional emails via Gmail
  - User needs to respond to business inquiries
  - User wants to send follow-up emails
  - User needs to send notifications or updates
when_not_to_use:
  - Personal emails to family/friends (use personal Gmail)
  - Mass marketing emails (use dedicated email marketing tool)
  - Emails requiring legal review (route to Pending_Approval)
  - Emails with sensitive financial data (requires approval)
output_format:
  - Plan.md first (always)
  - Pending_Approval/EMAIL_*.md (if sensitive)
  - Direct send (if approved or non-sensitive)
sensitivity_thresholds:
  - financial_amount: $100 (any mention triggers approval)
  - new_contact: unknown email addresses trigger approval
  - confidential_keywords: confidential, NDA, proprietary, secret
---

# Email Sender Skill

## Overview

This skill sends professional emails via Gmail using email-mcp. It follows a structured workflow:
1. **Plan** - Create a Plan.md with email content and recipient analysis
2. **Sensitivity Check** - Detect financial mentions, new contacts, confidential content
3. **Review** - Human-in-loop approval for sensitive emails
4. **Execute** - Send email using email-mcp

## Instructions

### Core Principles

1. **Professional tone** - Maintain business-appropriate language
2. **Clear subject line** - Concise and informative (under 60 characters)
3. **Proper greeting/closing** - Use appropriate salutations
4. **Human-in-loop for sensitive content** - Route sensitive emails to Pending_Approval
5. **Verify recipients** - Double-check email addresses before sending

### Email Structure

Every professional email should include:

```
Subject: [Clear, specific subject]

Dear [Name],

[Opening] - Purpose of email

[Body] - Main content, details, context

[Call-to-Action] - What you want recipient to do

[Closing] - Professional sign-off

[Your Name]
[Your Title/Contact]
```

### Sensitivity Detection

**ALWAYS route to Pending_Approval if ANY of these are true:**

| Trigger | Pattern | Reason |
|---------|---------|--------|
| Financial >$100 | `\$[1-9]\d{2,}` | Large financial mentions |
| Financial >$100 | `\$[0-9]+ (?:hundred|thousand|million)` | Written amounts |
| New Contact | Email not in contacts | Unknown recipient |
| Confidential | `confidential|NDA|proprietary` | Sensitive information |
| Legal | `contract|agreement|legal|terms` | Legal implications |
| HR Sensitive | `salary|compensation|termination` | HR-related content |

### Subject Line Guidelines

- Keep under 60 characters
- Be specific and clear
- Avoid spam triggers (FREE, $$$$, !!!)
- Include context (Project name, reference)

**Good examples:**
- "Q1 Budget Review Meeting - March 15"
- "Follow-up: Product Demo Request"
- "Introduction: [Mutual Connection] Referral"

**Bad examples:**
- "Hello"
- "URGENT!!!"
- "Question"

## Workflow

### Step 1: Analyze Request

Understand what the user wants to send:
- Recipient(s) and relationship
- Purpose of email
- Any attachments or links
- Urgency level

### Step 2: Create Plan.md

Always create a Plan.md first with:

```markdown
# Email Plan

## Recipients
- To: [email]
- CC: [emails]
- BCC: [emails]

## Subject
[Subject line]

## Content
[Full email body]

## Sensitivity Check
- [ ] Financial amount >$100
- [ ] New contact (not in contacts)
- [ ] Confidential information
- [ ] Legal implications
- [ ] HR-sensitive content

## Approval Required
[Yes/No based on sensitivity check]
```

### Step 3: Sensitivity Check

**Automatic Approval Required triggers:**

1. **Financial mentions >$100**
   - `$500`, `$1,500`, `$10K`, etc.
   - "five hundred dollars", "ten thousand"
   - Budget, invoice, payment amounts

2. **New Contact Detection**
   - Email not in known contacts list
   - First-time correspondence
   - Cold outreach

3. **Confidential Keywords**
   - confidential, NDA, proprietary
   - trade secret, internal only
   - restricted, private

4. **Legal/Contract Terms**
   - contract, agreement, terms
   - legal, liability, indemnification

5. **HR-Sensitive Topics**
   - salary, compensation, bonus
   - termination, layoff, discipline

### Step 4: Human Approval (if required)

Wait for human to:
1. Review the Pending_Approval file
2. Approve, modify, or reject
3. Move to Approved/ folder

### Step 5: Execute Send

Use email-mcp to send:

```json
{
  "method": "email/send",
  "params": {
    "to": "recipient@example.com",
    "subject": "Email Subject",
    "body": "Email content...",
    "html": false,
    "cc": "optional@example.com"
  }
}
```

### Step 6: Confirm & Log

Create confirmation in Done/ folder with:
- Email content
- Recipients
- Timestamp
- Message ID

## Tool Usage

### email-mcp Commands

| Command | Purpose |
|---------|---------|
| `email/send` | Send an email |
| `email/draft` | Create draft (fallback) |
| `email/search` | Search sent emails |
| `email/read` | Read incoming emails |

### Example email-mcp Sequence

```json
{"method": "email/send", "params": {"to": "user@example.com", "subject": "Hello", "body": "Content"}}
```

### Browser Fallback

If email-mcp unavailable:
1. Use browser-mcp to navigate to Gmail
2. Compose email manually
3. Fill subject and body
4. Send

## File Structure

```
Skills/Email_Sender/
├── SKILL.md              # This file
├── Plan.md               # Current email plan
├── agent.py              # Agent implementation
└── templates/
    └── email_template.md # Email template

Pending_Approval/
└── EMAIL_*.md            # Emails awaiting approval

Approved/
└── EMAIL_*.md            # Approved emails

Done/
└── EMAIL_*.md            # Sent emails with confirmation
```

## Examples

### Example 1: Meeting Request (Non-sensitive)

**User:** "Email John about tomorrow's meeting"

**Plan.md:**
```markdown
# Email Plan

## Recipients
- To: john@company.com (known contact)

## Subject
Meeting Tomorrow at 2 PM - Conference Room A

## Content
Hi John,

Just confirming our meeting tomorrow at 2 PM in Conference Room A.

Please let me know if you need to reschedule.

Best regards,
[Name]

## Sensitivity Check
- [ ] Financial amount >$100 → No
- [ ] New contact → No (known contact)
- [ ] Confidential information → No
- [ ] Legal implications → No
- [ ] HR-sensitive content → No

## Approval Required: No
```

### Example 2: Invoice Email (Sensitive - Financial)

**User:** "Send invoice for $1,500 to client"

**Plan.md:**
```markdown
# Email Plan

## Sensitivity Check
- [x] Financial amount >$100 → $1,500 mentioned
- [ ] New contact → No
- [ ] Confidential information → No
- [ ] Legal implications → No
- [ ] HR-sensitive content → No

## Approval Required: YES
```

**Action:** Create `Pending_Approval/EMAIL_20250217_143022.md`

### Example 3: Cold Outreach (Sensitive - New Contact)

**User:** "Email potential client at newcompany.com"

**Plan.md:**
```markdown
# Email Plan

## Sensitivity Check
- [ ] Financial amount >$100 → No
- [x] New contact → First time contacting
- [ ] Confidential information → No
- [ ] Legal implications → No
- [ ] HR-sensitive content → No

## Approval Required: YES
```

**Action:** Create `Pending_Approval/EMAIL_20250217_143530.md`

## Quality Checklist

Before sending, verify:
- [ ] Professional tone maintained
- [ ] No spelling/grammar errors
- [ ] Subject line is clear (<60 chars)
- [ ] Recipients verified
- [ ] Attachments included (if mentioned)
- [ ] Sensitivity check completed
- [ ] Approval obtained if required
- [ ] CC/BCC appropriate

## Troubleshooting

| Issue | Solution |
|-------|----------|
| email-mcp unavailable | Use browser-mcp fallback |
| Gmail API auth failed | Re-authenticate with credentials.json |
| Recipient not found | Verify email address spelling |
| Send failed | Check Gmail quota limits |

## Related Skills

- **LinkedIn_Poster** - For social media updates
- **Calendar_Manager** - For meeting scheduling
- **Document_Writer** - For formal documents

---

*Email Sender Skill v1.0.0 | Personal AI Employee*
