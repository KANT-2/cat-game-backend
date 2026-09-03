import json
import py_compile
import subprocess
import sys
import tempfile


def main():
    payload = json.load(sys.stdin)
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
        try:
            run = subprocess.run([sys.executable, path], input=case["input"], text=True,
                                 capture_output=True, timeout=2, check=False)
        except subprocess.TimeoutExpired:
            print(json.dumps({"verdict": "TIMEOUT", "passed": passed}))
            return
        if run.returncode:
            print(json.dumps({"verdict": "RUNTIME_ERROR", "passed": passed,
                              "detail": run.stderr[-500:]}))
            return
        if run.stdout.rstrip() != case["expected_output"].rstrip():
            print(json.dumps({"verdict": "WRONG_ANSWER", "passed": passed}))
            return
        passed += 1
    print(json.dumps({"verdict": "ACCEPTED", "passed": passed}))


if __name__ == "__main__":
    main()
