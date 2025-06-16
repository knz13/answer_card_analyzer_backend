#!/usr/bin/env python3
"""
Cross-platform Nuitka build script for main_processing_computer.py
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


def get_poppler_data_files(poppler_path: str) -> List[tuple]:
    """Get list of poppler files to include as data files for Nuitka."""
    system = platform.system().lower()
    poppler_dir = Path(poppler_path)
    data_files = []
    
    if system == 'windows':
        # Windows poppler executables
        binaries = [
            "pdftoppm.exe",
            "pdftocairo.exe", 
            "pdfinfo.exe",
            "pdfimages.exe",
        ]
        # Include executables
        for binary in binaries:
            binary_path = poppler_dir / binary
            if binary_path.exists():
                data_files.append((str(binary_path), "poppler"))
        
        # Include any DLL dependencies
        for dll_file in poppler_dir.glob("*.dll"):
            data_files.append((str(dll_file), "poppler"))
    
    elif system in ['darwin', 'linux']:
        binaries = [
            "pdftoppm",
            "pdftocairo",
            "pdfinfo", 
            "pdfimages",
        ]
        for binary in binaries:
            binary_path = poppler_dir / binary
            if binary_path.exists():
                data_files.append((str(binary_path), "poppler"))
    
    return data_files


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


def build_nuitka_command(poppler_data_files: List[tuple], config: Dict[str, str]) -> list:
    """Build Nuitka command with appropriate arguments."""
    cmd = ["python", "-m", "nuitka"]
    
    # Basic options
    if config.get('ONE_FILE', 'true').lower() == 'true':
        cmd.append("--onefile")
    
    # Output directory
    cmd.append("--output-dir=dist")
    
    # Remove output for clean build
    if config.get('CLEAN_BUILD', 'true').lower() == 'true':
        cmd.append("--remove-output")
    
    # Icon/Logo
    logo_path = Path("assets/corigge_logo.ico")
    if logo_path.exists():
        cmd.append(f"--windows-icon-from-ico={logo_path}")
        print(f"📱 Adding logo: {logo_path}")
    else:
        print("⚠️  Logo not found at assets/corigge_logo.ico")
    
    # Enable valid plugins
    cmd.extend([
        "--enable-plugin=anti-bloat",     # Removes unused modules
        "--enable-plugin=data-files",     # Better data file handling
    ])
    
    # Include packages explicitly (more reliable than plugins for some packages)
    cmd.append("--include-package=cv2")
    cmd.append("--include-package=numpy")
    cmd.append("--include-package=PIL")
    cmd.append("--include-package=websockets")
    cmd.append("--include-package=asyncio")
    cmd.append("--include-package=json")
    cmd.append("--include-package=base64")
    cmd.append("--include-package=io")
    cmd.append("--include-package=queue")
    cmd.append("--include-package=traceback")
    cmd.append("--include-package=psutil")
    cmd.append("--include-package=pdf2image")
    cmd.append("--include-package=pathlib")
    
    # Add poppler data files
    for src_path, dest_dir in poppler_data_files:
        cmd.append(f"--include-data-file={src_path}={dest_dir}/{Path(src_path).name}")
    
    # Performance optimizations
    if config.get('OPTIMIZE', 'true').lower() == 'true':
        cmd.append("--lto=yes")  # Link-time optimization
    
    # Show progress
    if config.get('SHOW_PROGRESS', 'true').lower() == 'true':
        cmd.append("--show-progress")
    
    # Warning control
    cmd.append("--assume-yes-for-downloads")
    
    # Follow imports for better compatibility
    cmd.append("--follow-imports")
    
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


def check_nuitka_installation():
    """Check if Nuitka is installed and install if needed."""
    try:
        result = subprocess.run(["python", "-m", "nuitka", "--version"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"✅ Nuitka found: {result.stdout.strip()}")
            return True
    except:
        pass
    
    print("❌ Nuitka not found. Installing...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "nuitka"], check=True)
        print("✅ Nuitka installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install Nuitka. Please install manually: pip install nuitka")
        return False


def main():
    """Main build function."""
    print("🚀 Starting cross-platform Nuitka build with poppler support...")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    
    # Check Nuitka installation
    if not check_nuitka_installation():
        sys.exit(1)
    
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
    
    # Find poppler binaries
    poppler_path = find_poppler_path(config)
    poppler_data_files = []
    
    if poppler_path:
        poppler_data_files = get_poppler_data_files(poppler_path)
        if poppler_data_files:
            print(f"✅ Found poppler at: {poppler_path}")
            print(f"   Including {len(poppler_data_files)} poppler files")
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
    
    # Build Nuitka command
    cmd = build_nuitka_command(poppler_data_files, config)
    
    print("\n🔧 Nuitka command:")
    print(" ".join(f'"{arg}"' if ' ' in arg else arg for arg in cmd))
    print()
    
    # Execute build
    try:
        print("🏗️  Building executable with Nuitka...")
        print("   Note: Nuitka compilation may take several minutes...")
        result = subprocess.run(cmd, check=True, capture_output=False)
        print("\n✅ Build completed successfully!")
        
        # Show output information
        dist_dir = Path("dist")
        if dist_dir.exists():
            executables = list(dist_dir.glob("*"))
            if executables:
                print(f"\n📦 Built executable(s):")
                for exe in executables:
                    if exe.is_file() and exe.suffix in ['.exe', ''] and not exe.suffix == '.build':
                        size_mb = exe.stat().st_size / (1024 * 1024)
                        print(f"   {exe.name} ({size_mb:.1f} MB)")
        
        # Show poppler status
        if poppler_data_files:
            print(f"\n🔧 Poppler integration: ✅ Included {len(poppler_data_files)} files")
        else:
            print(f"\n🔧 Poppler integration: ❌ Not included")
        
        print(f"\n🎉 Nuitka build benefits:")
        print(f"   • Faster startup and execution")
        print(f"   • Better memory usage")
        print(f"   • Native executable (not Python bytecode)")
        
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

    