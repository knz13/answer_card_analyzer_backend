# Poppler Setup Guide

This guide explains how to install and configure poppler for the Answer Card Analyzer, especially for building executables with PyInstaller.

## What is Poppler?

Poppler is a PDF rendering library that the `pdf2image` Python package uses to convert PDF pages to images. For the Answer Card Analyzer to process PDF files, poppler must be available.

## Platform-Specific Setup

### Windows

#### Option 1: Download Pre-built Binaries (Recommended for building)

1. **Download poppler for Windows:**
   - Go to: https://github.com/oschwartz10612/poppler-windows/releases
   - Download the latest release (e.g., `poppler-23.08.0_x86_64.7z`)

2. **Extract to a standard location:**
   ```
   Extract to: C:\poppler\
   ```
   After extraction, you should have: `C:\poppler\bin\pdftoppm.exe`

3. **Configure the build system:**
   Edit `build_config.env` and set:
   ```
   WINDOWS_POPPLER_PATH=C:\poppler\bin
   ```

4. **Build the executable:**
   ```bash
   python build.py
   ```

#### Option 2: Add to System PATH

1. Follow steps 1-2 from Option 1
2. **Add to PATH environment variable:**
   - Open System Properties → Advanced → Environment Variables
   - Add `C:\poppler\bin` to your PATH
   - Restart your command prompt/IDE

#### Option 3: Using Conda

```bash
conda install -c conda-forge poppler
```

### macOS

#### Option 1: Homebrew (Recommended)

```bash
brew install poppler
```

The build script will automatically detect Homebrew-installed poppler.

#### Option 2: MacPorts

```bash
sudo port install poppler
```

#### Manual Configuration

If poppler is installed in a custom location, set in `build_config.env`:
```
MACOS_POPPLER_PATH=/opt/local/bin
```

### Linux

#### Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install poppler-utils
```

#### CentOS/RHEL/Fedora

```bash
# CentOS/RHEL
sudo yum install poppler-utils

# Fedora
sudo dnf install poppler-utils
```

#### Arch Linux

```bash
sudo pacman -S poppler
```

## Testing Poppler Installation

### Command Line Test

**Windows:**
```cmd
pdftoppm.exe -h
```

**macOS/Linux:**
```bash
pdftoppm -h
```

If this command works, poppler is correctly installed and accessible.

### Python Test

Create a test file `test_poppler.py`:

```python
from pdf2image import convert_from_path
import sys
from pathlib import Path

def test_poppler():
    # Test if poppler is accessible
    try:
        # This will test if poppler binaries are found
        from pdf2image.exceptions import PDFInfoNotInstalledError
        import pdf2image.pdf2image as pdf2image_module
        
        # Try to get poppler version
        version = pdf2image_module._get_poppler_version()
        print(f"✅ Poppler version: {version}")
        return True
        
    except PDFInfoNotInstalledError:
        print("❌ Poppler not found in PATH")
        return False
    except Exception as e:
        print(f"❌ Error testing poppler: {e}")
        return False

if __name__ == "__main__":
    success = test_poppler()
    sys.exit(0 if success else 1)
```

Run the test:
```bash
python test_poppler.py
```

## Building with Poppler Support

### Automatic Detection

The build script automatically detects poppler in these locations:

**Windows:**
- `C:\poppler\bin`
- `C:\Program Files\poppler\bin`  
- `C:\Program Files (x86)\poppler\bin`
- `C:\tools\poppler\bin`
- System PATH

**macOS:**
- Homebrew installation via `brew --prefix poppler`
- System PATH

**Linux:**
- `/usr/bin`
- `/usr/local/bin`
- `/opt/poppler/bin`
- System PATH

### Manual Configuration

If poppler is in a custom location, edit `build_config.env`:

```env
# Windows
WINDOWS_POPPLER_PATH=D:\custom\poppler\bin

# macOS  
MACOS_POPPLER_PATH=/opt/custom/bin

# Linux
LINUX_POPPLER_PATH=/opt/custom/bin
```

### Build Process

1. **Run the build script:**
   ```bash
   python build.py
   ```

2. **Check build output:**
   The script will show whether poppler was found and included:
   ```
   ✅ Found poppler at: C:\poppler\bin
      Including 8 poppler binaries
   
   🔧 Poppler integration: ✅ Included 8 binaries
   ```

3. **If poppler is not found:**
   ```
   ⚠️  Poppler not found - PDF processing may not work in built executable
   
   📋 Poppler Installation Instructions for Windows:
   1. Download poppler for Windows from: https://github.com/oschwartz10612/poppler-windows/releases
   2. Extract to C:\poppler (or another location)
   3. Add C:\poppler\bin to your PATH environment variable
   4. Or set WINDOWS_POPPLER_PATH=C:\poppler\bin in build_config.env
   
   Continue build without poppler? (y/N):
   ```

## Troubleshooting

### Common Issues

#### "Unable to get page count. Is poppler installed and in PATH?"

**Cause:** Poppler binaries not found or not accessible.

**Solutions:**
1. Verify poppler installation with command line test
2. Check PATH environment variable
3. Set explicit path in `build_config.env`
4. Rebuild the executable with poppler included

#### "pdf2image.exceptions.PDFInfoNotInstalledError"

**Cause:** `pdfinfo` utility not found.

**Solutions:**
1. Ensure complete poppler installation (not just `pdftoppm`)
2. Verify all poppler utilities are in the same directory
3. Check if antivirus is blocking poppler executables

#### Built Executable Shows Poppler Errors

**Cause:** Poppler binaries not included in the build.

**Solutions:**
1. Verify poppler was detected during build (check build output)
2. Ensure `build_config.env` has correct poppler path
3. Rebuild with poppler properly configured

### Debug Mode

Enable debug mode to see detailed poppler detection:

```bash
python set_debug_mode.py debug on
python build.py
```

This will show detailed information about poppler detection and bundling.

## File Locations After Build

When poppler is successfully bundled, the executable will contain:

```
dist/
└── main_processing_computer.exe (or .app on macOS)
    └── (internal structure)
        └── poppler/
            ├── pdftoppm.exe (Windows) or pdftoppm (Unix)
            ├── pdfinfo.exe (Windows) or pdfinfo (Unix)
            ├── pdftocairo.exe (Windows) or pdftocairo (Unix)
            └── *.dll files (Windows only)
```

The application automatically detects and uses these bundled binaries at runtime. 