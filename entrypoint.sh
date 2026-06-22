#!/bin/bash
set -e

echo "=== LojiNext Backend Starting ==="

echo "Waiting for database..."
until pg_isready -h ${DB_HOST:-db} -p ${DB_PORT:-5432} -U ${POSTGRES_USER:-lojinext_user} -q 2>/dev/null; do
    echo "Database not ready, waiting 2s..."
    sleep 2
done
echo "Database is ready!"

ROLE=${SERVICE_ROLE:-api}

if [ "$ROLE" = "api" ]; then
  echo "Running database migrations..."
  cd /app
  alembic upgrade head
else
  echo "Role '$ROLE' detected; skipping Alembic migrations."
fi

if [ "$ROLE" = "api" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-1}
else
  # worker, beat, or any other role: pass through the docker-compose command
  exec "$@"
fi
