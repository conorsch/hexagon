"""
Helper functions, pytest fixtures for test suite.
"""
import qubesadmin
from hexagon import qmgr
import subprocess
import time


FEDORA_VERSION = 32


def generate_vm_names(fmt_string="hexagon-test-{}", n=2):
    for i in range(1, n):
        vm_name = fmt_string.format(i)
        yield vm_name


def setup_module(module):
    ensure_vms_absent()
    ensure_vms_present()


def teardown_module(module):
    ensure_vms_absent()


def ensure_vms_present():
    for vm_name in generate_vm_names():
        q = qubesadmin.Qubes()
        if vm_name not in q.domains:
            x = qmgr.HexagonQube(vm_name)
            x.reconcile()
            x.vm.tags.add("hexagon")
        q = qubesadmin.Qubes()
        assert vm_name in q.domains


def ensure_vms_absent():
    for vm_name in generate_vm_names():
        q = qubesadmin.Qubes()
        if vm_name in q.domains:
            subprocess.check_call(["qvm-shutdown", "--wait", vm_name])
            time.sleep(1)
            subprocess.check_call(["qvm-remove", "-f", vm_name])
            time.sleep(1)
        q = qubesadmin.Qubes()
        assert vm_name not in q.domains
