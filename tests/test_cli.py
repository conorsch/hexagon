import subprocess

from .base import ensure_vms_absent, ensure_vms_present


def setup_module(module):
    ensure_vms_absent()
    ensure_vms_present()


def teardown_module(module):
    ensure_vms_absent()


def test_ls_by_tag():
    cmd = "./bin/hexagon ls --tags hexagon"
    output = "hexagon-test-1"
    run_hexagon(cmd, expected_output=output)


def test_ls_by_template():
    cmd = "./bin/hexagon ls --template fedora-31"
    output = run_hexagon(cmd)
    stdout_lines = output.split("\n")
    assert "sys-firewall" in stdout_lines
    assert "sys-net" in stdout_lines
    assert "sys-usb" in stdout_lines


def test_ls_by_tag_and_template():
    cmd = "./bin/hexagon ls --tags hexagon --template fedora-31"
    output = "hexagon-test-1"
    run_hexagon(cmd, expected_output=output)


def test_ls_by_name():
    cmd = "./bin/hexagon ls hexagon-test-1"
    output = "hexagon-test-1"
    run_hexagon(cmd, expected_output=output)


"""
All should be possible:

    hexagon ls --tags foo
    hexagon ls --feature updates-available=1
    hexagon reboot --tags network
    hexagon reboot --outdated
    hexagon update --force foo1
    hexagon reconcile
"""


def run_hexagon(cmd, expected_output="", expected_rc=0):
    cmd_l = cmd.split()
    try:
        output = subprocess.check_output(cmd_l)
    except subprocess.CalledProcessError as e:
        assert e.returncode == expected_rc
    output = output.decode("utf-8").rstrip()
    if expected_output:
        assert output == expected_output
    return output
