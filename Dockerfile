####################################
# STAGE: builder
####################################
FROM python:3.11.4-slim-bullseye AS builder

# evita .pyc e buffer de saída
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /usr/src/app

# instala compiladores e libs para psycopg2 e pysqlite3
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      gcc \
      libpq-dev \
      libsqlite3-dev \
      python3-dev \
 && rm -rf /var/lib/apt/lists/*

# copia requirements e gera wheels
COPY requirements.txt .
RUN pip install --upgrade pip wheel \
 && pip wheel --no-cache-dir --wheel-dir /usr/src/app/wheels -r requirements.txt

####################################
# STAGE: web (final)
####################################
FROM python:3.11.4-slim-bullseye AS web

# cria usuário e diretórios
RUN mkdir -p /home/app/web/staticfiles \
 && mkdir -p /home/app/web/mediafiles \
 && addgroup --system app \
 && adduser --system --ingroup app app

ENV HOME=/home/app
ENV APP_HOME=/home/app/web

WORKDIR $APP_HOME

# instala runtime deps
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      netcat \
      postgresql-client \
      sqlite3 \
      libsqlite3-dev \
 && rm -rf /var/lib/apt/lists/*

# copia e instala as wheels (incluindo channels, daphne, uvicorn etc.)
COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache /wheels/*

# configura entrypoint
COPY entrypoint.sh .
RUN sed -i 's/\r$//g' entrypoint.sh \
 && chmod +x entrypoint.sh

# copia o código da aplicação
COPY . .

# ajusta permissões e troca para usuário não‑root
RUN chown -R app:app $APP_HOME
USER app

# entrypoint final (vai rodar o comando passado, ex: uvicorn config.asgi:application)
ENTRYPOINT ["sh", "/home/app/web/entrypoint.sh"]
