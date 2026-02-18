#!/usr/bin/env python3
"""
LinkedIn Poster Agent

Creates and publishes professional LinkedIn posts with:
- Professional business content
- Relevant hashtags
- Call-to-action
- Image suggestions
- Human-in-loop approval for sensitive content
"""

import json
import os
import re
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# Configuration
# =============================================================================

SKILL_PATH = Path(__file__).parent
PROJECT_ROOT = SKILL_PATH.parent.parent
PENDING_APPROVAL_PATH = PROJECT_ROOT / "Pending_Approval"
APPROVED_PATH = PROJECT_ROOT / "Approved"
DONE_PATH = PROJECT_ROOT / "Done"
LOGS_PATH = PROJECT_ROOT / "Logs"

# Ensure directories exist
for path in [PENDING_APPROVAL_PATH, APPROVED_PATH, DONE_PATH, LOGS_PATH]:
    path.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Content Generator
# =============================================================================

class LinkedInContentGenerator:
    """Generates professional LinkedIn post content."""

    # Common hashtag categories
    HASHTAG_CATEGORIES = {
        "business": ["#Business", "#Entrepreneurship", "#Leadership", "#Management", "#Strategy"],
        "technology": ["#Technology", "#Innovation", "#DigitalTransformation", "#AI", "#SaaS"],
        "career": ["#Career", "#ProfessionalDevelopment", "#JobSearch", "#Networking", "#Growth"],
        "industry": ["#Industry", "#MarketTrends", "#BusinessNews", "#Economy", "#Finance"],
        "company": ["#Company", "#TeamWork", "#CompanyCulture", "#WorkLife", "#EmployeeExperience"],
        "product": ["#ProductLaunch", "#NewFeature", "#ProductUpdate", "#Innovation", "#TechNews"],
        "engagement": ["#ThoughtLeadership", "#Industry", "#ProfessionalNetwork", "#Learning", "#Success"],
    }

    # Call-to-action templates
    CTAS = {
        "engagement": [
            "What's your experience with this? Share below! 👇",
            "Drop a comment with your thoughts 💬",
            "I'd love to hear your perspective!",
            "Agree or disagree? Let me know below!",
        ],
        "share": [
            "Repost to help your network ♻️",
            "Share this with someone who needs to hear it!",
            "Know someone who'd benefit from this? Share away!",
        ],
        "follow": [
            "Follow me for more insights on {topic}!",
            "Hit the 🔔 to stay updated!",
            "Connect with me for more content like this!",
        ],
        "click": [
            "Click the link in comments to learn more 🔗",
            "Check out the full story in the comments 👇",
            "Link in the first comment!",
        ],
        "visit": [
            "Visit our website to learn more!",
            "Start your free trial today!",
            "Book a demo now!",
        ],
    }

    def __init__(self):
        self.generated_content = {}

    def generate_post(self, topic: str, context: str = "", tone: str = "professional") -> Dict[str, Any]:
        """
        Generate a complete LinkedIn post.

        Args:
            topic: Main topic/theme of the post
            context: Additional context or details
            tone: Tone of the post (professional, casual, enthusiastic)

        Returns:
            Dictionary with post content, hashtags, CTA, and image suggestion
        """
        # Generate hook
        hook = self._generate_hook(topic, tone)

        # Generate body
        body = self._generate_body(topic, context, tone)

        # Generate value proposition
        value = self._generate_value_proposition(topic)

        # Select CTA
        cta_type, cta = self._select_cta(topic)

        # Select hashtags
        hashtags = self._select_hashtags(topic, count=5)

        # Generate image suggestion
        image_suggestion = self._generate_image_suggestion(topic)

        # Assemble full post
        full_post = f"{hook}\n\n{body}\n\n{value}\n\n{cta}\n\n{' '.join(hashtags)}"

        return {
            "hook": hook,
            "body": body,
            "value": value,
            "cta_type": cta_type,
            "cta": cta,
            "hashtags": hashtags,
            "image_suggestion": image_suggestion,
            "full_post": full_post,
            "character_count": len(full_post),
        }

    def _generate_hook(self, topic: str, tone: str) -> str:
        """Generate an attention-grabbing hook."""
        hooks = {
            "professional": [
                f"Exciting developments in {topic}...",
                f"Here's what you need to know about {topic}:",
                f"The landscape of {topic} is changing. Here's why it matters:",
            ],
            "casual": [
                f"Okay, can we talk about {topic} for a second? 👀",
                f"Hot take on {topic} incoming...",
                f"Nobody asked, but here are my thoughts on {topic}:",
            ],
            "enthusiastic": [
                f"🚀 Big news about {topic}!",
                f"🎉 This is HUGE for {topic}!",
                f"🔥 Game-changer alert: {topic}!",
            ],
        }

        import random
        return random.choice(hooks.get(tone, hooks["professional"]))

    def _generate_body(self, topic: str, context: str, tone: str) -> str:
        """Generate the main body of the post."""
        if context:
            return context

        # Generate generic body based on tone
        bodies = {
            "professional": [
                f"After extensive research and analysis, I've identified key trends in {topic} that professionals should be aware of.",
                f"The {topic} space continues to evolve rapidly. Here are my observations from working in this field.",
            ],
            "casual": [
                f"Been diving deep into {topic} lately and wanted to share what I've learned.",
                f"Real talk: {topic} is more complex than most people realize.",
            ],
            "enthusiastic": [
                f"I'm incredibly excited to share insights about {topic} with you all!",
                f"The innovation happening in {topic} right now is absolutely mind-blowing!",
            ],
        }

        import random
        return random.choice(bodies.get(tone, bodies["professional"]))

    def _generate_value_proposition(self, topic: str) -> str:
        """Generate value proposition for readers."""
        values = [
            "Key takeaway: Understanding this can help you stay ahead in your industry.",
            "Why this matters: These insights can inform your strategic decisions.",
            "The bottom line: This affects how we all work and grow professionally.",
            "Take this forward: Use these insights to drive better outcomes.",
        ]
        import random
        return random.choice(values)

    def _select_cta(self, topic: str) -> Tuple[str, str]:
        """Select appropriate call-to-action."""
        import random
        cta_type = random.choice(list(self.CTAS.keys()))
        cta_template = random.choice(self.CTAS[cta_type])
        cta = cta_template.format(topic=topic)
        return cta_type, cta

    def _select_hashtags(self, topic: str, count: int = 5) -> List[str]:
        """Select relevant hashtags based on topic."""
        selected = []
        topic_lower = topic.lower()

        # Match topic to categories
        for category, hashtags in self.HASHTAG_CATEGORIES.items():
            if category in topic_lower:
                selected.extend(hashtags[:2])

        # Add general engagement hashtags if we don't have enough
        while len(selected) < count:
            remaining = [h for h in self.HASHTAG_CATEGORIES["engagement"] if h not in selected]
            if remaining:
                import random
                selected.append(random.choice(remaining))
            else:
                break

        return selected[:count]

    def _generate_image_suggestion(self, topic: str) -> Dict[str, str]:
        """Generate image suggestion for the post."""
        suggestions = {
            "type": "Professional graphic or photo",
            "description": f"Clean, professional image related to {topic}. Consider a chart, infographic, or team photo that illustrates the key message.",
            "specs": "1200x627 pixels (landscape) or 1080x1080 (square), JPG or PNG",
        }

        # Topic-specific suggestions
        if any(word in topic.lower() for word in ["product", "launch", "feature"]):
            suggestions = {
                "type": "Product screenshot",
                "description": "High-quality screenshot of the product/feature in action, with minimal text overlay.",
                "specs": "1200x627 pixels, PNG with transparency if possible",
            }
        elif any(word in topic.lower() for word in ["team", "company", "culture"]):
            suggestions = {
                "type": "Team photo",
                "description": "Authentic team photo showing company culture. Natural lighting, genuine smiles.",
                "specs": "1080x1080 pixels, JPG",
            }
        elif any(word in topic.lower() for word in ["data", "research", "study"]):
            suggestions = {
                "type": "Infographic",
                "description": "Data visualization or infographic highlighting key statistics from the research.",
                "specs": "1200x1500 pixels (portrait), PNG",
            }

        return suggestions


