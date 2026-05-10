---
description: Promote project instincts to global scope
---

# Promote Command

Promote instincts from project scope to global scope (CLv2 instinct system).

## Your Task

Run:

```bash
python3 skills/continuous-learning-v2/scripts/instinct-cli.py promote [instinct-id] [--force] [--dry-run]
```

## Usage

```
/promote                      # Auto-detect promotion candidates
/promote --dry-run            # Preview auto-promotion candidates
/promote --force              # Promote all qualified candidates without prompt
/promote grep-before-edit     # Promote one specific instinct from current project
```

## What to Do

1. Detect current project
2. If `instinct-id` is provided, promote only that instinct
3. Otherwise, find cross-project candidates that appear in 2+ projects above confidence threshold
4. Write promoted instincts to `$ECC_DATA_DIR/homunculus/instincts/personal/` with `scope: global`
