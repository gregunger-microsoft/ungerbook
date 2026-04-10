FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY VERSION .
COPY personalities.json .
COPY entrypoint.sh .
COPY app/ ./app/

RUN chmod +x entrypoint.sh && \
    mkdir -p data/sessions

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
