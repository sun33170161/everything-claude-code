---
name: continuous-learning-v2
description: Instinct-based learning system that observes sessions via hooks, creates atomic instincts with confidence scoring, and evolves them into skills/commands/agents. v2.1 adds project-scoped instincts. v2.2 adds confidence decay, auto-deprecation, user profiles, session-end analysis, and prompt injection.
origin: ECC
version: 2.2.0
---

# Continuous Learning v2.2 - Instinct-Based Architecture

An advanced learning system that turns your Claude Code sessions into reusable knowledge through atomic "instincts" - small learned behaviors with confidence scoring.

**v2.1** adds **project-scoped instincts** — React patterns stay in your React project, Python conventions stay in your Python project, and universal patterns (like "always validate input") are shared globally.

## When to Activate

- Setting up automatic learning from Claude Code sessions
- Configuring instinct-based behavior extraction via hooks
- Tuning confidence thresholds for learned behaviors
- Reviewing, exporting, or importing instinct libraries
- Evolving instincts into full skills, commands, or agents
- Managing project-scoped vs global instincts
- Promoting instincts from project to global scope
- Analyzing observations for pattern extraction with `/analyze`
- Viewing and managing user identity profile

## What's New in v2.1

| Feature | v2.0 | v2.1 |
|---------|------|------|
| Storage | Global (~/.opencode/homunculus/) | Project-scoped (projects/<hash>/) |
| Scope | All instincts apply everywhere | Project-scoped + global |
| Detection | None | git remote URL / repo path |
| Promotion | N/A | Project → global when seen in 2+ projects |
| Commands | 4 (status/evolve/export/import) | 6 (+promote/projects) |
| Cross-project | Contamination risk | Isolated by default |

## What's New in v2.2

| Feature | v2.1 | v2.2 |
|---------|------|------|
| Confidence Decay | None (static confidence) | Exponential decay with `last_observed` tracking |
| Auto-Deprecation | Manual via /prune | Automatic low-confidence → deprecated/ directory |
| User Profile | None | identity.json + domain: user-profile |
| Session-End Analysis | Manual via /learn | `analyze` subcommand + session.deleted hook |
| Prompt Injection | None | High-confidence instinct + identity injection at session start |
| LLM Evolve | Python heuristic only | Config-driven LLM clustering (config.json evolve.llm_enabled) |
| Config | Observer-only in config.json | Unified config.json with evolve, injection, decay, analysis |
| Identity System | None | identity.json with technical_level, preferences, expertise |

## What's New in v2 (vs v1)

| Feature | v1 | v2 |
|---------|----|----|
| Observation | Stop hook (session end) | PreToolUse/PostToolUse (100% reliable) |
| Analysis | Main context | Background agent (Haiku) |
| Granularity | Full skills | Atomic "instincts" |
| Confidence | None | 0.3-0.9 weighted |
| Evolution | Direct to skill | Instincts -> cluster -> skill/command/agent |
| Sharing | None | Export/import instincts |

## The Instinct Model

An instinct is a small learned behavior:

```yaml
---
id: prefer-functional-style
trigger: "when writing new functions"
confidence: 0.7
domain: "code-style"
source: "session-observation"
scope: project
project_id: "a1b2c3d4e5f6"
project_name: "my-react-app"
---

# Prefer Functional Style

## Action
Use functional patterns over classes when appropriate.

## Evidence
- Observed 5 instances of functional pattern preference
- User corrected class-based approach to functional on 2025-01-15
```

**Properties:**
- **Atomic** -- one trigger, one action
- **Confidence-weighted** -- 0.3 = tentative, 0.9 = near certain
- **Domain-tagged** -- code-style, testing, git, debugging, workflow, etc.
- **Evidence-backed** -- tracks what observations created it
- **Scope-aware** -- `project` (default) or `global`

## How It Works

```
Session Activity (in a git repo)
      |
      | Hooks capture prompts + tool use (100% reliable)
      | + detect project context (git remote / repo path)
      v
+---------------------------------------------+
|  projects/<project-hash>/observations.jsonl  |
|   (prompts, tool calls, outcomes, project)   |
+---------------------------------------------+
      |
      | Observer agent reads (background, Haiku)
      v
+---------------------------------------------+
|          PATTERN DETECTION                   |
|   * User corrections -> instinct             |
|   * Error resolutions -> instinct            |
|   * Repeated workflows -> instinct           |
|   * Scope decision: project or global?       |
+---------------------------------------------+
      |
      | Creates/updates
      v
+---------------------------------------------+
|  projects/<project-hash>/instincts/personal/ |
|   * prefer-functional.yaml (0.7) [project]   |
|   * use-react-hooks.yaml (0.9) [project]     |
+---------------------------------------------+
|  instincts/personal/  (GLOBAL)               |
|   * always-validate-input.yaml (0.85) [global]|
|   * grep-before-edit.yaml (0.6) [global]     |
+---------------------------------------------+
      |
      | /evolve clusters + /promote
      v
+---------------------------------------------+
|  projects/<hash>/evolved/ (project-scoped)   |
|  evolved/ (global)                           |
|   * commands/new-feature.md                  |
|   * skills/testing-workflow.md               |
|   * agents/refactor-specialist.md            |
+---------------------------------------------+
```

