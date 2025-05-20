FROM python:3.11

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8001
CMD ["daphne", "-b", "0.0.0.0", "-p", "8001", "config.asgi:application"]