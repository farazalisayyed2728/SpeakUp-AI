.PHONY: up down test lint fmt migrate assets
up:        ; docker compose up --build
down:      ; docker compose down
migrate:   ; docker compose run --rm migrate
test:      ; python -m pytest --cov=apps --cov-report=term-missing
lint:      ; ruff check . && ruff format --check .
fmt:       ; ruff check --fix . && ruff format .
assets:    ; npm ci && npm run build