## Project Detection

The system automatically detects your current project:

1. **`CLAUDE_PROJECT_DIR` env var** (highest priority)
2. **`git remote get-url origin`** -- hashed to create a portable project ID (same repo on different machines gets the same ID)
3. **`git rev-parse --show-toplevel`** -- fallback using repo path (machine-specific)
4. **Global fallback** -- if no project is detected, instincts go to global scope

Each project gets a 12-character hash ID (e.g., `a1b2c3d4e5f6`). A registry file at `~/.opencode/homunculus/projects.json` maps IDs to human-readable names.

## Quick Start

### 1. Enable Observation Hooks

**If installed as a plugin** (recommended):

No extra `settings.json` hook block is required. Claude Code v2.1+ auto-loads the plugin `hooks/hooks.json`, and `observe.sh` is already registered there.

If you previously copied `observe.sh` into `~/.opencode/settings.json`, remove that duplicate `PreToolUse` / `PostToolUse` block. Duplicating the plugin hook causes double execution and `${CLAUDE_PLUGIN_ROOT}` resolution errors because that variable is only available inside plugin-managed `hooks/hooks.json` entries.

**If installed manually** to `~/.opencode/skills`, add this to your `~/.opencode/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "~/.opencode/skills/continuous-learning-v2/hooks/observe.sh"
      }]
    }],
    "PostToolUse": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "~/.opencode/skills/continuous-learning-v2/hooks/observe.sh"
      }]
    }]
  }
}
```

### 2. Initialize Directory Structure

The system creates directories automatically on first use, but you can also create them manually:

```bash
# Global directories
mkdir -p ~/.opencode/homunculus/{instincts/{personal,inherited},evolved/{agents,skills,commands},projects}

# Project directories are auto-created when the hook first runs in a git repo
```

### 3. Use the Instinct Commands

```bash
/instinct-status     # Show learned instincts (project + global)
/evolve              # Cluster related instincts into skills/commands
/instinct-export     # Export instincts to file
/instinct-import     # Import instincts from others
/promote             # Promote project instincts to global scope
/projects            # List all known projects and their instinct counts
```

## Commands

| Command | Description |
|---------|-------------|
| `/instinct-status` | Show all instincts with confidence, config, identity, and deprecated info |
| `/evolve` | Cluster instincts into skills/commands (LLM or heuristic) |
| `/instinct-export` | Export instincts (filterable by scope/domain) |
| `/instinct-import <file>` | Import instincts with scope control |
| `/promote [id]` | Promote project instinct to global scope |
| `/projects` | List known projects and instinct counts |
| `/prune` | Delete expired pending instincts (>30 days) |

## Configuration

Edit `config.json` to control all aspects of the system:

```json
{
  "version": "2.2",
  "evolve": {
    "llm_enabled": true,
    "llm_timeout_seconds": 60
  },
  "injection": {
    "max_chars": 2000,
    "min_confidence": 0.7,
    "enabled": true
  },
  "decay": {
    "rate_per_30days": 0.8,
    "high_confidence_rate": 0.9,
    "deprecation_threshold": 0.3
  },
  "analysis": {
    "enabled": true,
    "timeout_ms": 10000,
    "min_observations": 20
  },
  "observer": {
    "enabled": false,
    "run_interval_minutes": 5,
    "min_observations_to_analyze": 20
  }
}
```

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| `evolve` | `llm_enabled` | `true` | Use LLM for clustering (vs heuristic) |
| `evolve` | `llm_timeout_seconds` | `60` | Timeout for LLM clustering operations |
| `injection` | `max_chars` | `2000` | Character limit for prompt injection |
| `injection` | `min_confidence` | `0.7` | Minimum confidence for injection |
| `injection` | `enabled` | `true` | Enable prompt injection at session start |
| `decay` | `rate_per_30days` | `0.8` | Decay rate for instincts < 0.9 confidence |
| `decay` | `high_confidence_rate` | `0.9` | Decay rate for instincts ≥ 0.9 confidence |
| `decay` | `deprecation_threshold` | `0.3` | Threshold for auto-deprecation |
| `analysis` | `enabled` | `true` | Enable session-end analysis |
| `analysis` | `timeout_ms` | `10000` | Timeout for session-end analysis hook |
| `analysis` | `min_observations` | `20` | Minimum observations for analysis |
| `observer` | `enabled` | `false` | Enable background observer agent |
| `observer` | `run_interval_minutes` | `5` | How often observer analyzes observations |
| `observer` | `min_observations_to_analyze` | `20` | Minimum observations before analysis runs |

