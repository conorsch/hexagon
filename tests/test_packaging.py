"""Packaging tests: verify built artifacts ship both console scripts.

Each install target (RPM, wheel, nix) must put both ``hexagon`` and
``qvm-reboot`` on PATH. The spec / pyproject.toml / flake.nix declare them in
different ways, so a regression in any one (e.g. a missing launcher in the RPM
spec) silently breaks the install target. These tests catch that by inspecting
the built artifact's payload.

Skipped unless the relevant tooling is on PATH and the artifact can be built.
Run with: ``pytest -m packaging``.
"""

import shutil
import subprocess
import zipfile

import pytest

pytestmark = pytest.mark.packaging

CONSOLE_SCRIPTS = ["hexagon", "qvm-reboot"]


def _have(cmd):
    return shutil.which(cmd) is not None


# --------------------------------------------------------------------------- #
# RPM payload
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def rpm_path(tmp_path_factory):
    """Build the RPM via `just rpm` and return the path to the .noarch.rpm."""
    if not _have("just"):
        pytest.skip("just not on PATH")
    if not _have("rpm"):
        pytest.skip("rpm not on PATH")
    result = subprocess.run(["just", "rpm"], capture_output=True, text=True, check=True)
    # The last line of `just rpm` output is:
    #   Built: <sha256>  rpm-build/RPMS/noarch/hexagon-*.noarch.rpm
    # but the path is relative to the repo root, so find the artifact directly.
    import glob

    rpms = glob.glob("rpm-build/RPMS/noarch/hexagon-*.noarch.rpm")
    assert rpms, f"just rpm produced no .noarch.rpm\nstdout:\n{result.stdout}"
    assert len(rpms) == 1, f"expected exactly one .noarch.rpm, found: {rpms}"
    return rpms[0]


def test_rpm_contains_both_launchers(rpm_path):
    """The noarch RPM must ship /usr/bin/hexagon and /usr/bin/qvm-reboot."""
    result = subprocess.run(["rpm", "-qlp", rpm_path], capture_output=True, text=True, check=True)
    files = result.stdout.splitlines()
    for script in CONSOLE_SCRIPTS:
        assert f"/usr/bin/{script}" in files, (
            f"RPM missing /usr/bin/{script}\nPayload:\n" + result.stdout
        )


def test_rpm_contains_version_module(rpm_path):
    """The RPM must ship hexagon/_version.py (baked at build time)."""
    result = subprocess.run(["rpm", "-qlp", rpm_path], capture_output=True, text=True, check=True)
    assert "/usr/lib/hexagon/hexagon/_version.py" in result.stdout.splitlines(), (
        "RPM missing _version.py; --version will fall back to 0.0.0+unknown\n" + result.stdout
    )


# --------------------------------------------------------------------------- #
# Wheel (pip install) payload
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def wheel_path(tmp_path_factory):
    """Build the wheel via `python -m build --wheel` and return its path."""
    try:
        from build import ProjectBuilder
    except ImportError:
        pytest.skip("python 'build' module not available (run in nix develop)")
    outdir = tmp_path_factory.mktemp("wheel")
    builder = ProjectBuilder(source_dir=".")
    wheel = builder.build(distribution="wheel", output_directory=str(outdir))
    return wheel


def test_wheel_contains_both_console_scripts(wheel_path):
    """The wheel's entry_points.txt must declare both console scripts."""
    with zipfile.ZipFile(wheel_path) as zf:
        entry_points = [name for name in zf.namelist() if name.endswith("entry_points.txt")]
        assert entry_points, "no entry_points.txt in wheel"
        content = zf.read(entry_points[0]).decode()
    for script in CONSOLE_SCRIPTS:
        assert f"{script} = " in content, f"wheel entry_points.txt missing {script}\n{content}"


# --------------------------------------------------------------------------- #
# Nix package payload
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def nix_store_path():
    """Build the nix package and return its store path."""
    if not _have("nix"):
        pytest.skip("nix not on PATH")
    result = subprocess.run(
        ["nix", "build", ".#hexagon", "--no-link", "--print-out-paths"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_nix_package_contains_both_launchers(nix_store_path):
    """The nix package's bin/ must contain both hexagon and qvm-reboot."""
    import os

    bin_dir = os.path.join(nix_store_path, "bin")
    actual = set(os.listdir(bin_dir))
    # buildPythonApplication wraps each console script as <name> + .<name>-wrapped;
    # check for the unwrapped entry points.
    for script in CONSOLE_SCRIPTS:
        assert script in actual, f"nix package bin/ missing {script}\nContents: {sorted(actual)}"


def test_nix_package_contains_version_module(nix_store_path):
    """The nix package must ship hexagon/_version.py (baked at build time)."""
    import glob
    import os

    pattern = os.path.join(nix_store_path, "lib", "python*", "site-packages", "hexagon")
    matches = glob.glob(pattern)
    assert matches, f"no hexagon/ in nix store path {nix_store_path}"
    version_file = os.path.join(matches[0], "_version.py")
    assert os.path.isfile(version_file), f"nix package missing _version.py at {version_file}"
