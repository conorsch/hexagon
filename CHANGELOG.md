# hexagon changelog

## unreleased

- feat(upgrade): default `--max-concurrency` raised from `2` to `5`
- feat(reboot): `-t`/`--terminal` opens a terminal in each rebooted VM
- feat(update): `--vms`/`--domus` (alias `--skip-dom0`) and `--dom0`
- feat(policy): `hexagon policy --test` renders the integration-test policy for this qube (replaces the `MGMT_QUBE`-placeholder file)
- feat(policy): grant `qubes.VMShell` + `qubes.StartApp` on managed VMs, so `hexagon reboot` works from the MgmtVM
- fix(qmgr): `reboot()` re-fetches the VM first, so a netvm reboot sees its clients
- fix(policy): test policy grants `admin.vm.CurrentState`; drops wildcard `tag.Set`/`tag.Remove` on test VMs
- fix(policy): both policies grant `admin.vm.feature.CheckWithTemplate` (the `poweroff` path needs it)
- fix(install-rpm): query with the host's `rpm`, so `just install` works in an AppVM, not only dom0
- chore: default TemplateVM is now `fedora-43-xfce`

## 0.3.2, 2026-08-28

- fix(policy): emit `ansible.{Create,Remove}ManagementPolicies` once, targeting the managed VM (matches upstream qubes-ansible)
- feat(cli): preflight — non-Qubes host, missing `qubesadmin`, or unreachable Admin API exits 69 with a specific message
- feat(update): delegate to `qubes-dom0-update` and `qubes-vm-update`; add `--skip-dom0`; naming VMs skips dom0
- refactor(qmgr): drop dead salt-era helpers
- fix(install-rpm): detect the installed version via `rpm -q`; upgrade in place and verify the NEVR
- feat(cli): `--tags` filter on all VM subcommands, e.g. `hexagon shutdown --tags foo`
- docs: add `docs/architecture.md`

## 0.3.1, 2026-07-26

- fix: dom0 policy grants for admin vms
- fix(build): remove unused follows declaration

## 0.3.0, 2026-07-25

- feat(cli): default `--mgmtvm` to the running machine's hostname (via `socket.gethostname()`)
- feat(cli): add `hexagon policy` subcommand — renders dom0 qrexec policy for a ManagementVM via Jinja2 template; uses hostname as default source when no `--mgmtvm` given
- build: resolve `qubesadmin` at install time so the same noarch RPM works in dom0 and AppVMs; also softens `qubes-core-admin-client` to `Recommends`
- build: add `packages.hexagon` nix output — `nix profile install .#hexagon`, `nix run .#hexagon`, `nix run .#qvm-reboot` all work
- feat(pyproject): declare `hexagon` console script in `[project.scripts]` (previously only `qvm-reboot`)
- fix(rpm): ship `qvm-reboot` launcher (was a pip entry point but never installed by RPM)
- fix: `hexagon --version` reports the real version (RPM shipped no dist-info for `importlib.metadata`)
- fix(build): support alpha version strings; DRY version via pyproject
- feat(qvm-reboot): add CLI shortcut to reboot qubes via hexagon
- docs: add AGENTS.md

## 0.2.0, 2026-07-03

- test: add integration testing via Qubes Admin API
- meta: set license to GPLv2 everywhere
- build: unify RPM builds under nix devshell

## 0.1.4
- Update docs and defaults for Qubes 4.2
- Move script back /usr/local/bin/hexagon -> /usr/bin/hexagon

## 0.1.3
- Update docs and defaults for Qubes 4.1
- Move script back /usr/bin/hexagon -> /usr/local/bin/hexagon

## 0.1.2
- Fix reconcile action for template migrations
- Support shutdown for DispVMs (destroys them)
- Move script /usr/local/bin/hexagon -> /usr/bin/hexagon
- Add --version flag

## 0.1.1
- Builds RPM, reproducibly, for Qubes 4.0 & 4.1
- Adds CI tests to verify reproducible builds via reprotest

## 0.1.0
- Simply trying to get a working RPM
