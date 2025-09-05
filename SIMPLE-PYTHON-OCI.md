# Simplified Python OCI Packaging

You're absolutely right - we were overcomplicating things! Here's the **simplest possible approach** using Python best practices.

## The Simple Truth

Every Python package should be runnable with:
```bash
python -m package_name
```

This is a Python best practice that we should follow. No need for complex wrapper scripts!

## Minimal Requirements

For this to work, your Python package needs:

1. **A `__main__.py` file** in your package:
```python
# src/your_package/__main__.py
from .server import main

if __name__ == "__main__":
    main()
```

2. **Standard `pyproject.toml`** (which you already have)

That's it! No complex entry point detection needed.

## Super Simple Workflow

### Build and Push (30 lines total!)

```yaml
name: Simple Python OCI Build
on:
  push:
    tags: ['v*']

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      
      - name: Build and Push
        run: |
          # Build wheel
          uv build --wheel --out-dir dist/
          
          # Create bundle
          cd dist
          tar czf bundle.tar.gz *.whl
          
          # Push to registry
          oras push ghcr.io/${{ github.repository }}:${{ github.ref_name }} bundle.tar.gz
```

### Pull and Run (10 lines!)

```bash
#!/bin/bash
# Pull artifact
oras pull ghcr.io/org/repo:latest
tar xzf bundle.tar.gz

# Install wheel
pip install *.whl

# Run with python -m
PACKAGE=$(ls *.whl | cut -d'-' -f1 | tr '-' '_')
python -m "$PACKAGE"
```

## Even Simpler: Direct Wheel Distribution

Skip OCI entirely and use GitHub releases:

```bash
# Upload wheel to GitHub release
gh release create v1.0.0 dist/*.whl

# Users download and run
wget https://github.com/org/repo/releases/download/v1.0.0/package.whl
pip install package.whl
python -m package_name
```

## Why This Works

1. **Standard Python:** Uses `python -m` which is how Python packages should be run
2. **No Magic:** Just a wheel file, no complex scripts
3. **Universal:** Works with ANY Python package that has `__main__.py`
4. **Simple:** Users understand `pip install` and `python -m`

## Comparison

| Approach | Lines of Code | Complexity | Compatibility |
|----------|--------------|------------|---------------|
| Our Complex Version | 500+ | High | Needs detection |
| Simple Version | 50 | Low | Just needs `__main__.py` |
| Direct GitHub Release | 20 | Minimal | Universal |

## For Your MCP Servers

All your Python MCP servers can be simplified:

1. **Ensure `__main__.py` exists:**
```python
# src/package_name/__main__.py
from . import main  # or from .server import main
if __name__ == "__main__":
    main()
```

2. **Build wheel:**
```bash
uv build --wheel
```

3. **Distribute:**
```bash
# Option A: OCI Registry
oras push ghcr.io/org/package:latest dist/*.whl

# Option B: GitHub Release  
gh release upload v1.0.0 dist/*.whl

# Option C: PyPI
twine upload dist/*.whl
```

4. **Users run:**
```bash
# From OCI
oras pull ghcr.io/org/package:latest
pip install *.whl
python -m package_name

# From GitHub
pip install https://github.com/org/repo/releases/download/v1.0.0/package.whl
python -m package_name

# From PyPI
pip install package-name
python -m package_name
```

## The Absolute Simplest

For maximum simplicity, just use PyPI:

```bash
# Developer publishes
uv build --wheel
twine upload dist/*.whl

# User installs and runs
pip install your-mcp-server
python -m your_mcp_server
```

No OCI, no ORAS, no complexity - just standard Python packaging!

## Recommendation

For your use case:

1. **If you need OCI:** Use the simple 50-line workflow
2. **If you don't need OCI:** Use GitHub releases or PyPI
3. **Always:** Ensure packages have `__main__.py` and can run with `python -m`

This follows Python best practices and is much simpler than what we built before. Sometimes the simplest solution is the best solution!

## Testing

To verify any package works with this approach:

```bash
# Build wheel
uv build --wheel --out-dir dist/

# Install locally
pip install dist/*.whl

# Test running with -m
PACKAGE_NAME=$(ls dist/*.whl | head -1 | xargs basename | cut -d'-' -f1 | tr '-' '_')
python -m "$PACKAGE_NAME"
```

If this works, the package is ready for simple distribution!