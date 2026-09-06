import json
import py_compile
import resource
import signal
import subprocess
import sys
import tempfile

DEFAULT_OUTPUT_LIMIT_BYTES = 65_536


def _limit_output(output_limit):
    resource.setrlimit(resource.RLIMIT_FSIZE, (output_limit, output_limit))


def _read_output(stream, output_limit):
    stream.seek(0)
    return stream.read(output_limit + 1).decode(errors="replace")


def main():
    payload = json.load(sys.stdin)
    output_limit = int(payload.get("output_limit_bytes", DEFAULT_OUTPUT_LIMIT_BYTES))
    output_limit = min(max(output_limit, 1_024), 1_048_576)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", dir=tempfile.gettempdir(), delete=False
    ) as source:
        source.write(payload["code"])
        path = source.name
    try:
        py_compile.compile(path, doraise=True)
    except py_compile.PyCompileError as exc:
        print(json.dumps({"verdict": "SYNTAX_ERROR", "detail": str(exc)}))
        return
    passed = 0
    for case in payload["test_cases"]:
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            try:
                run = subprocess.run(
                    [sys.executable, path],
                    input=case["input"].encode(),
                    stdout=stdout_file,
                    stderr=stderr_file,
                    timeout=2,
                    check=False,
                    preexec_fn=lambda: _limit_output(output_limit),
                )
            except subprocess.TimeoutExpired:
                print(json.dumps({"verdict": "TIMEOUT", "passed": passed}))
                return
            stdout = _read_output(stdout_file, output_limit)
            stderr = _read_output(stderr_file, output_limit)
        if (
            len(stdout.encode()) + len(stderr.encode()) >= output_limit
            or run.returncode == -signal.SIGXFSZ
        ):
            print(json.dumps({"verdict": "OUTPUT_LIMIT", "passed": passed}))
            return
        if run.returncode == -signal.SIGKILL:
            print(json.dumps({"verdict": "MEMORY_LIMIT", "passed": passed}))
            return
        if run.returncode:
            print(json.dumps({"verdict": "RUNTIME_ERROR", "passed": passed,
                              "detail": stderr[-500:]}))
            return
        if stdout.rstrip() != case["expected_output"].rstrip():
            print(json.dumps({"verdict": "WRONG_ANSWER", "passed": passed}))
            return
        passed += 1
    print(json.dumps({"verdict": "ACCEPTED", "passed": passed}))


if __name__ == "__main__":
    main()
