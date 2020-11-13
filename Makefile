.PHONY: lint
lint:
	black --line-length 100 --check .
	flake8 --max-line-length 100

.PHONY: fmt
fmt:
	black --line-length 100 .

.PHONY: clean
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
	sudo apt-get install --no-install-recommends -y black flake8 python3-pytest qubes-core-admin-client \
		rpm rpm-common diffoscope reprotest disorderfs faketime

.PHONY: rpm
rpm: clean
	./scripts/build-dom0-rpm

.PHONY: reprotest
reprotest:
	reprotest -c "make rpm" . "rpm-build/RPMS/noarch/*.rpm"

.PHONY: install
install:
	./scripts/install-rpm
	@echo "###"
	@echo "# Installation complete! Try running:"
	@echo "#    hexagon ls"
	@echo "###"