The config.json is auto-created with defaults on first CLI invocation.

## File Structure

```
~/.opencode/homunculus/
+-- config.json              # Unified configuration (v2.2 schema)
+-- identity.json            # User identity profile
+-- projects.json            # Registry: project hash -> name/path/remote
+-- observations.jsonl       # Global observations (fallback)
+-- instincts/
|   +-- personal/            # Global auto-learned instincts
|   +-- inherited/           # Global imported instincts
|   +-- deprecated/          # Auto-deprecated low-confidence instincts
|   +-- pending/             # Pending instincts from analysis
+-- evolved/
|   +-- agents/              # Global generated agents
|   +-- skills/              # Global generated skills
|   +-- commands/            # Global generated commands
+-- projects/
    +-- a1b2c3d4e5f6/        # Project hash
        +-- project.json
        +-- observations.jsonl
        +-- observations.archive/
        +-- instincts/
        |   +-- personal/
        |   +-- inherited/
        |   +-- deprecated/
        |   +-- pending/
        +-- evolved/
            +-- skills/
            +-- commands/
            +-- agents/
```

## Scope Decision Guide

| Pattern Type | Scope | Examples |
|-------------|-------|---------|
| Language/framework conventions | **project** | "Use React hooks", "Follow Django REST patterns" |
| File structure preferences | **project** | "Tests in `__tests__`/", "Components in src/components/" |
| Code style | **project** | "Use functional style", "Prefer dataclasses" |
| Error handling strategies | **project** | "Use Result type for errors" |
| Security practices | **global** | "Validate user input", "Sanitize SQL" |
| General best practices | **global** | "Write tests first", "Always handle errors" |
| Tool workflow preferences | **global** | "Grep before Edit", "Read before Write" |
| Git practices | **global** | "Conventional commits", "Small focused commits" |

## Instinct Promotion (Project -> Global)

When the same instinct appears in multiple projects with high confidence, it's a candidate for promotion to global scope.

**Auto-promotion criteria:**
- Same instinct ID in 2+ projects
- Average confidence >= 0.8

**How to promote:**

```bash
# Promote a specific instinct
python3 instinct-cli.py promote prefer-explicit-errors

# Auto-promote all qualifying instincts
python3 instinct-cli.py promote

# Preview without changes
python3 instinct-cli.py promote --dry-run
```

The `/evolve` command also suggests promotion candidates.

## Confidence Scoring

Confidence evolves over time:

| Score | Meaning | Behavior |
|-------|---------|----------|
| 0.3 | Tentative | Suggested but not enforced |
| 0.5 | Moderate | Applied when relevant |
| 0.7 | Strong | Auto-approved for application |
| 0.9 | Near-certain | Core behavior |

**Confidence increases** when:
- Pattern is repeatedly observed
- User doesn't correct the suggested behavior
- Similar instincts from other sources agree

**Confidence decreases** when:
- User explicitly corrects the behavior
- Pattern isn't observed for extended periods
- Contradicting evidence appears

## Confidence Decay

Instinct confidence decays over time when an instinct hasn't been observed.

**Formula**: `decayed = original * (rate_per_30days ** (days_since_last_observed / 30))`

- Default decay rate: 0.8 per 30 days
- High-confidence instincts (≥0.9) decay at 0.9 rate (slower)
- Floor at 0.0 (never negative)
- Decay is display-only — original confidence value is preserved in the file

**Flags**:
- `--no-decay`: Show original confidence values without decay
- `--decay`: (default) Show decayed confidence values

**last_observed tracking**: Each instinct file has a `last_observed` field (ISO 8601 timestamp) that is updated on every status read. Backward compatibility: files without `last_observed` use file modification time as default.

## Auto-Deprecation

Instincts with confidence below the deprecation threshold are automatically moved to the `deprecated/` directory.

**Threshold**: `deprecation_threshold` (default: 0.3)

**Behavior**:
- On every `status` and `analyze` run, eligible instincts are moved from `personal/` to `deprecated/`
- User-profile domain instincts are NEVER auto-deprecated (they represent user preferences, not behavioral patterns)
- Deprecated instincts are preserved for audit (never deleted)
- `--show-deprecated` flag displays deprecated instincts
- Default status display shows deprecated count in footer but not the instincts themselves

## User Profile & Identity

The system supports a user profile that personalizes AI behavior.

