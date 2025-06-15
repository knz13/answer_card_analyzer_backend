# Poppler Setup Guide

This guide explains how to install and configure poppler for the Answer Card Analyzer, especially for building executables with PyInstaller.

## What is Poppler?

Poppler is a PDF rendering library that the `pdf2image` Python package uses to convert PDF pages to images. For the Answer Card Analyzer to process PDF files, poppler must be available.

## Platform-Specific Setup

### Windows

#### Option 1: Local Project Directory (⭐ Recommended for portable builds)

This method bundles poppler directly with your project, making builds completely self-contained and portable.

1. **Download poppler for Windows:**
   - Go to: https://github.com/oschwartz10612/poppler-windows/releases
   - Download the latest release (e.g., `poppler-23.08.0_x86_64.7z`)

2. **Extract and place in your project:**
   ```
   Extract the archive, then copy the poppler folder to your project:
   
   YourProject/
   ├── poppler/
   │   └── bin/
   │       ├── pdftoppm.exe
   │       ├── pdfinfo.exe
   │       ├── pdftocairo.exe
   │       ├── pdfimages.exe
   │       └── *.dll files (freetype, jpeg, etc.)
   ├── build.py
   ├── main_processing_computer.py
   └── ... (other project files)
   ```

3. **Build the executable:**
   ```bash
   python build.py
   ```
   
   The build script will automatically detect the local poppler and show:
   ```
   🎯 Found local poppler in project: /path/to/your/project/poppler/bin
   ✅ Found poppler at: /path/to/your/project/poppler/bin
      Including X poppler binaries
   ```

4. **Benefits of this approach:**
   - ✅ **Portable**: No need to install poppler on build machines
   - ✅ **Consistent**: Same poppler version across all builds  
   - ✅ **Automatic**: Build script detects it automatically
   - ✅ **Self-contained**: Built executable works on any Windows machine
   - ✅ **Version control**: You can commit poppler with your project (if desired)

#### Option 2: Download Pre-built Binaries (System installation)

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

#### Option 3: Add to System PATH

1. Follow steps 1-2 from Option 2
2. **Add to PATH environment variable:**
   - Open System Properties → Advanced → Environment Variables
   - Add `C:\poppler\bin` to your PATH
   - Restart your command prompt/IDE

#### Option 4: Using Conda

```bash
conda install -c conda-forge poppler
```

### macOS

#### Option 1: Homebrew (Recommended)

```bash
brew install poppler
```

The build script will automatically detect Homebrew-installed poppler.

#### Option 2: Local Project Directory

For portable builds, you can also use local poppler on macOS:

1. Download and compile poppler from source or get pre-built binaries
2. Place in your project:
   ```
   YourProject/
   ├── poppler/
   │   └── bin/
   │       ├── pdftoppm
   │       ├── pdfinfo
   │       └── pdftocairo
   └── ... (other files)
   ```

#### Option 3: MacPorts

```bash
sudo port install poppler
```

#### Manual Configuration

If poppler is installed in a custom location, set in `build_config.env`:
```
MACOS_POPPLER_PATH=/opt/local/bin
```

### Linux

#### Option 1: Package Managers (Recommended)

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install poppler-utils
```

**CentOS/RHEL/Fedora:**
```bash
# CentOS/RHEL
sudo yum install poppler-utils

# Fedora
sudo dnf install poppler-utils
```

**Arch Linux:**
```bash
sudo pacman -S poppler
```

#### Option 2: Local Project Directory

For portable builds on Linux:

1. Install poppler-utils via package manager temporarily
2. Copy binaries to your project:
   ```bash
   mkdir -p poppler/bin
   cp /usr/bin/pdftoppm poppler/bin/
   cp /usr/bin/pdfinfo poppler/bin/
   cp /usr/bin/pdftocairo poppler/bin/
   ```

## Build Script Detection Priority

The build script checks for poppler in this order:

1. **🎯 Local project directory** (`./poppler/bin/`)
2. **🔧 Configuration override** (`build_config.env`)
3. **🔍 System PATH** (via `which`/`where` commands)
4. **📁 Common installation paths** (platform-specific)

## Testing Poppler Installation

### Command Line Test

**Windows:**
```cmd
# If using local project poppler
poppler\bin\pdftoppm.exe -h

