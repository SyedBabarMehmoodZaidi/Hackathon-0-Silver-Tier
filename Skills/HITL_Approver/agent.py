#!/usr/bin/env python3
"""
HITL Approver Agent - Human-in-the-Loop Approval System

Detects sensitive actions and routes to Pending_Approval/.
Orchestrator watches /Approved folder and triggers MCP.
Logs everything in /Logs/.

Sensitivity Rules:
- Financial amounts >$50
- LinkedIn posts (always)
- Emails to unknown contacts
- Payment mentions
- Confidential/legal/HR content
"""

import json
import os
import re
import sys
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

# =============================================================================
# Configuration
# =============================================================================

SKILL_PATH = Path(__file__).parent
PROJECT_ROOT = SKILL_PATH.parent.parent
NEEDS_ACTION_PATH = PROJECT_ROOT / "Needs_Action"
PENDING_APPROVAL_PATH = PROJECT_ROOT / "Pending_Approval"
APPROVED_PATH = PROJECT_ROOT / "Approved"
DONE_PATH = PROJECT_ROOT / "Done"
LOGS_PATH = PROJECT_ROOT / "Logs"
CONTACTS_FILE = SKILL_PATH / "contacts.json"

# Ensure directories exist
for path in [PENDING_APPROVAL_PATH, APPROVED_PATH, DONE_PATH, LOGS_PATH]:
    path.mkdir(parents=True, exist_ok=True)

# Sensitivity thresholds
FINANCIAL_THRESHOLD = 50  # Dollars


# =============================================================================
# Enums and Data Classes
# =============================================================================

