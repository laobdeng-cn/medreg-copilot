.PHONY: bootstrap dev demo-up demo-seed api worker beat web db-up db-down migrate db-current infra-up infra-down test test-integration lint build doctor prod-init prod-config prod-build prod-up prod-deploy prod-smoke prod-ps prod-logs prod-backup prod-restore prod-down

PROD_COMPOSE = docker compose --env-file .env.production -f compose.production.yaml

bootstrap:
	./scripts/bootstrap.sh

dev:
	./scripts/dev.sh

demo-up:
	./scripts/demo-up.sh

demo-seed:
	docker compose up -d --wait postgres minio redis qdrant neo4j
	$(MAKE) migrate
	PYTHONPATH=backend/src backend/.venv/bin/python scripts/seed_demo.py

api:
	cd backend && .venv/bin/uvicorn medreg.main:app --reload --host 127.0.0.1 --port 8200

worker:
	cd backend && .venv/bin/celery -A medreg.core.celery_app:celery_app worker --loglevel=INFO --pool=solo

beat:
	cd backend && .venv/bin/celery -A medreg.core.celery_app:celery_app beat --loglevel=INFO

web:
	cd frontend && npm run dev -- --host 127.0.0.1 --port 5273

db-up:
	docker compose up -d --wait postgres

db-down:
	docker compose stop postgres

migrate:
	cd backend && .venv/bin/alembic upgrade head

db-current:
	cd backend && .venv/bin/alembic current

infra-up:
	docker compose up -d --wait

infra-down:
	docker compose down

test:
	cd backend && .venv/bin/pytest

test-integration: db-up migrate
	docker compose up -d --wait minio redis qdrant neo4j
	cd backend && .venv/bin/pytest -m integration

lint:
	cd backend && .venv/bin/ruff check src tests
	cd frontend && npm run lint

build:
	cd frontend && npm run build

doctor:
	./scripts/doctor.sh

prod-init:
	./scripts/init-production-env.sh

prod-config:
	$(PROD_COMPOSE) config --quiet

prod-build: prod-config
	$(PROD_COMPOSE) build

prod-up: prod-config
	$(PROD_COMPOSE) up -d --wait

prod-deploy:
	./scripts/production-deploy.sh

prod-smoke:
	./scripts/production-smoke.sh

prod-ps:
	$(PROD_COMPOSE) ps

prod-logs:
	$(PROD_COMPOSE) logs --tail=200 -f api worker beat web

prod-backup:
	./scripts/production-backup.sh

prod-restore:
	MEDREG_CONFIRM_RESTORE="$(CONFIRM)" ./scripts/production-restore.sh "$(BACKUP_DIR)"

prod-down:
	$(PROD_COMPOSE) down
