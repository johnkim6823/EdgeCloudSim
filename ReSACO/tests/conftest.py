"""Makes the `resaco` and `bridge` packages importable regardless of which
directory pytest is invoked from (mirrors the sys.path.insert pattern
already used by bridge/inference_server.py and the scripts/ entry points)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
