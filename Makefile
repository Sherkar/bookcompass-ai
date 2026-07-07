# Makefile for BookCompass AI

.PHONY: install playground run test

install:
	uv sync

playground:
	uv run adk web app --host 127.0.0.1 --port 18081 --reload_agents

run:
	uv run python -m app.agent

test:
	uv run pytest
