#!/usr/bin/env bash
# Pull and run MCP server from OCI registry
set -e

# Default values
REGISTRY="${REGISTRY:-ghcr.io}"
REPOSITORY="${REPOSITORY:-capten-ai/mise-tasks-mcp}"
VERSION="${VERSION:-latest}"
INSTALL_MODE="${INSTALL_MODE:-run}"  # run, install, or both

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

# Function to check and install ORAS
install_oras() {
    if command -v oras &> /dev/null; then
        print_info "ORAS is already installed: $(oras version)"
        return 0
    fi
    
    print_info "Installing ORAS..."
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
    
    curl -sL "$url" | tar -xz -C /tmp
    
    if [ -w "/usr/local/bin" ]; then
        sudo mv /tmp/oras /usr/local/bin/
    else
        mkdir -p "$HOME/.local/bin"
        mv /tmp/oras "$HOME/.local/bin/"
        export PATH="$HOME/.local/bin:$PATH"
        print_warning "ORAS installed to ~/.local/bin. Add to PATH if needed."
    fi
    
    print_success "ORAS installed successfully"
}

# Function to check and install uv
install_uv() {
    if command -v uv &> /dev/null; then
        print_info "uv is already installed: $(uv --version)"
        return 0
    fi
    
    print_info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    print_success "uv installed successfully"
}

# Function to pull OCI artifact
pull_artifact() {
    local artifact_ref="$1"
    
    print_info "Pulling artifact from: $artifact_ref"
    
    # Create temporary directory for download
    local work_dir=$(mktemp -d)
    cd "$work_dir"
    
    # Pull the artifact
    if ! oras pull "$artifact_ref"; then
        print_error "Failed to pull artifact"
        rm -rf "$work_dir"
        return 1
    fi
    
    # Check what we got
    if [ -f "mcp-server-bundle.tar.gz" ]; then
        print_info "Extracting bundle..."
        tar xzf mcp-server-bundle.tar.gz
        rm mcp-server-bundle.tar.gz
    elif ls *.whl &> /dev/null; then
        print_info "Found wheel file"
    else
        print_error "No recognizable artifacts found"
        ls -la
        rm -rf "$work_dir"
        return 1
    fi
    
    echo "$work_dir"
}

# Function to run MCP server
run_mcp_server() {
    local work_dir="$1"
    
    cd "$work_dir"
    
    # Check for runner scripts
    if [ -f "run-mcp-server.sh" ]; then
        print_info "Running MCP server using provided script..."
        exec ./run-mcp-server.sh
    elif [ -f "mcp-server.py" ]; then
        print_info "Running MCP server using Python script..."
        exec python3 mcp-server.py
    elif ls *.whl &> /dev/null; then
        print_info "Running MCP server from wheel..."
        local wheel_file=$(ls *.whl | head -1)
        local package_name=$(basename "$wheel_file" | cut -d'-' -f1 | tr '_' '-')
        exec uv run --from "$wheel_file" "$package_name"
    else
        print_error "No runnable artifacts found"
        return 1
    fi
}

# Function to install MCP server
install_mcp_server() {
    local work_dir="$1"
    
    cd "$work_dir"
    
    # Check for installer script
    if [ -f "install-mcp-server.sh" ]; then
        print_info "Installing MCP server using provided script..."
        ./install-mcp-server.sh
    elif ls *.whl &> /dev/null; then
        print_info "Installing MCP server from wheel..."
        local wheel_file=$(ls *.whl | head -1)
        local package_name=$(basename "$wheel_file" | cut -d'-' -f1 | tr '_' '-')
        uv tool install --from "$wheel_file" "$package_name"
        print_success "Installed! Run with: $package_name"
    else
        print_error "No installable artifacts found"
        return 1
    fi
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Pull and run MCP server from OCI registry

Options:
    --registry REGISTRY    OCI registry (default: ghcr.io)
    --repository REPO      Repository path (default: capten-ai/mise-tasks-mcp)
    --version VERSION      Version tag (default: latest)
    --mode MODE           Mode: run, install, or both (default: run)
    --output-dir DIR      Save artifacts to directory instead of temp
    --help                Show this help message

Examples:
    # Run directly from registry (default)
    $0

    # Install the tool globally
    $0 --mode install

    # Pull specific version
    $0 --version v1.0.0

    # Pull from different registry
    $0 --registry docker.io --repository myorg/my-mcp

    # Save artifacts locally
    $0 --output-dir ./mcp-artifacts --mode run

Environment Variables:
    REGISTRY      - OCI registry URL
    REPOSITORY    - Repository path
    VERSION       - Version tag
    INSTALL_MODE  - Installation mode

Full artifact reference format:
    REGISTRY/REPOSITORY:VERSION
    Example: ghcr.io/capten-ai/mise-tasks-mcp:latest
EOF
}

# Main function
main() {
    local output_dir=""
    
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
            --mode)
                INSTALL_MODE="$2"
                shift 2
                ;;
            --output-dir)
                output_dir="$2"
                shift 2
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Build full artifact reference
    ARTIFACT_REF="${REGISTRY}/${REPOSITORY}:${VERSION}"
    
    print_info "MCP Server OCI Artifact Fetcher"
    echo "================================"
    print_info "Registry:   $REGISTRY"
    print_info "Repository: $REPOSITORY"  
    print_info "Version:    $VERSION"
    print_info "Mode:       $INSTALL_MODE"
    echo "================================"
    
    # Install required tools
    install_oras
    install_uv
    
    # Pull the artifact
    work_dir=$(pull_artifact "$ARTIFACT_REF")
    
    if [ $? -ne 0 ]; then
        print_error "Failed to pull artifact"
        exit 1
    fi
    
    # If output directory specified, copy artifacts there
    if [ -n "$output_dir" ]; then
        mkdir -p "$output_dir"
        cp -r "$work_dir"/* "$output_dir/"
        print_success "Artifacts saved to: $output_dir"
        work_dir="$output_dir"
    fi
    
    # Handle installation mode
    case "$INSTALL_MODE" in
        run)
            run_mcp_server "$work_dir"
            ;;
        install)
            install_mcp_server "$work_dir"
            # Clean up temp directory if used
            if [ -z "$output_dir" ]; then
                rm -rf "$work_dir"
            fi
            ;;
        both)
            install_mcp_server "$work_dir"
            print_info "Starting MCP server..."
            run_mcp_server "$work_dir"
            ;;
        *)
            print_error "Invalid mode: $INSTALL_MODE"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"