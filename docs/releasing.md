# Releasing

## Where the version lives

The version is declared in **one** place: `pyproject.toml` (`version = "…"`).
Everything else derives from it:

- `flake.nix` reads it for the derivation names and the sdist that becomes the
  RPM's `Source0`, and passes it to `rpmbuild` as `--define version` /
  `--define srcversion`. The spec has no version literal of its own
  (`Version: %{version}`).
- PEP 440 pre-releases are mapped to rpm tilde form on the way in
  (`0.3.2a2` → `0.3.2~a2`) so they sort *below* the final release.
- The runtime reads it back via the generated `hexagon/_version.py`
  (`hexagon --version`).

Between releases the tree carries an alpha of the *next* version (`0.3.2a2`),
so a build from `main` never collides with a tagged release.

Version recipes (all rewrite `pyproject.toml` only):

| Recipe | Effect |
|--------|--------|
| `just bump` | next alpha: `0.3.1` → `0.3.2a1`, `0.3.2a1` → `0.3.2a2` |
| `just bump-stable` | finalize the current pre-release: `0.3.2a2` → `0.3.2` |
| `just version X.Y.Z` | set an explicit version; also prompts an agent to draft the spec `%changelog` stanza and prints the tag command |

## What must be kept in sync by hand

There are **two changelogs**, and no tooling links them:

- `CHANGELOG.md` — the human-facing one. Work accrues under `## unreleased`.
- `rpm-build/SPECS/hexagon.spec` `%changelog` — what `rpm -q --changelog` shows
  in dom0. One stanza per release, newest first, plain version (no tilde).

Forgetting one of them is the classic slip (0.3.1 shipped with a spec stanza
but no `CHANGELOG.md` section).

## Cutting a release

1. Finalize the version: `just bump-stable` (or `just version X.Y.Z`).
2. `CHANGELOG.md`: rename `## unreleased` to `## X.Y.Z, YYYY-MM-DD` and open a
   fresh, empty `## unreleased` above it.
3. Spec `%changelog`: add the `X.Y.Z` stanza (newest first), mirroring the
   `CHANGELOG.md` section.
4. Verify: `just lint && just test && just rpm`. The RPM in
   `rpm-build/RPMS/noarch/` should carry the new version in its filename.
5. Commit as `chore: release vX.Y.Z` and tag:

   ```
   git tag -a -s X.Y.Z -m 'hexagon X.Y.Z'
   ```

6. Reopen development: `just bump` (→ `X.Y.(Z+1)a1`), commit as
   `chore: bump alpha version`.

The README's install example names a concrete RPM filename; it is
hand-maintained and need not track every release.

The build is reproducible by construction (see the "Reproducible builds" section
of the README), so the same tag always yields an identical `noarch` RPM.
