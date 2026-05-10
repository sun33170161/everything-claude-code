---
description: Show learned instincts (project + global) with confidence
---

# Instinct Status Command

Show instinct status (CLv2 instinct system): $ARGUMENTS

## Your Task

1. Locate `instinct-cli.py` (part of ecc plugin, in its skills directory):
   - Use `glob(**/instinct-cli.py)` or `find ~/.cache/opencode -name "instinct-cli.py" 2>/dev/null`
2. Run the located script with the `status` subcommand

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
