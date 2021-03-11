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

.PHONY: watch
watch:
	inotify-hookable -t 1000 -w . -c "make test"

.PHONY: install-deps
install-deps:
	sudo apt install -y black flake8 python3-pytest qubes-core-admin-client inotify-hookable \
		rpm rpm-common diffoscope reprotest

.PHONY: rpm
rpm:
	./scripts/build-dom0-rpm

.PHONY: reprotest
reprotest:
	reprotest -c "make rpm" . "rpm-build/RPMS/noarch/*.rpm"

.PHONY: install
install:
	find hexagon/ -type f -iname '*.pyc' -delete
	find hexagon/ -type d -empty -delete
	sudo install -m 755 -d /usr/lib/python3.5/site-packages/hexagon
	sudo install -m 644 hexagon/* -t /usr/lib/python3.5/site-packages/hexagon
	sudo install -m 755 bin/hexagon /usr/local/bin
	@echo "###"
	@echo "# Installation complete! Try running:"
	@echo "#    hexagon ls"
	@echo "###"
