#!/bin/bash

# Claude-OpenRouter MCP Server Quick Install Script

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Claude-OpenRouter MCP Server Installer${NC}"
echo "======================================"
echo ""

# Check if we're in the right directory or need to clone
if [ -f "server_openrouter.py" ]; then
    echo -e "${GREEN}Found server files in current directory${NC}"
else
    echo -e "${YELLOW}Cloning repository...${NC}"
    git clone https://github.com/your-username/claude-openrouter-mcp.git
    cd claude-openrouter-mcp
fi

# Get API key
echo ""
echo -e "${YELLOW}Please enter your OpenRouter API key${NC}"
echo -e "${BLUE}Get your key from: https://openrouter.ai/keys${NC}"
echo -n "API Key: "
read -s OPENROUTER_API_KEY
echo ""

# Validate API key format (basic check)
if [ ${#OPENROUTER_API_KEY} -lt 20 ]; then
    echo -e "${RED}Error: API key seems too short${NC}"
    exit 1
fi

# Run setup
echo ""
echo -e "${YELLOW}Running setup...${NC}"
./setup_openrouter.sh "$OPENROUTER_API_KEY"

echo ""
echo -e "${GREEN}Installation complete! 🎉${NC}"