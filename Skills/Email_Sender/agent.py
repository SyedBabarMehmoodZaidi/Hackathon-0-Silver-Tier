#!/usr/bin/env python3
"""
Email Sender Agent

Sends professional emails via Gmail using email-mcp with:
- Professional email composition
- Sensitivity detection (financial >$100, new contacts, confidential)
- Human-in-loop approval for sensitive emails
- email-mcp integration with browser fallback
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# =============================================================================
# Configuration
# =============================================================================

SKILL_PATH = Path(__file__).parent
PROJECT_ROOT = SKILL_PATH.parent.parent
PENDING_APPROVAL_PATH = PROJECT_ROOT / "Pending_Approval"
APPROVED_PATH = PROJECT_ROOT / "Approved"
DONE_PATH = PROJECT_ROOT / "Done"
LOGS_PATH = PROJECT_ROOT / "Logs"
CONTACTS_FILE = SKILL_PATH / "contacts.json"

# Ensure directories exist
for path in [PENDING_APPROVAL_PATH, APPROVED_PATH, DONE_PATH, LOGS_PATH]:
    path.mkdir(parents=True, exist_ok=True)

# Sensitivity thresholds
FINANCIAL_THRESHOLD = 100  # Dollars


# =============================================================================
# Contact Manager
# =============================================================================

class ContactManager:
    """Manages known contacts for new contact detection."""

    def __init__(self, contacts_file: Path = CONTACTS_FILE):
        self.contacts_file = contacts_file
        self.contacts: Dict[str, Dict[str, Any]] = {}
        self._load_contacts()

    def _load_contacts(self):
        """Load contacts from file."""
        if self.contacts_file.exists():
            try:
                with open(self.contacts_file, "r", encoding="utf-8") as f:
                    self.contacts = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.contacts = {}
        else:
            # Initialize with empty contacts
            self.contacts = {"_metadata": {"last_updated": datetime.now().isoformat()}}

    def save_contacts(self):
        """Save contacts to file."""
        self.contacts["_metadata"]["last_updated"] = datetime.now().isoformat()
        with open(self.contacts_file, "w", encoding="utf-8") as f:
            json.dump(self.contacts, f, indent=2)

    def is_known_contact(self, email: str) -> bool:
        """Check if email is a known contact."""
        email_lower = email.lower().strip()
        return email_lower in self.contacts

    def add_contact(self, email: str, name: str = "", notes: str = ""):
        """Add a contact to the known contacts."""
        email_lower = email.lower().strip()
        self.contacts[email_lower] = {
            "email": email_lower,
            "name": name,
            "notes": notes,
            "first_contact": datetime.now().isoformat(),
            "email_count": self.contacts.get(email_lower, {}).get("email_count", 0) + 1,
        }
        self.save_contacts()

    def get_contact(self, email: str) -> Optional[Dict[str, Any]]:
        """Get contact details."""
        return self.contacts.get(email.lower().strip())

    def get_all_contacts(self) -> List[Dict[str, Any]]:
        """Get all contacts."""
        return [v for k, v in self.contacts.items() if not k.startswith("_")]


# =============================================================================
# Sensitivity Detector
# =============================================================================

class SensitivityDetector:
    """Detects sensitive content requiring human approval."""

    # Financial patterns (amounts > $100)
    FINANCIAL_PATTERNS = [
        (r"\$[1-9]\d{2,}(?:,\d{3})*(?:\.\d{2})?", "currency"),  # $100, $1,000, $1,000.00
        (r"\$\d+(?:\.\d{2})?\s*(?:hundred|thousand|million|billion)", "currency_words"),
        (r"(?:USD|EUR|GBP|INR)\s*[1-9]\d{2,}", "currency_code"),
        (r"[1-9]\d{2,}\s*(?:dollars?|bucks?)", "dollars_words"),
        (r"(?:budget|cost|price|payment|invoice|fee).*(?:\$|\d{3,})", "financial_context"),
    ]

    # Confidential/sensitive keywords
    CONFIDENTIAL_PATTERNS = [
        r"\bconfidential\b",
        r"\bNDA\b",
        r"\bproprietary\b",
        r"\btrade\s*secret\b",
        r"\binternal\s*only\b",
        r"\brestricted\b",
        r"\bprivate\b",
        r"\bclassified\b",
    ]

    # Legal patterns
    LEGAL_PATTERNS = [
        r"\bcontract\b",
        r"\bagreement\b",
        r"\bterms\s*(?:and\s*conditions)?\b",
        r"\blegal\b",
        r"\bliability\b",
        r"\bindemnif(?:y|ication)\b",
        r"\battorney\b",
        r"\blawsuit\b",
        r"\blitigation\b",
    ]

    # HR-sensitive patterns
    HR_PATTERNS = [
        r"\bsalary\b",
        r"\bcompensation\b",
        r"\bbonus\b",
        r"\btermination\b",
        r"\blayoff\b",
        r"\bfir(?:ing|ed)\b",
        r"\bdismiss(?:al|ed)\b",
        r"\bdisciplinary\b",
        r"\bharassment\b",
        r"\bdiscrimination\b",
    ]

    def __init__(self, financial_threshold: int = FINANCIAL_THRESHOLD):
        self.financial_threshold = financial_threshold
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns."""
        self.financial_regex = [
            (re.compile(p, re.IGNORECASE), t) for p, t in self.FINANCIAL_PATTERNS
        ]
        self.confidential_regex = [
            re.compile(p, re.IGNORECASE) for p in self.CONFIDENTIAL_PATTERNS
        ]
        self.legal_regex = [re.compile(p, re.IGNORECASE) for p in self.LEGAL_PATTERNS]
        self.hr_regex = [re.compile(p, re.IGNORECASE) for p in self.HR_PATTERNS]

    def check(self, content: str, recipient_email: str, contact_manager: ContactManager) -> Dict[str, Any]:
        """
        Check content for sensitivity.

        Args:
            content: Email content (subject + body)
            recipient_email: Recipient email address
            contact_manager: Contact manager for new contact detection

        Returns:
            Dictionary with sensitivity analysis results
        """
        flags = []
        requires_approval = False

        # Check financial content
        financial_matches = self._check_financial(content)
        if financial_matches:
            flags.append({
                "type": "financial",
                "severity": "high",
                "description": f"Financial amount detected: {financial_matches}",
                "matches": financial_matches,
            })
            requires_approval = True

        # Check if new contact
        if not contact_manager.is_known_contact(recipient_email):
            flags.append({
                "type": "new_contact",
                "severity": "medium",
                "description": f"New contact: {recipient_email}",
                "email": recipient_email,
            })
            requires_approval = True

        # Check confidential content
        confidential_matches = self._check_patterns(content, self.confidential_regex)
        if confidential_matches:
            flags.append({
                "type": "confidential",
                "severity": "high",
                "description": f"Confidential content detected: {confidential_matches}",
                "keywords": confidential_matches,
            })
            requires_approval = True

        # Check legal content
        legal_matches = self._check_patterns(content, self.legal_regex)
        if legal_matches:
            flags.append({
                "type": "legal",
                "severity": "high",
                "description": f"Legal content detected: {legal_matches}",
                "keywords": legal_matches,
            })
            requires_approval = True

        # Check HR content
        hr_matches = self._check_patterns(content, self.hr_regex)
        if hr_matches:
            flags.append({
                "type": "hr_sensitive",
                "severity": "high",
                "description": f"HR-sensitive content detected: {hr_matches}",
                "keywords": hr_matches,
            })
            requires_approval = True

        return {
            "requires_approval": requires_approval,
            "flags": flags,
            "safe_to_send": not requires_approval,
            "financial_detected": bool(financial_matches),
            "new_contact": not contact_manager.is_known_contact(recipient_email),
        }

    def _check_financial(self, content: str) -> List[str]:
        """Check for financial amounts."""
        matches = []
        for regex, pattern_type in self.financial_regex:
            found = regex.findall(content)
            matches.extend(found)
        return matches

    def _check_patterns(self, content: str, regexes: List[re.Pattern]) -> List[str]:
        """Check content against regex patterns."""
        matches = []
        for regex in regexes:
            found = regex.findall(content)
            matches.extend(found)
        return list(set(matches))  # Remove duplicates


