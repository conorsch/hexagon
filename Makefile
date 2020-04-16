.PHONY: lint
lint:
	black --check .
	flake8 --max-line-length 100
	
.PHONY: fmt
fmt:
	black .

.PHONY: test
test:
	pytest-3 -vv

.PHONY: install-deps
install-deps:
	sudo apt install -y black flake8 python3-pytest qubes-core-admin-client
