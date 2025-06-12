#!/bin/bash

# Claude-OpenRouter MCP Server Setup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

# Check Claude Code CLI
if ! command -v claude &> /dev/null; then
    echo -e "${RED}Error: Claude Code CLI is not installed${NC}"
    echo "Please install from: https://github.com/anthropics/claude-code"
    exit 1
fi

# Hardcoded API key for local use
OPENROUTER_API_KEY="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"

# Optional: still allow command line override
if [ ! -z "$1" ]; then
    OPENROUTER_API_KEY="$1"
fi

# Create installation directory
INSTALL_DIR="$HOME/.claude-mcp-servers/openrouter-collab"
echo -e "${YELLOW}Creating installation directory...${NC}"
mkdir -p "$INSTALL_DIR"

# Copy files
echo -e "${YELLOW}Copying files...${NC}"
cp server_openrouter.py "$INSTALL_DIR/"
cp requirements.txt "$INSTALL_DIR/"

# Update API key in server
echo -e "${YELLOW}Configuring API key...${NC}"
sed -i.bak "s/YOUR_API_KEY_HERE/$OPENROUTER_API_KEY/g" "$INSTALL_DIR/server_openrouter.py"
rm "$INSTALL_DIR/server_openrouter.py.bak"

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
cd "$INSTALL_DIR"
python3 -m venv venv

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
./venv/bin/pip install -r requirements.txt

# Remove any existing MCP configuration
echo -e "${YELLOW}Removing any existing MCP configuration...${NC}"
claude mcp remove openrouter-collab 2>/dev/null || true

# Register with Claude Code globally
echo -e "${YELLOW}Registering MCP server with Claude Code (global scope)...${NC}"
claude mcp add --scope user openrouter-collab "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/server_openrouter.py"

echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo -e "${GREEN}The OpenRouter MCP server has been installed and registered.${NC}"
echo ""
echo "Available models:"
echo "  - Claude 3 (Opus, Sonnet, Haiku)"
echo "  - GPT-4, GPT-4 Turbo, GPT-3.5 Turbo"
echo "  - Gemini Pro, Gemini Pro Vision"
echo "  - Mixtral 8x7B"
echo "  - Llama 3 (70B, 8B)"
echo "  - PaLM 2"
echo "  - Command R+"
echo "  - Qwen 72B"
echo ""
echo "Available tools in Claude:"
echo "  - ask_ai: Ask any AI model"
echo "  - ai_code_review: Get code reviews from any model"
echo "  - ai_brainstorm: Brainstorm with any model"
echo "  - list_models: See all available models"
echo "  - get_token_usage: Track token usage and costs"
echo ""
echo -e "${YELLOW}Note: Restart Claude Code for the changes to take effect.${NC}"