class ApprovalStatus(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"
    EXECUTED = "EXECUTED"


class ActionType(Enum):
    EMAIL = "email"
    LINKEDIN_POST = "linkedin_post"
    LINKEDIN_MESSAGE = "linkedin_message"
    PAYMENT = "payment"
    CALENDAR = "calendar"
    FILE_OPERATION = "file_operation"
    GENERAL = "general"


@dataclass
class ApprovalRequest:
    """Represents an approval request."""
    approval_id: str
    type: str
    source: str
    source_path: str
    created: str
    status: str = "PENDING"
    priority: str = "medium"
    sensitivity_flags: List[str] = field(default_factory=list)
    title: str = ""
    summary: str = ""
    action_details: str = ""
    risk_level: str = "medium"
    risk_description: str = ""
    reversibility: str = "Reversible"
    decision: Optional[str] = None
    decision_notes: str = ""
    decided_by: str = ""
    decided_at: Optional[str] = None
    executed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
                self.contacts = {"_metadata": {"last_updated": datetime.now().isoformat()}}
        else:
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
        """Add a contact."""
        email_lower = email.lower().strip()
        self.contacts[email_lower] = {
            "email": email_lower,
            "name": name,
            "notes": notes,
            "first_contact": datetime.now().isoformat(),
            "email_count": self.contacts.get(email_lower, {}).get("email_count", 0) + 1,
        }
        self.save_contacts()

    def get_all_emails(self) -> Set[str]:
        """Get all known email addresses."""
        return {k for k in self.contacts.keys() if not k.startswith("_")}


# =============================================================================
# Sensitivity Detector
# =============================================================================

class SensitivityDetector:
    """Detects sensitive content requiring human approval."""

    # Financial patterns (amounts >$50)
    FINANCIAL_PATTERNS = [
        (r"\$[5-9]\d(?:,\d{3})*(?:\.\d{2})?", "currency"),  # $50-$99
        (r"\$[1-9]\d{2,}(?:,\d{3})*(?:\.\d{2})?", "currency"),  # $100+
        (r"\$\d+(?:\.\d{2})?\s*(?:hundred|thousand|million)", "currency_words"),
        (r"(?:USD|EUR|GBP)\s*[5-9]\d", "currency_code"),
        (r"[5-9]\d\s*(?:dollars?|bucks?)", "dollars_words"),
        (r"(?:budget|cost|price|payment|invoice|fee|pay).*(?:\$|\d{2,})", "financial_context"),
    ]

    # Payment patterns (any mention)
    PAYMENT_PATTERNS = [
        r"\bpayment\b",
        r"\bpay\b",
        r"\bpaid\b",
        r"\btransfer\b",
        r"\binvoice\b",
        r"\bbill\b",
        r"\brefund\b",
        r"\breimburse\b",
    ]

    # LinkedIn patterns
    LINKEDIN_PATTERNS = [
        r"\blinkedin\b",
        r"\bpost\b.*\blinkedin\b",
        r"\bpublish\b",
        r"\bshare\b.*\bpost\b",
    ]

    # Confidential patterns
    CONFIDENTIAL_PATTERNS = [
        r"\bconfidential\b",
        r"\bNDA\b",
        r"\bproprietary\b",
        r"\btrade\s*secret\b",
        r"\binternal\s*only\b",
        r"\brestricted\b",
        r"\bprivate\b",
    ]

    # Legal patterns
    LEGAL_PATTERNS = [
        r"\bcontract\b",
        r"\bagreement\b",
        r"\bterms\s*(?:and\s*conditions)?\b",
        r"\blegal\b",
        r"\bliability\b",
        r"\bindemnif(?:y|ication)\b",
        r"\blawsuit\b",
        r"\blitigation\b",
    ]

    # HR patterns
    HR_PATTERNS = [
        r"\bsalary\b",
        r"\bcompensation\b",
        r"\bbonus\b",
        r"\btermination\b",
        r"\blayoff\b",
        r"\bfir(?:ing|ed)\b",
        r"\bhire\b",
        r"\bhiring\b",
        r"\binterview\b",
    ]

    def __init__(self, financial_threshold: int = FINANCIAL_THRESHOLD):
        self.financial_threshold = financial_threshold
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns."""
        self.financial_regex = [
            (re.compile(p, re.IGNORECASE), t) for p, t in self.FINANCIAL_PATTERNS
        ]
        self.payment_regex = [re.compile(p, re.IGNORECASE) for p in self.PAYMENT_PATTERNS]
        self.linkedin_regex = [re.compile(p, re.IGNORECASE) for p in self.LINKEDIN_PATTERNS]
        self.confidential_regex = [re.compile(p, re.IGNORECASE) for p in self.CONFIDENTIAL_PATTERNS]
        self.legal_regex = [re.compile(p, re.IGNORECASE) for p in self.LEGAL_PATTERNS]
        self.hr_regex = [re.compile(p, re.IGNORECASE) for p in self.HR_PATTERNS]

    def check(self, content: str, action_type: str = "general", 
              recipient_email: Optional[str] = None,
              contact_manager: Optional[ContactManager] = None) -> Dict[str, Any]:
        """
        Check content for sensitivity.

        Args:
            content: Action content
            action_type: Type of action (email, linkedin, payment, etc.)
            recipient_email: Recipient email (for contact check)
            contact_manager: Contact manager instance

        Returns:
            Dictionary with sensitivity analysis
        """
        flags = []
        requires_approval = False

        # LinkedIn posts always require approval
        if action_type in ["linkedin_post", "linkedin"]:
            flags.append({
                "type": "linkedin_post",
                "severity": "medium",
                "description": "LinkedIn posts always require human approval",
            })
            requires_approval = True

        # Check financial content
        financial_matches = self._check_financial(content)
        if financial_matches:
            total_amount = self._extract_total_amount(financial_matches)
            if total_amount >= self.financial_threshold:
                flags.append({
                    "type": "financial",
                    "severity": "high",
                    "description": f"Financial amount detected: ${total_amount}",
                    "matches": financial_matches,
                    "amount": total_amount,
                })
                requires_approval = True

        # Check payment mentions
        payment_matches = self._check_patterns(content, self.payment_regex)
        if payment_matches:
            flags.append({
                "type": "payment",
                "severity": "high",
                "description": f"Payment mentioned: {payment_matches}",
                "keywords": payment_matches,
            })
            requires_approval = True

        # Check new contact (for emails)
        if recipient_email and contact_manager:
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
                "description": f"Confidential content: {confidential_matches}",
                "keywords": confidential_matches,
            })
            requires_approval = True

        # Check legal content
        legal_matches = self._check_patterns(content, self.legal_regex)
        if legal_matches:
            flags.append({
                "type": "legal",
                "severity": "high",
                "description": f"Legal content: {legal_matches}",
                "keywords": legal_matches,
            })
            requires_approval = True

        # Check HR content
        hr_matches = self._check_patterns(content, self.hr_regex)
        if hr_matches:
            flags.append({
                "type": "hr_sensitive",
                "severity": "high",
                "description": f"HR-sensitive content: {hr_matches}",
                "keywords": hr_matches,
            })
            requires_approval = True

        return {
            "requires_approval": requires_approval,
            "flags": flags,
            "safe_to_execute": not requires_approval,
            "flag_count": len(flags),
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
        return list(set(matches))

    def _extract_total_amount(self, matches: List[str]) -> float:
        """Extract total dollar amount from matches."""
        total = 0.0
        for match in matches:
            # Extract numeric value
            nums = re.findall(r"\d+(?:,\d{3})*(?:\.\d{2})?", match)
            for num in nums:
                try:
                    value = float(num.replace(",", ""))
                    total += value
                except ValueError:
                    pass
        return total


# =============================================================================
# Approval Request Generator
# =============================================================================

class ApprovalRequestGenerator:
    """Generates approval request files."""

    def __init__(self, pending_path: Path = PENDING_APPROVAL_PATH):
        self.pending_path = pending_path

    def generate(self, content: str, analysis: Dict[str, Any], 
                 source_path: Path, action_type: str = "general") -> Tuple[Path, ApprovalRequest]:
        """
        Generate an approval request file.

        Args:
            content: Original content
            analysis: Sensitivity analysis results
            source_path: Source file path
            action_type: Type of action

        Returns:
            Tuple of (file_path, approval_request)
        """
        timestamp = datetime.now()
        unique_suffix = hashlib.md5(str(source_path).encode()).hexdigest()[:6]
        approval_id = f"APPROVAL_{timestamp.strftime('%Y%m%d_%H%M%S')}_{unique_suffix}"

        # Determine risk level
        risk_level = self._assess_risk(analysis)

        # Create approval request
        approval_request = ApprovalRequest(
            approval_id=approval_id,
            type=action_type,
            source=source_path.name,
            source_path=str(source_path),
            created=timestamp.isoformat(),
            status=ApprovalStatus.PENDING.value,
            priority=self._determine_priority(analysis),
            sensitivity_flags=[f["type"] for f in analysis.get("flags", [])],
            title=self._generate_title(action_type, source_path),
            summary=self._generate_summary(content, analysis),
            action_details=content[:2000],
            risk_level=risk_level,
            risk_description=self._generate_risk_description(analysis),
            reversibility=self._assess_reversibility(action_type),
            metadata={
                "flag_count": analysis.get("flag_count", 0),
                "requires_approval": analysis.get("requires_approval", False),
            },
        )

        # Generate markdown
        markdown = self._generate_markdown(approval_request, analysis)

        # Write file
        file_path = self.pending_path / f"{action_type.upper()}_{timestamp.strftime('%Y%m%d_%H%M%S')}_{unique_suffix}.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown)

        return file_path, approval_request

    def _assess_risk(self, analysis: Dict[str, Any]) -> str:
        """Assess overall risk level."""
        flags = analysis.get("flags", [])
        high_severity = sum(1 for f in flags if f.get("severity") == "high")

        if high_severity >= 2:
            return "high"
        elif high_severity == 1 or len(flags) >= 3:
            return "medium"
        return "low"

    def _determine_priority(self, analysis: Dict[str, Any]) -> str:
        """Determine approval priority."""
        flags = analysis.get("flags", [])
        
        # High priority for financial/legal
        for flag in flags:
            if flag.get("type") in ["financial", "legal", "payment"]:
                return "high"
        
        # Medium for new contacts, LinkedIn
        for flag in flags:
            if flag.get("type") in ["new_contact", "linkedin_post"]:
                return "medium"
        
        return "low"

    def _generate_title(self, action_type: str, source_path: Path) -> str:
        """Generate approval request title."""
        titles = {
            "email": "Email Approval Required",
            "linkedin_post": "LinkedIn Post Approval Required",
            "linkedin_message": "LinkedIn Message Approval Required",
            "payment": "Payment Approval Required",
            "calendar": "Calendar Event Approval Required",
            "file_operation": "File Operation Approval Required",
            "general": "Action Approval Required",
        }
        return titles.get(action_type, f"Approval Required: {source_path.stem}")

    def _generate_summary(self, content: str, analysis: Dict[str, Any]) -> str:
        """Generate brief summary."""
        # Extract first meaningful paragraph
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip() and not p.startswith("---")]
        if paragraphs:
            return paragraphs[0][:300]
        return "Action requires human approval before execution."

    def _generate_risk_description(self, analysis: Dict[str, Any]) -> str:
        """Generate risk description."""
        flags = analysis.get("flags", [])
        if not flags:
            return "No significant risks identified."

        descriptions = []
        for flag in flags:
            descriptions.append(flag.get("description", flag.get("type")))

        return "; ".join(descriptions)

    def _assess_reversibility(self, action_type: str) -> str:
        """Assess if action is reversible."""
        reversible = {
            "email": "Partially reversible (can send follow-up)",
            "linkedin_post": "Reversible (can delete post)",
            "linkedin_message": "Partially reversible (can send clarification)",
            "payment": "Difficult to reverse once processed",
            "calendar": "Reversible (can cancel/reschedule)",
            "file_operation": "Depends on operation type",
            "general": "Unknown",
        }
        return reversible.get(action_type, "Unknown")

    def _generate_markdown(self, request: ApprovalRequest, analysis: Dict[str, Any]) -> str:
        """Generate markdown content for approval request."""
        # Build sensitivity table
        sensitivity_rows = []
        for flag in analysis.get("flags", []):
            severity_icon = "🔴" if flag.get("severity") == "high" else "🟡"
            sensitivity_rows.append(
                f"| {flag['type'].replace('_', ' ').title()} | {severity_icon} | {flag.get('description', 'N/A')} |"
            )

        if not sensitivity_rows:
            sensitivity_rows = ["| None | ✅ | No sensitivity flags detected |"]

        # Build action type specific details
        action_details = request.action_details

        markdown = f"""---
approval_id: {request.approval_id}
type: {request.type}
source: {request.source}
created: {request.created}
status: {request.status}
priority: {request.priority}
sensitivity_flags: {request.sensitivity_flags}
risk_level: {request.risk_level}
---

# 🔒 Approval Required: {request.title}

## Summary

{request.summary}

---

## 📋 Action Details

```
{action_details}
```

---

## ⚠️ Sensitivity Detection

| Flag | Severity | Details |
|------|----------|---------|
{''.join(sensitivity_rows)}

**Total Flags:** {len(analysis.get('flags', []))}
**Risk Level:** {request.risk_level.upper()}

---

## 🎯 Risk Assessment

| Factor | Assessment |
|--------|------------|
| **Risk Level** | {request.risk_level.upper()} |
| **Description** | {request.risk_description} |
| **Reversibility** | {request.reversibility} |

---

## ✅ Approval Decision

**Current Status:** {request.status}

### Options

- [ ] **APPROVE** - Move to `Approved/` for MCP execution
- [ ] **REJECT** - Archive with reason below
- [ ] **MODIFY** - Request changes and re-submit

### Decision Notes

_Reason for decision:_

```
{request.decision_notes if request.decision_notes else '*Add notes here*'}
```

**Decided By:** {request.decided_by if request.decided_by else '*Pending*'}
**Decided At:** {request.decided_at if request.decided_at else '*Pending*'}

---

## 🔧 Execution Plan (After Approval)

Once approved, this action will be:
1. Moved to `Approved/` folder
2. Picked up by orchestrator
3. Executed via appropriate MCP server
4. Logged to `Logs/`
5. Moved to `Done/` upon completion

---

## 📝 Metadata

| Field | Value |
|-------|-------|
| **Approval ID** | `{request.approval_id}` |
| **Source File** | `{request.source}` |
| **Created** | {request.created} |
| **Type** | {request.type} |
| **Priority** | {request.priority} |

---

*Generated by HITL Approver | Personal AI Employee*
*Follows Company_Handbook.md rules*
"""
        return markdown


# =============================================================================
# Approval Logger
# =============================================================================

class ApprovalLogger:
    """Logs all approval activities."""

    def __init__(self, logs_path: Path = LOGS_PATH):
        self.logs_path = logs_path

    def log(self, event_type: str, data: Dict[str, Any]):
        """Log an approval event."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "data": data,
        }

        log_file = self.logs_path / f"approval_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

    def log_request(self, request: ApprovalRequest, analysis: Dict[str, Any]):
        """Log approval request created."""
        self.log("approval_requested", {
            "approval_id": request.approval_id,
            "type": request.type,
            "priority": request.priority,
            "sensitivity_flags": request.sensitivity_flags,
            "risk_level": request.risk_level,
            "status": request.status,
        })

    def log_decision(self, request: ApprovalRequest, decision: str, decided_by: str = "human"):
        """Log approval decision."""
        self.log("approval_decided", {
            "approval_id": request.approval_id,
            "type": request.type,
            "decision": decision,
            "decided_by": decided_by,
            "decided_at": request.decided_at,
        })

    def log_execution(self, request: ApprovalRequest, result: Dict[str, Any]):
        """Log approval execution."""
        self.log("approval_executed", {
            "approval_id": request.approval_id,
            "type": request.type,
            "result": result,
            "executed_at": request.executed_at,
        })


