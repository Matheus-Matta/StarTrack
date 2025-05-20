FROM python:3.11



WORKDIR /app

# Instala dependências Python
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copia o código fonte e os assets já compilados
COPY . .

# Entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
