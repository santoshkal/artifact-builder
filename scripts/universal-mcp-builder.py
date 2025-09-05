#!/usr/bin/env python3
"""
Universal MCP Server Builder for Python Projects
Builds standalone executables for any Python-based MCP Server
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

class MCPServerBuilder:
    """Universal builder for Python MCP Servers."""
    
    def __init__(self, project_path: Path, output_dir: Path = None):
        self.project_path = Path(project_path).resolve()
        self.output_dir = output_dir or self.project_path / "dist"
        self.build_dir = self.project_path / "build"
        self.temp_dir = None
        
    def detect_project_info(self) -> Dict[str, any]:
        """Detect project information from pyproject.toml or setup.py."""
        info = {
            "name": "mcp-server",
            "version": "1.0.0",
            "entry_point": None,
            "dependencies": [],
            "python_version": "3.12"
        }
        
        # Check for pyproject.toml
        pyproject_path = self.project_path / "pyproject.toml"
        if pyproject_path.exists():
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib
            
            with open(pyproject_path, 'rb') as f:
                data = tomllib.load(f)
                project = data.get('project', {})
                info['name'] = project.get('name', info['name'])
                info['version'] = project.get('version', info['version'])
                info['dependencies'] = project.get('dependencies', [])
                
                # Try to find entry point
                scripts = project.get('scripts', {})
                if scripts:
                    # Get first script entry
                    first_script = list(scripts.values())[0]
                    info['entry_point'] = first_script
                
                # Check for Python version requirement
                requires_python = project.get('requires-python', '')
                if requires_python:
                    # Extract version number (e.g., ">=3.12" -> "3.12")
                    import re
                    match = re.search(r'(\d+\.\d+)', requires_python)
                    if match:
                        info['python_version'] = match.group(1)
        
        # Auto-detect entry point if not found
        if not info['entry_point']:
            info['entry_point'] = self._detect_entry_point()
        
        return info
    
    def _detect_entry_point(self) -> Optional[str]:
        """Auto-detect the entry point for the MCP server."""
        # Common patterns for MCP server entry points
        patterns = [
            ('src/*/server.py', 'main'),
            ('*/server.py', 'main'),
            ('src/*/__main__.py', 'main'),
            ('*/__main__.py', 'main'),
            ('main.py', 'main'),
            ('app.py', 'main'),
        ]
        
        for pattern, func in patterns:
            files = list(self.project_path.glob(pattern))
            if files:
                # Get module path
                file_path = files[0]
                rel_path = file_path.relative_to(self.project_path)
                
                # Convert to module notation
                if rel_path.parts[0] == 'src':
                    module_parts = rel_path.parts[1:]
                else:
                    module_parts = rel_path.parts
                
                module = '.'.join(module_parts).replace('.py', '')
                module = module.replace('.__main__', '')
                
                return f"{module}:{func}"
        
        return None
    
    def check_requirements(self) -> bool:
        """Check if required tools are installed."""
        print("Checking requirements...")
        
        required_tools = ['python3', 'pip']
        missing = []
        
        for tool in required_tools:
            if not shutil.which(tool):
                missing.append(tool)
        
        if missing:
            print(f"❌ Missing required tools: {', '.join(missing)}")
            return False
        
        # Check for uv (optional but recommended)
        if not shutil.which('uv'):
            print("⚠️  uv not found. Installing for better dependency management...")
            try:
                subprocess.run(
                    "curl -LsSf https://astral.sh/uv/install.sh | sh",
                    shell=True, check=True
                )
                # Add to PATH for current session
                os.environ['PATH'] = f"{Path.home()}/.cargo/bin:{os.environ['PATH']}"
            except subprocess.CalledProcessError:
                print("⚠️  Could not install uv. Falling back to pip.")
        
        return True
    
    def create_standalone_zipapp(self, project_info: Dict) -> Path:
        """Create a standalone zipapp executable."""
        print(f"Building standalone executable for {project_info['name']}...")
        
        # Create build directory
        self.build_dir.mkdir(parents=True, exist_ok=True)
        zipapp_build = self.build_dir / "zipapp"
        zipapp_build.mkdir(exist_ok=True)
        
        # Copy source code
        print("Copying source code...")
        src_dirs = ['src', 'lib']
        copied = False
        
        for src_dir in src_dirs:
            src_path = self.project_path / src_dir
            if src_path.exists():
                shutil.copytree(src_path, zipapp_build / src_dir, dirs_exist_ok=True)
                copied = True
        
        # If no src/lib directory, copy all Python files
        if not copied:
            for py_file in self.project_path.glob("**/*.py"):
                if 'test' not in str(py_file).lower() and 'build' not in str(py_file):
                    rel_path = py_file.relative_to(self.project_path)
                    dest = zipapp_build / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(py_file, dest)
        
        # Install dependencies to the build directory
        print("Installing dependencies...")
        if shutil.which('uv'):
            self._install_deps_with_uv(zipapp_build, project_info)
        else:
            self._install_deps_with_pip(zipapp_build, project_info)
        
        # Create __main__.py for zipapp
        self._create_main_entry(zipapp_build, project_info)
        
        # Create the zipapp
        output_file = self.output_dir / project_info['name']
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Creating zipapp: {output_file}")
        subprocess.run([
            sys.executable, '-m', 'zipapp',
            str(zipapp_build),
            '--python', '/usr/bin/env python3',
            '--output', str(output_file),
            '--compress'
        ], check=True)
        
        # Make executable on Unix
        if os.name != 'nt':
            output_file.chmod(0o755)
        
        return output_file
    
    def _install_deps_with_uv(self, build_dir: Path, project_info: Dict):
        """Install dependencies using uv."""
        # Create a temporary virtual environment
        venv_path = build_dir / ".venv"
        subprocess.run(['uv', 'venv', str(venv_path)], check=True)
        
        # Install the project and dependencies
        if (self.project_path / 'pyproject.toml').exists():
            subprocess.run([
                'uv', 'pip', 'install',
                '--python', str(venv_path / 'bin' / 'python'),
                str(self.project_path)
            ], check=True)
        
        # Copy site-packages to build directory
        site_packages = venv_path / 'lib' / f'python{project_info["python_version"]}' / 'site-packages'
        if not site_packages.exists():
            # Try alternative path
            site_packages = list(venv_path.glob('lib/python*/site-packages'))[0]
        
        # List of packages to exclude from bundling
        exclude_patterns = [
            '__pycache__', '*.dist-info', '*.egg-info', 
            'pip', 'setuptools', 'wheel', '_distutils_hack'
        ]
        
        for item in site_packages.iterdir():
            # Check if item should be excluded
            skip = False
            for pattern in exclude_patterns:
                if pattern.startswith('*'):
                    if item.name.endswith(pattern[1:]):
                        skip = True
                        break
                elif item.name == pattern:
                    skip = True
                    break
            
            if not skip:
                if item.is_dir():
                    shutil.copytree(item, build_dir / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, build_dir / item.name)
    
    def _install_deps_with_pip(self, build_dir: Path, project_info: Dict):
        """Install dependencies using pip."""
        if project_info['dependencies']:
            subprocess.run([
                sys.executable, '-m', 'pip', 'install',
                '--target', str(build_dir),
                *project_info['dependencies']
            ], check=True)
    
    def _create_main_entry(self, build_dir: Path, project_info: Dict):
        """Create __main__.py entry point for zipapp."""
        entry_point = project_info['entry_point']
        
        if entry_point:
            module, func = entry_point.split(':')
            main_content = f"""#!/usr/bin/env python3
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the main function
from {module} import {func}

