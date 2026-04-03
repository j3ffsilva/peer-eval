"""
Pytest configuration file.
Adds the project root to sys.path so modules can be imported.
"""

import sys
from pathlib import Path

# Add parent directory (project root) to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
