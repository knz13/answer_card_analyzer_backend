# Configuration Guide

This guide explains how to configure debug mode and environment settings for the Answer Card Analyzer using the new configuration system.

## Configuration Files

### `runtime_config.env` - Runtime Configuration
This is the main configuration file that controls how the application runs:

```env
# Debug Mode (true/false)
DEBUG_MODE=true

# Environment (DEV/PROD)
ENVIRONMENT=DEV

# Logging Level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# HTTP Server Settings
HTTP_PORT_DEV=8000
HTTP_PORT_PROD=8080
HTTP_HOST=0.0.0.0

# WebSocket Settings
WEBSOCKET_URI_DEV=ws://localhost:8000
WEBSOCKET_URI_PROD=wss://orca-app-h5tlv.ondigitalocean.app

# Memory Monitoring
MEMORY_THRESHOLD_PERCENT=90
MEMORY_CHECK_INTERVAL=2
```

### `build_config.env` - Build Configuration
This file is used by the build system for PyInstaller settings.

## How Debug Mode Works

When debug mode is enabled, the applications will:

1. **Show detailed configuration summary** at startup
2. **Enable verbose logging** through `Utils.set_debug(True)`
3. **Print memory usage statistics** more frequently
4. **Use development WebSocket URIs** and ports

## Quick Configuration Commands

### Using the Configuration Utility Script

```bash
# Enable debug mode
python set_debug_mode.py debug on

# Disable debug mode
python set_debug_mode.py debug off

# Set environment to development
python set_debug_mode.py env dev

# Set environment to production
python set_debug_mode.py env prod

# Change log level
python set_debug_mode.py log DEBUG

# Show current configuration
python set_debug_mode.py show
```

### Manual Configuration

Edit `runtime_config.env` directly:

```env
# For development with debug mode
DEBUG_MODE=true
ENVIRONMENT=DEV
LOG_LEVEL=DEBUG

# For production
DEBUG_MODE=false
ENVIRONMENT=PROD
LOG_LEVEL=INFO
```

## Environment Modes

### Development Mode (`ENVIRONMENT=DEV`)
- Uses `HTTP_PORT_DEV` (default: 8000)
- Connects to `WEBSOCKET_URI_DEV` (default: ws://localhost:8000)
- Typically used with `DEBUG_MODE=true`

### Production Mode (`ENVIRONMENT=PROD`)
- Uses `HTTP_PORT_PROD` (default: 8080)
- Connects to `WEBSOCKET_URI_PROD` (default: wss://orca-app-h5tlv.ondigitalocean.app)
- Typically used with `DEBUG_MODE=false`

## Configuration Loading

The configuration system:

1. **Tries to load python-dotenv** if available (recommended)
2. **Falls back to manual loading** if python-dotenv is not installed
3. **Supports environment variables** as overrides
4. **Provides sensible defaults** for all settings

## Running the Applications

### HTTP Server (`main_http.py`)

```bash
# With debug output
python main_http.py
```

Sample output with debug mode enabled:
```
🔧 Configuration Summary:
   Debug Mode: True
   Environment: DEV
   Log Level: INFO
   HTTP Config: {'host': '0.0.0.0', 'port': 8000, 'is_dev': True}
   WebSocket URI: ws://localhost:8000
   Memory Config: {'threshold_percent': 90, 'check_interval': 2}

🚀 Starting HTTP server on 0.0.0.0:8000
🔧 Environment: Development
🐛 Debug Mode: Enabled
```

### Processing Computer (`main_processing_computer.py`)

```bash
# With debug output
python main_processing_computer.py
```

Sample output with debug mode enabled:
```
🔧 Configuration Summary:
   Debug Mode: True
   Environment: DEV
   Log Level: INFO
   HTTP Config: {'host': '0.0.0.0', 'port': 8000, 'is_dev': True}
   WebSocket URI: ws://localhost:8000
   Memory Config: {'threshold_percent': 90, 'check_interval': 2}

Connected to websocket: ws://localhost:8000
```

## Dependencies

Make sure to install the required dependency:

```bash
pip install python-dotenv
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## Configuration Precedence

1. **Environment variables** (highest priority)
2. **Configuration file** (`runtime_config.env`)
3. **Default values** (lowest priority)

## Troubleshooting

### Configuration Not Loading
- Ensure `runtime_config.env` exists in the same directory as the Python scripts
- Check file permissions
- Verify the file format (key=value pairs)

### Debug Mode Not Working
- Check that `Utils.set_debug()` is being called in your code
- Verify the Utils class supports debug mode
- Ensure `DEBUG_MODE=true` (case-sensitive)

### Port Conflicts
- Change `HTTP_PORT_DEV` or `HTTP_PORT_PROD` in `runtime_config.env`
- Check that the port is not already in use
- Use `netstat -an | grep :8000` (replace 8000 with your port) to check usage 