---
description: Import instincts from external sources
---

# Instinct Import Command

Import instincts from local file paths or HTTP(S) URLs.

## Your Task

1. Locate `instinct-cli.py` (part of ecc plugin, in its skills directory):
   - Use `glob(**/instinct-cli.py)` or `find ~/.cache/opencode -name "instinct-cli.py" 2>/dev/null`
2. Run the located script with the `import` subcommand and passed flags

## Usage

```
/instinct-import team-instincts.yaml
/instinct-import https://github.com/org/repo/instincts.yaml
/instinct-import team-instincts.yaml --dry-run
/instinct-import team-instincts.yaml --scope global --force
```

## What to Do

1. Fetch the instinct file (local path or URL)
2. Parse and validate the format
3. Check for duplicates with existing instincts
4. Merge or add new instincts
5. Save to inherited instincts directory:
   - Project scope: `$ECC_DATA_DIR/homunculus/projects/<project-id>/instincts/inherited/`
   - Global scope: `$ECC_DATA_DIR/homunculus/instincts/inherited/`

## Merge Behavior

- Higher-confidence import → update candidate
- Equal/lower-confidence import → skipped
- User confirms unless `--force`

## Flags

- `--dry-run`: Preview without importing
- `--force`: Skip confirmation prompt
- `--min-confidence <n>`: Only import instincts above threshold
- `--scope <project|global>`: Target scope (default: `project`)
