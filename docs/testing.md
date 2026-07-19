# Testing hexagon

The suite has three tiers, separated by pytest marker:

| Tier | Marker | Needs Qubes? | Where it runs | Command |
|------|--------|--------------|---------------|---------|
| Unit | `unit` | No | Anywhere (Nix dev shell, CI) | `just test` |
| Packaging | `packaging` | No | Nix dev shell (needs `just`, `rpm`, `nix`, `python -m build`) | `just test-packaging` |
| Integration | `integration` | Yes (live Admin API) | dom0 **or** a management AppVM | `just test-integration` |

## Unit tests

Pure logic, no Qubes. `qubesadmin` is stubbed by `tests/conftest.py` when it
isn't installed, and the `fake_qubes` fixture supplies an in-memory app, so the
real application code is exercised without a hypervisor. These run under the Nix
dev shell's Python:

```
just test          # pytest -m unit
```

## Packaging tests

Each install target (RPM, wheel, nix) must put both `hexagon` and `qvm-reboot`
on PATH. The spec, `pyproject.toml`, and `flake.nix` declare them in different
ways, so a regression in any one (e.g. a missing launcher in the RPM spec)
silently breaks that install target. These tests catch that by building each
artifact and inspecting its payload.

```
just test-packaging          # nix develop -c pytest -m packaging
```

Each test is skipped if its tooling isn't on PATH, so the suite degrades
gracefully outside the Nix dev shell.

## Integration tests

These drive the real [Qubes Admin API](https://doc.qubes-os.org/en/latest/developer/services/admin-api.html).
`qubesadmin.Qubes()` auto-selects its transport — the `qubesd` socket in dom0,
or qrexec from an AppVM — so the *same* tests run in either place; only the
qrexec policy differs. They are skipped unless explicitly enabled **and** the
Admin API is reachable:

```
just test-integration                  # or:
HEXAGON_INTEGRATION=1 pytest -m integration --run-integration
```

Every test VM is named `hexagon-test-<n>` and tagged `hexagon-test`. The
`make_test_vm` fixture creates them and tears down **only** VMs that are both
tagged and name-prefixed, so a stray run can never touch your real qubes.

### Running from a management AppVM (not dom0)

This is the interesting mode: grant a normal AppVM scoped Admin API access so the
tests never need to run in dom0.

1. Pick the qube that holds your hexagon checkout (the "management qube").
2. In **dom0**, install `qubes/policy.d/30-hexagon-test.policy` as
   `/etc/qubes/policy.d/30-hexagon-test.policy`, replacing `MGMT_QUBE` with that
   qube's name.
3. Install runtime deps in the management qube's template (`just install-deps`).
4. From the management qube: `just test-integration`.

The policy grants the qube permission to **create** test VMs and **fully manage
only the VMs tagged `hexagon-test`** (bootstrapped via the unforgeable
`created-by-<mgmtqube>` tag Qubes applies at creation). It also grants
**read-only** access to all VMs, because `hexagon ls` enumerates every domain.

#### Privilege tiers

- Lifecycle/management on self-created VMs needs only the scoped grant.
- The CLI (`hexagon ls`) additionally needs the global *read* grants in the
  policy — it lists and inspects every VM.
- Nothing in the suite requires write access to VMs it didn't create.

Running in **dom0** needs no policy (dom0 has full access); the same commands
work there.

## Configuration knobs

| Env var | Default | Meaning |
|---------|---------|---------|
| `HEXAGON_INTEGRATION` | unset | `1` enables integration tests (same as `--run-integration`) |
| `HEXAGON_TEST_TEMPLATE` | `hexagon.qmgr.DEFAULT_TEMPLATE` (`fedora-43`) | TemplateVM for created test VMs |
| `HEXAGON_BIN` | unset → `python -m hexagon` | CLI invocation for end-to-end tests; set to `hexagon` to test the installed console script |

The default template lives in **one** place — `hexagon.qmgr.DEFAULT_TEMPLATE` —
and the suite re-imports it (`tests/base.py`); bump it there.
