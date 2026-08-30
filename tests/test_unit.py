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


def test_tags_option_accepted_on_all_vm_subcommands(monkeypatch):
    for cmd in ("ls", "reboot", "update", "reconcile", "shutdown", "start"):
        monkeypatch.setattr(cli.sys, "argv", ["hexagon", cmd, "--tags", "foo"])
        args = cli.parse_args()
        assert args.tags == "foo", cmd


def test_update_skip_dom0_flag_parses(monkeypatch):
    monkeypatch.setattr(cli.sys, "argv", ["hexagon", "update", "--skip-dom0"])
    assert cli.parse_args().skip_dom0 is True
    monkeypatch.setattr(cli.sys, "argv", ["hexagon", "update"])
    assert cli.parse_args().skip_dom0 is False


def test_update_scope_aliases_parse(monkeypatch):
    for flag in ("--vms", "--domus"):
        monkeypatch.setattr(cli.sys, "argv", ["hexagon", "update", flag])
        assert cli.parse_args().skip_dom0 is True, flag
    monkeypatch.setattr(cli.sys, "argv", ["hexagon", "update", "--dom0"])
    assert cli.parse_args().only_dom0 is True


def test_update_dom0_and_vms_flags_are_exclusive(monkeypatch):
    monkeypatch.setattr(cli.sys, "argv", ["hexagon", "update", "--dom0", "--vms"])
    with pytest.raises(SystemExit) as excinfo:
        cli.parse_args()
    assert excinfo.value.code == 2


def test_reboot_terminal_flag_parses(monkeypatch):
    for flag in ("-t", "--terminal"):
        monkeypatch.setattr(cli.sys, "argv", ["hexagon", "reboot", flag, "work-vm"])
        args = cli.parse_args()
        assert args.terminal is True, flag
        assert args.vms == ["work-vm"]


def test_dom0_update_cmd():
    assert qmgr.dom0_update_cmd() == ["sudo", "qubes-dom0-update", "-y"]


def test_vm_update_cmd_with_targets():
    assert qmgr.vm_update_cmd(["a", "b"], 4) == [
        "qubes-vm-update",
        "--max-concurrency",
        "4",
        "--targets",
        "a,b",
    ]


def test_vm_update_cmd_no_targets_updates_if_available():
    assert qmgr.vm_update_cmd([], 2)[-1] == "--update-if-available"


def test_vm_update_cmd_no_targets_force():
    assert qmgr.vm_update_cmd([], 2, force=True)[-1] == "--force-update"


def test_vm_update_cmd_targets_win_over_force():
    cmd = qmgr.vm_update_cmd(["a"], 2, force=True)
    assert "--targets" in cmd
    assert "--force-update" not in cmd


@pytest.fixture
def record_check_call(monkeypatch):
    calls = []
    monkeypatch.setattr(cli.subprocess, "check_call", lambda cmd: calls.append(cmd))
    return calls


def _run_update(monkeypatch, *argv):
    monkeypatch.setattr(cli.sys, "argv", ["hexagon", *argv])
    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    return excinfo.value.code


def test_update_runs_dom0_then_vm_update(fake_qubes, monkeypatch, record_check_call):
    assert _run_update(monkeypatch, "update") == 0
    assert record_check_call == [
        ["sudo", "qubes-dom0-update", "-y"],
        ["qubes-vm-update", "--max-concurrency", "5", "--update-if-available"],
    ]


def test_upgrade_aliases_update(fake_qubes, monkeypatch, record_check_call):
    assert _run_update(monkeypatch, "upgrade") == 0
    assert record_check_call == [
        ["sudo", "qubes-dom0-update", "-y"],
        ["qubes-vm-update", "--max-concurrency", "5", "--update-if-available"],
    ]


def test_update_skip_dom0(fake_qubes, monkeypatch, record_check_call):
    assert _run_update(monkeypatch, "update", "--skip-dom0") == 0
    assert record_check_call == [
        ["qubes-vm-update", "--max-concurrency", "5", "--update-if-available"]
    ]


def test_update_named_vm_skips_dom0(fake_qubes, monkeypatch, record_check_call):
    assert _run_update(monkeypatch, "update", "work-vm") == 0
    assert record_check_call == [
        ["qubes-vm-update", "--max-concurrency", "5", "--targets", "work-vm"]
    ]


def test_update_dom0_only(fake_qubes, monkeypatch, record_check_call):
    assert _run_update(monkeypatch, "update", "dom0") == 0
    assert record_check_call == [["sudo", "qubes-dom0-update", "-y"]]


def test_update_dom0_flag_skips_vms(fake_qubes, monkeypatch, record_check_call):
    assert _run_update(monkeypatch, "update", "--dom0") == 0
    assert record_check_call == [["sudo", "qubes-dom0-update", "-y"]]


def test_update_vms_flag_skips_dom0(fake_qubes, monkeypatch, record_check_call):
    assert _run_update(monkeypatch, "update", "--vms") == 0
    assert record_check_call == [
        ["qubes-vm-update", "--max-concurrency", "5", "--update-if-available"]
    ]


def test_update_dom0_flag_rejects_named_vms(fake_qubes, monkeypatch, record_check_call):
    assert _run_update(monkeypatch, "update", "--dom0", "work-vm") == 1
    assert record_check_call == []


