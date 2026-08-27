"""Preflight: refuse to run outside Qubes OS, and say exactly why.

hexagon reaches AppVMs via the Nix flake and dom0 via the RPM, so it can land
on a host that isn't Qubes at all, or under an interpreter that can't see the
system's ``qubesadmin``. Each check names the missing piece and its remedy, so
an inadvertent invocation fails fast instead of unwinding into a traceback.

Checks run in dependency order (host, module, Admin API); the first failure
exits with EXIT_CODE. ``hexagon --help``/``--version`` and the pure-text
``policy`` subcommand never reach them.
"""

import glob
import os
import sys

# qubes-core-agent ships this in every Qubes VM (App/Template/Standalone/Disp).
MARKER_VM = "/usr/share/qubes/marker-vm"
# qubes-release ships this in dom0 only; qubesadmin keys QubesLocal on it too.
MARKER_DOM0 = "/etc/qubes-release"

# sysexits(3) EX_UNAVAILABLE (69): distinct from argparse's 2 and hexagon's 1
# for a failed operation, so wrappers can tell "cannot run here" apart.
EXIT_CODE = os.EX_UNAVAILABLE


class PreflightError(Exception):
    """A precondition for running here is unmet; str() names it and the fix."""


def check_qubes_host():
    """We are inside a Qubes VM, or dom0."""
    if os.path.exists(MARKER_VM) or os.path.exists(MARKER_DOM0):
        return
    raise PreflightError(
        "not running inside Qubes OS (found neither {} for a VM nor {} for dom0); "
        "hexagon drives the Qubes Admin API and cannot work here.".format(MARKER_VM, MARKER_DOM0)
    )


def check_qubesadmin():
    """The qubesadmin module (qubes-core-admin-client) is importable."""
    try:
        import qubesadmin  # noqa: F401
    except ImportError as exc:
        raise PreflightError(_missing_qubesadmin(exc)) from exc


def _missing_qubesadmin(exc):
    # Installed for the system Python but invisible to this interpreter (the
    # Nix build ships its own) is a different fix from not installed at all.
    system = sorted(glob.glob("/usr/lib/python3*/*-packages/qubesadmin"))
    if system:
        site_dir = os.path.dirname(system[-1])
        return (
            "qubesadmin is installed under {} but not importable by {} ({}); "
            "expose it with: export PYTHONPATH={}".format(site_dir, sys.executable, exc, site_dir)
        )
    return (
        "qubesadmin is not installed ({}); install qubes-core-admin-client "
        "(in this qube's template: sudo dnf install qubes-core-admin-client)".format(exc)
    )


def check_admin_api():
    """qubesd answers admin.vm.List: it is up and, from a VM, policy admits us.

    Returns the connected app so the caller needn't open a second one.
    """
    import qubesadmin

    app = qubesadmin.Qubes()
    try:
        # Cheapest call proving both transport and the read grant every
        # subcommand relies on. Any failure means the API is unusable, whatever
        # its class (qubesadmin.exc.*, a missing qrexec-client-vm, ...).
        list(app.domains)
    except Exception as exc:
        raise PreflightError(
            "Qubes Admin API unavailable: {}: {}; {}".format(
                type(exc).__name__, str(exc).strip(), _admin_api_hint()
            )
        ) from exc
    return app


def _admin_api_hint():
    if os.path.exists(MARKER_DOM0):
        return "is qubesd running? (systemctl status qubesd)"
    return (
        "from a VM, dom0 qrexec policy must grant this qube admin.vm.List and friends "
        "(see docs/testing.md)"
    )


def run():
    """Verify hexagon can work here, or exit EXIT_CODE with a specific reason.

    Returns the verified Qubes app.
    """
    try:
        check_qubes_host()
        check_qubesadmin()
        return check_admin_api()
    except PreflightError as exc:
        print("hexagon: error: {}".format(exc), file=sys.stderr)
        sys.exit(EXIT_CODE)
