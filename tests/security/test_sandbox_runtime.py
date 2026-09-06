import os

import pytest

from app.modules.grading.sandbox.runner import DockerSandbox, Verdict
from app.modules.grading.test_cases import TestCase as Case

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DOCKER_GRADING_TESTS") != "1",
    reason="set RUN_DOCKER_GRADING_TESTS=1 after building the grader image",
)


def test_sandbox_blocks_root_filesystem_write() -> None:
    result = DockerSandbox().grade(
        "open('/sandbox-escape', 'w').write('escape')",
        [Case("", "")],
    )

    assert result.verdict is Verdict.RUNTIME_ERROR


def test_sandbox_blocks_outbound_network() -> None:
    result = DockerSandbox().grade(
        "import socket\nsocket.create_connection(('1.1.1.1', 53), timeout=0.2)\nprint('open')",
        [Case("", "open")],
    )

    assert result.verdict is Verdict.RUNTIME_ERROR


def test_sandbox_stops_direct_container_output_bypass() -> None:
    result = DockerSandbox().grade(
        "stream = open('/proc/1/fd/1', 'w')\n"
        "while True:\n"
        "    stream.write('x' * 8192)\n"
        "    stream.flush()",
        [Case("", "")],
    )

    assert result.verdict is Verdict.OUTPUT_LIMIT


def test_sandbox_stops_memory_exhaustion() -> None:
    result = DockerSandbox().grade(
        "chunks = []\n"
        "while True:\n"
        "    chunks.append(bytearray(8 * 1024 * 1024))",
        [Case("", "")],
    )

    assert result.verdict is Verdict.MEMORY_LIMIT


def test_sandbox_enforces_process_limit() -> None:
    result = DockerSandbox().grade(
        "import os, time\n"
        "while True:\n"
        "    try:\n"
        "        pid = os.fork()\n"
        "    except OSError:\n"
        "        print('limited')\n"
        "        break\n"
        "    if pid == 0:\n"
        "        time.sleep(10)\n"
        "        os._exit(0)",
        [Case("", "limited")],
    )

    assert result.verdict is Verdict.ACCEPTED
