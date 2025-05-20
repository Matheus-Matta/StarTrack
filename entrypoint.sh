#!/bin/bash

echo ">>> buscando migrações..."
python manage.py makemigrations --noinput

echo ">>> Aplicando migrações..."
python manage.py migrate --noinput

echo ">>> Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo ">>> Iniciando serviço: $@"
exec "$@"