"""Summarize manually adjudicated audit runs; never infer correctness from titles."""

import csv
import json
import sys


EXPECTED = {
    "tenant-write-vulnerable": True,
    "tenant-write-protected": False,
    "path-read-vulnerable": True,
    "path-read-protected": False,
}
FIELDS = {"case_id", "run_id", "detected", "false_positives", "agent_calls", "duration_seconds", "complete"}


def read_rows(filename):
    with open(filename, newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not FIELDS.issubset(reader.fieldnames):
            raise ValueError("CSV is missing required columns")
        rows = list(reader)
    seen = set()
    for row in rows:
        if row["case_id"] not in EXPECTED or not row["run_id"]:
            raise ValueError("unknown case or empty run ID")
        key = (row["case_id"], row["run_id"])
        if key in seen:
            raise ValueError("duplicate case and run ID")
        seen.add(key)
        for field in ("detected", "complete"):
            if row[field] not in ("true", "false"):
                raise ValueError(f"{field} must be true or false")
        for field in ("false_positives", "agent_calls", "duration_seconds"):
            value = float(row[field])
            if value < 0 or not value < float("inf"):
                raise ValueError(f"{field} must be finite and nonnegative")
        if int(row["false_positives"]) != float(row["false_positives"]):
            raise ValueError("false_positives must be an integer")
        if int(row["agent_calls"]) != float(row["agent_calls"]):
            raise ValueError("agent_calls must be an integer")
    return rows


def score(rows):
    result = {"completed_runs": 0, "incomplete_runs": 0, "positive_hits": 0,
              "positive_misses": 0, "protected_false_positives": 0,
              "other_false_positives": 0, "agent_calls": 0, "duration_seconds": 0.0}
    for row in rows:
        if row["complete"] == "false":
            result["incomplete_runs"] += 1
            continue
        result["completed_runs"] += 1
        detected = row["detected"] == "true"
        if EXPECTED[row["case_id"]]:
            result["positive_hits" if detected else "positive_misses"] += 1
        elif detected:
            result["protected_false_positives"] += 1
        result["other_false_positives"] += int(row["false_positives"])
        result["agent_calls"] += int(row["agent_calls"])
        result["duration_seconds"] += float(row["duration_seconds"])
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python evaluation/score.py <adjudicated-runs.csv>")
    try:
        print(json.dumps(score(read_rows(sys.argv[1])), indent=2))
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
