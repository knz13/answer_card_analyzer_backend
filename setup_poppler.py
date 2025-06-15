#!/usr/bin/env python3
"""
Automatic poppler setup script for Answer Card Analyzer.
Downloads and configures poppler for building with PyInstaller.
"""

import os
import sys
import platform
import zipfile
import tarfile
from pathlib import Path
import urllib.request
import shutil


def download_file(url: str, filepath: Path, progress_callback=None):
    """Download a file with optional progress callback."""
    def report_progress(chunk_num, chunk_size, total_size):
        if progress_callback and total_size > 0:
            progress = min(100, (chunk_num * chunk_size * 100) // total_size)
            progress_callback(progress)
    
    urllib.request.urlretrieve(url, filepath, reporthook=report_progress)


def extract_archive(archive_path: Path, extract_to: Path):
    """Extract archive (zip or tar) to specified directory."""
    if archive_path.suffix.lower() == '.zip' or archive_path.name.endswith('.7z'):
        # For .7z files, we'll need to handle them differently
        if archive_path.name.endswith('.7z'):
            print("⚠️  .7z archive detected. Please extract manually or install 7zip.")
            print(f"   Extract {archive_path} to {extract_to}")
            return False
        
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
    elif archive_path.suffix.lower() in ['.tar', '.gz', '.bz2', '.xz']:
        with tarfile.open(archive_path, 'r:*') as tar_ref:
            tar_ref.extractall(extract_to)
    else:
        print(f"❌ Unsupported archive format: {archive_path.suffix}")
        return False
    
    return True


def setup_windows_poppler():
    """Setup poppler for Windows."""
    print("🪟 Setting up poppler for Windows...")
    
    # Note: GitHub releases API would be ideal, but we'll use a known working version
    poppler_version = "23.08.0"
    archive_name = f"poppler-{poppler_version}_x86_64.7z"
    download_url = f"https://github.com/oschwartz10612/poppler-windows/releases/download/v{poppler_version}/{archive_name}"
    
    downloads_dir = Path.cwd() / "downloads"
    downloads_dir.mkdir(exist_ok=True)
    
    archive_path = downloads_dir / archive_name
    
    if not archive_path.exists():
        print(f"📥 Downloading poppler {poppler_version}...")
        print(f"   URL: {download_url}")
        
        try:
            def show_progress(progress):
                bar_length = 30
                filled = int(bar_length * progress / 100)
                bar = '█' * filled + '░' * (bar_length - filled)
                print(f"\r   Progress: [{bar}] {progress}%", end='', flush=True)
            
            download_file(download_url, archive_path, show_progress)
            print("\n✅ Download completed!")
            
        except Exception as e:
            print(f"\n❌ Download failed: {e}")
            print("\nPlease download manually from:")
            print(f"   {download_url}")
            print(f"   Save as: {archive_path}")
            return False
    else:
        print(f"✅ Found existing download: {archive_path}")
    
    # For .7z files, provide manual instructions
    if archive_path.name.endswith('.7z'):
        print("\n📋 Manual extraction required for .7z files:")
        print(f"1. Install 7-Zip from: https://www.7-zip.org/")
        print(f"2. Extract {archive_path}")
        print(f"3. Copy the extracted 'poppler' folder to your project directory")
        print("4. Your project should look like:")
        print("   YourProject/")
        print("   ├── poppler/")
        print("   │   └── bin/")
        print("   │       ├── pdftoppm.exe")
        print("   │       └── *.dll files")
        print("   ├── build.py")
        print("   └── ...")
        print("\n5. Run: python build.py")
        return True
    
    # Extract archive
    print("📦 Extracting archive...")
    temp_extract = downloads_dir / "temp_extract"
    temp_extract.mkdir(exist_ok=True)
    
    if not extract_archive(archive_path, temp_extract):
        return False
    
    # Find the poppler directory in extracted files
    extracted_items = list(temp_extract.iterdir())
    poppler_source = None
    
    for item in extracted_items:
        if item.is_dir() and 'poppler' in item.name.lower():
            poppler_source = item
            break
    
    if not poppler_source:
        print("❌ Could not find poppler directory in extracted files")
        return False
    
    # Copy to project directory
    project_poppler = Path.cwd() / "poppler"
    if project_poppler.exists():
        print("🔄 Removing existing poppler directory...")
        shutil.rmtree(project_poppler)
    
    print(f"📁 Copying poppler to project directory...")
    shutil.copytree(poppler_source, project_poppler)
    
    # Cleanup
    shutil.rmtree(temp_extract)
    
    # Verify installation
    poppler_bin = project_poppler / "bin"
    pdftoppm_exe = poppler_bin / "pdftoppm.exe"
    
    if pdftoppm_exe.exists():
        print("✅ Poppler setup completed successfully!")
        print(f"   Installed to: {project_poppler}")
        print(f"   Binary location: {pdftoppm_exe}")
        print("\n🚀 You can now run: python build.py")
        return True
    else:
        print("❌ Setup completed but pdftoppm.exe not found")
        print(f"   Check: {poppler_bin}")
        return False


def setup_macos_poppler():
    """Setup poppler for macOS."""
    print("🍎 Setting up poppler for macOS...")
    
    # Check if Homebrew is available
    try:
        import subprocess
        result = subprocess.run(["brew", "--version"], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("🍺 Homebrew detected, installing poppler...")
            install_result = subprocess.run(["brew", "install", "poppler"], 
                                          capture_output=False)
            if install_result.returncode == 0:
                print("✅ Poppler installed via Homebrew!")
                print("🚀 You can now run: python build.py")
                return True
            else:
                print("❌ Homebrew installation failed")
        else:
            print("❌ Homebrew not found")
    except:
        print("❌ Could not run Homebrew")
    
    print("\n📋 Manual installation instructions:")
    print("1. Install Homebrew: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
    print("2. Install poppler: brew install poppler")
    print("3. Or download and compile from source")
    return False


def setup_linux_poppler():
    """Setup poppler for Linux."""
    print("🐧 Setting up poppler for Linux...")
    
    # Try common package managers
    package_managers = [
        ("apt-get", ["sudo", "apt-get", "update", "&&", "sudo", "apt-get", "install", "poppler-utils"]),
        ("yum", ["sudo", "yum", "install", "poppler-utils"]),
        ("dnf", ["sudo", "dnf", "install", "poppler-utils"]),
        ("pacman", ["sudo", "pacman", "-S", "poppler"]),
    ]
    
    print("🔍 Detecting package manager...")
    
    for pm_name, pm_cmd in package_managers:
        try:
            import subprocess
            result = subprocess.run(["which", pm_name], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"✅ Found {pm_name}")
                print(f"💡 Run this command to install poppler:")
                print(f"   {' '.join(pm_cmd)}")
                
                response = input("   Install now? (y/N): ").lower()
                if response in ['y', 'yes']:
                    install_result = subprocess.run(pm_cmd, capture_output=False)
                    if install_result.returncode == 0:
                        print("✅ Poppler installed!")
                        print("🚀 You can now run: python build.py")
                        return True
                return False
        except:
            continue
    
    print("❌ No supported package manager found")
    print("\n📋 Manual installation instructions:")
    print("1. Install poppler-utils using your distribution's package manager")
    print("2. Or compile from source: https://poppler.freedesktop.org/")
    return False


def main():
    """Main setup function."""
    print("🔧 Poppler Setup for Answer Card Analyzer")
    print("=" * 50)
    
    system = platform.system().lower()
    
    if system == 'windows':
        success = setup_windows_poppler()
    elif system == 'darwin':
        success = setup_macos_poppler()
    elif system == 'linux':
        success = setup_linux_poppler()
    else:
        print(f"❌ Unsupported platform: {system}")
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Setup completed successfully!")
        print("🚀 Next step: python build.py")
    else:
        print("⚠️  Setup incomplete - manual installation may be required")
        print("📚 See POPPLER_SETUP.md for detailed instructions")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main()) 