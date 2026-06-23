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

# build RPM for dom0 (native Fedora rpm toolchain; see also: nix build .#rpm)
[group('build')]
rpm:
	./scripts/build-dom0-rpm

# check package reproducibility (builds with the native rpm toolchain)
[group('build')]
reprotest:
	./scripts/reprotest-wrapper

# copy repo contents from AppVM to dom0
[group('dom0')]
clone:
	./scripts/clone-to-dom0

# run unit tests (no Qubes required; runs in the dev shell / CI)
[group('dev')]
test:
	pytest -m unit -vv

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
    ruff python3-pytest python3-build rpm diffoscope reprotest faketime \
    python3-devel qubes-core-admin-client
