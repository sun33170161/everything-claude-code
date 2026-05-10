---
description: Delete pending instincts older than 30 days that were never promoted
---

# Prune Pending Instincts

Remove expired pending instincts that were auto-generated but never reviewed or promoted.

## Your Task

Run `python3 "$ECC_INSTINCT_CLI" prune $ARGUMENTS`

## Usage

```
/prune                    # Delete instincts older than 30 days
/prune --max-age 60      # Custom age threshold (days)
/prune --dry-run         # Preview without deleting
```

## What to Do

1. Scan pending instincts in `$ECC_DATA_DIR/homunculus/`
2. Delete instincts whose creation date exceeds the max age threshold (default: 30 days)
3. Report: how many deleted, how much space freed