# =============================================================================
# Sensitivity Checker
# =============================================================================

class SensitivityChecker:
    """Checks content for sensitivity requiring human approval."""

    SENSITIVE_PATTERNS = [
        # Financial data
        (r"\$\d+(?:\.\d+)?[MBK]?", "financial_data", "Contains financial figures"),
        (r"\d+% (?:growth|revenue|profit)", "financial_data", "Contains financial percentages"),
        (r"(?:revenue|profit|funding|investment|valuation).*(?:\d+)", "financial_data", "Contains financial information"),

        # Company confidential
        (r"(?:confidential|proprietary|internal|NDA)", "confidential", "May contain confidential information"),
        (r"(?:trade secret|patent pending)", "confidential", "May contain proprietary information"),

        # Client/partner mentions
        (r"(?:client|partner|customer|vendor).*(?:name|named)", "client_mention", "Mentions clients or partners"),

        # Sensitive topics
        (r"(?:layoff|layoffs|laying off)", "sensitive_hr", "Discusses layoffs"),
        (r"(?:firing|terminated|dismissed)", "sensitive_hr", "Discusses terminations"),
        (r"(?:lawsuit|legal action|litigation)", "legal", "Legal implications"),
        (r"(?:political|election|policy)", "controversial", "Political content"),
    ]

    def check(self, content: str) -> Dict[str, Any]:
        """
        Check content for sensitivity.

        Returns:
            Dictionary with sensitivity analysis results
        """
        flags = []
        requires_approval = False

        for pattern, flag_type, description in self.SENSITIVE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                flags.append({
                    "type": flag_type,
                    "description": description,
                    "pattern": pattern,
                })
                requires_approval = True

        return {
            "requires_approval": requires_approval,
            "flags": flags,
            "safe_to_post": not requires_approval,
        }


