# Rastro API — tarefas locais (sempre via venv/bin/python)
SHELL := /bin/bash

VENV        ?= venv
PYTHON      := $(VENV)/bin/python
PIP         := $(VENV)/bin/pip
UVICORN     := $(PYTHON) -m uvicorn

HOST        ?= 127.0.0.1
PORT        ?= 8000
APP         ?= app.main:app

.PHONY: help setup venv install env run dev docker-up docker-down health clean

help: ## Lista alvos disponíveis
	@grep -E '^[a-zA-Z0-9_-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: venv install env ## venv + deps + .env a partir do example
	@echo "Pronto. Rode: make dev"

venv: ## Cria ambiente virtual ($(VENV)/)
	@test -d $(VENV) || $(shell command -v python3) -m venv $(VENV)
	@$(PIP) install --upgrade pip

install: venv ## Instala requirements.txt no venv
	@$(PIP) install -r requirements.txt

env: ## Copia .env.example → .env se não existir
	@test -f .env || (cp .env.example .env && echo "Criado .env — edite TURSO_* e SECRET_KEY")

run: install ## Sobe API (sem reload)
	@$(UVICORN) $(APP) --host $(HOST) --port $(PORT)

dev: install ## Sobe API com reload (desenvolvimento)
	@$(UVICORN) $(APP) --reload --host $(HOST) --port $(PORT)

docker-up: ## Docker Compose (build + up)
	docker compose up --build

docker-down: ## Para containers do compose
	docker compose down

health: ## GET /health (PORT=$(PORT))
	@curl -sf "http://$(HOST):$(PORT)/health" | $(PYTHON) -m json.tool || (echo "API não responde em http://$(HOST):$(PORT)"; exit 1)

clean: ## Remove __pycache__ e *.pyc
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
