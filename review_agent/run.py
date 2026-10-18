"""The reviewing entry point - what the fetched copy actually executes.

`bootstrap.py` decides *which* copy of the agent reviews; this module is what
that copy runs. Keeping them apart is what stops the child re-fetching itself,
and it is the reason `python -m review_agent.run` exists as a separate target
from `python -m review_agent`.
"""

import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from review_agent import main as main_module


def main(argv=None, agent_source=None):
    """Review, with no bootstrapping. `agent_source` is the provenance to report."""
    return main_module.main(argv, agent_source=agent_source)


if __name__ == "__main__":
    sys.exit(main())
