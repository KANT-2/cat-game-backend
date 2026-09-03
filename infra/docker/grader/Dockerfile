FROM python:3.12-slim
RUN useradd --create-home --uid 10001 sandbox
COPY runner.py /opt/grader/runner.py
RUN chmod 0555 /opt/grader/runner.py
USER sandbox
ENTRYPOINT ["python", "/opt/grader/runner.py"]
