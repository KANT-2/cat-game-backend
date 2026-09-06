import json
import resource
import subprocess
import tempfile
import threading
import uuid
from dataclasses import dataclass
from enum import StrEnum

from app.core.config import settings
from app.modules.grading.test_cases import TestCase


class Verdict(StrEnum):
    ACCEPTED = "ACCEPTED"
    WRONG_ANSWER = "WRONG_ANSWER"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    TIMEOUT = "TIMEOUT"
    OUTPUT_LIMIT = "OUTPUT_LIMIT"
    MEMORY_LIMIT = "MEMORY_LIMIT"
    SYSTEM_ERROR = "SYSTEM_ERROR"


@dataclass(frozen=True)
class GradeResult:
    verdict: Verdict
    passed: int = 0
    total: int = 0
    detail: str | None = None

    @property
    def is_system_failure(self) -> bool:
        return self.verdict is Verdict.SYSTEM_ERROR

    @property
    def is_correct(self) -> bool:
        return self.verdict is Verdict.ACCEPTED


class DockerSandbox:
    def __init__(self) -> None:
        self._slots = threading.BoundedSemaphore(settings.grading_max_concurrency)

    def grade(self, code: str, cases: list[TestCase]) -> GradeResult:
        payload = json.dumps(
            {
                "code": code,
                "test_cases": [c.__dict__ for c in cases],
                "output_limit_bytes": settings.grading_output_bytes,
            }
        )
        container_name = f"cat-grader-{uuid.uuid4().hex}"
        command = [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "--interactive",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m",
            "--memory",
            settings.grading_memory,
            "--cpus",
            str(settings.grading_cpus),
            "--pids-limit",
            str(settings.grading_pids_limit),
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--user",
            "sandbox",
            settings.grading_image,
        ]
        with self._slots:
            try:
                completed, output_exceeded = _run_capped(
                    command,
                    payload,
                    timeout=settings.grading_timeout_seconds,
                    output_limit=settings.grading_output_bytes,
                )
            except subprocess.TimeoutExpired:
                _remove_container(container_name)
                return GradeResult(Verdict.TIMEOUT, total=len(cases), detail="time limit exceeded")
            except (OSError, subprocess.SubprocessError) as exc:
                return GradeResult(Verdict.SYSTEM_ERROR, total=len(cases), detail=str(exc))
        if output_exceeded:
            _remove_container(container_name)
            return GradeResult(Verdict.OUTPUT_LIMIT, total=len(cases), detail="output limit exceeded")
        if completed.returncode == 137:
            return GradeResult(Verdict.MEMORY_LIMIT, total=len(cases), detail="memory limit exceeded")
        combined = completed.stdout + completed.stderr
        if completed.returncode != 0:
            return GradeResult(Verdict.SYSTEM_ERROR, total=len(cases), detail=combined[-1000:])
        try:
            data = json.loads(completed.stdout)
            return GradeResult(
                Verdict(data["verdict"]), data.get("passed", 0), len(cases), data.get("detail")
            )
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            return GradeResult(
                Verdict.SYSTEM_ERROR, total=len(cases), detail=f"invalid runner result: {exc}"
            )


def _run_capped(
    command: list[str],
    payload: str,
    *,
    timeout: float,
    output_limit: int,
) -> tuple[subprocess.CompletedProcess[str], bool]:
    """Run Docker with regular-file output caps so pipes cannot exhaust worker memory."""
    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        completed = subprocess.run(
            command,
            input=payload.encode(),
            stdout=stdout_file,
            stderr=stderr_file,
            timeout=timeout,
            check=False,
            preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_FSIZE, (output_limit, output_limit)),
        )
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout_bytes = stdout_file.read(output_limit + 1)
        stderr_bytes = stderr_file.read(output_limit + 1)
    output_exceeded = len(stdout_bytes) + len(stderr_bytes) >= output_limit
    return (
        subprocess.CompletedProcess(
            completed.args,
            completed.returncode,
            stdout_bytes.decode(errors="replace"),
            stderr_bytes.decode(errors="replace"),
        ),
        output_exceeded,
    )


def _remove_container(container_name: str) -> None:
    subprocess.run(
        ["docker", "rm", "--force", container_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


sandbox = DockerSandbox()
