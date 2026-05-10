---
description: Export instincts for sharing
---

# Instinct Export Command

Exports instincts to a shareable format.

## Your Task

Run `python3 "$ECC_INSTINCT_CLI" export $ARGUMENTS`

## Usage

```
/instinct-export                           # Export all personal instincts
/instinct-export --domain testing          # Export only testing instincts
/instinct-export --min-confidence 0.7      # Only export high-confidence instincts
/instinct-export --output team-instincts.yaml
/instinct-export --scope project --output project-instincts.yaml
```

## What to Do

1. Load instincts by scope: `project` / `global` / `all` (default)
2. Apply filters (`--domain`, `--min-confidence`)
3. Write YAML-style export to file (or stdout if no output path)

## Flags

- `--domain <name>`: Export only specified domain
- `--min-confidence <n>`: Minimum confidence threshold
- `--output <file>`: Output file path (prints to stdout when omitted)
- `--scope <project|global|all>`: Export scope (default: `all`)