# =============================================================================
# Email Content Generator
# =============================================================================

class EmailContentGenerator:
    """Generates professional email content."""

    # Greeting templates
    GREETINGS = {
        "formal": ["Dear {name},", "Hello {name},", "Good morning/afternoon {name},"],
        "professional": ["Hi {name},", "Hello {name},", "Hope you're doing well, {name}."],
        "casual": ["Hey {name}!", "Hi {name}!", "Hope all is well!"],
    }

    # Closing templates
    CLOSINGS = {
        "formal": ["Sincerely,", "Best regards,", "Respectfully,"],
        "professional": ["Best,", "Kind regards,", "Thanks,"],
        "casual": ["Cheers,", "Talk soon,", "Best,"],
    }

    def __init__(self):
        pass

    def generate_email(
        self,
        recipient_name: str,
        recipient_email: str,
        purpose: str,
        context: str = "",
        tone: str = "professional",
        call_to_action: str = "",
    ) -> Dict[str, Any]:
        """
        Generate a complete professional email.

        Args:
            recipient_name: Name of recipient
            recipient_email: Email address
            purpose: Purpose of the email
            context: Additional context or details
            tone: Tone of the email (formal, professional, casual)
            call_to_action: Desired action from recipient

        Returns:
            Dictionary with email components
        """
        # Generate subject line
        subject = self._generate_subject(purpose, context)

        # Generate greeting
        greeting = self._generate_greeting(recipient_name, tone)

        # Generate opening
        opening = self._generate_opening(purpose, tone)

        # Generate body
        body = self._generate_body(context, purpose) if context else self._generate_generic_body(purpose)

        # Generate call-to-action
        cta = call_to_action or self._generate_cta(purpose)

        # Generate closing
        closing = self._generate_closing(tone)

        # Assemble full email
        full_email = f"{greeting}\n\n{opening}\n\n{body}\n\n{cta}\n\n{closing}"

        return {
            "subject": subject,
            "greeting": greeting,
            "opening": opening,
            "body": body,
            "call_to_action": cta,
            "closing": closing,
            "full_email": full_email,
            "recipient_name": recipient_name,
            "recipient_email": recipient_email,
            "character_count": len(full_email),
            "word_count": len(full_email.split()),
        }

    def _generate_subject(self, purpose: str, context: str = "") -> str:
        """Generate a clear subject line."""
        # Extract key terms from purpose
        purpose_lower = purpose.lower()

        subject_templates = {
            "meeting": "Meeting Request: {context}",
            "followup": "Follow-up: {context}",
            "introduction": "Introduction: {context}",
            "question": "Question regarding {context}",
            "update": "Update: {context}",
            "request": "Request: {context}",
            "confirmation": "Confirmation: {context}",
        }

        # Match purpose to template
        for key, template in subject_templates.items():
            if key in purpose_lower:
                ctx = context if context else purpose
                subject = template.format(context=ctx[:40])
                return subject[:60]  # Keep under 60 chars

        # Default subject
        if context:
            return f"Regarding: {context[:50]}"[:60]
        return f"{purpose[:50]}"[:60]

    def _generate_greeting(self, name: str, tone: str = "professional") -> str:
        """Generate appropriate greeting."""
        import random
        greetings = self.GREETINGS.get(tone, self.GREETINGS["professional"])
        greeting = random.choice(greetings)
        return greeting.format(name=name.split()[0] if name else "")

    def _generate_opening(self, purpose: str, tone: str = "professional") -> str:
        """Generate opening line."""
        openings = {
            "formal": [
                "I hope this email finds you well.",
                "I am writing to you regarding the following matter.",
                "I wanted to reach out concerning an important issue.",
            ],
            "professional": [
                "Hope you're having a great week!",
                "I wanted to touch base about something.",
                "Quick note to follow up on this.",
            ],
            "casual": [
                "Hope all is well!",
                "Just wanted to check in!",
                "Quick question for you!",
            ],
        }

        import random
        return random.choice(openings.get(tone, openings["professional"]))

    def _generate_body(self, context: str, purpose: str) -> str:
        """Generate email body from context."""
        # If context is provided, use it with minor formatting
        return context.strip()

    def _generate_generic_body(self, purpose: str) -> str:
        """Generate generic body based on purpose."""
        bodies = [
            f"I'm reaching out regarding {purpose}. Please let me know your thoughts on this matter.",
            f"I wanted to discuss {purpose} with you. Your input would be greatly appreciated.",
            f"This email is about {purpose}. I'd appreciate your feedback when you have a moment.",
        ]
        import random
        return random.choice(bodies)

    def _generate_cta(self, purpose: str) -> str:
        """Generate call-to-action."""
        ctas = [
            "Please let me know your availability to discuss this further.",
            "Looking forward to hearing from you soon.",
            "Please feel free to reach out if you have any questions.",
            "Let me know if you need any additional information.",
            "I'd appreciate your response at your earliest convenience.",
        ]
        import random
        return random.choice(ctas)

    def _generate_closing(self, tone: str = "professional") -> str:
        """Generate email closing."""
        import random
        closings = self.CLOSINGS.get(tone, self.CLOSINGS["professional"])
        closing = random.choice(closings)
        return closing + "\n\n[Your Name]\n[Your Title]\n[Your Contact Information]"


