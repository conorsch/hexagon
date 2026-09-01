# Architecture

hexagon is a thin CLI over the [Qubes Admin API](https://doc.qubes-os.org/en/latest/developer/services/admin-api.html)
(`qubesadmin`), installed in dom0 via RPM or in an AppVM via the Nix flake.

| Module | Role |
|--------|------|
| `hexagon/cli.py` | argparse front end; dispatches subcommands, fans VM operations out over a thread pool |
| `hexagon/qmgr.py` | `HexagonQube`: desired-config reconcile, reboot-without-dropping-clients, terminal launching, update commands |
| `hexagon/policy.py` | pure-text rendering of the dom0 qrexec policy for an Ansible ManagementVM |
| `hexagon/preflight.py` | refuses to run where the Admin API can't be reached, with a specific reason |

## Preflight

hexagon only works inside Qubes OS. Every VM-facing subcommand starts with a
preflight (`preflight.run()`, called from `cli.main()`) that checks, in
dependency order, and exits `69` (`EX_UNAVAILABLE` — distinct from argparse's
`2` and hexagon's own `1` for a failed operation) with a specific message on
the first miss:

1. **Qubes host** — `/usr/share/qubes/marker-vm` (shipped by `qubes-core-agent`
   in every VM) or `/etc/qubes-release` (dom0 only; `qubesadmin` keys
   `QubesLocal` on the same file) exists.
2. **`qubesadmin` importable** — i.e. `qubes-core-admin-client` is installed.
   If it's on disk under `/usr/lib/python3*/…-packages` but hexagon runs under
   another interpreter (the Nix flake ships its own Python), the message names
   the exact `PYTHONPATH` to export.
3. **Admin API reachable** — `admin.vm.List` succeeds: qubesd is up (dom0) and
   the qrexec policy admits this qube (AppVM; see [testing.md](testing.md)).
   The app opened for the probe is handed back to `cli.main()`, so no second
   connection is made.

`hexagon --help`, `--version`, and `hexagon policy` never reach the preflight,
so they run anywhere. `qvm-reboot` execs `hexagon reboot`, so it inherits it.

Unit tests fake the environment by monkeypatching `preflight.MARKER_VM` (the
`fake_qubes` fixture) and `sys.modules["qubesadmin"]`; see
`tests/test_preflight.py`.
