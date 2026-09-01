"""Unit tests for the preflight that gates every Admin API subcommand.

Each failure mode must be refused with a message naming what's missing and how
to fix it, and with the dedicated exit code, so an inadvertent call on the
wrong host never degenerates into a traceback.
"""

import pathlib
import sys

import pytest

from hexagon import cli, preflight

pytestmark = pytest.mark.unit


@pytest.fixture
def no_markers(monkeypatch, tmp_path):
    """Neither the VM nor the dom0 marker exists: a non-Qubes host."""
    monkeypatch.setattr(preflight, "MARKER_VM", str(tmp_path / "marker-vm"))
    monkeypatch.setattr(preflight, "MARKER_DOM0", str(tmp_path / "qubes-release"))


@pytest.fixture
def no_qubesadmin(monkeypatch):
    """Make ``import qubesadmin`` raise ImportError, as on a bare host."""
    monkeypatch.setitem(sys.modules, "qubesadmin", None)


def _main(monkeypatch, *argv):
    monkeypatch.setattr(cli.sys, "argv", ["hexagon", *argv])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    return excinfo.value.code


# --- host ------------------------------------------------------------------ #


def test_non_qubes_host_is_refused_naming_both_markers(no_markers):
    with pytest.raises(preflight.PreflightError, match="not running inside Qubes OS") as excinfo:
        preflight.check_qubes_host()
    assert preflight.MARKER_VM in str(excinfo.value)
    assert preflight.MARKER_DOM0 in str(excinfo.value)


@pytest.mark.parametrize("marker", ["MARKER_VM", "MARKER_DOM0"])
def test_either_marker_admits_host(no_markers, marker):
    pathlib.Path(getattr(preflight, marker)).touch()
    preflight.check_qubes_host()


# --- qubesadmin ------------------------------------------------------------ #


def test_missing_qubesadmin_names_the_package(no_qubesadmin, monkeypatch):
    monkeypatch.setattr(preflight.glob, "glob", lambda pattern: [])
    with pytest.raises(preflight.PreflightError, match="qubes-core-admin-client"):
        preflight.check_qubesadmin()


def test_qubesadmin_hidden_from_interpreter_hints_pythonpath(no_qubesadmin, monkeypatch):
    # Installed for the system Python (e.g. the Fedora RPM) but hexagon runs
    # under another interpreter (e.g. the Nix flake's): name the fix exactly.
    site = "/usr/lib/python3.14/site-packages"
    monkeypatch.setattr(preflight.glob, "glob", lambda pattern: [site + "/qubesadmin"])
    with pytest.raises(preflight.PreflightError) as excinfo:
        preflight.check_qubesadmin()
    assert "PYTHONPATH={}".format(site) in str(excinfo.value)
    assert sys.executable in str(excinfo.value)


# --- admin api ------------------------------------------------------------- #


def test_reachable_admin_api_returns_the_app(fake_qubes):
    assert preflight.check_admin_api() is fake_qubes


class _Denied:
    @property
    def domains(self):
        raise RuntimeError("Service call error: Request refused")


def test_denied_admin_api_from_vm_hints_policy(fake_qubes, monkeypatch):
    monkeypatch.setattr("qubesadmin.Qubes", _Denied)
    with pytest.raises(preflight.PreflightError) as excinfo:
        preflight.check_admin_api()
    msg = str(excinfo.value)
    assert "RuntimeError: Service call error: Request refused" in msg
    assert "admin.vm.List" in msg


def test_unreachable_admin_api_in_dom0_hints_qubesd(fake_qubes, monkeypatch, tmp_path):
    dom0 = tmp_path / "qubes-release"
    dom0.touch()
    monkeypatch.setattr(preflight, "MARKER_DOM0", str(dom0))
    monkeypatch.setattr("qubesadmin.Qubes", _Denied)
    with pytest.raises(preflight.PreflightError, match="qubesd"):
        preflight.check_admin_api()


# --- run() and the cli ----------------------------------------------------- #


def test_run_exits_with_dedicated_code_and_prefixed_message(no_markers, capsys):
    with pytest.raises(SystemExit) as excinfo:
        preflight.run()
    assert excinfo.value.code == preflight.EXIT_CODE == 69
    assert capsys.readouterr().err.startswith("hexagon: error: not running inside Qubes OS")


def test_vm_subcommands_preflight_before_touching_qubes(no_markers, no_qubesadmin, monkeypatch):
    for cmd in ("ls", "reboot", "update", "reconcile", "shutdown", "start", "terminal"):
        assert _main(monkeypatch, cmd) == preflight.EXIT_CODE, cmd


def test_policy_and_version_need_no_qubes(no_markers, no_qubesadmin, monkeypatch, capsys):
    assert _main(monkeypatch, "policy") == 0
    assert capsys.readouterr().out
    assert _main(monkeypatch, "--version") == 0
