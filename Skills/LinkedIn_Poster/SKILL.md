---
name: LinkedIn_Poster
description: Creates and publishes professional LinkedIn posts with hashtags, call-to-action, and image suggestions. Includes human-in-loop approval for sensitive content.
version: 1.0.0
author: Personal AI Employee
capabilities:
  - linkedin_posting
  - content_creation
  - hashtag_generation
  - human_approval_workflow
tools_required:
  - browser-mcp
  - email-mcp (optional, for notifications)
when_to_use:
  - User wants to share professional updates on LinkedIn
  - User has content that needs to be formatted as a LinkedIn post
  - User wants to announce achievements, projects, or business updates
  - User wants to engage with LinkedIn network through posts
when_not_to_use:
  - Personal/private content not suitable for professional network
  - Content requiring legal/compliance review (route to Pending_Approval)
  - Sensitive company information (requires human approval)
  - Political or controversial topics (requires human approval)
output_format:
  - Plan.md first (always)
  - Pending_Approval/LINKEDIN_POST_*.md (if sensitive)
  - Direct post (if approved or non-sensitive)
---

# LinkedIn Poster Skill

## Overview

This skill creates and publishes professional LinkedIn posts. It follows a structured workflow:
1. **Plan** - Create a Plan.md with post content, hashtags, and image suggestions
2. **Review** - Human-in-loop approval for sensitive content
3. **Execute** - Post to LinkedIn using browser-mcp

## Instructions

### Core Principles

1. **Always create professional business content** - Maintain a professional tone suitable for LinkedIn's business network
2. **Add relevant hashtags** - Include 3-7 targeted hashtags for discoverability
3. **Include call-to-action (CTA)** - Every post should have a clear CTA
4. **Suggest images** - Recommend visual content to increase engagement
5. **Human-in-loop for sensitive content** - Route sensitive posts to Pending_Approval

### Post Structure

Every LinkedIn post should include:

```
[Hook/Opening] - Grab attention in first 2-3 lines

[Body] - Main content, story, or announcement

[Value] - What readers gain from this post

[Call-to-Action] - What you want readers to do

[Hashtags] - 3-7 relevant hashtags
```

### Hashtag Guidelines

