"""Integration tests for reboot behavior against the live Qubes Admin API.

These start real VMs, so they're slower than the rest of the suite.
"""

import subprocess

import pytest

from .base import hexagon_cmd, vm_name

pytestmark = pytest.mark.integration


def test_reboot_resets_uptime(make_test_vm):
    vm = make_test_vm(vm_name(1))
    vm.vm.start()
    uptime_before = vm.uptime()
    vm.reboot()
    uptime_after = vm.uptime()
    # After a reboot the VM has only just come back up.
    assert uptime_after < uptime_before


def test_reboot_terminal_flag_is_granted(make_test_vm):
    """End-to-end `reboot -t`. Its qubes.StartApp call is refused unless the
    policy grants it (the interesting case when run from a management qube),
    and hexagon exits non-zero on refusal -- so a clean exit *is* the
    assertion. The terminal window goes away with the VM at teardown."""
    vm = make_test_vm(vm_name(1))
    vm.vm.start()
    uptime_before = vm.uptime()

    subprocess.run(hexagon_cmd("reboot", "-t", vm.name), check=True, timeout=180)

    assert vm.uptime() < uptime_before


def test_reboot_netvm_keeps_client_up(make_test_vm):
    netvm_name = vm_name(1)
    client_name = vm_name(2)
    netvm = make_test_vm(netvm_name, provides_network=True)
    client = make_test_vm(client_name, netvm=netvm_name)
    netvm.vm.start()
    client.vm.start()
    netvm_uptime_before = netvm.uptime()
    client_uptime_before = client.uptime()

    netvm.reboot()

    # The netvm itself restarted...
    assert netvm.uptime() < netvm_uptime_before
    # ...but its client stays up (hexagon's headline feature: reboot a netvm
    # without taking down attached clients), so the client's uptime keeps growing.
    assert client.uptime() > client_uptime_before