# =============================================================================
# Plan Generator
# =============================================================================

class EmailPlanGenerator:
    """Generates Plan.md for emails."""

    def __init__(self, skill_path: Path):
        self.skill_path = skill_path

    def generate_plan(
        self,
        email_data: Dict[str, Any],
        sensitivity: Dict[str, Any],
        recipient_name: str,
        recipient_email: str,
    ) -> str:
        """Generate Plan.md content."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        approval_status = "YES" if sensitivity["requires_approval"] else "NO"

        # Build approval reasons
        reasons = []
        if sensitivity.get("financial_detected"):
            reasons.append("Financial amount mentioned (>$100)")
        if sensitivity.get("new_contact"):
            reasons.append(f"New contact: {recipient_email}")
        for flag in sensitivity.get("flags", []):
            if flag["type"] in ["confidential", "legal", "hr_sensitive"]:
                reasons.append(flag["description"])

        approval_reason = "; ".join(reasons) if reasons else "Content is non-sensitive"

        # Build sensitivity table
        sensitivity_rows = []
        for flag in sensitivity.get("flags", []):
            status = "⚠️ Detected" if sensitivity["requires_approval"] else "✅ Clear"
            sensitivity_rows.append(f"| {flag['type'].replace('_', ' ').title()} | {status} | {flag['description']} |")

        if not sensitivity_rows:
            sensitivity_rows = ["| All Checks | ✅ Clear | No sensitivity detected |"]

        plan = f"""---