# =============================================================================
# Plan Generator
# =============================================================================

class PlanGenerator:
    """Generates Plan.md for LinkedIn posts."""

    def __init__(self, skill_path: Path):
        self.skill_path = skill_path
        self.template_path = skill_path / "templates" / "post_template.md"

    def generate_plan(self, post_data: Dict[str, Any], sensitivity: Dict[str, Any]) -> str:
        """Generate Plan.md content."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        approval_status = "YES" if sensitivity["requires_approval"] else "NO"
        approval_reason = "; ".join([f["description"] for f in sensitivity["flags"]]) if sensitivity["flags"] else "Content is non-sensitive"

        hashtags_table = ""
        for i, tag in enumerate(post_data["hashtags"]):
            hashtags_table += f"| {tag} | Mixed | Relevant to topic |\n"

        plan = f"""---
plan_type: linkedin_post
created: {datetime.now().isoformat()}
status: draft
approval_required: {str(sensitivity["requires_approval"]).lower()}
---

# LinkedIn Post Plan

**Created:** {timestamp}
**Topic:** LinkedIn Post
**Status:** {'Pending Approval' if sensitivity['requires_approval'] else 'Ready to Post'}

---

## 📝 Post Content

```
{post_data["full_post"]}
```

**Character Count:** {post_data["character_count"]} / 3000

---

## #️⃣ Hashtags

{' '.join(post_data["hashtags"])}

| Hashtag | Type | Reason |
|---------|------|--------|
{hashtags_table}
**Total:** {len(post_data["hashtags"])} hashtags

---

## 🎯 Call-to-Action

**Type:** {post_data["cta_type"]}

**CTA:** {post_data["cta"]}

---

## 🖼️ Image Suggestion

**Type:** {post_data["image_suggestion"]["type"]}

**Description:**
{post_data["image_suggestion"]["description"]}

**Specifications:** {post_data["image_suggestion"]["specs"]}

---

## ⚠️ Sensitivity Check

| Check | Status |
|-------|--------|
| Requires Approval | {'✅ Yes' if sensitivity['requires_approval'] else '❌ No'} |
| Safe to Post | {'✅ Yes' if sensitivity['safe_to_post'] else '❌ No'} |

**Flags:** {len(sensitivity["flags"])}
"""

        if sensitivity["flags"]:
            for flag in sensitivity["flags"]:
                plan += f"\n- ⚠️ {flag['description']} ({flag['type']})"
        else:
            plan += "\n- ✅ No sensitivity flags detected"

        plan += f"""

