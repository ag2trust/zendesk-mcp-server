FROM python:3.12-slim

RUN useradd --create-home appuser

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir .

USER appuser

EXPOSE 8000

ENTRYPOINT ["zendesk-mcp"]