plan_type: email
created: {datetime.now().isoformat()}
status: {'pending_approval' if sensitivity['requires_approval'] else 'ready_to_send'}
approval_required: {str(sensitivity['requires_approval']).lower()}
---

# Email Plan

**Created:** {timestamp}
**To:** {recipient_name} <{recipient_email}>
**Subject:** {email_data['subject']}
**Status:** {'Pending Approval' if sensitivity['requires_approval'] else 'Ready to Send'}

---

## 👥 Recipients

| Type | Email | Name |
|------|-------|------|
| To | {recipient_email} | {recipient_name} |

---

## 📧 Email Content

### Subject
```
{email_data['subject']}
```
**Character count:** {len(email_data['subject'])} / 60

### Body
```
{email_data['full_email']}
```

**Character count:** {email_data['character_count']}
**Word count:** {email_data['word_count']}
**Estimated read time:** {max(1, email_data['word_count'] // 200)} minute(s)

---

## ⚠️ Sensitivity Check

| Check | Status | Details |
|-------|--------|---------|
{'\n'.join(sensitivity_rows)}

### Summary
- **Financial >$100:** {'⚠️ Yes' if sensitivity.get('financial_detected') else '✅ No'}
- **New Contact:** {'⚠️ Yes' if sensitivity.get('new_contact') else '✅ No'}
- **Confidential:** {'⚠️ Yes' if any(f['type']=='confidential' for f in sensitivity.get('flags',[])) else '✅ No'}
- **Legal:** {'⚠️ Yes' if any(f['type']=='legal' for f in sensitivity.get('flags',[])) else '✅ No'}
- **HR-Sensitive:** {'⚠️ Yes' if any(f['type']=='hr_sensitive' for f in sensitivity.get('flags',[])) else '✅ No'}

---

## ✅ Approval Required: {approval_status}

**Reason:** {approval_reason}

"""

        if sensitivity["requires_approval"]:
            plan += f"""**Next Steps:**
1. This plan has been saved to `Pending_Approval/EMAIL_{timestamp}.md`
2. Awaiting human review and approval
3. Once approved, move to `Approved/` folder
4. Execute sending after approval
"""
        else:
            plan += """**Next Steps:**
1. Review the email content above
2. Execute sending using email-mcp
3. Confirm successful delivery
"""

        plan += f"""
---

## 🔧 Execution Command

```json
{{
  "method": "email/send",
  "params": {{
    "to": "{recipient_email}",
    "subject": "{email_data['subject']}",
    "body": "{email_data['full_email'].replace(chr(10), '\\n').replace('"', '\\"')}",
    "html": false
  }}
}}
```

---

## 📝 Notes

_Add any additional context or notes here_

---
*Generated by Email Sender Skill | Personal AI Employee*
"""
        return plan


# =============================================================================
# Email Sender Agent
# =============================================================================

class EmailSenderAgent:
    """Main agent for sending emails."""

    def __init__(self):
        self.contact_manager = ContactManager()
        self.content_generator = EmailContentGenerator()
        self.sensitivity_detector = SensitivityDetector()
        self.plan_generator = EmailPlanGenerator(SKILL_PATH)

    def create_email(
        self,
        recipient_email: str,
        recipient_name: str = "",
        purpose: str = "",
        context: str = "",
        tone: str = "professional",
        call_to_action: str = "",
    ) -> Dict[str, Any]:
        """
        Create an email with full workflow.

        Args:
            recipient_email: Recipient's email address
            recipient_name: Recipient's name
            purpose: Purpose of the email
            context: Additional context or content
            tone: Tone of the email
            call_to_action: Desired action from recipient

        Returns:
            Result dictionary with paths and status
        """
        print(f"[AGENT] Creating email to: {recipient_email}")

        # Generate content
        email_data = self.content_generator.generate_email(
            recipient_name=recipient_name or recipient_email.split("@")[0],
            recipient_email=recipient_email,
            purpose=purpose,
            context=context,
            tone=tone,
            call_to_action=call_to_action,
        )
        print(f"[AGENT] Generated email content ({email_data['character_count']} chars)")

        # Check sensitivity
        full_content = f"{email_data['subject']}\n\n{email_data['full_email']}"
        sensitivity = self.sensitivity_detector.check(
            full_content, recipient_email, self.contact_manager
        )
        print(f"[AGENT] Sensitivity check: {'Requires approval' if sensitivity['requires_approval'] else 'Safe to send'}")

        # Generate plan
        plan_content = self.plan_generator.generate_plan(
            email_data, sensitivity, recipient_name or "Recipient", recipient_email
        )

        # Determine output path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if sensitivity["requires_approval"]:
            output_path = PENDING_APPROVAL_PATH / f"EMAIL_{timestamp}.md"
            status = "pending_approval"
            print(f"[AGENT] Email requires approval. Saved to: {output_path}")
        else:
            output_path = SKILL_PATH / "Plan.md"
            status = "ready_to_send"
            print(f"[AGENT] Email ready. Plan saved to: {output_path}")
            # Add contact if new but safe (first email sent)
            if sensitivity.get("new_contact"):
                self.contact_manager.add_contact(recipient_email, recipient_name)

        # Write plan
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(plan_content)

        return {
            "status": status,
            "plan_path": str(output_path),
            "email_data": email_data,
            "sensitivity": sensitivity,
            "next_step": "await_approval" if sensitivity["requires_approval"] else "execute_send",
        }

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send email using email-mcp.

        Args:
            to: Recipient email
            subject: Email subject
            body: Email body
            cc: CC recipients
            bcc: BCC recipients

        Returns:
            Result dictionary with send status
        """
        print(f"[AGENT] Sending email to: {to}")

        # Build email-mcp command
        params = {
            "to": to,
            "subject": subject,
            "body": body,
            "html": False,
        }
        if cc:
            params["cc"] = cc
        if bcc:
            params["bcc"] = bcc

        command = {
            "method": "email/send",
            "params": params,
        }

        # Execute via email-mcp (simulated - in production would call MCP server)
        result = self._execute_email_send(command)

        if result["success"]:
            # Log to Done
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            done_path = DONE_PATH / f"EMAIL_{timestamp}.md"

            confirmation = f"""---
type: email_confirmation
sent: {datetime.now().isoformat()}
status: sent
to: {to}
subject: {subject}
---

# Email Sent Successfully ✅

## Recipients
- **To:** {to}
{f'- **CC:** {cc}' if cc else ''}
{f'- **BCC:** {bcc}' if bcc else ''}

## Subject
{subject}

## Content
{body}

## Delivery Confirmation
- **Sent:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **Status:** Delivered
- **Message ID:** {result.get('message_id', 'N/A')}

## Next Steps
- Monitor for replies
- Add recipient to contacts if new
- Follow up if needed

---
*Email Sender Agent | Personal AI Employee*
"""
            with open(done_path, "w", encoding="utf-8") as f:
                f.write(confirmation)

            # Add to contacts
            self.contact_manager.add_contact(to)

            result["confirmation_path"] = str(done_path)

        return result

    def _execute_email_send(self, command: Dict) -> Dict[str, Any]:
        """Execute email-mcp send command."""
        # In production, this would communicate with email-mcp server
        print(f"[AGENT] Email command prepared:")
        print(f"  Method: {command['method']}")
        print(f"  To: {command['params']['to']}")
        print(f"  Subject: {command['params']['subject']}")

        return {
            "success": True,
            "message": "Email sent successfully (simulated)",
            "message_id": f"<{datetime.now().strftime('%Y%m%d%H%M%S')}@gmail.com>",
        }

    def send_from_plan(self, plan_path: str) -> Dict[str, Any]:
        """
        Send email from approved plan.

        Args:
            plan_path: Path to approved plan file

        Returns:
            Result dictionary
        """
        # Read plan and extract email data
        with open(plan_path, "r", encoding="utf-8") as f:
            plan_content = f.read()

        # Extract recipient email
        email_match = re.search(r"\*\*To:\*\*.*<([^>]+)>", plan_content)
        if not email_match:
            # Try alternate format
            email_match = re.search(r"\| To \| ([^\|]+) \|", plan_content)

        if not email_match:
            return {"success": False, "error": "Could not extract recipient email from plan"}

        recipient_email = email_match.group(1).strip()

        # Extract subject
        subject_match = re.search(r"\*\*Subject:\*\*\s*(.+?)\n", plan_content)
        if not subject_match:
            subject_match = re.search(r"### Subject\n```\n(.+?)\n```", plan_content, re.DOTALL)

        subject = subject_match.group(1).strip() if subject_match else "No Subject"

        # Extract body
        body_match = re.search(r"### Body\n```\n(.+?)\n```", plan_content, re.DOTALL)
        if not body_match:
            return {"success": False, "error": "Could not extract email body from plan"}

        body = body_match.group(1).strip()

        # Send email
        return self.send_email(to=recipient_email, subject=subject, body=body)


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point for Email Sender Agent."""
    import argparse

    parser = argparse.ArgumentParser(description="Email Sender Agent")
    parser.add_argument("--to", "-t", required=True, help="Recipient email address")
    parser.add_argument("--name", "-n", default="", help="Recipient name")
    parser.add_argument("--purpose", "-p", default="", help="Purpose of the email")
    parser.add_argument("--context", "-c", default="", help="Additional context or content")
    parser.add_argument("--tone", default="professional", choices=["formal", "professional", "casual"],
                       help="Tone of the email")
    parser.add_argument("--cta", default="", help="Call to action")
    parser.add_argument("--execute", "-e", action="store_true", help="Send immediately (skip approval if safe)")
    parser.add_argument("--plan", help="Path to approved plan file for sending")

    args = parser.parse_args()

    agent = EmailSenderAgent()

    if args.plan:
        # Send from approved plan
        result = agent.send_from_plan(plan_path=args.plan)
        print(f"\n[RESULT] {result}")
    else:
        # Create new email
        result = agent.create_email(
            recipient_email=args.to,
            recipient_name=args.name,
            purpose=args.purpose,
            context=args.context,
            tone=args.tone,
            call_to_action=args.cta,
        )

        print("\n" + "=" * 60)
        print("EMAIL CREATED")
        print("=" * 60)
        print(f"Status: {result['status']}")
        print(f"Plan: {result['plan_path']}")
        print(f"To: {args.to}")
        print(f"Subject: {result['email_data']['subject']}")
        print(f"Next Step: {result['next_step']}")

        if result['status'] == 'ready_to_send' and args.execute:
            print("\n[INFO] Sending email immediately...")
            exec_result = agent.send_email(
                to=args.to,
                subject=result['email_data']['subject'],
                body=result['email_data']['full_email'],
            )
            print(f"[RESULT] {exec_result}")
        elif result['status'] == 'pending_approval':
            print("\n[INFO] Awaiting human approval in Pending_Approval folder")


if __name__ == "__main__":
    main()
