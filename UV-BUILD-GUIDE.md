# Building Standalone MCP Servers with UV

## The Challenge

Python MCP servers with binary dependencies (like `rpds-py` used by `jsonschema`) cannot be fully bundled into zipapps because Python's zipapp format doesn't support loading compiled `.so` files from within the archive.

## Solution: UV Tool Installation

The best approach for creating portable MCP servers is using `uv tool`, which creates isolated environments with all dependencies properly installed.

## Method 1: Direct UV Tool Installation (Recommended)

This is the simplest and most reliable method:

```bash
# Install from local project
uv tool install --from /path/to/mcp-server package-name

# Install from GitHub
uv tool install --from git+https://github.com/org/mcp-server package-name

# Install from PyPI (if published)
uv tool install package-name
```

The tool is installed to `~/.local/bin/` and can be run directly:
```bash
mise-tasks-mcp  # Runs the MCP server
```

## Method 2: Portable UV Bundle

For distribution without requiring users to run install commands:

### Create Distribution Bundle

```bash
#!/usr/bin/env bash
# build-portable.sh

PROJECT_DIR="/path/to/mcp-server"
OUTPUT_DIR="./portable-mcp"

# Create bundle directory
mkdir -p "$OUTPUT_DIR"

# Build wheel
uv build --wheel --out-dir "$OUTPUT_DIR/wheels" "$PROJECT_DIR"

# Create installer script
cat > "$OUTPUT_DIR/install.sh" << 'EOF'
#!/usr/bin/env bash
set -e

# Install uv if needed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Install the MCP server
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WHEEL=$(ls "$SCRIPT_DIR/wheels"/*.whl | head -1)

echo "Installing MCP server..."
uv tool install --from "$WHEEL" mise-tasks-mcp

echo "✅ Installation complete!"
echo "Run with: mise-tasks-mcp"
EOF

chmod +x "$OUTPUT_DIR/install.sh"

# Create runner script (no installation needed)
cat > "$OUTPUT_DIR/run.sh" << 'EOF'
#!/usr/bin/env bash
set -e

# Check/install uv
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Run directly without installation
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WHEEL=$(ls "$SCRIPT_DIR/wheels"/*.whl | head -1)

uv run --from "$WHEEL" mise-tasks-mcp "$@"
EOF

chmod +x "$OUTPUT_DIR/run.sh"

echo "Bundle created in $OUTPUT_DIR"
```

Users can then:
- Run `./install.sh` once to install permanently
- Or run `./run.sh` to execute without installation

## Method 3: GitHub Actions with OCI Distribution

Complete workflow for building and pushing MCP servers as OCI artifacts:

### Workflow Features
- Builds wheel with `uv build`
- Creates multiple runner scripts (bash, Python)
- Packages as OCI artifact with ORAS
- Supports pulling and running without Docker

### Complete Workflow

See `.github/workflows/build-oci-uv.yml` for the full implementation. Key steps:

```yaml
name: Build and Push MCP Server as OCI Artifact

on:
  push:
    tags: ['v*']

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      
      - name: Build wheel with uv
        run: |
          uv build --wheel --out-dir dist/
      
      - name: Create runner scripts
        run: |
          # Create run-mcp-server.sh (auto-installs uv)
          cat > dist/run-mcp-server.sh << 'EOF'
          #!/usr/bin/env bash
          if ! command -v uv &> /dev/null; then
              curl -LsSf https://astral.sh/uv/install.sh | sh
              export PATH="$HOME/.local/bin:$PATH"
          fi
          WHEEL=$(ls "$(dirname "$0")/*.whl" | head -1)
          exec uv run --from "$WHEEL" mise-tasks-mcp "$@"
          EOF
          chmod +x dist/run-mcp-server.sh
      
      - name: Create bundle and push with ORAS
        run: |
          # Create tarball bundle
          cd dist && tar czf mcp-server-bundle.tar.gz *.whl *.sh
          
          # Push as OCI artifact
          oras push ${{ env.REGISTRY }}/${{ env.REPOSITORY }}:${{ github.ref_name }} \
            --artifact-type "application/vnd.mcp.server.v1+tar" \
            mcp-server-bundle.tar.gz:application/tar+gzip
```

### Pulling and Running the Artifact

Users can pull and run with a single script:

```bash
# One-liner to pull and run
curl -sSL https://raw.githubusercontent.com/org/repo/main/scripts/pull-and-run-oci.sh | bash

# Or with options
./pull-and-run-oci.sh --version v1.0.0 --mode install
```

The pull script (`scripts/pull-and-run-oci.sh`):
- Auto-installs ORAS and uv if needed
- Pulls the OCI artifact from the registry
- Extracts and runs the MCP server
- Supports multiple modes (run, install, both)

