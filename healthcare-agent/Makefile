.PHONY: dev seed provision run-agent help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start backend in development mode
	uvicorn backend.main:app --host 0.0.0.0 --port 3002 --reload

seed: ## Seed database with demo data
	curl -X POST http://localhost:3002/api/seed | python -m json.tool

provision: ## Provision ApprovalKit rules
	python -m setup.provision_rules

run-agent: ## Start interactive CLI agent
	python -m agent.healthcare_agent --interactive

run-scenario: ## Run a specific scenario (usage: make run-scenario SCENARIO=patient-onboarding)
	python -m agent.healthcare_agent --scenario $(SCENARIO)

mcp: ## Start MCP server
	python -m mcp_server.server

docker-up: ## Start all services with Docker
	docker compose up -d --build

docker-down: ## Stop all services
	docker compose down

docker-logs: ## View logs
	docker compose logs -f healthcare-api

frontend-dev: ## Start frontend in development mode
	cd frontend && npm run dev

install: ## Install Python dependencies
	pip install -r backend/requirements.txt
