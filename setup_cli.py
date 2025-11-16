#!/usr/bin/env python3
"""
Setup script to install ADAPT CLI command.

This makes the 'adapt' command available globally.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cli.main import cli

if __name__ == '__main__':
    cli()
