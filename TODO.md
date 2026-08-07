# TODO

- [x] add "--tags" option to subcommands, e.g. "hexagon shutdown --tags foo"
- [x] convert `hexagon update` logic to use `qubes-dom0-update -y` unless `--skip-dom0` is applied
- [x] convert `hexagon update` logic to use `qubes-vm-update` for the various per-VM updates; pass appropriate parallelism flags
