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

# bump the project version everywhere it's declared (see docs/releasing.md)
[group('build')]
bump version:
	sed -i 's/^version = .*/version = "{{version}}"/' pyproject.toml
	sed -i 's/^%global version .*/%global version {{version}}/' rpm-build/SPECS/hexagon.spec
	sed -i 's/hexagon-[0-9.]\+-1\.noarch\.rpm/hexagon-{{version}}-1.noarch.rpm/' README.md
	@echo "Bumped to {{version}}. Next: add a %changelog entry in rpm-build/SPECS/hexagon.spec, then:"
	@echo "    git tag -a -s {{version}} -m 'hexagon {{version}}'"

# build the dom0 RPM hermetically via Nix; artifact lands in rpm-build/RPMS/noarch/
[group('build')]
rpm:
	nix build .#rpm
	mkdir -p rpm-build/RPMS/noarch
	install -m 0644 result/*.rpm rpm-build/RPMS/noarch/
	@printf '\nBuilt: '; sha256sum rpm-build/RPMS/noarch/*.rpm

# copy repo contents from AppVM to dom0
[group('dom0')]
clone:
	./scripts/clone-to-dom0

# run integration tests (dom0 only; uses system python since qubesadmin isn't in nixpkgs)
[group('dom0')]
test:
	@/usr/bin/python3 -c 'import qubesadmin' 2>/dev/null || { echo "ERROR: qubesadmin not importable; run in dom0 after 'just install-deps'." >&2; exit 1; }
	PYTHONPATH=$$PWD /usr/bin/python3 -m pytest -vv tests

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
