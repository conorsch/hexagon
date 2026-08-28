# hexagon changelog

## unreleased

- fix(policy): emit `ansible.{Create,Remove}ManagementPolicies` once rather than per admin qube,
  and correct the template comment: their qrexec target is the managed VM (`@tag:hexagon`), the
  disposable is only the `+argument`. Unit test now matches upstream qubes-ansible behavior.
- feat(cli): preflight before every Admin API subcommand — refuses non-Qubes hosts (neither
  `/usr/share/qubes/marker-vm` nor `/etc/qubes-release`), a missing or interpreter-invisible
  `qubesadmin` (naming the `PYTHONPATH` to export), and an unreachable/denied Admin API, each
  with a specific message and exit 69 (`EX_UNAVAILABLE`) instead of a traceback
- feat(update): replace salt/qubesctl with upstream tooling — `sudo qubes-dom0-update -y` for dom0
  and a single batch `qubes-vm-update` call, passing `--max-concurrency` through natively; adds
  `--skip-dom0`. Naming specific VMs now skips dom0; bare `hexagon update` always updates dom0.
- refactor(qmgr): drop dead salt-era helpers (`update`, `updates_available`, `in_dom0`) and their
  latent bugs (truthy `"0"` feature check; bound-method dom0 guard)
- fix(install-rpm): `rpm -qa` always exits 0, so the script always chose `dnf reinstall`, which
  no-ops (exit 0) when the built version isn't installed. Now branches on `rpm -q`, swaps existing
  installs via `rpm -Uvh --replacepkgs --oldpackage`, and verifies the installed NEVR afterwards.
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
