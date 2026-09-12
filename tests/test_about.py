# © MNELAB developers
#
# License: BSD (3-clause)

from unittest.mock import patch

import pytest

from mnelab import __fork_version__
from mnelab.mainwindow import MainWindow
from mnelab.model import Model


@pytest.fixture
def view(qtbot):
    model = Model()
    win = MainWindow(model)
    model.view = win
    qtbot.addWidget(win)
    return win


def test_show_about_includes_fork_repo_and_build(view):
    """The About dialog links the fork repo and shows the fork build number."""
    with patch("mnelab.mainwindow.QMessageBox") as MockBox:
        view.show_about()

    instance = MockBox.return_value
    informative = instance.setInformativeText.call_args[0][0]
    assert "github.com/mikotorz/mnelab" in informative
    assert "github.com/cbrnr/mnelab" in informative
    assert __fork_version__ in informative
    instance.exec.assert_called_once()
