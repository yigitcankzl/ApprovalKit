up:
	docker compose up -d

down:
	docker compose down

rebuild:
	docker compose build --no-cache
	docker compose up -d

rebuild-frontend:
	docker compose build --no-cache frontend
	docker compose up -d --force-recreate frontend

rebuild-api:
	docker compose build --no-cache api worker
	docker compose up -d --force-recreate api worker

logs:
	docker compose logs -f

test:
	docker compose exec -T api python -m pytest tests/ -v

migrate:
	docker compose exec -T api python -m alembic upgrade head

clean:
	docker compose down -v --remove-orphans

health:
	@docker compose ps --format "table {{.Name}}\t{{.Status}}"
	@echo ""
	@curl -sf http://localhost:8000/health 2>/dev/null && echo "API: healthy" || echo "API: unreachable"

shell:
	docker compose exec api bash

seed:
	docker compose exec -T api python -c "from api.routes.demo import seed_demo_data; import asyncio; asyncio.run(seed_demo_data())"

.PHONY: up down rebuild rebuild-frontend rebuild-api logs test migrate clean health shell seed
