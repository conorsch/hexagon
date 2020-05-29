import subprocess
import qubesadmin
import time

from hexagon import qmgr


def generate_vm_names(fmt_string="hexagon-test-{}", n=5):
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
        q = qubesadmin.Qubes()
        assert vm_name in q.domains


def ensure_vms_absent():
    for vm_name in generate_vm_names():
        q = qubesadmin.Qubes()
        if vm_name in q.domains:
            subprocess.check_call(["qvm-shutdown", "--wait", vm_name])
            subprocess.check_call(["qvm-remove", "-f", vm_name])
            time.sleep(1)
        q = qubesadmin.Qubes()
        assert vm_name not in q.domains


def test_true():
    assert True


def test_template_change_while_halted():
    vm = qmgr.HexagonQube("hexagon-test-1", template="debian-10")
    q = qubesadmin.Qubes()
    assert vm.name in q.domains
    assert not vm.pending_changes
    assert vm.desired_config["template"] == "debian-10"
    vm.desired_config["template"] = "fedora-31"
    vm.reconcile()
    assert vm.desired_config["template"] == "fedora-31"


def test_template_change_while_running():
    vm_name = "hexagon-test-2"
    vm = qmgr.HexagonQube(vm_name, template="debian-10", autostart=True)
    q = qubesadmin.Qubes()
    assert vm.name in q.domains
    assert not vm.pending_changes
    assert vm.vm.start_time == ""
    assert get_pref(vm_name, "start_time") == ""
    vm.vm.start()
    assert get_pref(vm_name, "start_time") != ""
    time_before_reconcile = get_pref(vm_name, "start_time")
    assert vm.desired_config["template"] == "debian-10"
    vm.desired_config["template"] = "fedora-31"
    vm.reconcile()
    assert get_pref(vm_name, "template") == "fedora-31"
    # TODO: figure out why this reboot cycle is required
    # Maybe the reconcile isn't rebooting?
    vm.ensure_halted()
    vm.vm.start()
    time_after_reconcile = get_pref(vm_name, "start_time")
    assert time_after_reconcile > time_before_reconcile


def test_default_netvm_is_none():
    vm_name = "hexagon-test-3"
    q = qubesadmin.Qubes()
    assert vm_name in q.domains
    vm = qmgr.HexagonQube(vm_name, template="debian-10")
    q = qubesadmin.Qubes()
    assert vm_name in q.domains
    vm.reconcile()
    q = qubesadmin.Qubes()
    assert vm.name in q.domains
    assert str(vm.vm.netvm) == "None"


def test_netvm_change_while_running():
    vm = qmgr.HexagonQube("hexagon-test-4", template="debian-10", autostart=True)
    q = qubesadmin.Qubes()
    assert vm.name in q.domains
    assert str(vm.vm.netvm) == "None"
    vm.desired_config["netvm"] = "sys-firewall"
    vm.reconcile()
    assert vm.desired_config["netvm"] == "sys-firewall"


def get_pref(vm_name, pref_name):
    cmd = ["qvm-prefs", vm_name, pref_name]
    results = ""
    try:
        results = subprocess.check_output(cmd).decode("utf-8").strip()
    except subprocess.CalledProcessError:
        pass
    return results


def run_cmd(args=[]):
    cmd = ["./qmgr"]
    cmd += args
    subprocess.check_call(cmd)
