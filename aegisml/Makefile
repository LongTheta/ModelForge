.PHONY: install test lint run docker-build docker-run

PYTHON ?= python
DOCKER_IMAGE ?= aegisml:local
UVICORN ?= $(PYTHON) -m uvicorn

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/ -v --tb=short --cov=app --cov=src/retrieval --cov-report=term-missing

lint:
	ruff check app src tests
	ruff format --check app src tests

run:
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8080

docker-build:
	docker build -f docker/Dockerfile -t $(DOCKER_IMAGE) --build-arg GIT_COMMIT=local --build-arg VERSION=local .

docker-run:
	docker run --rm -p 8080:8080 -e AEGISML_ENVIRONMENT=local $(DOCKER_IMAGE)