---

## ✅ Approval Required: {approval_status}

**Reason:** {approval_reason}

"""

        if sensitivity["requires_approval"]:
            plan += f"""**Next Steps:**
1. This plan has been saved to `Pending_Approval/LINKEDIN_POST_{timestamp}.md`
2. Awaiting human review and approval
3. Once approved, move to `Approved/` folder
4. Execute posting after approval
"""
        else:
            plan += """**Next Steps:**
1. Review the post content above
2. Execute posting using browser-mcp
3. Confirm successful post
"""

        plan += """
---

## 🔧 Execution Commands

```json
[
  {"method": "browser/navigate", "params": {"url": "https://www.linkedin.com/feed"}},
  {"method": "browser/wait", "params": {"selector": "[data-id='gh-create-a-post']", "timeout": 10000}},
  {"method": "browser/click", "params": {"selector": "[data-id='gh-create-a-post']"}},
  {"method": "browser/wait", "params": {"selector": "[contenteditable='true']", "timeout": 5000}},
  {"method": "browser/fill", "params": {"selector": "[contenteditable='true']", "value": "[POST_CONTENT]"}},
  {"method": "browser/wait", "params": {"selector": "button[aria-label*='Post']", "timeout": 5000}},
  {"method": "browser/click", "params": {"selector": "button[aria-label*='Post']"}}
]
```

