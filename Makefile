.PHONY: dev backend frontend

backend:
	@cd backend && . .venv/bin/activate && exec flask --app run.py run --host=0.0.0.0 --port=5000

frontend:
	@cd frontend && exec pnpm dev --hostname=0.0.0.0 --port=3000

dev:
	@set -e; \
	backend_pid=""; frontend_pid=""; \
	cleanup() { \
		[ -z "$$backend_pid" ] || kill "$$backend_pid" 2>/dev/null || true; \
		[ -z "$$frontend_pid" ] || kill "$$frontend_pid" 2>/dev/null || true; \
		[ -z "$$backend_pid" ] || wait "$$backend_pid" 2>/dev/null || true; \
		[ -z "$$frontend_pid" ] || wait "$$frontend_pid" 2>/dev/null || true; \
	}; \
	trap cleanup EXIT; \
	trap 'exit 130' INT TERM; \
	echo "Iniciando backend en http://localhost:5000"; \
	( cd backend && . .venv/bin/activate && exec flask --app run.py run --host=0.0.0.0 --port=5000 ) & backend_pid=$$!; \
	echo "Iniciando frontend en http://localhost:3000"; \
	( cd frontend && exec pnpm dev --hostname=0.0.0.0 --port=3000 ) & frontend_pid=$$!; \
	wait "$$backend_pid" "$$frontend_pid"
