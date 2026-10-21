ifeq ($(OS),Windows_NT)
    VENV_BIN = .venv/Scripts
    PYTHON = $(if $(wildcard $(VENV_BIN)/python.exe),$(VENV_BIN)/python.exe,python)
    PYTEST = $(if $(wildcard $(VENV_BIN)/pytest.exe),$(VENV_BIN)/pytest.exe,pytest)
    RUFF = $(if $(wildcard $(VENV_BIN)/ruff.exe),$(VENV_BIN)/ruff.exe,ruff)
else
    VENV_BIN = .venv/bin
    PYTHON = $(if $(wildcard $(VENV_BIN)/python),$(VENV_BIN)/python,python3)
    PYTEST = $(if $(wildcard $(VENV_BIN)/pytest),$(VENV_BIN)/pytest,pytest)
    RUFF = $(if $(wildcard $(VENV_BIN)/ruff),$(VENV_BIN)/ruff,ruff)
endif

.PHONY: test lint run smoke

test:
	$(PYTEST) tests/

lint:
	$(RUFF) check .

run:
	$(PYTHON) -m uvicorn skeptid.main:app --host 0.0.0.0 --port 8000

smoke:
	$(PYTHON) tests/e2e_smoke.py
