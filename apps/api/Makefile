.PHONY: dev migrate revision

dev:
	uvicorn soc_api.main:app --reload

migrate:
	alembic -c apps/api/alembic.ini upgrade head

revision:
	alembic -c apps/api/alembic.ini revision -m "$(m)"
