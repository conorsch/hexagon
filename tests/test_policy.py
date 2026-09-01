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


def _targets_of(body, svc):
    matches = [ln for ln in body.splitlines() if ln.startswith(svc + " ")]
    assert matches, "missing rule for {}".format(svc)
    return {ln.split()[3] for ln in matches}


def test_proxy_exec_services_target_the_dispmgmt_created_by_tag():
    # qubes.AnsibleVM / Filecopy run ON the disp-mgmt DISPOSABLE, not the managed
    # VM -- so they must target @tag:created-by-<admin> (col 3), else the run
    # dies with "126 Request refused". Regression guard.
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE])
    created = "@tag:created-by-" + ADMIN_QUBE
    for svc in ("qubes.AnsibleVM", "qubes.Filecopy"):
        assert _targets_of(body, svc) == {created}, svc


def test_management_policies_rpcs_target_the_managed_vm():
    # qubes_proxy invokes `qrexec-client-vm <managed-vm> ansible.Create...+<disp>`:
    # the qrexec TARGET is the managed VM; the disposable is only the argument
    # (dom0's service checks its created-by tag itself). So col 3 must be the
    # target tag, and the rule must not be repeated per admin qube.
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE, "other-admin"])
    for svc in ("ansible.CreateManagementPolicies", "ansible.RemoveManagementPolicies"):
        assert _targets_of(body, svc) == {TARGET}, svc
        assert sum(ln.startswith(svc + " ") for ln in body.splitlines()) == 1, svc


def test_hexagon_cli_grants_are_plain_calls_into_managed_vms():
    # hexagon's own verbs from the MgmtVM run qrexec services IN the managed VM
    # (reboot: qubes.VMShell for `sudo poweroff`; terminal/reboot -t: qubes.StartApp).
    # They must ride the target tag with a bare `allow`: a target=dom0 redirect
    # (right for admin.* calls) would run them in dom0.
    body = policy.render_policy(admin_qubes=[ADMIN_QUBE])
    expected = {"qubes.VMShell": "*", "qubes.StartApp": "+qubes-run-terminal"}
    seen = {}
    for svc, arg, source, target, rest in _rules(body):
        if svc in expected:
            assert (source, target, rest) == (ADMIN, TARGET, ["allow"]), svc
            seen[svc] = arg
    assert seen == expected


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


# ---------------------------------------------------------------- test policy
MGMT = "fleet"
TEST_TARGET = "@tag:" + policy.TEST_TAG


def _test_rules(admin_qubes=(MGMT,)):
    return list(_rules(policy.render_test_policy(admin_qubes=list(admin_qubes))))


def test_test_policy_every_grant_sourced_from_mgmt_qube():
    for svc, _arg, source, _target, _rest in _test_rules():
        assert source == MGMT, svc


def test_test_policy_admin_calls_redirect_to_adminvm_plain_calls_do_not():
    for svc, _arg, _source, _target, rest in _test_rules():
        expected = ["allow", "target=@adminvm"] if svc.startswith("admin.") else ["allow"]
        assert rest == expected, svc


def test_test_policy_anyvm_grants_are_read_only():
    for svc, _arg, _source, target, _rest in _test_rules():
        if target == "@anyvm":
            assert svc.endswith((".List", ".Get", ".CheckWithTemplate")), (
                "write granted on @anyvm: {}".format(svc)
            )


def test_test_policy_bootstrap_is_the_only_created_by_grant():
    # Not-yet-tagged VMs: the ONE thing allowed is applying the test tag to VMs
    # this qube created (unforgeable created-by-<qube>). Everything else waits
    # for the tag.
    created = [r for r in _test_rules() if r[3] == "@tag:created-by-" + MGMT]
    assert [(r[0], r[1]) for r in created] == [("admin.vm.tag.Set", "+" + policy.TEST_TAG)]