if __name__ == "__main__":
    {func}()
"""
        else:
            # Generic fallback
            main_content = """#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to find and run the MCP server
try:
    from server import main
    main()
except ImportError:
    try:
        from mcp_server import main
        main()
    except ImportError:
        print("Error: Could not find MCP server entry point")
        print("Please specify the entry point in pyproject.toml")
        sys.exit(1)
"""
        
        (build_dir / '__main__.py').write_text(main_content)
    
    def create_installer_script(self, project_info: Dict) -> Path:
        """Create an installer script for the standalone executable."""
        installer_path = self.output_dir / f"install-{project_info['name']}.sh"
        
        installer_content = f"""#!/usr/bin/env bash
# Installer for {project_info['name']} v{project_info['version']}

set -e

# Configuration
INSTALL_DIR="${{INSTALL_DIR:-$HOME/.local/bin}}"
APP_NAME="{project_info['name']}"
APP_VERSION="{project_info['version']}"

# Colors
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m'

echo -e "${{GREEN}}Installing $APP_NAME v$APP_VERSION...${{NC}}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${{RED}}Error: Python 3 is required${{NC}}"
    exit 1
fi

# Create install directory
mkdir -p "$INSTALL_DIR"

# Copy executable
cp "$(dirname "$0")/$APP_NAME" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/$APP_NAME"

