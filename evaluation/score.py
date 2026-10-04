"""Summarize manually adjudicated audit runs; never infer correctness from titles."""

import csv
import json
import argparse


EXPECTED = {
    "tenant-write-vulnerable": True,
    "tenant-write-protected": False,
    "path-read-vulnerable": True,
    "path-read-protected": False,
}
FIELDS = {"case_id", "run_id", "detected", "false_positives", "agent_calls", "duration_seconds", "complete"}


def read_rows(filename, expected=EXPECTED):
    with open(filename, newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not FIELDS.issubset(reader.fieldnames):
            raise ValueError("CSV is missing required columns")
        rows = list(reader)
    seen = set()
    for row in rows:
        if row["case_id"] not in expected or not row["run_id"]:
            raise ValueError("unknown case or empty run ID")
        key = (row["case_id"], row["run_id"])
        if key in seen:
            raise ValueError("duplicate case and run ID")
        seen.add(key)
        for field in ("detected", "complete"):
            if row[field] not in ("true", "false"):
                raise ValueError(f"{field} must be true or false")
        for field in ("false_positives", "agent_calls"):
            value = float(row[field])
            if value < 0 or not value < float("inf"):
                raise ValueError(f"{field} must be finite and nonnegative")
        if row["duration_seconds"]:
            duration = float(row["duration_seconds"])
            if duration < 0 or not duration < float("inf"):
                raise ValueError("duration_seconds must be finite and nonnegative")
        if int(row["false_positives"]) != float(row["false_positives"]):
            raise ValueError("false_positives must be an integer")
        if int(row["agent_calls"]) != float(row["agent_calls"]):
            raise ValueError("agent_calls must be an integer")
    return rows


def score(rows, expected=EXPECTED):
    result = {"completed_runs": 0, "incomplete_runs": 0, "positive_hits": 0,
              "positive_misses": 0, "protected_false_positives": 0,
              "other_false_positives": 0, "agent_calls": 0, "duration_seconds": 0.0,
              "timed_runs": 0}
    for row in rows:
        if row["complete"] == "false":
            result["incomplete_runs"] += 1
            continue
        result["completed_runs"] += 1
        detected = row["detected"] == "true"
        if expected[row["case_id"]]:
            result["positive_hits" if detected else "positive_misses"] += 1
        elif detected:
            result["protected_false_positives"] += 1
        result["other_false_positives"] += int(row["false_positives"])
        result["agent_calls"] += int(row["agent_calls"])
        if row["duration_seconds"]:
            result["duration_seconds"] += float(row["duration_seconds"])
            result["timed_runs"] += 1
    if not result["timed_runs"]:
        result["duration_seconds"] = None
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", help="Adjudicated run CSV")
    parser.add_argument("--cases", help="JSON object mapping case IDs to expected booleans")
    args = parser.parse_args()
    try:
        expected = EXPECTED
        if args.cases:
            with open(args.cases, encoding="utf-8-sig") as source:
                expected = json.load(source)
            if (not isinstance(expected, dict) or not expected or
                    any(not isinstance(key, str) or not key or type(value) is not bool
                        for key, value in expected.items())):
                raise ValueError("case manifest must map nonempty IDs to booleans")
        print(json.dumps(score(read_rows(args.runs, expected), expected), indent=2))
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
