FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY app ./app
COPY init_db.py bootstrap_fresh_db.py prepare_database.py ./

EXPOSE 8000

CMD ["sh", "-c", "python prepare_database.py && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]