# If in system PATH
pdftoppm.exe -h
```

**macOS/Linux:**
```bash
# If using local project poppler
./poppler/bin/pdftoppm -h

# If in system PATH
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
- 🎯 `./poppler/bin` (local project directory)
- `C:\poppler\bin`
- `C:\Program Files\poppler\bin`  
- `C:\Program Files (x86)\poppler\bin`
- `C:\tools\poppler\bin`
- System PATH

**macOS:**
- 🎯 `./poppler/bin` (local project directory)
- Homebrew installation via `brew --prefix poppler`
- System PATH

**Linux:**
- 🎯 `./poppler/bin` (local project directory)
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

2. **Check build output for local poppler:**
   ```
   🎯 Found local poppler in project: ./poppler/bin
   ✅ Found poppler at: ./poppler/bin
      Including 8 poppler binaries
   
   🔧 Poppler integration: ✅ Included 8 binaries
   ```

3. **If poppler is not found:**
   ```
   ⚠️  Poppler not found - PDF processing may not work in built executable
   
   📋 Poppler Setup Instructions:
   
   🎯 Option 1: Local Project Directory (Recommended for portable builds)
   1. Download poppler for Windows from: https://github.com/oschwartz10612/poppler-windows/releases
   2. Extract the downloaded archive
   3. Copy the entire poppler folder to your project directory:
      YourProject/
      ├── poppler/
      │   └── bin/
      │       ├── pdftoppm.exe
      │       ├── pdfinfo.exe
      │       └── *.dll files
      ├── build.py
      └── main_processing_computer.py
   4. Run: python build.py
      The build script will automatically detect and bundle the local poppler!
   
   Continue build without poppler? (y/N):
   ```

## Troubleshooting

### Common Issues

#### "Unable to get page count. Is poppler installed and in PATH?"

**Cause:** Poppler binaries not found or not accessible.

**Solutions:**
1. **Use local project directory method** (recommended for Windows)
2. Verify poppler installation with command line test
3. Check PATH environment variable
4. Set explicit path in `build_config.env`
5. Rebuild the executable with poppler included

#### "pdf2image.exceptions.PDFInfoNotInstalledError"

**Cause:** `pdfinfo` utility not found.

**Solutions:**
1. Ensure complete poppler installation (not just `pdftoppm`)
2. Verify all poppler utilities are in the same directory
3. Check if antivirus is blocking poppler executables
4. **Try the local project directory method**

#### Built Executable Shows Poppler Errors

**Cause:** Poppler binaries not included in the build.

**Solutions:**
1. Verify poppler was detected during build (check build output)
2. Ensure `build_config.env` has correct poppler path
3. **Use local project directory method for guaranteed inclusion**
4. Rebuild with poppler properly configured

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

## Git Considerations

### Should you commit poppler binaries?

**Pros of committing poppler:**
- ✅ Everyone gets the same poppler version
- ✅ New developers can build immediately
- ✅ No external dependencies for builds
- ✅ Consistent CI/CD builds

**Cons of committing poppler:**
- ❌ Larger repository size (~50MB for Windows poppler)
- ❌ Binary files in version control

### Recommended approach:

1. **Add to `.gitignore` if repository size is a concern:**
   ```gitignore
   # Poppler binaries (download separately)
   poppler/
   ```

2. **Create a setup script or documentation** for new developers:
   ```bash
   # setup_poppler.sh or setup_poppler.bat
   # Downloads and extracts poppler to the correct location
   ```

3. **Or commit them** if your team prefers convenience over repository size. 