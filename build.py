#!/usr/bin/env python3
"""
Cross-platform PyInstaller build script for main_processing_computer.py
Supports Windows, macOS, and Linux with automatic Python library detection and poppler bundling.
"""

import os
import sys
import platform
import subprocess
import sysconfig
from pathlib import Path
from typing import Optional, Dict, Any, List
import shutil


def find_python_executable() -> str:
    """Find the appropriate Python executable (python3 or python)."""
    def test_python_command(cmd: str) -> bool:
        """Test if a Python command exists and is Python 3.x."""
        try:
            result = subprocess.run([cmd, "--version"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version_output = result.stdout.strip()
                # Check if it's Python 3.x
                if "Python 3." in version_output:
                    return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        return False
    
    # Try python3 first (preferred)
    if test_python_command("python3"):
        return "python3"
    
    # Fall back to python
    if test_python_command("python"):
        return "python"
    
    # If we're running this script, we must have a working Python
    # Use the same executable that's running this script
    return sys.executable


def find_poppler_path(config: Dict[str, str]) -> Optional[str]:
    """Find poppler binaries path for current platform."""
    system = platform.system().lower()
    
    # First, check for local poppler directory in the project
    local_poppler_path = Path.cwd() / "poppler"
    if system == 'windows':
        local_bin_path = local_poppler_path / "bin"
    else:
        local_bin_path = local_poppler_path / "bin"
    
    # Check if local poppler exists and has the required binaries
    if local_bin_path.exists():
        required_binary = "pdftoppm.exe" if system == 'windows' else "pdftoppm"
        if (local_bin_path / required_binary).exists():
            print(f"🎯 Found local poppler in project: {local_bin_path}")
            return str(local_bin_path)
        else:
            print(f"⚠️  Local poppler directory found but missing {required_binary}: {local_bin_path}")
    
    # Check for override in config
    override_key = f"{system.upper()}_POPPLER_PATH"
    if override_key in config and config[override_key]:
        poppler_path = config[override_key]
        if Path(poppler_path).exists():
            return poppler_path
        else:
            print(f"⚠️  Configured poppler path doesn't exist: {poppler_path}")
    
    # Auto-detect based on platform
    if system == 'windows':
        # Common Windows poppler installation paths
        common_paths = [
            r"C:\poppler\bin",
            r"C:\Program Files\poppler\bin",
            r"C:\Program Files (x86)\poppler\bin",
            r"C:\tools\poppler\bin",
        ]
        
        # Also check if poppler is in PATH
        try:
            result = subprocess.run(["where", "pdftoppm.exe"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                exe_path = result.stdout.strip().split('\n')[0]
                return str(Path(exe_path).parent)
        except:
            pass
        
        # Check common installation paths
        for path in common_paths:
            if Path(path).exists() and (Path(path) / "pdftoppm.exe").exists():
                return path
    
    elif system == 'darwin':  # macOS
        # Check Homebrew installation
        try:
            result = subprocess.run(["brew", "--prefix", "poppler"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                brew_path = result.stdout.strip()
                bin_path = Path(brew_path) / "bin"
                if bin_path.exists() and (bin_path / "pdftoppm").exists():
                    return str(bin_path)
        except:
            pass
        
        # Check if poppler is in PATH
        try:
            result = subprocess.run(["which", "pdftoppm"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                exe_path = result.stdout.strip()
                return str(Path(exe_path).parent)
        except:
            pass
    
    elif system == 'linux':
        # Check if poppler is in PATH
        try:
            result = subprocess.run(["which", "pdftoppm"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                exe_path = result.stdout.strip()
                return str(Path(exe_path).parent)
        except:
            pass
        
        # Common Linux paths
        common_paths = [
            "/usr/bin",
            "/usr/local/bin",
            "/opt/poppler/bin",
        ]
        
        for path in common_paths:
            if Path(path).exists() and (Path(path) / "pdftoppm").exists():
                return path
    
    return None


def get_poppler_binaries(poppler_path: str) -> List[str]:
    """Get list of poppler binary files to include."""
    system = platform.system().lower()
    poppler_dir = Path(poppler_path)
    
    if system == 'windows':
        # Windows poppler executables
        binaries = [
            "pdftoppm.exe",
            "pdftocairo.exe", 
            "pdfinfo.exe",
            "pdfimages.exe",
        ]
        # Also include any DLL dependencies
        dll_files = list(poppler_dir.glob("*.dll"))
        return [str(poppler_dir / binary) for binary in binaries if (poppler_dir / binary).exists()] + [str(dll) for dll in dll_files]
    
    elif system == 'darwin':  # macOS
        binaries = [
            "pdftoppm",
            "pdftocairo",
            "pdfinfo", 
            "pdfimages",
        ]
        return [str(poppler_dir / binary) for binary in binaries if (poppler_dir / binary).exists()]
    
    elif system == 'linux':
        binaries = [
            "pdftoppm",
            "pdftocairo",
            "pdfinfo",
            "pdfimages",
        ]
        return [str(poppler_dir / binary) for binary in binaries if (poppler_dir / binary).exists()]
    
    return []


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


def get_python_lib_info(python_cmd: str) -> Dict[str, Any]:
    """Get Python library information for current platform."""
    system = platform.system().lower()
    python_version = get_python_version()
    
    info = {
        'system': system,
        'python_version': python_version,
        'python_cmd': python_cmd,
        'lib_dir': sysconfig.get_config_var('LIBDIR'),
        'lib_name': None,
        'lib_path': None
    }
    
    # For cross-system compatibility, also try to get LIBDIR using the found python executable
    try:
        result = subprocess.run([
            python_cmd, "-c", 
            "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            external_libdir = result.stdout.strip()
            if external_libdir != "None":
                info['lib_dir'] = external_libdir
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass  # Fall back to sysconfig from current Python
    
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
            # Try to get the Python executable directory using the found command
            try:
                result = subprocess.run([
                    python_cmd, "-c", "import sys; print(sys.executable)"
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    python_dir = Path(result.stdout.strip()).parent
                    for name in possible_names:
                        potential_path = python_dir / name
                        if potential_path.exists():
                            info['lib_name'] = name
                            info['lib_dir'] = str(python_dir)
                            break
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                pass
    
    elif system == 'linux':
        info['lib_name'] = f"libpython{python_version}.so"
    
    # Construct full library path
    if info['lib_dir'] and info['lib_name']:
        info['lib_path'] = str(Path(info['lib_dir']) / info['lib_name'])
    
    return info


def get_python_lib_path(config: Dict[str, str], python_cmd: str) -> Optional[str]:
    """Get Python library path, checking config overrides first."""
    system = platform.system().lower()
    
    # Check for override in config
    override_key = f"{system.upper()}_PYTHON_LIB_PATH"
    if override_key in config and config[override_key]:
        return config[override_key]
    
    # Auto-detect
    lib_info = get_python_lib_info(python_cmd)
    
    if not lib_info['lib_path']:
        print(f"❌ Could not find Python library for {system}")
        print(f"Python command: {python_cmd}")
        print(f"Library directory: {lib_info['lib_dir']}")
        print(f"Expected library name: {lib_info['lib_name']}")
        return None
    
    if not Path(lib_info['lib_path']).exists():
        print(f"❌ Python library not found at: {lib_info['lib_path']}")
        return None
    
    return lib_info['lib_path']


def build_pyinstaller_command(python_lib_path: str, poppler_binaries: List[str], config: Dict[str, str]) -> list:
    """Build PyInstaller command with appropriate arguments."""
    cmd = ["pyinstaller"]
    
    # Basic options
    if config.get('ONE_FILE', 'true').lower() == 'true':
        cmd.append("--onefile")
    
    if config.get('CLEAN_BUILD', 'true').lower() == 'true':
        cmd.append("--clean")
    
    # Icon/Logo
    logo_path = Path("assets/corigge_logo.ico")
    if logo_path.exists():
        cmd.extend(["--icon", str(logo_path)])
        print(f"📱 Adding logo: {logo_path}")
    else:
        print("⚠️  Logo not found at assets/corigge_logo.ico")
    
    # Hidden imports
    cmd.extend(["--hidden-import", "cv2"])
    
    # Add Python library binary
    cmd.extend(["--add-binary", f"{python_lib_path}:."])
    
    # Add poppler binaries
    for binary in poppler_binaries:
        cmd.extend(["--add-binary", f"{binary}:poppler"])
    
    # Log level
    log_level = config.get('LOG_LEVEL', 'INFO')
    cmd.extend(["--log-level", log_level])
    
    # Target script
    cmd.append("main_processing_computer.py")
    
    return cmd


def create_poppler_setup_instructions():
    """Create instructions for installing poppler on different platforms."""
    system = platform.system().lower()
    
    print("\n📋 Poppler Setup Instructions:")
    print("\n🎯 Option 1: Local Project Directory (Recommended for portable builds)")
    
    if system == 'windows':
        print("1. Download poppler for Windows from: https://github.com/oschwartz10612/poppler-windows/releases")
        print("2. Extract the downloaded archive")
        print("3. Copy the entire poppler folder to your project directory:")
        print("   YourProject/")
        print("   ├── poppler/")
        print("   │   └── bin/")
        print("   │       ├── pdftoppm.exe")
        print("   │       ├── pdfinfo.exe")
        print("   │       └── *.dll files")
        print("   ├── build.py")
        print("   └── main_processing_computer.py")
        print("4. Run: python build.py")
        print("   The build script will automatically detect and bundle the local poppler!")
        
        print("\n🔧 Option 2: System Installation")
        print("1. Download poppler for Windows from: https://github.com/oschwartz10612/poppler-windows/releases")
        print("2. Extract to C:\\poppler (or another location)")
        print("3. Add C:\\poppler\\bin to your PATH environment variable")
        print("4. Or set WINDOWS_POPPLER_PATH=C:\\poppler\\bin in build_config.env")
        
    elif system == 'darwin':
        print("For macOS, local bundling is supported but Homebrew is usually easier:")
        print("1. Install via Homebrew: brew install poppler")
        print("2. Or for local bundling:")
        print("   - Download poppler source and compile")
        print("   - Place binaries in YourProject/poppler/bin/")
        
    elif system == 'linux':
        print("For Linux, package managers are recommended:")
        print("1. Ubuntu/Debian: sudo apt-get install poppler-utils")
        print("2. CentOS/RHEL: sudo yum install poppler-utils") 
        print("3. Arch: sudo pacman -S poppler")
        print("4. Or for local bundling, place binaries in YourProject/poppler/bin/")


def main():
    """Main build function."""
    print("🚀 Starting cross-platform PyInstaller build with poppler support...")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    
    # Find appropriate Python executable
    python_cmd = find_python_executable()
    print(f"Using Python command: {python_cmd}")
    
    # Test the Python command
    try:
        result = subprocess.run([python_cmd, "--version"], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"Python version: {result.stdout.strip()}")
        else:
            print(f"⚠️  Warning: Could not verify Python version")
    except Exception as e:
        print(f"⚠️  Warning: Error testing Python command: {e}")
    
    print()
    
    # Load configuration
    config = load_config()
    
    # Get Python library path
    python_lib_path = get_python_lib_path(config, python_cmd)
    if not python_lib_path:
        print("❌ Build failed: Could not locate Python library")
        sys.exit(1)
    
    print(f"✅ Found Python library: {python_lib_path}")
    
    # Find poppler binaries
    poppler_path = find_poppler_path(config)
    poppler_binaries = []
    
    if poppler_path:
        poppler_binaries = get_poppler_binaries(poppler_path)
        if poppler_binaries:
            print(f"✅ Found poppler at: {poppler_path}")
            print(f"   Including {len(poppler_binaries)} poppler binaries")
        else:
            print(f"⚠️  Poppler path found but no binaries detected: {poppler_path}")
    else:
        print("⚠️  Poppler not found - PDF processing may not work in built executable")
        create_poppler_setup_instructions()
        
        # Ask user if they want to continue
        response = input("\nContinue build without poppler? (y/N): ").lower()
        if response not in ['y', 'yes']:
            print("❌ Build cancelled")
            sys.exit(1)
    
    # Build PyInstaller command
    cmd = build_pyinstaller_command(python_lib_path, poppler_binaries, config)
    
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
        
        # Show poppler status
        if poppler_binaries:
            print(f"\n🔧 Poppler integration: ✅ Included {len(poppler_binaries)} binaries")
        else:
            print(f"\n🔧 Poppler integration: ❌ Not included")
        
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

    