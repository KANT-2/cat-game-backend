"""Run a local concurrent load test against the Docker grading sandbox."""

from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from app.modules.grading.sandbox.runner import Verdict, sandbox
from app.modules.grading.test_cases import TestCase


@dataclass(frozen=True)
class Sample:
    number: int
    seconds: float
    verdict: Verdict
    passed: int
    total: int
    detail: str | None


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * percent + 0.9999) - 1))
    return ordered[index]


def make_cases(submission_number: int, count: int) -> list[TestCase]:
    return [
        TestCase(
            input=f"{submission_number + case_number}\n",
            expected_output=f"{(submission_number + case_number) ** 2}\n",
        )
        for case_number in range(1, count + 1)
    ]


def grade_one(number: int, case_count: int) -> Sample:
    code = "value = int(input())\nprint(value * value)"
    started = time.perf_counter()
    result = sandbox.grade(code, make_cases(number, case_count))
    elapsed = time.perf_counter() - started
    return Sample(number, elapsed, result.verdict, result.passed, result.total, result.detail)


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark concurrent Docker grading requests")
    parser.add_argument("--submissions", type=int, default=30, help="total submissions")
    parser.add_argument("--workers", type=int, default=10, help="simultaneous client requests")
    parser.add_argument("--cases", type=int, default=5, help="test cases per submission")
    args = parser.parse_args()

    if min(args.submissions, args.workers, args.cases) < 1:
        parser.error("all values must be at least 1")

    print(
        f"Starting: {args.submissions} submissions, "
        f"{args.workers} client workers, {args.cases} cases each"
    )
    print("The application sandbox limit still applies while requests wait in the queue.\n")

    wall_started = time.perf_counter()
    samples: list[Sample] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(grade_one, number, args.cases): number
            for number in range(1, args.submissions + 1)
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            sample = future.result()
            samples.append(sample)
            print(
                f"[{completed:>3}/{args.submissions}] submission {sample.number:>3}: "
                f"{sample.verdict.value:<14} {sample.seconds:>6.3f}s "
                f"({sample.passed}/{sample.total})"
            )

    wall_seconds = time.perf_counter() - wall_started
    latencies = [sample.seconds for sample in samples]
    failures = [sample for sample in samples if sample.verdict is not Verdict.ACCEPTED]

    print("\nSummary")
    print(f"  accepted       : {len(samples) - len(failures)}/{len(samples)}")
    print(f"  total wall time: {wall_seconds:.3f}s")
    print(f"  throughput     : {len(samples) / wall_seconds:.2f} submissions/sec")
    print(f"  average latency: {statistics.fmean(latencies):.3f}s")
    print(f"  median latency : {statistics.median(latencies):.3f}s")
    print(f"  p95 latency    : {percentile(latencies, 0.95):.3f}s")
    print(f"  maximum latency: {max(latencies):.3f}s")

    if failures:
        print("\nFailures")
        for sample in sorted(failures, key=lambda item: item.number):
            print(f"  #{sample.number}: {sample.verdict.value} - {sample.detail or 'no detail'}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
