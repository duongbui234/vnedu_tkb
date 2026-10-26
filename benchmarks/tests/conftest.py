"""Import local benchmark tooling without adding it to the product distribution."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
