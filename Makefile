.PHONY: lint
lint:
	black --line-length 100 --check .
	flake8 --max-line-length 100

.PHONY: fmt
fmt:
	black --line-length 100 .  .PHONY: clean
clean:
	git clean -fdX

.PHONY: clone
clone:
	./scripts/clone-to-dom0
.PHONY: test
test:
	PYTHONPATH=$$PWD pytest-3 -vv tests

.PHONY: install-deps
install-deps:
	sudo apt-get install --no-install-recommends -y black flake8 python3-pytest \
		rpm rpm-common diffoscope reprotest disorderfs faketime

.PHONY: rpm
rpm: clean
	./scripts/build-dom0-rpm

.PHONY: reprotest
reprotest:
	# Run reprotest with all variations
	reprotest -c "make rpm" . "rpm-build/RPMS/noarch/*.rpm"

.PHONY: reprotest-ci
reprotest-ci:
	# Disable a few variations, to support CircleCI container environments.
	# Requires a sed hack to reprotest, see .circle/config.yml
	TERM=xterm-256color reprotest --variations "+all, +kernel, -domain_host, -fileordering" -c "make rpm" . "rpm-build/RPMS/noarch/*.rpm"

.PHONY: install
install:
	./scripts/install-rpm
	@echo "###"
	@echo "# Installation complete! Try running:"
	@echo "#    hexagon ls"
	@echo "###"
