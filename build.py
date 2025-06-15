#!/usr/bin/env python3
"""
Cross-platform PyInstaller build script for main_processing_computer.py
Supports Windows, macOS, and Linux with automatic Python library detection.
"""

import os
import sys
import platform
import subprocess
import sysconfig
from pathlib import Path
from typing import Optional, Dict, Any


def load_config(config_file: str = "build_config.env") -> Dict[str, str]:
    """Load configuration from environment file."""
    config = {}
    config_path = Path(config_file)
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    
    return config


def get_python_version() -> str:
    """Get Python version in format like '3.13'."""
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def get_python_lib_info() -> Dict[str, Any]:
    """Get Python library information for current platform."""
    system = platform.system().lower()
    python_version = get_python_version()
    
    info = {
        'system': system,
        'python_version': python_version,
        'lib_dir': sysconfig.get_config_var('LIBDIR'),
        'lib_name': None,
        'lib_path': None
    }
    
    if system == 'darwin':  # macOS
        info['lib_name'] = f"libpython{python_version}.dylib"
    elif system == 'windows':
        # Windows can have different naming conventions
        version_nodot = python_version.replace('.', '')
        possible_names = [
            f"python{version_nodot}.dll",
            f"python{python_version}.dll",
            f"libpython{python_version}.dll"
        ]
        
        # Try to find the actual DLL
        lib_dir = info['lib_dir']
        if lib_dir:
            for name in possible_names:
                potential_path = Path(lib_dir) / name
                if potential_path.exists():
                    info['lib_name'] = name
                    break
        
        # If not found in LIBDIR, check common Windows locations
        if not info['lib_name']:
            import sys
            python_dir = Path(sys.executable).parent
            for name in possible_names:
                potential_path = python_dir / name
                if potential_path.exists():
                    info['lib_name'] = name
                    info['lib_dir'] = str(python_dir)
                    break
    
    elif system == 'linux':
        info['lib_name'] = f"libpython{python_version}.so"
    
    # Construct full library path
    if info['lib_dir'] and info['lib_name']:
        info['lib_path'] = str(Path(info['lib_dir']) / info['lib_name'])
    
    return info


def get_python_lib_path(config: Dict[str, str]) -> Optional[str]:
    """Get Python library path, checking config overrides first."""
    system = platform.system().lower()
    
    # Check for override in config
    override_key = f"{system.upper()}_PYTHON_LIB_PATH"
    if override_key in config and config[override_key]:
        return config[override_key]
    
    # Auto-detect
    lib_info = get_python_lib_info()
    
    if not lib_info['lib_path']:
        print(f"❌ Could not find Python library for {system}")
        print(f"Library directory: {lib_info['lib_dir']}")
        print(f"Expected library name: {lib_info['lib_name']}")
        return None
    
    if not Path(lib_info['lib_path']).exists():
        print(f"❌ Python library not found at: {lib_info['lib_path']}")
        return None
    
    return lib_info['lib_path']


def build_pyinstaller_command(python_lib_path: str, config: Dict[str, str]) -> list:
    """Build PyInstaller command with appropriate arguments."""
    cmd = ["pyinstaller"]
    
    # Basic options
    if config.get('ONE_FILE', 'true').lower() == 'true':
        cmd.append("--onefile")
    
    if config.get('CLEAN_BUILD', 'true').lower() == 'true':
        cmd.append("--clean")
    
    # Hidden imports
    cmd.extend(["--hidden-import", "cv2"])
    
    # Add Python library binary
    cmd.extend(["--add-binary", f"{python_lib_path}:."])
    
    # Log level
    log_level = config.get('LOG_LEVEL', 'INFO')
    cmd.extend(["--log-level", log_level])
    
    # Target script
    cmd.append("main_processing_computer.py")
    
    return cmd


def main():
    """Main build function."""
    print("🚀 Starting cross-platform PyInstaller build...")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    print()
    
    # Load configuration
    config = load_config()
    
    # Get Python library path
    python_lib_path = get_python_lib_path(config)
    if not python_lib_path:
        print("❌ Build failed: Could not locate Python library")
        sys.exit(1)
    
    print(f"✅ Found Python library: {python_lib_path}")
    
    # Build PyInstaller command
    cmd = build_pyinstaller_command(python_lib_path, config)
    
    print("\n🔧 PyInstaller command:")
    print(" ".join(f'"{arg}"' if ' ' in arg else arg for arg in cmd))
    print()
    
    # Execute build
    try:
        print("🏗️  Building executable...")
        result = subprocess.run(cmd, check=True, capture_output=False)
        print("\n✅ Build completed successfully!")
        
        # Show output information
        dist_dir = Path("dist")
        if dist_dir.exists():
            executables = list(dist_dir.glob("*"))
            if executables:
                print(f"\n📦 Built executable(s):")
                for exe in executables:
                    size_mb = exe.stat().st_size / (1024 * 1024)
                    print(f"   {exe.name} ({size_mb:.1f} MB)")
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Build failed with exit code {e.returncode}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Build interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Build failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

    