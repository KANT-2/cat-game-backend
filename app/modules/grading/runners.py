from typing import Protocol

from app.models.task import Task
from app.modules.grading.sandbox.runner import GradeResult, Verdict, sandbox
from app.modules.grading.sql_sandbox import sql_sandbox
from app.modules.grading.test_cases import parse_test_cases


class TaskRunner(Protocol):
    def grade(self, task: Task, submission: str) -> GradeResult: ...


class PythonSandboxRunner:
    def grade(self, task: Task, submission: str) -> GradeResult:
        return sandbox.grade(submission, parse_test_cases(task.test_cases))


class SQLSandboxRunner:
    def grade(self, task: Task, submission: str) -> GradeResult:
        return sql_sandbox.grade(submission, parse_test_cases(task.test_cases))


class MultipleChoiceRunner:
    def grade(self, task: Task, submission: str) -> GradeResult:
        correct = submission == task.correct_option
        return GradeResult(Verdict.ACCEPTED if correct else Verdict.WRONG_ANSWER, int(correct), 1)


class RunnerDispatcher:
    def __init__(self) -> None:
        self.python = PythonSandboxRunner()
        self.sql = SQLSandboxRunner()
        self.multiple_choice = MultipleChoiceRunner()

    def for_task(self, task: Task) -> TaskRunner:
        if task.type == "MULTIPLE_CHOICE":
            return self.multiple_choice
        if task.domain == "PYTHON":
            return self.python
        if task.domain == "SQL":
            return self.sql
        raise ValueError(f"unsupported task domain: {task.domain}")


dispatcher = RunnerDispatcher()
