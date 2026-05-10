# CLv2 — Continuous Learning v2

This is the **everything-claude-code** project — stripped to CLv2 only. CLv2 is a continuous learning system for AI coding agents (OpenCode). It observes tool usage, extracts behavioral patterns as atomic "instincts", clusters them into skills/commands, and persists them across sessions.

## Architecture

```
.opencode/opencode.json          # OpenCode configuration (plugin, commands, tools)
skills/continuous-learning-v2/   # Core CLv2: SKILL.md + instinct-cli.py
```

## Key Commands

All commands are registered in `.opencode/commands/`:

| Command | Action |
|---------|--------|
| `/instinct-status` | Show learned instincts (project + global) |
| `/learn` | Extract patterns from current session |
| `/learn-eval` | Extract + quality gate + save |
| `/evolve` | Cluster instincts into skills/commands/agents |
| `/instinct-export` | Export instincts to file |
| `/instinct-import` | Import instincts from file/URL |
| `/promote` | Promote project instinct to global scope |
| `/projects` | List known projects |
| `/prune` | Delete expired pending instincts |

## Data Storage

- **Default**: `~/.opencode/homunculus/`
- **Override**: `ECC_DATA_DIR` env var
- **Structure**:
  - `homunculus/projects/<project-id>/instincts/` — project-scoped
  - `homunculus/instincts/personal/` — global personal instincts
  - `homunculus/instincts/inherited/` — imported from others

## Development

```bash
npm install && npm run build   # Build OpenCode plugin
python3 skills/continuous-learning-v2/scripts/instinct-cli.py status  # Quick test
```

## Rules

- Don't modify `skills/continuous-learning-v2/` unless fixing a bug in CLv2 itself
- All paths respect `ECC_DATA_DIR` env var (fallback `~/.opencode`)
- `commands/` are OpenCode command templates — keep detailed enough for agent execution
