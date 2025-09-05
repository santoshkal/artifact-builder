#!/usr/bin/env python3
"""
Universal MCP Server Builder using uv
Creates standalone Python applications with full dependency support
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


class UVMCPBuilder:
    """Build standalone MCP servers using uv's built-in capabilities."""
    
    def __init__(self, project_path: Path, output_dir: Path = None):
        self.project_path = Path(project_path).resolve()
        self.output_dir = output_dir or self.project_path / "dist"
        self.build_dir = self.project_path / "build"
        
    def check_uv(self) -> bool:
        """Check if uv is installed and install if needed."""
        if not shutil.which('uv'):
            print("📦 Installing uv...")
            try:
                subprocess.run(
                    "curl -LsSf https://astral.sh/uv/install.sh | sh",
                    shell=True, 
                    check=True
                )
                # Add to PATH for current session
                os.environ['PATH'] = f"{Path.home()}/.cargo/bin:{os.environ['PATH']}"
                
                # Verify installation
                if not shutil.which('uv'):
                    print("❌ Failed to install uv")
                    return False
            except subprocess.CalledProcessError:
                print("❌ Could not install uv")
                return False
        
        # Get uv version
        result = subprocess.run(['uv', '--version'], capture_output=True, text=True)
        print(f"✅ Using {result.stdout.strip()}")
        return True
    
    def detect_project_info(self) -> Dict[str, any]:
        """Detect project information from pyproject.toml."""
        info = {
            "name": "mcp-server",
            "version": "1.0.0",
            "entry_point": None,
            "python_version": "3.12"
        }
        
        pyproject_path = self.project_path / "pyproject.toml"
        if pyproject_path.exists():
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib
                except ImportError:
                    subprocess.run(['uv', 'pip', 'install', 'tomli'], capture_output=True)
                    import tomli as tomllib
            
            with open(pyproject_path, 'rb') as f:
                data = tomllib.load(f)
                project = data.get('project', {})
                
                info['name'] = project.get('name', info['name'])
                info['version'] = project.get('version', info['version'])
                
                # Get entry point from scripts
                scripts = project.get('scripts', {})
                if scripts:
                    # Get the first script as entry point
                    script_name = list(scripts.keys())[0]
                    info['entry_point'] = scripts[script_name]
                    info['script_name'] = script_name
                
                # Get Python version requirement
                requires_python = project.get('requires-python', '')
                if requires_python:
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
        patterns = [
            ('src/*/server.py', 'main'),
            ('*/server.py', 'main'),
            ('src/*/__main__.py', 'main'),
            ('*/__main__.py', 'main'),
        ]
        
        for pattern, func in patterns:
            files = list(self.project_path.glob(pattern))
            if files:
                file_path = files[0]
                rel_path = file_path.relative_to(self.project_path)
                
                if rel_path.parts[0] == 'src':
                    module_parts = rel_path.parts[1:]
                else:
                    module_parts = rel_path.parts
                
                module = '.'.join(module_parts).replace('.py', '')
                module = module.replace('.__main__', '')
                
                return f"{module}:{func}"
        
        return None
    
    def build_standalone_with_uv(self, project_info: Dict) -> Path:
        """Build standalone executable using uv."""
        print(f"🔨 Building {project_info['name']} with uv...")
        
        # Clean and create build directory
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        self.build_dir.mkdir(parents=True)
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Method 1: Use uv to create a self-contained bundle
        bundle_dir = self.build_dir / "bundle"
        bundle_dir.mkdir()
        
        # Create a standalone Python installation
        print(f"📦 Creating standalone Python {project_info['python_version']} environment...")
        subprocess.run([
            'uv', 'python', 'install', project_info['python_version']
        ], check=True)
        
        # Create virtual environment with specific Python version
        print("🔧 Creating virtual environment...")
        venv_path = bundle_dir / ".venv"
        subprocess.run([
            'uv', 'venv', 
            '--python', project_info['python_version'],
            str(venv_path)
        ], check=True)
        
        # Install the project and all dependencies
        print("📚 Installing project and dependencies...")
        subprocess.run([
            'uv', 'pip', 'install',
            '--python', str(venv_path / 'bin' / 'python'),
            str(self.project_path)
        ], check=True)
        
        # Create standalone script using uv tool
        output_name = project_info['name']
        output_path = self.output_dir / output_name
        
        # Method 2: Use uv tool to create a standalone script
        if 'script_name' in project_info:
            print(f"🎯 Creating standalone tool with uv...")
            
            # First, build a wheel
            print("📦 Building wheel...")
            wheel_dir = self.build_dir / "wheels"
            wheel_dir.mkdir()
            subprocess.run([
                'uv', 'build',
                '--wheel',
                '--out-dir', str(wheel_dir),
                str(self.project_path)
            ], check=True)
            
            # Install as a tool (creates standalone script)
            print("🔨 Creating standalone executable...")
            
            # Create a Python script that bundles everything
            self._create_standalone_script(
                venv_path,
                output_path,
                project_info
            )
        else:
            # Fallback to creating a bundled script
            self._create_standalone_script(
                venv_path,
                output_path,
                project_info
            )
        
        print(f"✅ Created: {output_path}")
        return output_path
    
    def _create_standalone_script(self, venv_path: Path, output_path: Path, project_info: Dict):
        """Create a standalone script that includes all dependencies."""
        
        # Create a zipapp from the virtual environment
        print("📦 Creating self-contained bundle...")
        
        # Copy all site-packages to a staging directory
        staging_dir = self.build_dir / "staging"
        staging_dir.mkdir()
        
        # Find site-packages
        site_packages = list(venv_path.glob('lib/python*/site-packages'))[0]
        
        # Copy necessary packages (excluding build artifacts)
        exclude_patterns = {
            '__pycache__', 'pip', 'setuptools', 'wheel', 
            '_distutils_hack', 'pkg_resources', 'easy_install.py'
        }
        
        for item in site_packages.iterdir():
            # Skip excluded items and dist-info for build tools
            if item.name in exclude_patterns:
                continue
            if item.suffix in ['.dist-info', '.egg-info']:
                # Keep dist-info for actual dependencies
                if not any(x in item.name.lower() for x in ['pip', 'setuptools', 'wheel']):
                    shutil.copytree(item, staging_dir / item.name, dirs_exist_ok=True)
            elif item.is_dir():
                shutil.copytree(item, staging_dir / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, staging_dir / item.name)
        
        # Create __main__.py for zipapp
        main_content = self._generate_main_script(project_info)
        (staging_dir / '__main__.py').write_text(main_content)
        
        # Create zipapp using Python's zipapp module
        print("🗜️  Compressing into standalone executable...")
        subprocess.run([
            sys.executable, '-m', 'zipapp',
            str(staging_dir),
            '--python', '/usr/bin/env python3',
            '--output', str(output_path),
            '--compress'
        ], check=True)
        
        # Make executable
        output_path.chmod(0o755)
    
    def _generate_main_script(self, project_info: Dict) -> str:
        """Generate the __main__.py script for the zipapp."""
        entry_point = project_info.get('entry_point', '')
        
        if entry_point and ':' in entry_point:
            module, func = entry_point.split(':', 1)
            return f"""#!/usr/bin/env python3
import sys
import os

# Ensure the bundled packages are available
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the entry point
try:
    from {module} import {func}
    {func}()
except ImportError as e:
    print(f"Error importing module: {{e}}", file=sys.stderr)
    print(f"Python path: {{sys.path}}", file=sys.stderr)
    sys.exit(1)
"""
        else:
            # Generic fallback
            return """#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try common entry points
entry_points = [
    ('mise_tasks_mcp.server', 'main'),
    ('mcp_server', 'main'),
    ('server', 'main'),
    ('__main__', 'main'),
]

for module_name, func_name in entry_points:
    try:
        module = __import__(module_name, fromlist=[func_name])
        func = getattr(module, func_name)
        func()
        break
    except (ImportError, AttributeError):
        continue
else:
    print("Error: Could not find MCP server entry point", file=sys.stderr)
    print("Please ensure the entry point is specified in pyproject.toml", file=sys.stderr)
    sys.exit(1)
"""
    
    def create_uv_runner_script(self, project_info: Dict) -> Path:
        """Create a runner script that uses uv run for maximum compatibility."""
        runner_path = self.output_dir / f"{project_info['name']}-runner"
        
        runner_content = f"""#!/usr/bin/env bash
# Runner script for {project_info['name']} using uv
set -e

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${{BASH_SOURCE[0]}}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Run the MCP server with uv
cd "$PROJECT_DIR"
uv run --python {project_info['python_version']} \\
    --from . \\
    {project_info.get('script_name', project_info['name'])} "$@"
"""
        
        runner_path.write_text(runner_content)
        runner_path.chmod(0o755)
        
        return runner_path
    
    def build(self) -> Dict[str, Path]:
        """Main build process."""
        if not self.check_uv():
            print("❌ uv is required but could not be installed")
            sys.exit(1)
        
        print(f"\n🔍 Analyzing project: {self.project_path}")
        project_info = self.detect_project_info()
        
        print(f"📦 Project: {project_info['name']} v{project_info['version']}")
        print(f"🐍 Python: {project_info['python_version']}")
        print(f"🎯 Entry: {project_info['entry_point'] or 'auto-detect'}")
        
        results = {}
        
        # Build standalone executable
        try:
            executable = self.build_standalone_with_uv(project_info)
            results['executable'] = executable
        except Exception as e:
            print(f"⚠️  Standalone build failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Also create a uv runner script as fallback
        runner = self.create_uv_runner_script(project_info)
        results['runner'] = runner
        
        return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Build standalone MCP servers using uv",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This builder uses uv's capabilities to create standalone Python applications.

Examples:
  # Build current directory
  %(prog)s
  
  # Build specific project
  %(prog)s --project /path/to/mcp-server
  
  # Specify output directory
  %(prog)s --output /tmp/dist
  
  # Clean build
  %(prog)s --clean

The tool creates:
  1. Standalone executable (zipapp with all dependencies)
  2. Runner script (uses uv run for compatibility)
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
        help='Output directory (default: PROJECT/dist)'
    )
    
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Clean build directories before building'
    )
    
    args = parser.parse_args()
    
    if not args.project.exists():
        print(f"❌ Error: Project path does not exist: {args.project}")
        sys.exit(1)
    
    builder = UVMCPBuilder(args.project, args.output)
    
    if args.clean:
        print("🧹 Cleaning build directories...")
        if builder.build_dir.exists():
            shutil.rmtree(builder.build_dir)
        if builder.output_dir.exists():
            shutil.rmtree(builder.output_dir)
    
    print("🚀 UV MCP Server Builder")
    print("=" * 50)
    
    try:
        results = builder.build()
        
        print("\n" + "=" * 50)
        print("✨ Build completed!")
        print("\nGenerated files:")
        for name, path in results.items():
            size = path.stat().st_size / (1024 * 1024)  # MB
            print(f"  - {name}: {path} ({size:.1f} MB)")
        
        if 'executable' in results:
            print(f"\n🎯 Run standalone executable:")
            print(f"   {results['executable']}")
        
        if 'runner' in results:
            print(f"\n📝 Or use the runner script (requires uv):")
            print(f"   {results['runner']}")
        
        print(f"\n📦 To distribute:")
        print(f"   Share the files in: {builder.output_dir}")
        
    except Exception as e:
        print(f"\n❌ Build failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()