FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY pyproject.toml README.md ./
COPY evidenceops_fleet ./evidenceops_fleet
RUN pip install --no-cache-dir .
CMD ["sh", "-c", "uvicorn evidenceops_fleet.main:app --host 0.0.0.0 --port ${PORT}"]