# =============================================================================
# Approval Monitor (Orchestrator Integration)
# =============================================================================

class ApprovalMonitor:
    """Monitors Approved/ folder and triggers MCP execution."""

    def __init__(self, approved_path: Path = APPROVED_PATH, 
                 done_path: Path = DONE_PATH,
                 logs_path: Path = LOGS_PATH):
        self.approved_path = approved_path
        self.done_path = done_path
        self.logs_path = logs_path
        self.logger = ApprovalLogger(logs_path)
        self.processed_files: Set[str] = set()

    def check_and_execute(self) -> List[Dict[str, Any]]:
        """Check Approved/ folder and execute pending actions."""
        results = []

        # Get all approval files in Approved/
        approval_files = list(self.approved_path.glob("*.md"))

        for file_path in approval_files:
            if str(file_path) in self.processed_files:
                continue

            result = self._process_approved_file(file_path)
            results.append(result)
            self.processed_files.add(str(file_path))

        return results

    def _process_approved_file(self, file_path: Path) -> Dict[str, Any]:
        """Process an approved file and trigger MCP."""
        print(f"[MONITOR] Processing approved file: {file_path.name}")

        try:
            # Read and parse approval file
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract approval ID and type
            approval_id_match = re.search(r"approval_id:\s*(\S+)", content)
            type_match = re.search(r"type:\s*(\S+)", content)

            if not approval_id_match or not type_match:
                return {"success": False, "error": "Invalid approval file format"}

            approval_id = approval_id_match.group(1)
            action_type = type_match.group(1)

            # Check if already executed
            if "EXECUTED" in content:
                return {"success": False, "error": "Already executed"}

            # Execute based on type
            print(f"[MONITOR] Executing {action_type} action via MCP...")
            exec_result = self._execute_via_mcp(action_type, content)

            # Update file status
            self._mark_as_executed(file_path, approval_id)

            # Log execution
            self.logger.log("execution_triggered", {
                "approval_id": approval_id,
                "type": action_type,
                "result": exec_result,
            })

            return {
                "success": True,
                "approval_id": approval_id,
                "type": action_type,
                "result": exec_result,
            }

        except Exception as e:
            print(f"[MONITOR] Error processing {file_path.name}: {e}")
            self.logger.log("execution_error", {
                "file": str(file_path),
                "error": str(e),
            })
            return {"success": False, "error": str(e)}

    def _execute_via_mcp(self, action_type: str, content: str) -> Dict[str, Any]:
        """Execute action via appropriate MCP server."""
        # In production, this would call actual MCP servers
        # For now, simulate execution

        print(f"[MCP] Executing {action_type} action...")

        # Simulate MCP execution
        exec_result = {
            "mcp_server": self._get_mcp_server(action_type),
            "action": f"execute_{action_type}",
            "status": "simulated_success",
            "timestamp": datetime.now().isoformat(),
        }

        return exec_result

    def _get_mcp_server(self, action_type: str) -> str:
        """Get appropriate MCP server for action type."""
        servers = {
            "email": "email-mcp",
            "linkedin_post": "browser-mcp",
            "linkedin_message": "browser-mcp",
            "payment": "payment-mcp",
            "calendar": "calendar-mcp",
            "file_operation": "file-mcp",
            "general": "general-mcp",
        }
        return servers.get(action_type, "general-mcp")

    def _mark_as_executed(self, file_path: Path, approval_id: str):
        """Mark approval file as executed and move to Done/."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Update status
        content = content.replace(
            "**Current Status:** PENDING",
            "**Current Status:** EXECUTED"
        )
        content = content.replace(
            f"**Decided At:** *Pending*",
            f"**Executed At:** {datetime.now().isoformat()}"
        )

        # Move to Done/
        done_path = self.done_path / file_path.name
        with open(done_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Remove original
        file_path.unlink()

        print(f"[MONITOR] Moved to Done/: {done_path.name}")


# =============================================================================
# HITL Approver Agent (Main)
# =============================================================================

class HITLApproverAgent:
    """
    Human-in-the-Loop Approver Agent.

    - Detects sensitive actions
    - Creates Pending_Approval/ files
    - Monitors Approved/ for execution
    - Logs everything
    """

    def __init__(self):
        self.contact_manager = ContactManager()
        self.sensitivity_detector = SensitivityDetector()
        self.request_generator = ApprovalRequestGenerator()
        self.logger = ApprovalLogger()
        self.monitor = ApprovalMonitor()

    def evaluate_action(self, content: str, action_type: str = "general",
                       recipient_email: Optional[str] = None,
                       source_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Evaluate an action for sensitivity.

        Args:
            content: Action content
            action_type: Type of action
            recipient_email: Recipient email (for contact check)
            source_path: Source file path

        Returns:
            Evaluation result
        """
        print(f"[HITL] Evaluating {action_type} action...")

        # Check sensitivity
        analysis = self.sensitivity_detector.check(
            content, action_type, recipient_email, self.contact_manager
        )

        print(f"[HITL] Sensitivity check: {analysis['flag_count']} flags, "
              f"requires_approval={analysis['requires_approval']}")

        # Log evaluation
        self.logger.log("action_evaluated", {
            "type": action_type,
            "requires_approval": analysis["requires_approval"],
            "flag_count": analysis["flag_count"],
        })

        return {
            "requires_approval": analysis["requires_approval"],
            "analysis": analysis,
            "safe_to_execute": analysis["safe_to_execute"],
        }

    def request_approval(self, content: str, action_type: str = "general",
                        recipient_email: Optional[str] = None,
                        source_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Request approval for an action.

        Args:
            content: Action content
            action_type: Type of action
            recipient_email: Recipient email
            source_path: Source file path

        Returns:
            Approval request result
        """
        if source_path is None:
            source_path = Path("unknown")

        # Evaluate sensitivity
        evaluation = self.evaluate_action(content, action_type, recipient_email, source_path)

        if not evaluation["requires_approval"]:
            print("[HITL] Action does not require approval - can execute directly")
            return {
                "requires_approval": False,
                "message": "Action can be executed directly",
                "analysis": evaluation["analysis"],
            }

        # Generate approval request
        file_path, request = self.request_generator.generate(
            content, evaluation["analysis"], source_path, action_type
        )

        print(f"[HITL] Approval request created: {file_path.name}")

        # Log request
        self.logger.log_request(request, evaluation["analysis"])

        return {
            "requires_approval": True,
            "approval_id": request.approval_id,
            "file_path": str(file_path),
            "type": action_type,
            "priority": request.priority,
            "risk_level": request.risk_level,
            "message": f"Approval request created in Pending_Approval/",
        }

    def approve_action(self, approval_file: Path, decided_by: str = "human",
                      notes: str = "") -> Dict[str, Any]:
        """
        Approve an action (move to Approved/).

        Args:
            approval_file: Path to approval file
            decided_by: Who approved
            notes: Decision notes

        Returns:
            Approval result
        """
        print(f"[HITL] Approving action: {approval_file.name}")

        try:
            # Read approval file
            with open(approval_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract approval ID
            approval_id_match = re.search(r"approval_id:\s*(\S+)", content)
            if not approval_id_match:
                return {"success": False, "error": "Invalid approval file"}

            approval_id = approval_id_match.group(1)

            # Update content with approval
            timestamp = datetime.now().isoformat()
            content = content.replace(
                "**Current Status:** PENDING",
                f"**Current Status:** APPROVED\n**Decided By:** {decided_by}\n**Decided At:** {timestamp}"
            )
            content = content.replace(
                "- [ ] **APPROVE**",
                "- [x] **APPROVE**"
            )
            if notes:
                content = content.replace(
                    "*Add notes here*",
                    notes
                )

            # Move to Approved/
            approved_path = APPROVED_PATH / approval_file.name
            with open(approved_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Remove from Pending_Approval/
            approval_file.unlink()

            print(f"[HITL] Moved to Approved/: {approved_path.name}")

            # Log decision
            self.logger.log("approval_granted", {
                "approval_id": approval_id,
                "file": str(approved_path),
                "decided_by": decided_by,
            })

            return {
                "success": True,
                "approval_id": approval_id,
                "approved_path": str(approved_path),
                "message": "Action approved and moved to Approved/",
            }

        except Exception as e:
            print(f"[HITL] Error approving action: {e}")
            return {"success": False, "error": str(e)}

    def reject_action(self, approval_file: Path, reason: str = "",
                     decided_by: str = "human") -> Dict[str, Any]:
        """
        Reject an action (archive).

        Args:
            approval_file: Path to approval file
            reason: Rejection reason
            decided_by: Who rejected

        Returns:
            Rejection result
        """
        print(f"[HITL] Rejecting action: {approval_file.name}")

        try:
            # Read and update
            with open(approval_file, "r", encoding="utf-8") as f:
                content = f.read()

            timestamp = datetime.now().isoformat()
            content = content.replace(
                "**Current Status:** PENDING",
                f"**Current Status:** REJECTED\n**Decided By:** {decided_by}\n**Decided At:** {timestamp}"
            )
            content = content.replace(
                "- [ ] **REJECT**",
                f"- [x] **REJECT**\n\n**Reason:** {reason}"
            )

            # Archive (could move to Rejected/ folder)
            rejected_path = PROJECT_ROOT / "Rejected" / approval_file.name
            rejected_path.parent.mkdir(parents=True, exist_ok=True)
            with open(rejected_path, "w", encoding="utf-8") as f:
                f.write(content)

            approval_file.unlink()

            # Log
            self.logger.log("approval_rejected", {
                "file": str(approval_file),
                "reason": reason,
            })

            return {
                "success": True,
                "message": "Action rejected and archived",
                "rejected_path": str(rejected_path),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_monitor_loop(self, interval: int = 10):
        """Run continuous monitoring loop."""
        print("[HITL] Starting approval monitor loop...")
        print(f"[HITL] Checking Approved/ every {interval} seconds")

        try:
            while True:
                results = self.monitor.check_and_execute()

                if results:
                    for result in results:
                        if result.get("success"):
                            print(f"[HITL] ✓ Executed: {result['approval_id']}")
                        else:
                            print(f"[HITL] ✗ Error: {result.get('error')}")

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n[HITL] Monitor loop stopped")


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="HITL Approver Agent")
    parser.add_argument("--evaluate", "-e", help="Evaluate content for sensitivity")
    parser.add_argument("--type", "-t", default="general", help="Action type")
    parser.add_argument("--email", help="Recipient email (for contact check)")
    parser.add_argument("--approve", "-a", help="Approve a pending file")
    parser.add_argument("--reject", "-r", help="Reject a pending file")
    parser.add_argument("--reason", default="", help="Rejection reason")
    parser.add_argument("--monitor", "-m", action="store_true", help="Run monitor loop")
    parser.add_argument("--interval", "-i", type=int, default=10, help="Monitor interval")
    parser.add_argument("--list", action="store_true", help="List pending approvals")

    args = parser.parse_args()

    agent = HITLApproverAgent()

    if args.list:
        # List pending approvals
        pending = list(PENDING_APPROVAL_PATH.glob("*.md"))
        if pending:
            print(f"Pending approvals ({len(pending)}):")
            for f in pending:
                print(f"  - {f.name}")
        else:
            print("No pending approvals")

    elif args.approve:
        # Approve a file
        file_path = Path(args.approve)
        if not file_path.exists():
            file_path = PENDING_APPROVAL_PATH / args.approve

        result = agent.approve_action(file_path)
        print(f"[RESULT] {result}")

    elif args.reject:
        # Reject a file
        file_path = Path(args.reject)
        if not file_path.exists():
            file_path = PENDING_APPROVAL_PATH / args.reject

        result = agent.reject_action(file_path, args.reason)
        print(f"[RESULT] {result}")

    elif args.monitor:
        # Run monitor loop
        agent.run_monitor_loop(args.interval)

    elif args.evaluate:
        # Evaluate content
        content = args.evaluate
        result = agent.request_approval(content, args.type, args.email)
        print(f"\n[RESULT] {result}")

    else:
        # Default: check Pending_Approval/ and Approved/
        print("[HITL] Checking for pending approvals...")
        pending = list(PENDING_APPROVAL_PATH.glob("*.md"))
        print(f"Pending: {len(pending)} files")

        print("[HITL] Checking for approved actions to execute...")
        results = agent.monitor.check_and_execute()
        print(f"Executed: {len(results)} actions")


if __name__ == "__main__":
    main()
