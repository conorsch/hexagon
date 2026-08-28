# Releasing

## Where the version lives

The version is declared in **one** place: `pyproject.toml` (`version = "…"`),
read and rewritten only by `scripts/version`. Everything else derives from it:

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

`scripts/version` computes by default and writes only with `--write`, so it is
safe to ask it what a bump *would* give:

```
scripts/version                  # 0.3.2a2
scripts/version --stable         # 0.3.2      (finalize a pre-release)
scripts/version --alpha          # 0.3.2a3    (step the alpha)
scripts/version 0.4.0 --write    # set explicitly
```

`just bump` and `just bump-stable` are the `--alpha --write` / `--stable --write`
shorthands, for mid-cycle use. Neither is needed for a release — `just release`
drives both ends itself. (`uv version` would do the same arithmetic, but it
resolves and writes a `uv.lock` that carries the version in a second file,
defeating the single-source rule above; hexagon declares no dependencies for it
to lock anyway.)

## The two changelogs

- `CHANGELOG.md` — the human-facing one. Work accrues under `## unreleased`.
- `rpm-build/SPECS/hexagon.spec` `%changelog` — what `rpm -q --changelog` shows
  in dom0. One stanza per release, newest first, plain version (no tilde).

Forgetting one of them was the classic slip (0.3.1 shipped with a spec stanza
but no `CHANGELOG.md` section). They are no longer written separately: the spec
stanza is **derived** from the `CHANGELOG.md` unreleased block at release time,
so the only thing to curate is `CHANGELOG.md`.

## Cutting a release

Write the `## unreleased` entries as you go, then:

```
just release            # finalize the current pre-release: 0.3.2a2 -> 0.3.2
just release 0.4.0      # or set the version explicitly
just release --tag      # ...and create the signed tag inline
```

`scripts/release` runs the whole ritual, aborting on the first failure:

1. Refuses a dirty tree, an empty `## unreleased` block, a pre-release version,
   or a tag that already exists.
2. Rewrites `version` in `pyproject.toml`.
3. Renames `## unreleased` to `## X.Y.Z, YYYY-MM-DD` and opens a fresh, empty
   `## unreleased` above it.
4. Prepends the matching spec `%changelog` stanza, same notes, rpm date form.
5. Verifies: `just lint && just test && just rpm`, then checks the built RPM
   filename carries `X.Y.Z`.
6. Commits `chore: release vX.Y.Z`.
7. Reopens development at `X.Y.(Z+1)a1`, committed as `chore: bump alpha
   version`.

It stops short of tagging unless given `--tag`, and prints the command pinned to
the release commit:

```
git tag -a -s X.Y.Z -m 'hexagon X.Y.Z' <sha>
```

Nothing is committed until verification passes, so a failed run leaves only
working-tree edits — `git checkout -- .` to abandon it.

The README's install example names a concrete RPM filename; it is
hand-maintained and need not track every release.

The build is reproducible by construction (see the "Reproducible builds" section
of the README), so the same tag always yields an identical `noarch` RPM.
