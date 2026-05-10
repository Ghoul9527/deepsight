SHELL := /bin/bash

.PHONY: all install test clean run-mock lint

all: install

install:
	./scripts/setup_venv.sh

test:
	python -m pytest tests/ -v

run-mock:
	./scripts/run_all_mock.sh

clean:
	./scripts/clean.sh

lint:
	python -m ruff check .
	python -m mypy shared/src/ host/src/ pi/src/ tools/src/ --ignore-missing-imports

# Flashing / deployment (placeholder — real targets added in Phase 3)
flash-pico:
	python -m deepsight_tools.cli flash pico

flash-stm32:
	python -m deepsight_tools.cli flash stm32

deploy-pi:
	python -m deepsight_tools.cli deploy pi
