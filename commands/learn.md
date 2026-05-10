---
description: Extract patterns and learnings from current session
---

# Learn Command

Extract patterns, learnings, and reusable insights from the current session.

## Trigger

Run `/learn` at any point during a session when you've solved a non-trivial problem.

## What to Extract

1. **Error Resolution Patterns** — root cause + fix + reusability
2. **Debugging Techniques** — non-obvious steps, tool combinations
3. **Workarounds** — library quirks, API limitations, version-specific fixes
4. **Project-Specific Patterns** — conventions, architecture decisions

## Output Format

Save to `$ECC_DATA_DIR/skills/learned/[pattern-name].md` (default: `~/.opencode/skills/learned/`):

```markdown
# [Descriptive Pattern Name]

**Extracted:** [Date]
**Context:** [When this applies]

## Problem
[What this solves]

## Solution
[The pattern/technique/workaround]

## Example
[Code example if applicable]

## When to Use
[Trigger conditions]
```

## Process

1. Review the session for extractable patterns
2. Identify the most valuable/reusable insight
3. Draft the skill file
4. Ask user to confirm before saving
5. Save to `$ECC_DATA_DIR/skills/learned/`

## Notes

- Don't extract trivial fixes (typos, simple syntax errors)
- Don't extract one-time issues (specific API outages)
- Focus on patterns that will save time in future sessions
- Keep skills focused — one pattern per skill
