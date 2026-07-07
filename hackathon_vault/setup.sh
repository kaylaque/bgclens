#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Second Brain Vault — Setup Script  ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

# --- Step 1: Create CLAUDE.md from template ---
if [ -f "CLAUDE.md" ]; then
  echo -e "${GREEN}✓${NC} CLAUDE.md already exists, skipping."
else
  cp CLAUDE.example.md CLAUDE.md
  echo -e "${GREEN}✓${NC} Created CLAUDE.md from CLAUDE.example.md"
fi
echo ""

# --- Step 2: Prompt for personal info ---
echo "Let's set up your profile for Claude Code."
echo ""

read -p "$(echo -e ${CYAN}?${NC}) What is your name?           " NAME
read -p "$(echo -e ${CYAN}?${NC}) Describe yourself (e.g. researcher, student, engineer): " ROLE
read -p "$(echo -e ${CYAN}?${NC}) What are your focus areas?   " FOCUS

# --- Step 3: Replace placeholders ---
# Cross-platform sed (works on macOS & Linux)
sed -i.bak "s/__ROLES__/$ROLE/g" CLAUDE.md
sed -i.bak "s/__FOCUS_AREAS__/$FOCUS/g" CLAUDE.md
rm -f CLAUDE.md.bak

echo ""
echo -e "${GREEN}✓${NC} Profile written to CLAUDE.md"

# Also replace in session description in the Who section
if [ -n "$NAME" ]; then
  cat > .claude-whoami << EOF
name: $NAME
roles: $ROLE
focus: $FOCUS
EOF
  echo -e "${GREEN}✓${NC} Saved identity to .claude-whoami"
fi

echo ""

# --- Step 4: Create index.md if not exists ---
if [ -f "index.md" ]; then
  echo -e "${GREEN}✓${NC} index.md already exists, skipping."
else
  cp index.example.md index.md
  # Replace placeholder date
  TODAY=$(date +%Y-%m-%d)
  sed -i.bak "s/YYYY-MM-DD/$TODAY/g" index.md
  rm -f index.md.bak
  echo -e "${GREEN}✓${NC} Created index.md from template"
fi

echo ""

# --- Step 5: Clean up example files (optional, suggest) ---
if [ -d "examples" ]; then
  echo -e "${CYAN}Tip:${NC} Delete the examples/ directory once you understand the note format:"
  echo "     rm -rf examples/"
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Setup complete!                     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo "Next steps:"
echo "  1. Open this folder in Obsidian"
echo "  2. Run 'claude' to start your first session"
echo "  3. Drop a PDF or article into raw/ and Claude will ingest it"
echo ""
