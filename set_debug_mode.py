#!/usr/bin/env python3
"""
Utility script to easily toggle debug mode and environment settings
for Answer Card Analyzer.
"""

import sys
from pathlib import Path
from typing import Dict, Any


def load_config(config_file: str = "runtime_config.env") -> Dict[str, str]:
    """Load current configuration from file."""
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


def save_config(config: Dict[str, str], config_file: str = "runtime_config.env") -> None:
    """Save configuration to file."""
    lines = []
    
    # Read existing file to preserve comments and structure
    config_path = Path(config_file)
    if config_path.exists():
        with open(config_path, 'r') as f:
            for line in f:
                line_stripped = line.strip()
                if line_stripped and not line_stripped.startswith('#') and '=' in line_stripped:
                    key, _ = line_stripped.split('=', 1)
                    key = key.strip()
                    if key in config:
                        lines.append(f"{key}={config[key]}\n")
                        del config[key]  # Remove from dict so we don't add it again
                    else:
                        lines.append(line)
                else:
                    lines.append(line)
    
    # Add any remaining config items
    for key, value in config.items():
        lines.append(f"{key}={value}\n")
    
    with open(config_path, 'w') as f:
        f.writelines(lines)


def set_debug_mode(enabled: bool) -> None:
    """Enable or disable debug mode."""
    config = load_config()
    config['DEBUG_MODE'] = 'true' if enabled else 'false'
    save_config(config)
    
    status = "enabled" if enabled else "disabled"
    print(f"✅ Debug mode {status}")


def set_environment(env: str) -> None:
    """Set environment (DEV/PROD)."""
    env = env.upper()
    if env not in ['DEV', 'PROD']:
        print("❌ Environment must be 'DEV' or 'PROD'")
        return
    
    config = load_config()
    config['ENVIRONMENT'] = env
    save_config(config)
    
    print(f"✅ Environment set to {env}")


def set_log_level(level: str) -> None:
    """Set logging level."""
    level = level.upper()
    if level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
        print("❌ Log level must be one of: DEBUG, INFO, WARNING, ERROR")
        return
    
    config = load_config()
    config['LOG_LEVEL'] = level
    save_config(config)
    
    print(f"✅ Log level set to {level}")


def show_current_config() -> None:
    """Display current configuration."""
    config = load_config()
    
    print("🔧 Current Configuration:")
    print(f"   Debug Mode: {config.get('DEBUG_MODE', 'false')}")
    print(f"   Environment: {config.get('ENVIRONMENT', 'PROD')}")
    print(f"   Log Level: {config.get('LOG_LEVEL', 'INFO')}")
    print(f"   HTTP Port (DEV): {config.get('HTTP_PORT_DEV', '8000')}")
    print(f"   HTTP Port (PROD): {config.get('HTTP_PORT_PROD', '8080')}")
    print(f"   Memory Threshold: {config.get('MEMORY_THRESHOLD_PERCENT', '90')}%")


def print_usage() -> None:
    """Print usage information."""
    print("🔧 Debug Mode Configuration Utility")
    print()
    print("Usage:")
    print("  python set_debug_mode.py [command] [options]")
    print()
    print("Commands:")
    print("  debug on          - Enable debug mode")
    print("  debug off         - Disable debug mode")
    print("  env dev           - Set environment to development")
    print("  env prod          - Set environment to production")
    print("  log [level]       - Set log level (DEBUG, INFO, WARNING, ERROR)")
    print("  show              - Show current configuration")
    print("  help              - Show this help message")
    print()
    print("Examples:")
    print("  python set_debug_mode.py debug on")
    print("  python set_debug_mode.py env dev")
    print("  python set_debug_mode.py log DEBUG")
    print("  python set_debug_mode.py show")


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print_usage()
        return
    
    command = sys.argv[1].lower()
    
    if command == 'debug':
        if len(sys.argv) < 3:
            print("❌ Missing debug mode argument (on/off)")
            return
        
        mode = sys.argv[2].lower()
        if mode in ['on', 'true', '1', 'enable']:
            set_debug_mode(True)
        elif mode in ['off', 'false', '0', 'disable']:
            set_debug_mode(False)
        else:
            print("❌ Debug mode must be 'on' or 'off'")
    
    elif command == 'env':
        if len(sys.argv) < 3:
            print("❌ Missing environment argument (dev/prod)")
            return
        
        set_environment(sys.argv[2])
    
    elif command == 'log':
        if len(sys.argv) < 3:
            print("❌ Missing log level argument")
            return
        
        set_log_level(sys.argv[2])
    
    elif command == 'show':
        show_current_config()
    
    elif command in ['help', '--help', '-h']:
        print_usage()
    
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    main() 