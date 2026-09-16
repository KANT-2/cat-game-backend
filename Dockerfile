FROM python:3.12-alpine AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir .

EXPOSE 8000

FROM docker:27-cli AS docker_cli

FROM base AS api

COPY --from=docker_cli /usr/local/bin/docker /usr/local/bin/docker

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM api AS worker

CMD ["python", "-m", "app.modules.grading.worker"]

FROM api AS final
