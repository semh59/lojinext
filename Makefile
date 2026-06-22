# LojiNext geliştirici komutları.
# Kullanım: `make <komut>`. Windows'ta GNU Make veya `nmake` gerekir.

# .env varsa otomatik yükle — POSTGRES_PASSWORD, REDIS_PASSWORD, vs.
# child process'lere export edilsin. Bunsuz lokal `make test-fast` env'siz
# çalışır ve DB/Redis auth fail eder.
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

.PHONY: help up down logs logs-be logs-fe logs-worker psql redis test test-fast \
        test-unit test-int lint fmt ruff mypy fe-lint fe-test fe-build \
        trace health smoke build rebuild bash precommit clean-models

help:
	@echo "Operasyon:"
	@echo "  up               Docker stack'i ayağa kaldır"
	@echo "  down             Stack'i durdur (data korunur)"
	@echo "  rebuild          Backend+frontend yeniden build + recreate"
	@echo "  health           /api/v1/health JSON yanıtı"
	@echo ""
	@echo "Log + Debug:"
	@echo "  logs-be          backend canlı log akışı"
	@echo "  logs-worker      celery worker log"
	@echo "  logs-fe          frontend (nginx) log"
	@echo "  trace TRACE=xxx  Bir trace_id'ye ait tüm event'ler"
	@echo "  psql             PostgreSQL CLI (lojinext_db)"
	@echo "  redis            Redis CLI"
	@echo "  bash             backend container'da bash"
	@echo ""
	@echo "Kalite:"
	@echo "  lint             ruff (E,F,W,I) + frontend ESLint"
	@echo "  fmt              ruff format + prettier"
	@echo "  mypy             Python type check (baseline aware)"
	@echo "  test-fast        Unit tests (no integration, 30 sn)"
	@echo "  test             Tüm unit+non-integration suite"
	@echo "  fe-test          Frontend vitest"
	@echo "  precommit        pre-commit hook'u her dosyada çalıştır"

# ── Operasyon ──────────────────────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build backend worker celery-beat frontend

rebuild:
	docker compose build backend worker celery-beat frontend
	docker compose up -d --force-recreate backend worker celery-beat frontend

health:
	@curl -s http://127.0.0.1:8000/api/v1/health/ | python -m json.tool || \
	  echo "Backend down — `make up` ?"

smoke:
	@curl -sI http://127.0.0.1/ | head -1
	@curl -sI http://127.0.0.1:8000/api/v1/health/ | head -1
	@curl -sI http://127.0.0.1:3001/ | head -1
	@curl -sI http://127.0.0.1:9090/-/ready | head -1

# ── Log + Debug ────────────────────────────────────────────────────────────
logs-be:
	docker compose logs -f --tail=100 backend

logs-worker:
	docker compose logs -f --tail=100 worker celery-beat

logs-fe:
	docker compose logs -f --tail=50 frontend

# trace_id ile filtreli backend log — debugging'in en pratik aracı
# Kullanım: make trace TRACE=4e1df02e-31f5-4e03-829b-e8f02437823a
trace:
	@if [ -z "$(TRACE)" ]; then \
	  echo "Kullanım: make trace TRACE=<trace_id>"; exit 1; \
	fi
	docker compose logs backend worker celery-beat --since=24h 2>&1 | grep "$(TRACE)"

psql:
	docker compose exec db psql -U lojinext_user -d lojinext_db

redis:
	docker compose exec redis redis-cli

bash:
	docker compose exec backend bash

# ── Kalite ─────────────────────────────────────────────────────────────────
lint:
	ruff check app --select E,F,W,I --ignore=E501
	cd frontend && npm run lint

fmt:
	ruff check app --select E,F,W,I --ignore=E501 --fix
	ruff format app
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,css,json}"

ruff:
	ruff check app --select E,F,W,I --ignore=E501

mypy:
	mypy app --ignore-missing-imports --no-strict-optional

precommit:
	pre-commit run --all-files

# ── Test ───────────────────────────────────────────────────────────────────
# TEST_DATABASE_URL + REDIS_URL ortam değişkeninden okunur. Local dev:
#   POSTGRES_USER=lojinext_user POSTGRES_PASSWORD=... DB_HOST=127.0.0.1 make test-fast
# .env zaten docker compose ile picklenir. Hardcoded user:pass kullanma —
# pre-commit detect-secrets bunu engeller.
TEST_DATABASE_URL ?= $(shell python -c "import os; from urllib.parse import quote_plus as q; u=os.getenv('POSTGRES_USER','lojinext_user'); p=q(os.getenv('POSTGRES_PASSWORD','')); h=os.getenv('DB_HOST','127.0.0.1'); print(f'postgresql+asyncpg://{u}:{p}@{h}:5432/lojinext_test')")
# REDIS_URL — REDIS_PASSWORD özel karakter (parantez/noktalı virgül) içeriyorsa
# urllib.parse port'u parse edemiyor; quote_plus ile URL-encode etmek şart.
REDIS_URL ?= $(shell python -c "import os; from urllib.parse import quote_plus as q; pw=os.getenv('REDIS_PASSWORD',''); h=os.getenv('REDIS_HOST','127.0.0.1'); print((f'redis://default:{q(pw)}@{h}:6379/0' if pw else f'redis://{h}:6379/0'))")

test-fast:
	@TEST_DATABASE_URL="$(TEST_DATABASE_URL)" REDIS_URL="$(REDIS_URL)" \
	  python -m pytest -m unit -q --tb=line

test-unit:
	@TEST_DATABASE_URL="$(TEST_DATABASE_URL)" REDIS_URL="$(REDIS_URL)" \
	  python -m pytest -m "unit or not integration" -q --tb=short

test:
	@TEST_DATABASE_URL="$(TEST_DATABASE_URL)" REDIS_URL="$(REDIS_URL)" \
	  python -m pytest -q --tb=short

test-int:
	@TEST_DATABASE_URL="$(TEST_DATABASE_URL)" REDIS_URL="$(REDIS_URL)" \
	  python -m pytest -m integration -q --tb=short

fe-test:
	cd frontend && npx vitest --run

fe-build:
	cd frontend && npx vite build

# ── Maintenance ────────────────────────────────────────────────────────────
clean-models:
	docker compose exec backend bash -c \
	  "mkdir -p /app/app/models.archive_\$$(date +%Y-%m-%d) && \
	   mv /app/app/models/ensemble_v2_*.{json,joblib,pkl} \
	      /app/app/models.archive_\$$(date +%Y-%m-%d)/ 2>/dev/null || true"
