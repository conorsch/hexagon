# run project linters
[group('dev')]
lint:
	ruff check .
	ruff format --check .

# format python code
[group('dev')]
fmt:
	ruff format .
	ruff check --fix .

# cut a release: finalize version, close both changelogs, verify, commit, reopen alpha
[group('build')]
release *args:
  ./scripts/release {{args}}

# step the alpha pre-release (0.3.1 -> 0.3.2a1; 0.3.2a1 -> 0.3.2a2)
[group('build')]
bump:
  ./scripts/version --alpha --write

# finalize the current pre-release (0.3.2a2 -> 0.3.2)
[group('build')]
bump-stable:
  ./scripts/version --stable --write

# build the default nix package (hexagon + qvm-reboot CLIs)
[group('build')]
build:
	nix build

# build the dom0 RPM hermetically via Nix; artifact lands in rpm-build/RPMS/noarch/
[group('build')]
rpm:
	nix build .#rpm
	mkdir -p rpm-build/RPMS/noarch
	rm -f rpm-build/RPMS/noarch/*.rpm
	install -m 0644 result/*.rpm rpm-build/RPMS/noarch/
	@printf '\nBuilt: '; sha256sum rpm-build/RPMS/noarch/*.rpm

# copy repo contents from AppVM to dom0
[group('dom0')]
clone:
	./scripts/clone-to-dom0

# run unit tests (no Qubes required; runs in the dev shell / CI)
[group('dev')]
test:
	pytest -m unit -vv

# run packaging tests (inspects built RPM, wheel, and nix artifacts)
[group('dev')]
test-packaging:
	nix develop -c pytest -m packaging -vv

# run integration tests against the live Qubes Admin API (dom0 or a management AppVM)
[group('dom0')]
test-integration:
	@/usr/bin/python3 -c 'import qubesadmin' 2>/dev/null || { echo "ERROR: qubesadmin not importable; run in dom0 or a management AppVM after 'just install-deps'." >&2; exit 1; }
	PYTHONPATH=$$PWD /usr/bin/python3 -m pytest -m integration --run-integration -vv

# install built RPM in dom0
[group('dom0')]
install:
	./scripts/install-rpm
	@echo "###"
	@echo "# Installation complete! Try running:"
	@echo "#    hexagon ls"
	@echo "###"

# install dev dependencies; assumes fedora host system
[group('setup')]
install-deps:
  sudo dnf install -y \
    ruff python3-pytest python3-devel qubes-core-admin-client
