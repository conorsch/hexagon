"""Unit tests: pure logic, no Qubes required.

These run in the Nix dev shell and CI. `qubesadmin` is stubbed by
tests/conftest.py and the `fake_qubes` fixture supplies an in-memory app.
"""

import types

import pytest

from hexagon import qmgr
from hexagon import cli

pytestmark = pytest.mark.unit


def test_default_template_is_single_sourced():
    # The suite and CONFIG_DEFAULTS must agree on one default template.
    assert qmgr.CONFIG_DEFAULTS["template"] == qmgr.DEFAULT_TEMPLATE


def test_vmconfigchange_infers_reboot_for_disruptive_attrs():
    for attr in ("label", "template", "vcpus", "virt_mode", "kernel"):
        change = qmgr.VMConfigChange(attr, "old", "new")
        assert change.reboot_required is True, attr


def test_vmconfigchange_no_reboot_for_netvm():
    assert qmgr.VMConfigChange("netvm", None, "sys-firewall").reboot_required is False


def test_vmconfigchange_explicit_reboot_flag_respected():
    assert qmgr.VMConfigChange("autostart", False, True, reboot_required=True).reboot_required


def test_vmconfigchange_apply_casts_vcpus_to_int():
    vm = types.SimpleNamespace()
    qmgr.VMConfigChange("vcpus", "2", "4").apply(vm)
    assert vm.vcpus == 4


def test_vmconfigchange_apply_clears_netvm_when_none():
    vm = types.SimpleNamespace()
    qmgr.VMConfigChange("netvm", "sys-firewall", None).apply(vm)
    assert vm.netvm == ""


def test_vmconfigchange_apply_rejects_unsupported_attr():
    vm = types.SimpleNamespace()
    with pytest.raises(NotImplementedError):
        qmgr.VMConfigChange("bogus", "a", "b").apply(vm)


def test_new_vm_gets_default_config(fake_qubes):
    vm = qmgr.HexagonQube("hexagon-test-1")
    assert vm.desired_config == qmgr.CONFIG_DEFAULTS


def test_unknown_template_raises(fake_qubes):
    with pytest.raises(Exception, match="TemplateVM does not exist"):
        qmgr.HexagonQube("hexagon-test-1", template="no-such-template")


def test_existing_vm_config_not_clobbered(fake_qubes):
    name = "hexagon-test-1"

    class FakeVM:
        def __init__(self, name):
            self.name = name
            self.tags = set()

    fake_qubes.domains[name] = FakeVM(name)
    vm = qmgr.HexagonQube(name)
    # Existing VMs keep their config; desired_config only holds explicit overrides.
    assert vm.desired_config == {}


def test_qvm_reboot_main_execs_hexagon_reboot(monkeypatch):
    # qvm_reboot_main() is a thin wrapper that execs "hexagon reboot <args>".
    # Verify it dispatches correctly: right binary, right subcommand, passthrough argv.
    captured = {}

    def fake_execvp(file, args):
        captured["file"] = file
        captured["args"] = args

    monkeypatch.setattr(cli.os, "execvp", fake_execvp)
    monkeypatch.setattr(cli.sys, "argv", ["qvm-reboot", "sys-net", "sys-firewall"])

    cli.qvm_reboot_main()

    assert captured["file"] == "hexagon"
    assert captured["args"] == ["hexagon", "reboot", "sys-net", "sys-firewall"]


def test_qvm_reboot_main_passes_no_args(monkeypatch):
    # With no extra argv, qvm-reboot should still inject "reboot".
    captured = {}

    def fake_execvp(file, args):
        captured["file"] = file
        captured["args"] = args

    monkeypatch.setattr(cli.os, "execvp", fake_execvp)
    monkeypatch.setattr(cli.sys, "argv", ["qvm-reboot"])

    cli.qvm_reboot_main()

    assert captured["args"] == ["hexagon", "reboot"]
