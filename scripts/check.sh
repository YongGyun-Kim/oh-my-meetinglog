#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv run --no-sync ruff check backend tests
uv run --no-sync ruff format --check backend tests
uv run --no-sync pytest -m 'not live' -q
npm --prefix web run typecheck
npm --prefix web run test -- --run
npm --prefix web run build
npm --prefix web run e2e
git diff --check
