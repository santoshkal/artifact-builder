#!/bin/bash
# Simplest possible pull and run for Python MCP servers
set -e

# Default settings
REGISTRY="${REGISTRY:-ghcr.io}"
REPO="${1:-capten-ai/mise-tasks-mcp}"
TAG="${2:-latest}"

# Pull OCI artifact
echo "Pulling $REGISTRY/$REPO:$TAG..."
if ! command -v oras &> /dev/null; then
    echo "Installing ORAS..."
    curl -sL https://github.com/oras-project/oras/releases/download/v1.2.0/oras_1.2.0_linux_amd64.tar.gz | tar xz
    sudo mv oras /usr/local/bin/ 2>/dev/null || mv oras ~/.local/bin/
fi

# Pull and extract
oras pull "$REGISTRY/$REPO:$TAG"
tar xzf bundle.tar.gz

# Install and run
WHEEL=$(ls *.whl | head -1)
PACKAGE=$(basename "$WHEEL" | cut -d'-' -f1 | tr '-' '_')

echo "Installing $WHEEL..."
pip install "$WHEEL" --quiet

echo "Running: python -m $PACKAGE"
python -m "$PACKAGE"