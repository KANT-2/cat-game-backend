import json
import subprocess
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
        payload = json.dumps({"code": code, "test_cases": [c.__dict__ for c in cases]})
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
                completed = subprocess.run(
                    command,
                    input=payload,
                    text=True,
                    capture_output=True,
                    timeout=settings.grading_timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                subprocess.run(
                    ["docker", "rm", "--force", container_name],
                    capture_output=True,
                    check=False,
                )
                return GradeResult(Verdict.TIMEOUT, total=len(cases), detail="time limit exceeded")
            except (OSError, subprocess.SubprocessError) as exc:
                return GradeResult(Verdict.SYSTEM_ERROR, total=len(cases), detail=str(exc))
        combined = completed.stdout + completed.stderr
        if len(combined.encode()) > settings.grading_output_bytes:
            return GradeResult(
                Verdict.OUTPUT_LIMIT, total=len(cases), detail="output limit exceeded"
            )
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


sandbox = DockerSandbox()
