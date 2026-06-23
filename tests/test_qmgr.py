"""Integration tests for hexagon.qmgr against the live Qubes Admin API.

Runs from dom0 or a management AppVM granted access via qrexec policy. All test
VMs are created tagged TEST_TAG and torn down by the make_test_vm fixture.
"""

import pytest

from hexagon import qmgr

from .base import TEMPLATE, TEST_TAG, vm_name

pytestmark = pytest.mark.integration


def test_create_is_tagged_and_templated(make_test_vm, app):
    name = vm_name(1)
    make_test_vm(name)
    assert name in app.domains
    assert TEST_TAG in app.domains[name].tags
    assert str(app.domains[name].template) == TEMPLATE


def test_default_netvm_is_none(make_test_vm):
    vm = make_test_vm(vm_name(2))
    assert str(vm.vm.netvm) == "None"


def test_netvm_change_while_halted(make_test_vm):
    vm = make_test_vm(vm_name(3))
    vm.desired_config["netvm"] = "sys-firewall"
    vm.reconcile()
    assert str(vm.vm.netvm) == "sys-firewall"


def test_no_pending_changes_after_reconcile(make_test_vm):
    name = vm_name(4)
    make_test_vm(name)
    # A fresh view of a just-reconciled VM should report no pending changes.
    fresh = qmgr.HexagonQube(name, template=TEMPLATE)
    assert not fresh.changes_required()
