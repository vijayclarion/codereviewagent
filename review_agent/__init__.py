"""AI code review agent for on-prem TFS / Azure DevOps Server pull requests.

Reviews one pull request against its linked user story and the team's shared
checklists, then posts structured feedback back onto the pull request.

A reviewer aid, not a merge gate: it reasons over diff text and cannot verify
runtime behaviour, so a human always decides the merge.
"""

__version__ = "0.1.0"
