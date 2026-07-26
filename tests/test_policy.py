"""Unit tests for the dom0 Ansible-ManagementVM policy renderer.

Pure string-building, no Qubes required. We assert the invariants that matter:
the scheme is tag-based (source = @tag:<admin-tag>, managed VMs = @tag:<target-tag>),
the disp-mgmt exception is keyed on created-by-<admin>, and CLI overrides thread
through.
"""

import pytest

from hexagon import policy
from hexagon import cli

pytestmark = pytest.mark.unit

ADMIN = "@tag:" + policy.DEFAULT_ADMIN_TAG
TARGET = "@tag:" + policy.DEFAULT_TARGET_TAG

# Default admin qube name used across the test suite
ADMIN_QUBE = "fleet"


def _rules(body):
    """Yield (svc, arg, source, target, rest) for each non-comment rule line."""
    for line in body.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        yield parts[0], parts[1], parts[2], parts[3], parts[4:]


def test_every_grant_sourced_from_admin_tag():
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE])
    for svc, _arg, source, _target, _rest in _rules(body):
        assert source == ADMIN, "grant not sourced from admin tag: {} {}".format(svc, source)


def test_managed_verbs_target_the_target_tag():
    # Management + exec on the MANAGED VMs rides @tag:<target-tag>. Check the
    # TARGET column exactly (col 3) -- not `TARGET in ln`, which would spuriously
    # match the source column @tag:hexagon-admin (superstring of @tag:hexagon).
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE])
    for svc in ("admin.vm.Shutdown", "admin.vm.tag.Set", "admin.vm.property.Set"):
        matches = [ln for ln in body.splitlines() if ln.startswith(svc + " ")]
        assert matches, "missing rule for {}".format(svc)
        assert any(ln.split()[3] == TARGET for ln in matches), "{} not on target tag".format(svc)


def test_proxy_rpc_services_target_the_dispmgmt_created_by_tag():
    # qubes.AnsibleVM / Filecopy / CreateManagementPolicies act on the disp-mgmt
    # DISPOSABLE, not the managed VM -- so they must target @tag:created-by-<admin>
    # (col 3), else the run dies with "126 Request refused". Regression guard.
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE])
    created = "@tag:created-by-" + ADMIN_QUBE
    for svc in ("qubes.AnsibleVM", "qubes.Filecopy", "ansible.CreateManagementPolicies"):
        matches = [ln for ln in body.splitlines() if ln.startswith(svc + " ")]
        assert matches, "missing rule for {}".format(svc)
        targets = {ln.split()[3] for ln in matches}
        assert targets == {created}, "{} targets {}, want {{{}}}".format(svc, targets, created)


def test_create_appvm_targets_dom0():
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE])
    line = next(ln for ln in body.splitlines() if ln.startswith("admin.vm.Create.AppVM "))
    assert line.split()[3] == "dom0"


def test_tag_names_thread_through():
    body = policy.render_policy(admin_tag="ops-admin", target_tag="ops", admin_qubes=[ADMIN_QUBE])
    assert "@tag:ops-admin" in body
    assert "@tag:ops " in body  # trailing space -> the tag as a column, not a substring
    # defaults must not leak
    assert "@tag:hexagon-admin" not in body
    assert "@tag:hexagon " not in body


def test_admin_vm_list_has_both_adminvm_and_target_tag_rules():
    # THE crux: app.domains.get(<host>) returns None ("Host not found") unless
    # admin.vm.List is granted BOTH at @adminvm (the call target) and on the
    # managed VM's tag (qubesd's per-VM list filter). Regression guard for the
    # KeyError('Host ... not found') we hit in the strategy.
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE])
    targets = {ln.split()[3] for ln in body.splitlines() if ln.startswith("admin.vm.List ")}
    assert "@adminvm" in targets, "admin.vm.List missing @adminvm rule"
    assert TARGET in targets, "admin.vm.List missing managed-tag rule"


def test_visibility_reads_scoped_to_target_tag():
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE])
    for svc in (
        "admin.vm.CurrentState",
        "admin.vm.property.Get",
        "admin.vm.feature.Get",
        "admin.vm.tag.Get",
    ):
        matches = [ln for ln in body.splitlines() if ln.startswith(svc + " ")]
        assert any(TARGET in ln for ln in matches), "missing {} on {}".format(svc, TARGET)


def test_dispmgmt_grants_keyed_on_created_by_per_admin():
    # The disp-mgmt exception: lifecycle grants for the disposable are keyed on
    # created-by-<admin> (the RPC's check_tag mandates it), one block per admin.
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE, "petrichor"])
    for aq in (ADMIN_QUBE, "petrichor"):
        tag = "@tag:created-by-" + aq
        for svc in ("admin.vm.Start", "admin.vm.Kill", "admin.vm.property.Set"):
            matches = [ln for ln in body.splitlines() if ln.startswith(svc + " ") and tag in ln]
            assert matches, "missing disp-mgmt {} for admin {}".format(svc, aq)


def test_clone_rides_the_target_tag_no_hardcoded_names():
    # Cloning is permitted by tagging a TemplateVM @tag:<target-tag>; there must
    # be no hardcoded template name in the policy.
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE])
    clone = next(ln for ln in body.splitlines() if ln.startswith("admin.vm.volume.CloneFrom "))
    assert clone.split()[3] == TARGET
    assert "fedora" not in body and "debian" not in body


def test_sys_vm_override():
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE], sys_vms=["sys-net"])
    assert any(
        ln.startswith("admin.vm.property.Get ") and ln.split()[3] == "sys-net"
        for ln in body.splitlines()
    )
    # default sys-VMs must NOT leak when overridden
    assert "sys-usb" not in body


def test_mgmt_dispvm_override():
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE], mgmt_dispvm="custom-mgmt-dvm")
    assert "+custom-mgmt-dvm" in body
    assert "+default-mgmt-dvm" not in body


def test_render_leaves_no_unexpanded_jinja():
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE])
    assert "{{" not in body and "}}" not in body
    assert "{%" not in body and "%}" not in body


def test_every_rule_has_five_columns():
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE])
    for line in body.splitlines():
        if not line or line.startswith("#"):
            continue
        assert len(line.split()) >= 5, "malformed rule: {!r}".format(line)


def test_qubes_proxy_grants_present():
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE])
    for svc in (
        "admin.vm.Create.DispVM",
        "ansible.CreateManagementPolicies",
        "ansible.RemoveManagementPolicies",
        "qubes.AnsibleVM",
        "qubes.Filecopy",
    ):
        assert svc in body, "missing qubes_proxy grant: {}".format(svc)


def test_cli_policy_command_prints_and_exits(monkeypatch, capsys):
    # `hexagon policy` must emit the rendered policy and exit 0 without ever
    # constructing a Qubes app (works in any AppVM, no qrexec grants).
    def boom(*a, **k):
        raise AssertionError("policy must not touch the Admin API")

    monkeypatch.setattr(cli.qubesadmin, "Qubes", boom, raising=False)
    monkeypatch.setattr(cli.sys, "argv", ["hexagon", "policy"])

    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "30-mgmtvm.policy" in out
    assert ADMIN in out
    assert TARGET in out
