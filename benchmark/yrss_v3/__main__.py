"""Command line for the YRSS evaluation v3 corpus.

``YRSS_V3_TEST_KEY_FILE=/path/to/keyfile python -m benchmark.yrss_v3 seal``

The variable is a path. The key itself is never an argument and never printed.
"""

from __future__ import annotations

import sys

from .corpus import main

if __name__ == "__main__":
    sys.exit(main())
