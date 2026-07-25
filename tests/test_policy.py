"""Unit tests for the dom0 Ansible-ManagementVM policy renderer.

Pure string-building, no Qubes required. The offline analogue of qubesd's own
policy-lint would be nice, but here we assert the invariants that matter:
grants are sourced from the concrete MgmtVM, full management is tag-scoped, and
the CLI overrides thread through.
"""

import pytest

from hexagon import policy
from hexagon import cli

pytestmark = pytest.mark.unit


def test_every_grant_sourced_from_mgmtvm():
    body = policy.render_policy(mgmtvm=policy.DEFAULT_MGMTVM)
    for line in body.splitlines():
        if not line or line.startswith("#"):
            continue
        # Columns: SERVICE ARG SOURCE TARGET ACTION
        source = line.split()[2]
        assert source == policy.DEFAULT_MGMTVM, "grant not sourced from mgmtvm: {}".format(line)


def test_destructive_management_is_tag_scoped():
    body = policy.render_policy(mgmtvm=policy.DEFAULT_MGMTVM)
    tag = "@tag:created-by-" + policy.DEFAULT_MGMTVM
    for svc in ("admin.vm.Remove", "qubes.AnsibleVM", "qubes.Filecopy"):
        matches = [ln for ln in body.splitlines() if ln.startswith(svc + " ")]
        assert matches, "missing rule for {}".format(svc)
        for ln in matches:
            assert tag in ln, "unscoped destructive grant: {}".format(ln)


def test_create_appvm_targets_dom0():
    body = policy.render_policy(mgmtvm=policy.DEFAULT_MGMTVM)
    line = next(ln for ln in body.splitlines() if ln.startswith("admin.vm.Create.AppVM "))
    assert line.split()[3] == "dom0"


def test_mgmtvm_name_threads_into_created_by_tag():
    body = policy.render_policy(mgmtvm="ansible-jawn")
    assert "@tag:created-by-ansible-jawn" in body
    assert "@tag:created-by-" + policy.DEFAULT_MGMTVM not in body


def test_template_and_sys_vm_overrides():
    body = policy.render_policy(
        mgmtvm=policy.DEFAULT_MGMTVM,
        templates=["fedora-99-xfce"],
        sys_vms=["sys-net"],
    )
    assert "fedora-99-xfce" in body
    # defaults must NOT leak when overridden
    assert "debian-13-xfce" not in body
    assert "sys-usb" not in body
    # clone-from and property.Get both reference the custom template
    assert "admin.vm.volume.CloneFrom" in body
    clone = next(ln for ln in body.splitlines() if ln.startswith("admin.vm.volume.CloneFrom "))
    assert clone.split()[3] == "fedora-99-xfce"


def test_mgmt_dispvm_override():
    body = policy.render_policy(mgmtvm=policy.DEFAULT_MGMTVM, mgmt_dispvm="custom-mgmt-dvm")
    assert "+custom-mgmt-dvm" in body
    assert "+default-mgmt-dvm" not in body


def test_render_leaves_no_unexpanded_jinja():
    # Guard the inline template against a mangled edit: no stray {{ }} / {% %}.
    body = policy.render_policy(mgmtvm=policy.DEFAULT_MGMTVM)
    assert "{{" not in body and "}}" not in body
    assert "{%" not in body and "%}" not in body


def test_every_rule_has_five_columns():
    # Each non-comment, non-blank line must be a well-formed qrexec rule:
    # SERVICE ARG SOURCE TARGET ACTION[ tail].
    body = policy.render_policy(mgmtvm=policy.DEFAULT_MGMTVM)
    for line in body.splitlines():
        if not line or line.startswith("#"):
            continue
        assert len(line.split()) >= 5, "malformed rule: {!r}".format(line)


def test_qubes_proxy_grants_present():
    body = policy.render_policy(mgmtvm=policy.DEFAULT_MGMTVM)
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
    tag = "@tag:created-by-{}".format(policy.DEFAULT_MGMTVM)
    assert tag in out
