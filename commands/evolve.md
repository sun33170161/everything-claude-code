---
description: Analyze instincts using LLM (default) or heuristic clustering
---

# Evolve Command

Analyzes instincts and clusters related ones into higher-level structures.
Uses LLM-based semantic clustering by default (controlled by config.json).

## Configuration

Set `evolve.llm_enabled` in `~/.opencode/homunculus/config.json`:

- `true` (default): Uses AI to semantically cluster instincts (recommended)
- `false`: Falls back to Python heuristic clustering

Override at runtime: `ECC_EVOLVE_LLM_ENABLED=false`

## Your Task

Follow these steps exactly:

### Step 1: Check Configuration

1. Read `~/.opencode/homunculus/config.json`
   - If file does not exist, use default: `llm_enabled = true`
   - If file exists, check `evolve.llm_enabled` field
   - If field is missing, use default: `llm_enabled = true`

2. Check environment variable `ECC_EVOLVE_LLM_ENABLED`
   - If set, use this value ("true" or "false")
   - This overrides the config file setting

3. Store the final decision: `use_llm` (boolean)

### Step 2: Get Instincts

Run: `python3 "$ECC_INSTINCT_CLI" status --no-decay --format json`

Parse the JSON output. Each instinct has:
- `id`: Unique identifier
- `trigger`: When the instinct applies
- `confidence`: 0.3-0.9 confidence score
- `domain`: Category (code-style, workflow, debugging, etc.)
- `scope`: project or global
- `content`: The instinct content/description

If the command fails or returns empty, display: "No instincts found to analyze."

### Step 3: Cluster (LLM Path)

If `use_llm` is `true`:

1. Format instincts for LLM clustering with this prompt structure:

```
I have {N} instincts. Each instinct has:
- id, trigger, domain, confidence, content

Please analyze and cluster these instincts semantically:

1. Group related instincts into clusters based on MEANING and PATTERN, not just domain tags
2. Name each cluster descriptively (what pattern unifies the instincts)
3. Write a skill description for each cluster
4. Suggest trigger conditions for when this skill should activate

Return as JSON:
{
  "clusters": [
    {
      "name": "descriptive-cluster-name",
      "description": "What these instincts have in common and when to apply",
      "trigger": "When to use this skill",
      "instinct_ids": ["id1", "id2", "id3"],
      "avg_confidence": 0.75
    }
  ]
}
```

2. Use your own LLM (current session) to process the clustering prompt

3. Parse the JSON response:
   - If parsing fails or JSON is invalid → fall back to **Step 3 (Heuristic Path)**
   - If LLM returns error or empty response → fall back to **Step 3 (Heuristic Path)**

4. If `--generate` flag is present:
   - For each cluster, create an evolved skill file
   - Save to:
     - Project instincts: `$ECC_DATA_DIR/homunculus/projects/<project-id>/evolved/skills/`
     - Global instincts: `$ECC_DATA_DIR/homunculus/evolved/skills/`
   - Filename: `{cluster-name}.md`
   - Format:
```markdown
---
name: {cluster-name}
description: "{description}"
evolved_from: [{instinct_ids}]
avg_confidence: {avg_confidence}
---

# {Cluster Name}

## Trigger
{trigger}

## Description
{description}

## Source Instincts
{list of instinct IDs and their confidences}
```

### Step 3 (alt): Cluster (Heuristic Path)

If `use_llm` is `false` OR if LLM path failed:

1. Run: `python3 "$ECC_INSTINCT_CLI" evolve $ARGUMENTS`

2. Capture and display the output

### Step 4: Show Results

Display clusters with clear labeling:

**If LLM path was used successfully:**
```
## LLM Clustering Results

### Cluster 1: {name}
- **Description**: {description}
- **Instincts**: {count} instincts (list: id1, id2, id3)
- **Average Confidence**: {avg_confidence}
- **Trigger**: {trigger}

[Additional clusters...]

_Total instincts analyzed: {N}_
_Configuration: LLM clustering enabled_
```

**If Heuristic path was used:**
```
## Heuristic Clustering Results

[Output from instinct-cli.py evolve]

_Configuration: Heuristic clustering (llm_enabled: false)_
```

**If fallback occurred:**
```
## LLM Clustering Results

[Attempted LLM clustering but it failed...]

---

## Heuristic Clustering Results (Fallback)

[Output from instinct-cli.py evolve]

_Note: LLM clustering failed, fell back to heuristic method_
```

### Step 5: Summary

End with a brief summary:
- Total instincts analyzed
- Number of clusters found
- Which clustering method was used
- If `--generate` was used, list files created

## Usage

```
/evolve                    # LLM cluster (or heuristic if llm_enabled: false)
/evolve --generate         # Also generate evolved files
```

## Flags

- `--generate`: Generate evolved files in addition to analysis output

## Examples

### Default LLM clustering
```
/evolve
```
Uses LLM to semantically cluster instincts.

### Force heuristic clustering
```bash
# Set env var before running
ECC_EVOLVE_LLM_ENABLED=false /evolve
```

### Generate evolved files
```
/evolve --generate
```
Clusters instincts AND writes skill files to `evolved/skills/`.

## Implementation Notes

- LLM clustering groups by semantic meaning, not just domain tags
- Heuristic clustering uses rule-based grouping by domain and trigger patterns
- LLM failures are graceful — always falls back to heuristic
- Generated files include metadata about source instincts and confidence
- Project-scoped instincts are clustered separately from global ones
