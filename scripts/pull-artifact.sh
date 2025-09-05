#!/usr/bin/env bash
# Script to pull mise-tasks-mcp executable from OCI registry using ORAS

set -e

# Default values
REGISTRY="${REGISTRY:-ghcr.io}"
REPOSITORY="${REPOSITORY:-capten-ai/mise-tasks-mcp}"
VERSION="${VERSION:-latest}"
OUTPUT_DIR="${OUTPUT_DIR:-./bin}"

# Detect platform
detect_platform() {
    local os=$(uname -s | tr '[:upper:]' '[:lower:]')
    local arch=$(uname -m)
    
    case "$os" in
        linux)
            os="linux"
            ;;
        darwin)
            os="darwin"
            ;;
        mingw*|msys*|cygwin*)
            os="windows"
            ;;
        *)
            echo "Unsupported OS: $os"
            exit 1
            ;;
    esac
    
    case "$arch" in
        x86_64|amd64)
            arch="amd64"
            ;;
        aarch64|arm64)
            arch="arm64"
            ;;
        *)
            echo "Unsupported architecture: $arch"
            exit 1
            ;;
    esac
    
    echo "${os}-${arch}"
}

# Function to check if ORAS is installed
check_oras() {
    if ! command -v oras &> /dev/null; then
        echo "ORAS CLI not found. Installing..."
        install_oras
    else
        echo "ORAS CLI found: $(oras version)"
    fi
}

# Function to install ORAS
install_oras() {
    local version="1.2.0"
    local os=$(uname -s | tr '[:upper:]' '[:lower:]')
    local arch=$(uname -m)
    
    case "$arch" in
        x86_64|amd64)
            arch="amd64"
            ;;
        aarch64|arm64)
            arch="arm64"
            ;;
    esac
    
    local url="https://github.com/oras-project/oras/releases/download/v${version}/oras_${version}_${os}_${arch}.tar.gz"
    
    echo "Downloading ORAS from $url..."
    curl -sL "$url" | tar -xz -C /tmp
    
    if [ -w "/usr/local/bin" ]; then
        mv /tmp/oras /usr/local/bin/
    else
        echo "Moving ORAS to current directory. Add it to your PATH."
        mv /tmp/oras ./
    fi
}

# Function to pull the artifact
pull_artifact() {
    local platform=$1
    local artifact_name="mise-tasks-mcp-${platform}"
    local output_file="${OUTPUT_DIR}/mise-tasks-mcp"
    
    if [[ "$platform" == "windows-amd64" ]]; then
        output_file="${output_file}.exe"
    fi
    
    echo "Pulling artifact for platform: $platform"
    echo "Registry: ${REGISTRY}/${REPOSITORY}-${platform}:${VERSION}"
    
    # Create output directory if it doesn't exist
    mkdir -p "${OUTPUT_DIR}"
    
    # Pull the blob using ORAS
    oras blob fetch \
        "${REGISTRY}/${REPOSITORY}-${platform}:${VERSION}" \
        --output "${output_file}"
    
    # Make executable (except for Windows)
    if [[ "$platform" != "windows-amd64" ]]; then
        chmod +x "${output_file}"
    fi
    
    echo "Artifact downloaded to: ${output_file}"
}

# Main function
main() {
    echo "=== mise-tasks-mcp Artifact Downloader ==="
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --registry)
                REGISTRY="$2"
                shift 2
                ;;
            --repository)
                REPOSITORY="$2"
                shift 2
                ;;
            --version)
                VERSION="$2"
                shift 2
                ;;
            --output-dir)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            --platform)
                PLATFORM="$2"
                shift 2
                ;;
            --help)
                cat << EOF
Usage: $0 [OPTIONS]

Options:
    --registry REGISTRY       Container registry (default: ghcr.io)
    --repository REPO        Repository name (default: capten-ai/mise-tasks-mcp)
    --version VERSION        Version tag (default: latest)
    --output-dir DIR         Output directory (default: ./bin)
    --platform PLATFORM      Platform (auto-detected if not specified)
    --help                   Show this help message

Examples:
    # Pull latest version for current platform
    $0

    # Pull specific version
    $0 --version v1.0.0

    # Pull for specific platform
    $0 --platform linux-arm64

    # Pull from custom registry
    $0 --registry docker.io --repository myorg/mise-tasks-mcp
EOF
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Check for ORAS
    check_oras
    
    # Detect platform if not specified
    if [ -z "$PLATFORM" ]; then
        PLATFORM=$(detect_platform)
        echo "Detected platform: $PLATFORM"
    fi
    
    # Pull the artifact
    pull_artifact "$PLATFORM"
    
    echo ""
    echo "=== Setup Complete ==="
    echo "You can now run: ${OUTPUT_DIR}/mise-tasks-mcp"
}

# Run main function
main "$@"