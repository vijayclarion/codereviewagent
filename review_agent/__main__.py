"""`python -m review_agent` - fetch the review logic, then review with it.

The default path goes through the bootstrap so that a review always reflects the
latest committed logic (FR-012). `python -m review_agent.run` is the way in for
a process that has already been bootstrapped.
"""

import sys

from .bootstrap import main

if __name__ == "__main__":
    sys.exit(main())
