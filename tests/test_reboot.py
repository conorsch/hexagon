from .base import ensure_vms_absent, ensure_vms_present
from hexagon import qmgr


CLIENTVM = "hexagon-test-1"
NETVM = "hexagon-test-2"


def setup_module(module):
    ensure_vms_absent()
    ensure_vms_present()
    netvm = qmgr.HexagonQube(NETVM, provides_network=True)
    netvm.reconcile()
    clientvm = qmgr.HexagonQube(CLIENTVM, netvm=NETVM)
    clientvm.reconcile()
    netvm.vm.start()
    clientvm.vm.start()


def teardown_module(module):
    ensure_vms_absent()


def test_reboot_clientvm():
    clientvm = qmgr.HexagonQube(CLIENTVM)
    clientvm_uptime_before = clientvm.uptime()
    clientvm.reboot()
    clientvm_uptime_after = clientvm.uptime()
    assert clientvm_uptime_before > clientvm_uptime_after


def test_reboot_netvm():
    netvm = qmgr.HexagonQube(NETVM)
    netvm_uptime_before = netvm.uptime()

    clientvm = qmgr.HexagonQube(CLIENTVM)
    clientvm_uptime_before = clientvm.uptime()

    netvm.reboot()

    netvm_uptime_after = netvm.uptime()
    assert netvm_uptime_before > netvm_uptime_after
    clientvm_uptime_after = clientvm.uptime()
    assert clientvm_uptime_after > clientvm_uptime_before
