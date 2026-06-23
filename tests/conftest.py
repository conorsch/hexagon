"""pytest configuration for the hexagon test suite.

Two tiers of tests, separated by marker:

  * ``unit``        - pure logic, no Qubes. Runs anywhere (Nix dev shell, CI).
                      ``qubesadmin`` is stubbed if it isn't installed, and the
                      ``fake_qubes`` fixture patches ``qubesadmin.Qubes`` with an
                      in-memory app so the real application code can be exercised.
  * ``integration`` - drives the live Qubes Admin API. Works from dom0 *or* from
                      a management AppVM granted access via qrexec policy (the
                      ``qubesadmin.Qubes()`` factory auto-selects the socket vs.
                      qrexec transport). Skipped unless explicitly enabled AND
                      the API is reachable.

Enable integration tests with ``--run-integration`` or ``HEXAGON_INTEGRATION=1``.
See docs/testing.md for the management-qube setup and qrexec policy.
"""

import os
import sys
import types

import pytest

# --------------------------------------------------------------------------- #
# Unit-test support: make `import qubesadmin` succeed without Qubes installed.
# Done at import time so it's in place before test modules (and tests/base.py,
# which imports the app) are collected. A real qubesadmin always wins.
# --------------------------------------------------------------------------- #
if "qubesadmin" not in sys.modules:
    try:
        import qubesadmin  # noqa: F401
    except ImportError:
        _stub = types.ModuleType("qubesadmin")
        _stub.Qubes = None  # replaced per-test by the fake_qubes fixture
        _stub.__doc__ = "Test stub injected by tests/conftest.py (qubesadmin absent)."
        sys.modules["qubesadmin"] = _stub


INTEGRATION_ENV = "HEXAGON_INTEGRATION"


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run integration tests against a live Qubes Admin API",
    )


def _integration_requested(config):
    return config.getoption("--run-integration") or os.environ.get(INTEGRATION_ENV) == "1"


def _admin_api_unavailable_reason():
    """Return a human-readable reason the Admin API can't be used, or None if OK."""
    try:
        import qubesadmin
    except ImportError as exc:  # pragma: no cover - exercised only without Qubes
        return "qubesadmin not importable ({})".format(exc)
    if getattr(qubesadmin, "Qubes", None) is None:
        return "qubesadmin is a test stub (Qubes not installed)"
    try:
        # Cheapest call that proves both connectivity and admin.vm.List access.
        list(qubesadmin.Qubes().domains)
    except Exception as exc:  # qubesadmin.exc.QubesException, qrexec denial, etc.
        return "{}: {}".format(type(exc).__name__, exc)
    return None


def pytest_collection_modifyitems(config, items):
    if _integration_requested(config):
        reason = _admin_api_unavailable_reason()
        skip = (
            pytest.mark.skip(reason="integration enabled but Admin API unavailable: " + reason)
            if reason
            else None
        )
    else:
        skip = pytest.mark.skip(
            reason="integration tests disabled (use --run-integration or HEXAGON_INTEGRATION=1)"
        )
    if skip is None:
        return
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)


# --------------------------------------------------------------------------- #
# Unit fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def fake_qubes(monkeypatch):
    """Patch qubesadmin.Qubes() with an in-memory app exposing ``.domains``.

    Pre-populated with the default template so HexagonQube's template-existence
    check passes. Add fake VMs via ``app.domains[name] = FakeVM(name)``.
    """
    from hexagon.qmgr import DEFAULT_TEMPLATE

    class FakeVM:
        def __init__(self, name):
            self.name = name
            self.tags = set()
            self.features = {}
            self.klass = "AppVM"

    class FakeApp:
        def __init__(self):
            self.domains = {DEFAULT_TEMPLATE: FakeVM(DEFAULT_TEMPLATE)}

    app = FakeApp()
    monkeypatch.setattr("qubesadmin.Qubes", lambda *a, **k: app, raising=False)
    return app


# --------------------------------------------------------------------------- #
# Integration fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session")
def app():
    """Live Qubes app (QubesLocal in dom0, QubesRemote via qrexec from an AppVM)."""
    import qubesadmin

    return qubesadmin.Qubes()


def _remove_test_vms(app):
    """Remove every VM that is BOTH tagged TEST_TAG and name-prefixed. Idempotent."""
    from .base import NAME_PREFIX, TEST_TAG

    targets = [vm for vm in app.domains if vm.name.startswith(NAME_PREFIX) and TEST_TAG in vm.tags]
    # Break netvm dependencies first, so no test VM is "in use" by another at
    # kill/remove time (e.g. a client still pointing at a test netvm).
    for vm in targets:
        try:
            vm.netvm = ""
        except Exception:
            pass
    for vm in targets:
        try:
            if vm.is_running():
                vm.kill()
        except Exception:  # already halted / transient
            pass
    for vm in targets:
        try:
            del app.domains[vm.name]
        except Exception:
            pass


@pytest.fixture
def make_test_vm(app):
    """Factory that creates a tagged test VM and tears all of them down after.

    Creates the VM with its template at creation time, then applies TEST_TAG
    *before* any further configuration, so a tag-scoped policy covers the rest.
    """
    from hexagon import qmgr
    from hexagon.qmgr import CONFIG_DEFAULTS

    from .base import TEMPLATE, TEST_TAG

    _remove_test_vms(app)  # clean slate in case a previous run was interrupted

    def _make(name, **kwargs):
        # Apply hexagon's own defaults (notably netvm=None) so created VMs reflect
        # hexagon behavior rather than the system AppVM defaults. klass/label
        # aren't reconcilable post-create, so they're excluded from desired config.
        config = {k: v for k, v in CONFIG_DEFAULTS.items() if k not in ("klass", "label")}
        config["template"] = TEMPLATE
        config.update(kwargs)
        if name not in app.domains:
            app.add_new_vm("AppVM", name, kwargs.get("label", "blue"), template=config["template"])
        app.domains[name].tags.add(TEST_TAG)
        vm = qmgr.HexagonQube(name, **config)
        vm.reconcile()
        return vm

    yield _make

    _remove_test_vms(app)
