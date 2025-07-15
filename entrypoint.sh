#!/usr/bin/env sh
set -e

# 1) espera o Postgres, se estiver usando
if [ "$DATABASE" = "postgres" ]; then
  echo "→ Waiting for Postgres at $SQL_HOST:$SQL_PORT…"
  until pg_isready -h "$SQL_HOST" -p "$SQL_PORT" -U "$POSTGRES_USER" > /dev/null 2>&1; do
    sleep 0.1
  done
  echo "→ PostgreSQL started"
fi

# 2) executa makemigrations e migrate
python manage.py makemigrations --no-input
python manage.py migrate --no-input

# 3) executa collectstatic
python manage.py collectstatic --no-input --clear

# 4) executa o daphne (channels)
exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000

