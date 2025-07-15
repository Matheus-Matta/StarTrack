#!/usr/bin/env sh
set -e

# 1) espera o Postgres, se estiver usando
echo "→ Aguardando Postgres em $DB_HOST:$DB_PORT…"
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; do
  sleep 0.5
done
echo "→ PostgreSQL pronto!"

# 2) executa makemigrations e migrate
python manage.py makemigrations --no-input
python manage.py migrate --no-input

# 3) executa collectstatic
python manage.py collectstatic --no-input --clear

# 4) executa o daphne (channels)
exec uvicorn config.asgi:application --host 0.0.0.0 --port 8000

