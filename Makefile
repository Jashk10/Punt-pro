.PHONY: up down build logs db migrate migrate-new seed test-api test-web fmt

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

# Opens psql on the running postgres container.
db:
	docker compose exec postgres psql -U $${POSTGRES_USER:-moneyball} -d $${POSTGRES_DB:-moneyball}

migrate:
	docker compose exec api alembic upgrade head

migrate-new:
	docker compose exec api alembic revision --autogenerate -m "$(name)"

seed:
	docker compose exec api python -m scripts.seed_demo_slates

test-api:
	docker compose exec api pytest -q

test-web:
	docker compose exec web npm run test