def test_test_policy_writes_scoped_to_test_tag():
    on_tag = {r[0] for r in _test_rules() if r[3] == TEST_TARGET}
    for svc in ("admin.vm.Start", "admin.vm.Kill", "admin.vm.Remove", "admin.vm.property.Set"):
        assert svc in on_tag, svc
    writes_elsewhere = {
        r[0]
        for r in _test_rules()
        if r[3] not in (TEST_TARGET, "@tag:created-by-" + MGMT)
        and not r[0].endswith((".List", ".Get", ".CheckWithTemplate"))
    }
    assert writes_elsewhere == {"admin.vm.Create.AppVM"}


def test_test_policy_tag_power_is_bootstrap_only():
    # qubesd reserves no tag names, so a wildcard tag.Set on test VMs would let
    # the test qube tag one `hexagon-admin` and inherit the Ansible policy.
    # The only tag write: apply the test tag, to VMs this qube created.
    tag_rules = {
        (r[0], r[1], r[3])
        for r in _test_rules()
        if r[0].startswith("admin.vm.tag.") and not r[0].endswith((".Get", ".List"))
    }
    assert tag_rules == {("admin.vm.tag.Set", "+" + policy.TEST_TAG, "@tag:created-by-" + MGMT)}


def test_test_policy_grants_current_state_on_test_vms():
    # qubesadmin turns a refused admin.vm.CurrentState into power state "NA",
    # i.e. is_running() == False -- silently breaking reboot and teardown.
    assert ("admin.vm.CurrentState", "*", MGMT, TEST_TARGET, ["allow", "target=@adminvm"]) in [
        tuple(r) for r in _test_rules()
    ]


def test_policies_grant_check_with_template_for_poweroff():
    # The reboot poweroff path (netvm with clients) runs vm.run("sudo poweroff"),
    # whose qubesadmin prologue reads admin.vm.feature.CheckWithTemplate. Missing
    # it, the headline "reboot without dropping clients" dies "Request refused".
    assert "admin.vm.feature.CheckWithTemplate" in policy.render_test_policy(admin_qubes=[MGMT])
    assert "admin.vm.feature.CheckWithTemplate" in policy.render_policy(admin_qubes=[ADMIN_QUBE])


def test_test_policy_plain_qrexec_calls_into_test_vms():
    plain = {r[0]: (r[1], r[3]) for r in _test_rules() if not r[0].startswith("admin.")}
    assert plain == {
        "qubes.VMShell": ("*", TEST_TARGET),
        "qubes.StartApp": ("+qubes-run-terminal", TEST_TARGET),
    }


def test_test_policy_one_block_per_mgmt_qube():
    rules = _test_rules(admin_qubes=("a", "b"))
    assert {r[2] for r in rules} == {"a", "b"}
    assert len([r for r in rules if r[2] == "a"]) == len(_test_rules())


def test_test_policy_defaults_to_local_hostname():
    body = policy.render_test_policy()
    assert {r[2] for r in _rules(body)} == {policy.DEFAULT_ADMIN_QUBES[0]}


def test_test_policy_well_formed():
    body = policy.render_test_policy(admin_qubes=[MGMT])
    assert "{{" not in body and "{%" not in body
    assert "30-hexagon-test.policy" in body
    for line in body.splitlines():
        if line and not line.startswith("#"):
            assert len(line.split()) >= 5, "malformed rule: {!r}".format(line)


def test_cli_policy_test_flag(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys, "argv", ["hexagon", "policy", "--test", "--admin-qube", MGMT])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    assert capsys.readouterr().out == policy.render_test_policy(admin_qubes=[MGMT])


def test_cli_policy_command_prints_and_exits(monkeypatch, capsys):
    # `hexagon policy` must emit the rendered policy and exit 0 without ever
    # constructing a Qubes app (works in any AppVM, no qrexec grants).
    def boom(*a, **k):
        raise AssertionError("policy must not touch the Admin API")

    monkeypatch.setattr("qubesadmin.Qubes", boom, raising=False)
    monkeypatch.setattr(cli.sys, "argv", ["hexagon", "policy"])

    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "30-mgmtvm.policy" in out
    assert ADMIN in out
    assert TARGET in out
