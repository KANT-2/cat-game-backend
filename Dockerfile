FROM python:3.12-alpine AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir .

EXPOSE 8000

FROM base AS api

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM docker:27-cli AS docker_cli

FROM base AS worker

COPY --from=docker_cli /usr/local/bin/docker /usr/local/bin/docker

CMD ["python", "-m", "app.modules.grading.worker"]

FROM api AS final
