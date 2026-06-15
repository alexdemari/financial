import sys
from pathlib import Path

# Make fixtures.py importable as a plain module within this test directory
sys.path.insert(0, str(Path(__file__).parent))