- Use 3-7 hashtags per post
- Mix of broad (#Business, #Technology) and niche (#YourIndustry)
- Include 1-2 trending hashtags when relevant
- Avoid overused spammy hashtags

### Call-to-Action Examples

- "What's your experience with this? Share below! 👇"
- "Repost to help your network ♻️"
- "Follow me for more insights on [topic]"
- "Drop a comment with your thoughts 💬"
- "Click the link in comments to learn more 🔗"

### Image Suggestions

Always suggest visual content:
- **Charts/Graphs** - For data-driven posts
- **Team photos** - For company culture posts
- **Product screenshots** - For feature announcements
- **Infographics** - For educational content
- **Professional headshots** - For personal branding

## Workflow

### Step 1: Analyze Request

Understand what the user wants to post:
- Topic/theme
- Target audience
- Desired outcome
- Any specific messaging

### Step 2: Create Plan.md

Always create a Plan.md first with:

```markdown
# LinkedIn Post Plan

## Content
[Full post text with formatting]

## Hashtags
[#Hashtag1, #Hashtag2, ...]

## Call-to-Action
[Specific CTA]

## Image Suggestion
[Description of recommended image]

## Posting Schedule
[Recommended time to post]

## Sensitivity Check
- [ ] Contains company information
- [ ] Contains financial data
- [ ] Mentions clients/partners
- [ ] Potentially controversial
- [ ] Requires legal review

## Approval Required
[Yes/No based on sensitivity check]
```

### Step 3: Sensitivity Check

Route to Pending_Approval if ANY of these are true:
- ✅ Contains confidential company information
- ✅ Contains financial/revenue data
- ✅ Mentions specific clients or partners
- ✅ Discusses layoffs, hiring freezes, or sensitive HR topics
- ✅ Political or controversial opinions
- ✅ Legal or compliance implications
- ✅ Crisis communications

If sensitive → Create `Pending_Approval/LINKEDIN_POST_YYYYMMDD_HHMMSS.md`

### Step 4: Human Approval (if required)

Wait for human to:
1. Review the Pending_Approval file
2. Move to Approved/ or modify as needed
3. Signal approval

### Step 5: Execute Post

Use browser-mcp to publish:

```
1. Navigate to linkedin.com/feed
2. Click "Start a post" button
3. Fill in the post content
4. (Optional) Upload suggested image
5. Click "Post"
6. Verify post published successfully
```

### Step 6: Confirm & Log

Create confirmation in Done/ folder with:
- Post content
- Post URL
- Timestamp
- Engagement tracking note

## Tool Usage

### browser-mcp Commands

| Command | Purpose |
|---------|---------|
| `browser/navigate` | Go to linkedin.com/feed |
| `browser/click` | Click "Start a post" button |
| `browser/fill` | Enter post content |
| `browser/screenshot` | Verify post appearance |
| `linkedin/post` | Direct post creation (if available) |

### Example browser-mcp Sequence

```json
{"method": "browser/navigate", "params": {"url": "https://www.linkedin.com/feed"}}
{"method": "browser/wait", "params": {"selector": "[data-id='gh-create-a-post']"}}
{"method": "browser/click", "params": {"selector": "[data-id='gh-create-a-post']"}}
{"method": "browser/wait", "params": {"selector": "[contenteditable='true']"}}
{"method": "browser/fill", "params": {"selector": "[contenteditable='true']", "value": "[POST CONTENT]"}}
{"method": "browser/click", "params": {"selector": "button[aria-label*='Post']"}}
```

## File Structure

```
Skills/LinkedIn_Poster/
├── SKILL.md              # This file
├── Plan.md               # Current post plan
└── templates/
    └── post_template.md  # Post template

Pending_Approval/
└── LINKEDIN_POST_*.md    # Posts awaiting approval

Approved/
└── LINKEDIN_POST_*.md    # Approved posts

Done/
└── LINKEDIN_POST_*.md    # Published posts with confirmation
```

## Examples

### Example 1: Product Launch (Non-sensitive)

**User:** "Post about our new feature launch"

**Plan.md:**
```markdown
# LinkedIn Post Plan

## Content
🚀 Exciting news! We just launched [Feature Name]!

After months of development, our team is proud to introduce a game-changing solution that helps businesses [key benefit].

✨ What's new:
• Feature 1
• Feature 2  
• Feature 3

Try it today and let us know what you think!

## Hashtags
[#ProductLaunch, #Innovation, #TechNews, #SaaS, #BusinessGrowth]

## Call-to-Action
"Click the link in comments to start your free trial! 🔗"

## Image Suggestion
Product screenshot showing the new feature dashboard, or team celebration photo

## Sensitivity Check
- [ ] Contains company information → Generic only
- [ ] Contains financial data → No
- [ ] Mentions clients/partners → No
- [ ] Potentially controversial → No
- [ ] Requires legal review → No

## Approval Required: No
```

### Example 2: Funding Announcement (Sensitive)

**User:** "Post about our Series B funding"

**Plan.md:**
```markdown
# LinkedIn Post Plan

## Content
[Draft content about funding round]

## Sensitivity Check
- [x] Contains company information → Financial data
- [x] Contains financial data → Funding amount
- [ ] Mentions clients/partners → No
- [ ] Potentially controversial → No
- [x] Requires legal review → Investor communications

## Approval Required: YES
```

**Action:** Create `Pending_Approval/LINKEDIN_POST_20250217_143022.md`

## Quality Checklist

Before posting, verify:
- [ ] Professional tone maintained
- [ ] No spelling/grammar errors
- [ ] Hashtags are relevant (3-7)
- [ ] Clear call-to-action included
- [ ] Image suggestion provided
- [ ] Sensitivity check completed
- [ ] Approval obtained if required
- [ ] Post length under 3000 characters
- [ ] First 2 lines are compelling (preview text)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Post button not clickable | Wait for content to be filled, check character count |
| Image upload fails | Check file size, format (JPG/PNG), retry |
| Login required | Use linkedin/login capability first |
| Post doesn't appear | Take screenshot, verify network, retry |

## Related Skills

- **Content_Writer** - For long-form content creation
- **Social_Media_Manager** - For multi-platform posting
- **Analytics_Reporter** - For post-performance tracking

---

*LinkedIn Poster Skill v1.0.0 | Personal AI Employee*