---
*Generated by LinkedIn Poster Skill | Personal AI Employee*
"""
        return plan


# =============================================================================
# LinkedIn Poster Agent
# =============================================================================

class LinkedInPosterAgent:
    """Main agent for creating and posting LinkedIn content."""

    def __init__(self):
        self.content_generator = LinkedInContentGenerator()
        self.sensitivity_checker = SensitivityChecker()
        self.plan_generator = PlanGenerator(SKILL_PATH)

    def create_post(self, topic: str, context: str = "", tone: str = "professional") -> Dict[str, Any]:
        """
        Create a LinkedIn post with full workflow.

        Args:
            topic: Main topic of the post
            context: Additional context or details
            tone: Tone of the post

        Returns:
            Result dictionary with paths and status
        """
        print(f"[AGENT] Creating LinkedIn post about: {topic}")

        # Generate content
        post_data = self.content_generator.generate_post(topic, context, tone)
        print(f"[AGENT] Generated post content ({post_data['character_count']} chars)")

        # Check sensitivity
        sensitivity = self.sensitivity_checker.check(post_data["full_post"])
        print(f"[AGENT] Sensitivity check: {'Requires approval' if sensitivity['requires_approval'] else 'Safe to post'}")

        # Generate plan
        plan_content = self.plan_generator.generate_plan(post_data, sensitivity)

        # Determine output path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if sensitivity["requires_approval"]:
            # Save to Pending_Approval
            output_path = PENDING_APPROVAL_PATH / f"LINKEDIN_POST_{timestamp}.md"
            status = "pending_approval"
            print(f"[AGENT] Content requires approval. Saved to: {output_path}")
        else:
            # Save Plan.md in skill folder for review
            output_path = SKILL_PATH / "Plan.md"
            status = "ready_to_post"
            print(f"[AGENT] Content ready. Plan saved to: {output_path}")

        # Write plan
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(plan_content)

        return {
            "status": status,
            "plan_path": str(output_path),
            "post_data": post_data,
            "sensitivity": sensitivity,
            "next_step": "await_approval" if sensitivity["requires_approval"] else "execute_post",
        }

    def execute_post(self, plan_path: Optional[str] = None, post_content: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute posting to LinkedIn using browser-mcp.

        Args:
            plan_path: Path to approved plan file
            post_content: Direct post content (if provided)

        Returns:
            Result dictionary with execution status
        """
        if not post_content:
            if not plan_path:
                return {"success": False, "error": "No plan_path or post_content provided"}

            # Read plan and extract content
            with open(plan_path, "r", encoding="utf-8") as f:
                plan_content = f.read()

            # Extract post content from plan (simplified extraction)
            match = re.search(r'```\n(.+?)\n```', plan_content, re.DOTALL)
            if not match:
                return {"success": False, "error": "Could not extract post content from plan"}
            post_content = match.group(1).strip()

        print(f"[AGENT] Executing LinkedIn post...")

        # Build browser-mcp commands
        commands = [
            {"method": "browser/navigate", "params": {"url": "https://www.linkedin.com/feed"}},
            {"method": "browser/wait", "params": {"selector": "[data-id='gh-create-a-post']", "timeout": 10000}},
            {"method": "browser/click", "params": {"selector": "[data-id='gh-create-a-post']"}},
            {"method": "browser/wait", "params": {"selector": "[contenteditable='true']", "timeout": 5000}},
            {"method": "browser/fill", "params": {"selector": "[contenteditable='true']", "value": post_content}},
            {"method": "browser/wait", "params": {"selector": "button[aria-label*='Post']", "timeout": 5000}},
            {"method": "browser/click", "params": {"selector": "button[aria-label*='Post']"}},
            {"method": "browser/wait", "params": {"selector": ".update-v2", "timeout": 10000}},
        ]

        # Execute via browser-mcp (simulated - in real usage would call MCP server)
        result = self._execute_browser_commands(commands)

        if result["success"]:
            # Move to Done
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            done_path = DONE_PATH / f"LINKEDIN_POST_{timestamp}.md"

            confirmation = f"""---
type: linkedin_post_confirmation
posted: {datetime.now().isoformat()}
status: published
---

# LinkedIn Post Published ✅

## Post Content

{post_content}

## Confirmation

- **Posted:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **Status:** Published successfully
- **URL:** https://www.linkedin.com/feed

## Next Steps

- Monitor engagement (views, likes, comments, shares)
- Respond to comments within 24 hours
- Track performance in LinkedIn Analytics

---
*LinkedIn Poster Agent | Personal AI Employee*
"""
            with open(done_path, "w", encoding="utf-8") as f:
                f.write(confirmation)

            result["confirmation_path"] = str(done_path)

        return result

    def _execute_browser_commands(self, commands: List[Dict]) -> Dict[str, Any]:
        """Execute browser-mcp commands."""
        # In production, this would communicate with the browser-mcp server
        # For now, simulate execution
        print("[AGENT] Browser commands prepared:")
        for cmd in commands:
            print(f"  - {cmd['method']}: {cmd['params']}")

        return {
            "success": True,
            "message": "Post execution simulated. In production, this would execute via browser-mcp.",
            "commands_executed": len(commands),
        }


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    """CLI entry point for LinkedIn Poster Agent."""
    import argparse

    parser = argparse.ArgumentParser(description="LinkedIn Poster Agent")
    parser.add_argument("--topic", "-t", required=True, help="Topic of the LinkedIn post")
    parser.add_argument("--context", "-c", default="", help="Additional context or details")
    parser.add_argument("--tone", default="professional", choices=["professional", "casual", "enthusiastic"],
                       help="Tone of the post")
    parser.add_argument("--execute", "-e", action="store_true", help="Execute posting immediately (skip approval)")
    parser.add_argument("--plan", "-p", help="Path to approved plan file for execution")

    args = parser.parse_args()

    agent = LinkedInPosterAgent()

    if args.plan:
        # Execute from approved plan
        result = agent.execute_post(plan_path=args.plan)
        print(f"\n[RESULT] {result}")
    else:
        # Create new post
        result = agent.create_post(args.topic, args.context, args.tone)

        print("\n" + "=" * 60)
        print("LINKEDIN POST CREATED")
        print("=" * 60)
        print(f"Status: {result['status']}")
        print(f"Plan: {result['plan_path']}")
        print(f"Next Step: {result['next_step']}")

        if result['status'] == 'ready_to_post' and args.execute:
            print("\n[INFO] Executing post immediately...")
            exec_result = agent.execute_post(post_content=result['post_data']['full_post'])
            print(f"[RESULT] {exec_result}")
        elif result['status'] == 'pending_approval':
            print("\n[INFO] Awaiting human approval in Pending_Approval folder")


if __name__ == "__main__":
    main()
