#!/bin/bash
# CLv2 Installer — install everything-claude-code to ~/.opencode/
set -euo pipefail

ECC_SRC="$(cd "$(dirname "$0")" && pwd)"
ECC_DEST="${1:-$HOME/.opencode}"

echo "Installing CLv2 to $ECC_DEST ..."

mkdir -p "$ECC_DEST"

# Copy all project files (exclude git, build artifacts)
rsync -a --delete \
  --exclude='.git/' \
  --exclude='node_modules/' \
  --exclude='.opencode/node_modules/' \
  --exclude='.opencode/dist/' \
  "$ECC_SRC/" "$ECC_DEST/"

# Build OpenCode plugin
echo "Building OpenCode plugin ..."
cd "$ECC_DEST/.opencode"
npm install --silent 2>/dev/null
npm run build

echo ""
echo "✓ Installed to $ECC_DEST"
echo ""
echo "Project structure (superpowers-style):"
echo "  package.json             ← npm package (main → plugin)"
echo "  .opencode/opencode.json  ← OpenCode config"
echo "  .opencode/plugins/       ← Plugin with config + bootstrap hooks"
echo "  skills/                  ← Auto-discovered via skill tool"
echo "  commands/                ← 9 CLv2 command templates (root level)"
echo ""
echo "Usage:"
echo "  opencode $ECC_DEST"
echo ""
echo "CLv2 commands:"
echo "  /instinct-status    — Show learned instincts"
echo "  /learn              — Extract patterns from session"
echo "  /learn-eval         — Extract + evaluate + save"
echo "  /evolve             — Cluster instincts into skills"
echo "  /instinct-export    — Export instincts to file"
echo "  /instinct-import    — Import instincts from file/URL"
echo "  /promote            — Promote instincts to global scope"
echo "  /projects           — List known projects"
echo "  /prune              — Delete expired pending instincts"
