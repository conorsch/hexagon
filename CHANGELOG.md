# hexagon changelog

## unreleased

- feat(flake): add `packages.hexagon` nix output — `nix profile install .#hexagon` puts both `hexagon` and `qvm-reboot` on PATH; `nix run .#hexagon` and `nix run .#qvm-reboot` also work. qubesadmin is not bundled (install separately via RPM in dom0)
- feat(pyproject): declare `hexagon` console script in `[project.scripts]` (previously only `qvm-reboot` was declared; `hexagon` was created only by the RPM spec)
- fix(rpm): install `qvm-reboot` launcher (was declared as a pip entry point but never shipped in the noarch RPM)
- fix: `hexagon --version` now reports the real version (was `0.0.0+unknown` when installed via RPM, since the noarch RPM ships no dist-info for `importlib.metadata` to read)
- fix(build): support alpha version strings
- feat: qvm-reboot cli shortcut

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
