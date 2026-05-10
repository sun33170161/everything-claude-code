---
description: List registered projects and instinct counts
---

# Projects Command

List project registry entries and per-project instinct/observation counts.

## Your Task

Run `python3 "$ECC_INSTINCT_CLI" projects`

## Usage

```
/projects
```

## What to Do

1. Read `$ECC_DATA_DIR/homunculus/projects.json` (default: `~/.opencode/homunculus/projects.json`)
2. For each project, display: name, id, root, remote, instinct counts, observation count, last seen
3. Also display global instinct totals
