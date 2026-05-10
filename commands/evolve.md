---
description: Analyze instincts and suggest or generate evolved structures
---

# Evolve Command

Analyzes instincts and clusters related ones into higher-level structures.

## Your Task

1. Locate `instinct-cli.py` (part of ecc plugin, in its skills directory):
   - Use `glob(**/instinct-cli.py)` or `find ~/.cache/opencode -name "instinct-cli.py" 2>/dev/null`
2. Run the located script with the `evolve` subcommand and passed flags

## Usage

```
/evolve                    # Analyze all instincts and suggest evolutions
/evolve --generate         # Also generate files under evolved/{skills,commands,agents}
```

## What Gets Created

- **Commands**: When instincts describe user-invoked actions (e.g., "when user says create table")
- **Skills**: When instincts describe auto-triggered behaviors (e.g., "prefer functional style")
- **Agents**: When instincts describe complex multi-step processes (e.g., debugging workflows)

## What to Do

1. Read project + global instincts (project takes precedence on ID conflicts)
2. Group instincts by trigger/domain patterns
3. Identify skill/command/agent candidates
4. Show promotion candidates (project -> global)
5. If `--generate`, write files to:
   - Project: `$ECC_DATA_DIR/homunculus/projects/<project-id>/evolved/`
   - Global: `$ECC_DATA_DIR/homunculus/evolved/`

## Flags

- `--generate`: Generate evolved files in addition to analysis output
