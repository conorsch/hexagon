"""Integration tests for reboot behavior against the live Qubes Admin API.

These start real VMs, so they're slower than the rest of the suite.
"""

import subprocess

import pytest
import qubesadmin

from .base import hexagon_cmd, vm_name

pytestmark = pytest.mark.integration


def _start_time(name):
    """VM boot time, read from a fresh app so nothing is memoized across a
    reboot. A restart yields a strictly newer value -- a cleaner reset signal
    than whole-second uptime, which is too coarse for a fast reboot."""
    return float(qubesadmin.Qubes().domains[name].start_time)


def test_reboot_resets_uptime(make_test_vm):
    vm = make_test_vm(vm_name(1))
    vm.vm.start()
    start_before = _start_time(vm.name)
    vm.reboot()
    # A reboot gives the VM a strictly newer boot time.
    assert _start_time(vm.name) > start_before


def test_reboot_terminal_flag_is_granted(make_test_vm):
    """End-to-end `reboot -t`. Its qubes.StartApp call is refused unless the
    policy grants it (the interesting case when run from a management qube),
    and hexagon exits non-zero on refusal -- so a clean exit *is* the
    assertion. The terminal window goes away with the VM at teardown."""
    vm = make_test_vm(vm_name(1))
    vm.vm.start()
    start_before = _start_time(vm.name)

    subprocess.run(hexagon_cmd("reboot", "-t", vm.name), check=True, timeout=180)

    # Clean exit proves the qubes.StartApp grant; a newer boot proves the reboot.
    assert _start_time(vm.name) > start_before


def test_reboot_netvm_keeps_client_up(make_test_vm):
    netvm_name = vm_name(1)
    client_name = vm_name(2)
    netvm = make_test_vm(netvm_name, provides_network=True)
    client = make_test_vm(client_name, netvm=netvm_name)
    netvm.vm.start()
    client.vm.start()
    netvm_start_before = _start_time(netvm_name)
    client_start_before = _start_time(client_name)

    netvm.reboot()

    # The netvm itself restarted (newer boot)...
    assert _start_time(netvm_name) > netvm_start_before
    # ...but its client stays up (hexagon's headline feature: reboot a netvm
    # without taking down attached clients): same boot, still running.
    assert _start_time(client_name) == client_start_before
    assert client.vm.is_running()
