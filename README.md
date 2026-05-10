# CLv2 — Continuous Learning v2 for OpenCode

Instinct-based learning system for OpenCode. Observes tool use, extracts patterns as atomic "instincts", and evolves them into skills, commands, and agents.

## Quick Start

```bash
# Install to ~/.opencode/ (recommended)
./install.sh

# Start opencode with the project
opencode ~/.opencode
```

Or run directly from the project root:

```bash
cd .opencode && npm install && npm run build && cd ..
opencode .
```

## Commands

| Command | Description |
|---------|-------------|
| `/instinct-status` | Show learned instincts (project + global) |
| `/learn` | Extract patterns from current session |
| `/learn-eval` | Extract, evaluate quality gate, then save |
| `/evolve` | Cluster instincts into skills/commands |
| `/instinct-export` | Export instincts to file |
| `/instinct-import <file>` | Import instincts from file |
| `/promote [id]` | Promote project instinct to global scope |
| `/projects` | List known projects and instinct counts |
| `/prune` | Delete expired pending instincts (>30 days) |

## How It Works

1. **Observe** — hooks capture every tool invocation (read, write, edit, bash)
2. **Score** — patterns matching user intent get confidence scores (0.3–0.9)
3. **Evaluate** — session end triggers evaluation; high-confidence patterns become instincts
4. **Evolve** — related instincts cluster into skills/commands/agents
5. **Share** — export/import instincts across projects; promote cross-project patterns to global

## Configuration

### Data Directory

Instinct data is stored at `~/.opencode/homunculus/` by default. Override with:

```bash
ECC_DATA_DIR=/path/to/data opencode
```

### Plugin

The plugin at `.opencode/plugins/ecc-hooks.ts` provides lifecycle hooks via OpenCode's native event system:

- `tool.execute.after` — records tool-use observations for instinct learning
- `session.deleted` — session cleanup
- `session.created` — session lifecycle tracking

## Installation

### Option 1: Install to ~/.opencode/

```bash
./install.sh
opencode ~/.opencode
```

Copies the entire project (minus `.git`, `node_modules/`) to `~/.opencode/` and builds the OpenCode plugin. Custom destination:

```bash
./install.sh /custom/path
opencode /custom/path
```

### Option 2: Run in-place

```bash
cd .opencode && npm install && npm run build && cd ..
opencode .
```

## Project Structure

```
everything-claude-code/
├── package.json                     # npm package (main → plugin entry)
├── CLAUDE.md                        # AI agent configuration
├── README.md
├── install.sh                       # Install to ~/.opencode/
├── commands/                        # 9 CLv2 command templates (root level, like superpowers)
├── skills/                          # Auto-discovered via skill tool
│   └── continuous-learning-v2/
│       ├── SKILL.md                 # Full CLv2 documentation
│       └── scripts/
│           └── instinct-cli.py      # Core instinct CLI
└── .opencode/                       # Minimal (superpowers-style)
    ├── opencode.json                # Config only (no commands, no instructions)
    ├── plugins/ecc-hooks.ts         # Plugin: config.skills.paths + bootstrap injection
    ├── tools/                       # Custom tools (tied to plugin)
    └── dist/                        # Compiled plugin output
```

## Architecture (Superpowers-style)

This project follows the same plugin architecture as [superpowers](https://github.com/obra/superpowers):

| Feature | Approach |
|---------|----------|
| **Skills discovery** | Plugin registers `skills/` path via `config.skills.paths` — all SKILL.md files auto-discovered by `skill` tool |
| **Bootstrap** | Plugin injects CLv2 context into first user message via `experimental.chat.messages.transform` — replaces `instructions` field |
| **Commands** | OpenCode command templates at `.opencode/commands/` |
| **Installation** | `install.sh` copies to target directory; or use `opencode <path>` |
| **npm package** | Root `package.json` with `main` pointing to compiled plugin |
