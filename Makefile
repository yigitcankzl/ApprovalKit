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

.PHONY: up down rebuild rebuild-frontend rebuild-api logs