def test_update_dry_run_logs_without_running(fake_qubes, monkeypatch, record_check_call, caplog):
    caplog.set_level("DEBUG")
    assert _run_update(monkeypatch, "--dry-run", "update") == 0
    assert record_check_call == []
    assert "Would run: sudo qubes-dom0-update -y" in caplog.text
    assert "Would run: qubes-vm-update" in caplog.text


def test_update_failure_exits_nonzero_but_continues(fake_qubes, monkeypatch):
    calls = []

    def failing_check_call(cmd):
        calls.append(cmd)
        raise cli.subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(cli.subprocess, "check_call", failing_check_call)
    assert _run_update(monkeypatch, "update") == 1
    # dom0 failure must not abort the VM update.
    assert len(calls) == 2


class FakeDomains(dict):
    """Mimic qubesadmin's domains collection: iteration yields VM objects,
    membership and indexing are by name."""

    def __iter__(self):
        return iter(self.values())


def _tagged_fake_domains(fake_qubes):
    class FakeVM:
        def __init__(self, name, tags):
            self.name = name
            self.tags = tags

    fake_qubes.domains = FakeDomains(
        {
            "tagged-1": FakeVM("tagged-1", {"foo"}),
            "tagged-2": FakeVM("tagged-2", {"foo"}),
            "untagged": FakeVM("untagged", set()),
        }
    )


def test_shutdown_selects_vms_by_tag(fake_qubes, monkeypatch, caplog):
    caplog.set_level("DEBUG")
    _tagged_fake_domains(fake_qubes)
    monkeypatch.setattr(cli.sys, "argv", ["hexagon", "--dry-run", "shutdown", "--tags", "foo"])

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 0
    assert "tagged-1" in caplog.text
    assert "tagged-2" in caplog.text
    assert "untagged" not in caplog.text


def test_tags_narrow_explicitly_named_vms(fake_qubes, monkeypatch, caplog):
    caplog.set_level("DEBUG")
    _tagged_fake_domains(fake_qubes)
    argv = ["hexagon", "--dry-run", "shutdown", "--tags", "foo", "tagged-1", "untagged"]
    monkeypatch.setattr(cli.sys, "argv", argv)

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 0
    assert "tagged-1" in caplog.text
    assert "untagged" not in caplog.text


def test_no_vms_matching_tag_errors(fake_qubes, monkeypatch):
    _tagged_fake_domains(fake_qubes)
    monkeypatch.setattr(cli.sys, "argv", ["hexagon", "shutdown", "--tags", "no-such-tag"])

    with pytest.raises(SystemExit) as excinfo:
        cli.main()

    assert excinfo.value.code == 1


def test_reboot_vm_opens_terminal_after_reboot(fake_qubes, monkeypatch):
    calls = []
    monkeypatch.setattr(qmgr.HexagonQube, "reboot", lambda self: calls.append("reboot"))
    monkeypatch.setattr(qmgr.HexagonQube, "open_terminal", lambda self: calls.append("terminal"))

    cli.reboot_vm(types.SimpleNamespace(terminal=True), "work-vm")
    assert calls == ["reboot", "terminal"]

    calls.clear()
    cli.reboot_vm(types.SimpleNamespace(terminal=False), "work-vm")
    assert calls == ["reboot"]


def _terminal_vm(fake_qubes, rc):
    """Install a fake "work-vm" whose run_service returns a Popen-alike that
    has already exited with `rc`, or is still running when rc is None."""
    recorded = {}

    class FakePopen:
        def wait(self, timeout=None):
            if rc is None:
                raise qmgr.subprocess.TimeoutExpired("qrexec", timeout)
            return rc

    class FakeVM:
        def __init__(self, name):
            self.name = name
            self.tags = set()

        def run_service(self, service, **kwargs):
            recorded["service"] = service
            recorded["kwargs"] = kwargs
            return FakePopen()

    fake_qubes.domains["work-vm"] = FakeVM("work-vm")
    return recorded


def test_open_terminal_launches_detached(fake_qubes):
    recorded = _terminal_vm(fake_qubes, rc=None)
    qmgr.HexagonQube("work-vm").open_terminal()

    assert recorded["service"] == "qubes.StartApp+qubes-run-terminal"
    # Fire-and-forget: no dangling pipes, not tied to hexagon's session...
    assert recorded["kwargs"]["start_new_session"] is True
    assert recorded["kwargs"]["stdin"] is qmgr.subprocess.DEVNULL
    # ...but stderr is inherited, so a qrexec "Request refused" stays visible.
    assert "stderr" not in recorded["kwargs"]
    # `wait=False` would raise from an AppVM (qubesadmin QubesRemote); rely on
    # run_service returning a Popen without waiting instead.
    assert "wait" not in recorded["kwargs"]


def test_open_terminal_reports_early_failure(fake_qubes):
    # e.g. refused by qrexec policy from a management qube: exits 126 at once.
    _terminal_vm(fake_qubes, rc=126)
    with pytest.raises(qmgr.subprocess.CalledProcessError):
        qmgr.HexagonQube("work-vm").open_terminal()


def test_open_terminal_accepts_quick_clean_exit(fake_qubes):
    # A launcher that detaches and exits 0 immediately is still a success.
    _terminal_vm(fake_qubes, rc=0)
    qmgr.HexagonQube("work-vm").open_terminal()


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