# Add to PATH if needed
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo ""
    echo -e "${{YELLOW}}Add this to your shell configuration:${{NC}}"
    echo "export PATH=\\"$INSTALL_DIR:\\$PATH\\""
fi

echo -e "${{GREEN}}✓ Installation complete!${{NC}}"
echo "Run: $APP_NAME"
"""
        
        installer_path.write_text(installer_content)
        installer_path.chmod(0o755)
        
        return installer_path
    
    def create_github_workflow(self, project_info: Dict) -> Path:
        """Generate GitHub Actions workflow for building and publishing."""
        workflow_dir = self.project_path / '.github' / 'workflows'
        workflow_dir.mkdir(parents=True, exist_ok=True)
        workflow_path = workflow_dir / 'build-mcp-server.yml'
        
        workflow_content = f"""name: Build MCP Server

on:
  push:
    branches: [ main ]
    tags: [ 'v*' ]
  workflow_dispatch:

jobs:
  build:
    runs-on: ${{{{ matrix.os }}}}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ['{project_info["python_version"]}']
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ matrix.python-version }}}}
      
      - name: Install builder
        run: |
          curl -sSL https://raw.githubusercontent.com/capten-ai/mise-tasks-mcp/main/scripts/universal-mcp-builder.py -o builder.py
          chmod +x builder.py
      
      - name: Build standalone executable
        run: python builder.py --project . --output dist/
      
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: {project_info['name']}-${{{{ matrix.os }}}}
          path: dist/
"""
        
        workflow_path.write_text(workflow_content)
        return workflow_path
    
    def build(self) -> Dict[str, Path]:
        """Main build process."""
        if not self.check_requirements():
            sys.exit(1)
        
        print("\n🔍 Detecting project information...")
        project_info = self.detect_project_info()
        
        print(f"📦 Project: {project_info['name']} v{project_info['version']}")
        print(f"🐍 Python: {project_info['python_version']}")
        print(f"🎯 Entry point: {project_info['entry_point'] or 'auto-detect'}")
        
        results = {}
        
        # Build standalone executable
        print("\n🔨 Building standalone executable...")
        executable = self.create_standalone_zipapp(project_info)
        results['executable'] = executable
        print(f"✅ Created: {executable}")
        
        # Create installer
        print("\n📝 Creating installer script...")
        installer = self.create_installer_script(project_info)
        results['installer'] = installer
        print(f"✅ Created: {installer}")
        
        # Create GitHub workflow
        print("\n🔧 Generating GitHub workflow...")
        workflow = self.create_github_workflow(project_info)
        results['workflow'] = workflow
        print(f"✅ Created: {workflow}")
        
        return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Universal MCP Server Builder for Python Projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build MCP server in current directory
  %(prog)s
  
  # Build specific project
  %(prog)s --project /path/to/mcp-server
  
  # Specify output directory
  %(prog)s --output /tmp/build
  
  # Clean build
  %(prog)s --clean
"""
    )
    
    parser.add_argument(
        '--project',
        type=Path,
        default=Path.cwd(),
        help='Path to MCP server project (default: current directory)'
    )
    
    parser.add_argument(
        '--output',
        type=Path,
        help='Output directory for built files (default: PROJECT/dist)'
    )
    
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Clean build directories before building'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 1.0.0'
    )
    
    args = parser.parse_args()
    
    # Validate project path
    if not args.project.exists():
        print(f"❌ Error: Project path does not exist: {args.project}")
        sys.exit(1)
    
    # Initialize builder
    builder = MCPServerBuilder(args.project, args.output)
    
    # Clean if requested
    if args.clean:
        print("🧹 Cleaning build directories...")
        if builder.build_dir.exists():
            shutil.rmtree(builder.build_dir)
        if builder.output_dir.exists():
            shutil.rmtree(builder.output_dir)
    
    # Build
    print(f"\n🚀 Building MCP Server from: {args.project}")
    print("=" * 60)
    
    try:
        results = builder.build()
        
        print("\n" + "=" * 60)
        print("✨ Build completed successfully!")
        print("\nGenerated files:")
        for name, path in results.items():
            print(f"  - {name}: {path}")
        
        print(f"\n📦 To install locally:")
        print(f"   bash {results['installer']}")
        
        print(f"\n🐳 To distribute:")
        print(f"   Share the contents of: {builder.output_dir}")
        
    except Exception as e:
        print(f"\n❌ Build failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()