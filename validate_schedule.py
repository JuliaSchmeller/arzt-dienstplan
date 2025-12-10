#!/usr/bin/env python3
"""
validate_schedule.py

Run AutoScheduler in dry-run and validate assignments against a set of rules.

Usage:
  # from project root, in your activated venv
  python validate_schedule.py --year 2025 --month 12

Options:
  --max-per-week INT          max duties per doctor per ISO-week (default: 2)
  --max-weekends INT          max weekend duties per doctor per month (default: 2)
  --work-tolerance INT        allowed difference vs expected DIENST count from work_percentage (default: 1)
  --verbose                   print more details
"""
from __future__ import annotations

import argparse
import collections
import traceback
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple

# Import project scheduler (assumes scheduling.AutoScheduler is in repo)
try:
    from scheduling import AutoScheduler, to_date  # type: ignore
except Exception as e:
    raise SystemExit(f"Failed importing scheduling.AutoScheduler: {e}")

# Try to import Flask app for proper DB context
flask_app = None
try:
    from run import app as flask_app  # type: ignore
except Exception:
    flask_app = None

# Helper types
Violation = Tuple[str, str]  # (severity, message)


def analyze_duties(duties: List[Any], year: int, month: int, *,
                   max_per_week: int = 2,
                   max_weekends: int = 2,
                   work_tolerance: int = 1,
                   verbose: bool = False) -> Dict[str, Any]:
    """
    Analyze list of duty-like objects. Returns a report dict.
    duty: object with attributes date (date or datetime), duty_type, user (object or None), user_id
    """
    # Normalize duties: list of (date, duty_type, user_id, username)
    norm = []
    for d in duties:
        d_date = getattr(d, "date", None)
        if d_date is None:
            continue
        if hasattr(d_date, "date"):
            d_date = d_date.date()
        else:
            # if already a date or string
            if isinstance(d_date, datetime):
                d_date = d_date.date()
        duty_type = getattr(d, "duty_type", getattr(d, "type", None))
        user = getattr(d, "user", None)
        user_id = getattr(d, "user_id", None) or getattr(user, "id", None)
        username = getattr(user, "username", getattr(user, "name", None)) if user is not None else getattr(d, "username", str(user_id))
        norm.append((d_date, str(duty_type), user_id, username))

    # Build indices
    by_date: Dict[date, List[Tuple[str, Optional[int], str]]] = collections.defaultdict(list)
    by_user: Dict[Optional[int], List[Tuple[date, str]]] = collections.defaultdict(list)
    for d_date, duty_type, user_id, username in norm:
        by_date[d_date].append((duty_type, user_id, username))
        by_user[user_id].append((d_date, duty_type))

    violations: List[Violation] = []

    # 1) Per-day constraints: at most one of each duty_type; user cannot have >1 duty on same day
    for d_date, entries in sorted(by_date.items()):
        types = collections.Counter(t for t, _, _ in entries)
        for t, cnt in types.items():
            if cnt > 1:
                violations.append(("ERROR", f"{cnt} '{t}' entries on {d_date} (should be <= 1)"))
        # user duplicates same day
        users_on_day = [uid for _, uid, _ in entries]
        users_counter = collections.Counter(users_on_day)
        for uid, cnt in users_counter.items():
            if uid is not None and cnt > 1:
                violations.append(("ERROR", f"User id={uid} has {cnt} duties on {d_date}"))

    # 2) Weekly limits (ISO week)
    per_user_week = collections.defaultdict(lambda: collections.Counter())
    for uid, entries in by_user.items():
        for d_date, duty_type in entries:
            wk = d_date.isocalendar()[:2]  # (year, week)
            per_user_week[uid][wk] += 1
    for uid, wkcounts in per_user_week.items():
        for wk, cnt in wkcounts.items():
            if cnt > max_per_week:
                violations.append(("WARN", f"user id={uid} has {cnt} duties in ISO-week {wk}, max_per_week={max_per_week}"))

    # 3) Weekend counts per month
    per_user_weekends = collections.Counter()
    for uid, entries in by_user.items():
        for d_date, duty_type in entries:
            if d_date.weekday() >= 5:  # Sat=5, Sun=6
                if d_date.year == year and d_date.month == month:
                    per_user_weekends[uid] += 1
    for uid, cnt in per_user_weekends.items():
        if cnt > max_weekends:
            violations.append(("WARN", f"user id={uid} has {cnt} weekend duties in {year}-{month:02d}, max_weekends={max_weekends}"))

    # 4) VISITE + other duties same week (flag)
    for uid, entries in by_user.items():
        # group by ISO-week
        week_map = collections.defaultdict(list)
        for d_date, duty_type in entries:
            wk = d_date.isocalendar()[:2]
            week_map[wk].append(duty_type)
        for wk, duties in week_map.items():
            if any(str(d).upper() == "VISITE" or "VISITE" in str(d).upper() for d in duties):
                non_visite = [d for d in duties if str(d).upper() != "VISITE"]
                if non_visite:
                    violations.append(("INFO", f"user id={uid} has VISITE and other duties in week {wk}: {duties}"))

    # 5) Work percentage balance check for DIENST counts
    dienst_counts = collections.Counter()
    total_dienst = 0
    user_work_pct: Dict[Optional[int], int] = {}
    for uid, entries in by_user.items():
        for d_date, duty_type in entries:
            if str(duty_type).upper().endswith("DIENST") or str(duty_type).upper() == "DIENST":
                dienst_counts[uid] += 1
                total_dienst += 1

    if total_dienst > 0:
        try:
            import models  # type: ignore
            for u in getattr(models, "User").query.all():
                user_work_pct[getattr(u, "id", None)] = getattr(u, "work_percentage", None) or 100
        except Exception:
            user_work_pct = {}

        if user_work_pct:
            total_pct = sum(user_work_pct.get(uid, 0) for uid in dienst_counts.keys())
            if total_pct > 0:
                for uid, cnt in dienst_counts.items():
                    expected = total_dienst * (user_work_pct.get(uid, 0) / total_pct)
                    diff = cnt - expected
                    if abs(diff) > work_tolerance:
                        violations.append(("WARN", f"user id={uid} DIENST count {cnt} differs from expected {expected:.1f} by {diff:.1f} (tolerance {work_tolerance})"))

    # Summary metrics
    summary = {
        "num_duties": len(norm),
        "num_users": len([u for u in by_user.keys() if u is not None]),
        "violations": violations,
        "duties_by_date": {str(k): v for k, v in by_date.items()},
        "duties_by_user": {str(k): v for k, v in by_user.items()},
    }
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--year", type=int, default=datetime.now().year)
    p.add_argument("--month", type=int, default=datetime.now().month)
    p.add_argument("--max-per-week", type=int, default=2)
    p.add_argument("--max-weekends", type=int, default=2)
    p.add_argument("--work-tolerance", type=int, default=1)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    year = args.year
    month = args.month

    # Run scheduler in dry-run inside Flask app context if available
    duties: List[Any] = []
    try:
        if flask_app is not None:
            with flask_app.app_context():
                scheduler = AutoScheduler(year, month)
                duties = scheduler.distribute_duties()
        else:
            print("Warning: could not import Flask app; running without app context (DB queries may fail).")
            scheduler = AutoScheduler(year, month)
            duties = scheduler.distribute_duties()
    except Exception:
        print("Exception while running scheduler:")
        traceback.print_exc()
        duties = []

    report = analyze_duties(duties, year, month,
                             max_per_week=args.max_per_week,
                             max_weekends=args.max_weekends,
                             work_tolerance=args.work_tolerance,
                             verbose=args.verbose)

    print("=== Schedule validation report ===")
    print(f"Month: {year}-{month:02d}")
    print(f"Total duties returned by scheduler: {report['num_duties']}")
    print(f"Distinct users with duties: {report['num_users']}")
    print("Violations (severity, message):")
    for sev, msg in report["violations"]:
        print(f" - [{sev}] {msg}")

    if args.verbose:
        print("\nDuties by date (excerpt):")
        for d in sorted(report["duties_by_date"].keys())[:10]:
            print(d, report["duties_by_date"][d])


if __name__ == "__main__":
    main()