**identity.json** at `~/.opencode/homunculus/identity.json`:
```json
{
  "version": "1.0",
  "updated": "2026-05-11T00:00:00Z",
  "name": "(optional user name)",
  "technical_level": "beginner | intermediate | advanced | expert",
  "preferences": {
    "communication_style": "concise | detailed | mixed",
    "response_language": "en | zh | auto",
    "likes_type_hints": true,
    "likes_comments": "minimal | moderate | thorough"
  },
  "expertise_areas": ["python", "typescript", "react"]
}
```

**Features**:
- Auto-created with defaults on first CLI invocation
- `cmd_status --show-identity` displays identity profile
- `python3 instinct-cli.py identity --format inject` outputs compact text for prompt injection
- `domain: user-profile` instincts are NEVER auto-deprecated
- Privacy: identity.json is NEVER exported or shared

## Session-End Analysis

The `analyze` subcommand processes observations and creates pending instincts.

**Usage**: `python3 instinct-cli.py analyze [--dry-run] [--all-projects] [--min-observations N]`

**How it works**:
1. Reads `observations.jsonl` for the current project
2. Requires minimum observation count (default: 20, configurable via `--min-observations`)
3. Groups observations by tool (read, edit, write, bash, etc.)
4. Tools with ≥3 observations get pending instincts created
5. Confidence formula: `min(0.9, 0.3 + 0.6 * (count / 100))`

**Flags**:
- `--dry-run`: Preview without creating files
- `--all-projects`: Analyze all registered projects
- `--no-interactive`: Suppress prompts (for hook use)

**Auto-trigger**: The `session.deleted` hook calls analyze automatically (10s timeout, best-effort). Controlled by `ECC_SESSION_ANALYSIS_ENABLED` env var.

## Auto Prompt Injection

At session start, high-confidence instincts and identity are injected into the AI prompt.

**Injection Order**:
1. CLv2 bootstrap (SKILL.md content)
2. Identity block (`python3 instinct-cli.py identity --format inject`) — only if non-default identity exists
3. Instinct block — high-confidence instincts (≥0.7 confidence)

**Instinct Injection Details**:
- Formatted as `## Active Instincts for {project_name}` with bullet points
- Each bullet: `- {domain} ({confidence}%): {trigger}`
- 2000 character limit enforced (highest-confidence instincts included first)
- `###ECC_INSTINCTS_END###` marker prevents double-injection
- Falls back gracefully if Python/instinct-cli.py is unavailable

## LLM-Driven Evolve

The `/evolve` command now supports config-driven LLM clustering (default: on).

**Configuration**:
- Set `evolve.llm_enabled` in `config.json`:
  - `true` (default): Uses AI to semantically cluster instincts
  - `false`: Falls back to Python heuristic clustering
- Runtime override: `ECC_EVOLVE_LLM_ENABLED=false`

**LLM Path**:
1. AI reads instincts via `python3 instinct-cli.py status --format json`
2. AI clusters instincts semantically (by meaning, not just domain tags)
3. Names each cluster, writes descriptions, suggests triggers
4. Results displayed with "LLM Clustering Results" label
5. If LLM fails → automatic fallback to heuristic

**Heuristic Path**:
- Runs `python3 instinct-cli.py evolve` unchanged
- Groups by domain/trigger patterns
- Results displayed with "Heuristic Clustering Results" label

## Why Hooks vs Skills for Observation?

> "v1 relied on skills to observe. Skills are probabilistic -- they fire ~50-80% of the time based on Claude's judgment."

Hooks fire **100% of the time**, deterministically. This means:
- Every tool call is observed
- No patterns are missed
- Learning is comprehensive

## Backward Compatibility

v2.2 is fully compatible with v2.1, v2.0, and v1:
- Existing global instincts in `~/.opencode/homunculus/instincts/` still work as global instincts
- Existing `~/.opencode/skills/learned/` skills from v1 still work
- Stop hook still runs (but now also feeds into v2)
- Gradual migration: run both in parallel
- `last_observed` field is optional — defaults to file mtime for backward compatibility

## Privacy

- Observations stay **local** on your machine
- Project-scoped instincts are isolated per project
- Only **instincts** (patterns) can be exported — not raw observations
- No actual code or conversation content is shared
- You control what gets exported and promoted

## Related

- [ECC-Tools GitHub App](https://github.com/apps/ecc-tools) - Generate instincts from repo history
- Homunculus - Community project that inspired the v2 instinct-based architecture (atomic observations, confidence scoring, instinct evolution pipeline)
- [The Longform Guide](https://x.com/affaanmustafa/status/2014040193557471352) - Continuous learning section

---

*Instinct-based learning: teaching Claude your patterns, one project at a time.*
