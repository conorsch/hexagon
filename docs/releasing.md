# Releasing

The version is declared in two places:

- `pyproject.toml` — `version = "…"` (read by the Nix RPM derivation for its
  name/metadata, and by the sdist that becomes the RPM's `Source0`).
- `rpm-build/SPECS/hexagon.spec` — `%global version …` (authoritative for the
  built RPM's version).

Keep them in sync with `just bump`, which rewrites both plus the RPM filename in
the README's install example:

```
just bump 0.1.5
```

Then finish the release by hand:

1. Add a `%changelog` entry (newest first) in `rpm-build/SPECS/hexagon.spec`.
2. Build and sanity-check the RPM: `just rpm`.
3. Tag the release:

   ```
   git tag -a -s 0.1.5 -m 'hexagon 0.1.5'
   ```

The build is reproducible by construction (see the "Reproducible builds" section
of the README), so the same tag always yields an identical `noarch` RPM.
