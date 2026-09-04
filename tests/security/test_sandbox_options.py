import json
import subprocess

from app.modules.grading.sandbox.runner import DockerSandbox, Verdict
from app.modules.grading.test_cases import TestCase as Case


def test_docker_security_flags_and_accepted_result(monkeypatch):
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        return subprocess.CompletedProcess(
            command, 0, json.dumps({"verdict": "ACCEPTED", "passed": 1}), ""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = DockerSandbox().grade("print(input())", [Case("ok", "ok")])
    command = seen["command"]
    assert result.verdict is Verdict.ACCEPTED
    for pair in [
        ["--network", "none"],
        ["--read-only"],
        ["--cap-drop", "ALL"],
        ["--security-opt", "no-new-privileges:true"],
        ["--user", "sandbox"],
        ["--memory"],
        ["--cpus"],
        ["--pids-limit"],
    ]:
        assert any(command[i : i + len(pair)] == pair for i in range(len(command)))


def test_host_timeout_is_student_failure(monkeypatch):
    calls = []

    def timed_out(command, **kwargs):
        calls.append(command)
        if command[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired("docker", 1)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", timed_out)
    result = DockerSandbox().grade("while True: pass", [Case("", "")])
    assert result.verdict is Verdict.TIMEOUT
    assert not result.is_system_failure
    assert calls[1][:3] == ["docker", "rm", "--force"]
