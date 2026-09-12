# © MNELAB developers
#
# License: BSD (3-clause)

from mnelab import __fork_version__, __version__
from mnelab._fork_version import FORK_BUILD


def test_fork_version_format():
    """`__fork_version__` embeds the upstream version and the fork build number."""
    assert __fork_version__ == f"{__version__}+mikotorz.{FORK_BUILD}"


def test_fork_build_is_positive_int():
    """`FORK_BUILD` is a simple hand-bumped counter, never 0 or negative."""
    assert isinstance(FORK_BUILD, int)
    assert FORK_BUILD >= 1
