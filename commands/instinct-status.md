---
description: Show learned instincts (project + global) with confidence
---

# Instinct Status Command

Show instinct status (CLv2 instinct system): $ARGUMENTS

## Your Task

Run `python3 "$ECC_INSTINCT_CLI" status`

## What to Do

1. Detect current project context (git remote/path hash)
2. Read project instincts from `$ECC_DATA_DIR/homunculus/projects/<project-id>/instincts/` (defaults to `~/.opencode` or overridden by `ECC_DATA_DIR` env var)
3. Read global instincts from `$ECC_DATA_DIR/homunculus/instincts/`
4. Merge with precedence rules (project overrides global when IDs collide)
5. Display grouped by domain with confidence bars and observation stats

## Behavior Notes

- Output includes both project-scoped and global instincts.
- Project instincts override global instincts when IDs conflict.
- Output is grouped by domain with confidence bars.
- This command does not support extra filters in v2.1.
