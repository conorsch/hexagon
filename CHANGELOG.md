# hexagon changelog

## unreleased

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