## Method 4: Docker-less Deployment

For systems where you want a single command installation:

```bash
# One-liner installation from GitHub
curl -sSL https://github.com/org/mcp-server/releases/download/v1.0.0/install.sh | bash

# Or using uv directly
uv tool install --from git+https://github.com/org/mcp-server mise-tasks-mcp
```

## Comparison of Methods

| Method | Pros | Cons | Use Case |
|--------|------|------|----------|
| UV Tool Install | Simple, handles all dependencies | Requires uv | Development & personal use |
| Portable Bundle | Self-contained, includes installer | Larger size | Distribution to users |
| OCI Distribution | Version control, registry benefits | Requires ORAS | Enterprise deployment |
| Direct GitHub | One command install | Requires internet | Open source projects |

## Working with Binary Dependencies

For MCP servers with binary dependencies:

1. **Always use wheels** - Build wheels with `uv build --wheel`
2. **Don't use zipapp** - It can't handle `.so` files
3. **Use uv tool** - It properly manages binary dependencies
4. **Consider Docker** - For complex binary dependencies

## Example: Complete Build Script

```bash
#!/usr/bin/env python3
# build-mcp-portable.py

import subprocess
import sys
from pathlib import Path

def build_portable_mcp(project_path: Path):
    """Build a portable MCP server bundle."""
    
    output_dir = Path("portable-mcp")
    output_dir.mkdir(exist_ok=True)
    
    # Build wheel
    print("Building wheel...")
    subprocess.run([
        "uv", "build", "--wheel", 
        "--out-dir", str(output_dir / "wheels"),
        str(project_path)
    ], check=True)
    
    # Create scripts
    create_installer_script(output_dir)
    create_runner_script(output_dir)
    
    print(f"✅ Portable bundle created in {output_dir}")
    print(f"   - Install: {output_dir}/install.sh")
    print(f"   - Run directly: {output_dir}/run.sh")

def create_installer_script(output_dir: Path):
    """Create installation script."""
    script = output_dir / "install.sh"
    script.write_text('''#!/usr/bin/env bash
set -e

if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

WHEEL=$(ls "$(dirname "$0")/wheels"/*.whl | head -1)
uv tool install --from "$WHEEL" mise-tasks-mcp
echo "✅ Installed! Run with: mise-tasks-mcp"
''')
    script.chmod(0o755)

def create_runner_script(output_dir: Path):
    """Create direct runner script."""
    script = output_dir / "run.sh"
    script.write_text('''#!/usr/bin/env bash
set -e

if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

WHEEL=$(ls "$(dirname "$0")/wheels"/*.whl | head -1)
uv run --from "$WHEEL" mise-tasks-mcp "$@"
''')
    script.chmod(0o755)

if __name__ == "__main__":
    project = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    build_portable_mcp(project)
```

## OCI Artifact Details

### What Gets Packaged

The OCI artifact contains a tarball bundle with:
- Python wheel (`.whl` file) 
- `run-mcp-server.sh` - Bash runner that auto-installs uv
- `install-mcp-server.sh` - Global installer script
- `mcp-server.py` - Python fallback runner
- `metadata.json` - Build information

### Registry Structure

Two artifact types are pushed:
1. **Complete bundle**: `ghcr.io/org/repo:version` - Full package with all scripts
2. **Wheel only**: `ghcr.io/org/repo:wheel-version` - Just the Python wheel

### Pull Examples

```bash
# Pull complete bundle
oras pull ghcr.io/capten-ai/mise-tasks-mcp:latest
tar xzf mcp-server-bundle.tar.gz
./run-mcp-server.sh

# Pull wheel only
oras pull ghcr.io/capten-ai/mise-tasks-mcp:wheel-latest
uv run --from *.whl mise-tasks-mcp

# Pull with authentication (private registry)
oras login ghcr.io -u USERNAME
oras pull ghcr.io/org/private-mcp:v1.0.0
```

## Key Takeaways

1. **UV is the best tool** for Python MCP server distribution
2. **Binary dependencies** require proper package management (not zipapp)
3. **Wheels are portable** when used with uv
4. **Multiple distribution methods** available depending on needs
5. **ORAS integration** works well for OCI artifact storage
6. **GitHub Actions workflow** automates the entire build and push process
7. **Pull scripts** make consumption simple for end users

## Testing Your Build

```bash
# Test local installation
uv tool install --from . mise-tasks-mcp
mise-tasks-mcp --help

# Test from wheel
uv run --from dist/*.whl mise-tasks-mcp --help

# Test portable bundle
./portable-mcp/run.sh --help
```