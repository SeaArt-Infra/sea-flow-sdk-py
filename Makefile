PYTHON ?= python3
TWINE_REPOSITORY_URL ?=
TWINE_USERNAME ?= __token__
TWINE_PASSWORD ?=

.PHONY: help test clean build check release release-gitlab

help:
	@printf '%s\n' \
		'test           Run unit tests' \
		'clean          Remove build artifacts' \
		'build          Build sdist and wheel' \
		'check          Validate package metadata and distributions' \
		'release        Upload dist/* with default twine settings' \
		'release-gitlab Upload dist/* to GitLab Package Registry'

test:
	$(PYTHON) -m unittest discover -s tests -v

clean:
	rm -rf build dist .pytest_cache htmlcov .coverage .coverage.* *.egg-info sea_flow_sdk.egg-info
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +

build: clean
	$(PYTHON) -m pip install --upgrade build
	$(PYTHON) -m build

check: build
	$(PYTHON) -m pip install --upgrade twine
	$(PYTHON) -m twine check dist/*

release: check
	$(PYTHON) -m pip install --upgrade twine
	$(PYTHON) -m twine upload dist/*

release-gitlab: check
	@test -n "$(TWINE_REPOSITORY_URL)" || (echo "TWINE_REPOSITORY_URL is required"; exit 1)
	@test -n "$(TWINE_PASSWORD)" || (echo "TWINE_PASSWORD is required"; exit 1)
	$(PYTHON) -m pip install --upgrade twine
	$(PYTHON) -m twine upload \
		--repository-url "$(TWINE_REPOSITORY_URL)" \
		-u "$(TWINE_USERNAME)" \
		-p "$(TWINE_PASSWORD)" \
		dist/*
