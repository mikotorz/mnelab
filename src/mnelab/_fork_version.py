# © MNELAB developers
#
# License: BSD (3-clause)

"""Fork-specific build counter, independent of `pyproject.toml`'s `version` field
(reserved for the upstream-inherited release process, see AGENTS.md).

Bump `FORK_BUILD` by 1 in the same PR that adds a `CHANGELOG.fork.md` entry.
"""

FORK_BUILD = 2
