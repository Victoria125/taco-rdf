"""Write the TACO graph as a NICE-Food subgraph: an entry point to taco_rdf.nice_food.

The same runs as `taco-rdf nice-food`. taco_rdf.nice_food says what the subgraph holds; its names are
available from this script too, as the tests and other scripts read them from here.

    $env:PYTHONPATH = "src"; python scripts/taco_to_nice_food.py
"""

from __future__ import annotations

import sys

from taco_rdf.nice_food import *  # noqa: F403
from taco_rdf.nice_food import main

if __name__ == "__main__":
    sys.exit(main())
