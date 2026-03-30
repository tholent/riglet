.PHONY: help install install-server install-ui \
        dev server ui \
        test test-server test-ui lint lint-fix typecheck check \
        build clean

# ── Default ──────────────────────────────────────────────────────────────────

help:
	@echo "Riglet development targets"
	@echo ""
	@echo "  Setup"
	@echo "    install        Install all backend + frontend dependencies"
	@echo "    install-server Install backend dependencies (server/)"
	@echo "    install-ui     Install frontend dependencies (ui/)"
	@echo ""
	@echo "  Dev servers (run in separate terminals)"
	@echo "    server         FastAPI dev server on :8080 (with --reload)"
	@echo "    ui             Svelte dev server on :5173 (proxies /api → :8080)"
	@echo ""
	@echo "  Quality checks"
	@echo "    test           Run all tests (backend + frontend)"
	@echo "    test-server    Run backend pytest suite"
	@echo "    test-ui        Run frontend vitest suite"
	@echo "    lint           Ruff linter (backend)"
	@echo "    lint-fix       Ruff linter with auto-fix (backend)"
	@echo "    typecheck      mypy (backend) + svelte-check (frontend)"
	@echo "    check          All checks: lint + typecheck + test + build"
	@echo ""
	@echo "  Build & clean"
	@echo "    build          Production frontend build → ui/build/"
	@echo "    clean          Remove build artifacts and caches"

# ── Setup ─────────────────────────────────────────────────────────────────────

install: install-server install-ui

install-server:
	cd server && uv sync

install-ui:
	cd ui && npm install

# ── Dev servers ───────────────────────────────────────────────────────────────

server:
	cd server && uv run uvicorn main:app --reload --port 8080

ui:
	cd ui && npm run dev

# ── Quality checks ────────────────────────────────────────────────────────────

test: test-server test-ui

test-server:
	cd server && uv run pytest

test-ui:
	cd ui && npm run test

lint:
	cd server && uv run ruff check .

lint-fix:
	cd server && uv run ruff check --fix .

typecheck:
	cd server && uv run mypy .
	cd ui && npm run check

check: lint typecheck test build
	@echo ""
	@echo "All checks passed."

# ── Build & clean ─────────────────────────────────────────────────────────────

build:
	cd ui && npm run build

clean:
	rm -rf ui/build ui/.svelte-kit
	rm -rf server/.mypy_cache server/.ruff_cache server/.pytest_cache
	find server -type d -name __pycache__ -exec rm -rf {} +
