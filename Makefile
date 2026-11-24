# Makefile
# --------
# Convenience commands. The two required targets are `up` and `down`.
#
#   make up     -> build + start the whole stack (backend :8000, frontend :3000)
#   make down   -> stop and remove the containers
#   make logs   -> follow the logs
#   make test   -> run the backend test suite
#
# Uses the modern "docker compose" (v2) subcommand.

.PHONY: up down logs test rebuild

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f

# Rebuild images from scratch (no cache).
rebuild:
	docker compose build --no-cache

# Run the backend tests inside a throwaway Python container.
test:
	cd backend && python -m pytest -q
