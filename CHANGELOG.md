# hexagon changelog

## unreleased

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
