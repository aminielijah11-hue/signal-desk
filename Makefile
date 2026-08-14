.PHONY: setup lint typecheck test guardrails verify-phase ratchet db.up db.down db.migrate db.reset db.seed

UV := uv
PY_DIR := py
APP_DIR := app

setup:
	@echo "==> Python env (uv, pinned 3.12)"
	cd $(PY_DIR) && $(UV) sync
	@echo "==> Node env"
	cd $(APP_DIR) && npm install
	@echo "==> git hooks"
	cp scripts/hooks/pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
	@echo "==> setup complete"

lint:
	cd $(PY_DIR) && $(UV) run ruff check .
	cd $(PY_DIR) && $(UV) run black --check .
	cd $(APP_DIR) && npm run lint

typecheck:
	cd $(PY_DIR) && $(UV) run mypy --strict ingest scoring research alerting
	cd $(APP_DIR) && npx next typegen && npx tsc --noEmit

test:
	cd $(PY_DIR) && $(UV) run pytest

guardrails:
	python3 scripts/guardrails.py

verify-phase:
	@if [ -z "$(PHASE)" ]; then echo "usage: make verify-phase PHASE=<n>"; exit 2; fi
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test
	$(MAKE) guardrails
	python3 scripts/verify_phase.py $(PHASE)

ratchet:
	@if [ -z "$(SUITE)" ] || [ -z "$(REVERT_PATH)" ] || [ -z "$(ARGS)" ]; then \
		echo "usage: make ratchet SUITE=<name> REVERT_PATH=<path> ARGS=\"<pytest args>\""; \
		exit 2; \
	fi
	python3 scripts/ratchet.py check $(SUITE) $(REVERT_PATH) -- $(ARGS)

db.up:
	docker compose up -d
	@echo "Postgres on localhost:5432 (user=signal_desk db=signal_desk)"

db.down:
	docker compose down

db.migrate:
	cd $(PY_DIR) && $(UV) run python -m ingest.migrate migrate

db.reset:
	cd $(PY_DIR) && $(UV) run python -m ingest.migrate reset

db.seed:
	cd $(PY_DIR) && $(UV) run python -m ingest.sources.sec_tickers
