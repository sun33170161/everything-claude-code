---
description: List registered projects and instinct counts
---

# Projects Command

List project registry entries and per-project instinct/observation counts.

## Your Task

1. Locate `instinct-cli.py` (part of ecc plugin, in its skills directory):
   - Use `glob(**/instinct-cli.py)` or `find ~/.cache/opencode -name "instinct-cli.py" 2>/dev/null`
2. Run the located script with the `projects` subcommand

## Usage

```
/projects
```

## What to Do

1. Read `$ECC_DATA_DIR/homunculus/projects.json` (default: `~/.opencode/homunculus/projects.json`)
2. For each project, display: name, id, root, remote, instinct counts, observation count, last seen
3. Also display global instinct totals
