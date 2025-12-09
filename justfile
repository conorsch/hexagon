# run project linters
lint:
	black --line-length 100 --check .
	flake8 --max-line-length 100

# format python code
fmt:
	black --line-length 100 .

# remove all non-version-controlled artifacfts from the repo; destructive action!
clean:
	git clean -fdX

# target for copying repo contents from AppVM to dom0
clone:
	./scripts/clone-to-dom0

# run all tests
test:
	PYTHONPATH=$$PWD pytest-3 -vv tests

# install dev dependencies; assumes fedora host system
install-deps:
  sudo dnf install -y black flake8 python3-pytest rpm diffoscope reprotest faketime

# build RPM for dom0
rpm: clean
	./scripts/build-dom0-rpm

# check package reproducibility
reprotest:
	# Run reprotest with all variations
	reprotest -c "just rpm" . "rpm-build/RPMS/noarch/*.rpm"

# check package reproducibility, minimally, for CI-compatibility
reprotest-ci:
	# Disable a few variations, to support CircleCI container environments.
	# Requires a sed hack to reprotest, see .circle/config.yml
	TERM=xterm-256color reprotest --variations "+all, +kernel, -domain_host, -fileordering" -c "make rpm" . "rpm-build/RPMS/noarch/*.rpm"

# install built RPM in dom0
install:
	./scripts/install-rpm
	@echo "###"
	@echo "# Installation complete! Try running:"
	@echo "#    hexagon ls"
	@echo "###"
