#!/usr/bin/env python3
"""
Debug runner for AutoScheduler.

Usage:
  python debug_scheduler.py YEAR MONTH [--dry-run]

This runs AutoScheduler.distribute_duties inside the Flask app context and prints
detailed logs and exceptions to stdout.

--dry-run: suppresses db.session.commit() so the DB is not modified.
WARNING: distribute_duties() normally deletes and re-creates schedule entries
for the given month. Use --dry-run to avoid changes to your DB.
"""
import sys
import argparse
import logging

def make_logger():
    logger = logging.getLogger('scheduling_debug')
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        logger.addHandler(handler)
    return logger, handler

def run_scheduler(year: int, month: int, dry_run: bool):
    try:
        from run import app as flask_app
    except Exception:
        print("Failed to import Flask app from run.py. Run this from project root where run.py exists.")
        raise

    from scheduling import AutoScheduler
    from models import DutyType, db
    import scheduling as scheduling_module

    logger, handler = make_logger()
    scheduling_module.logger.setLevel(logging.DEBUG)
    scheduling_module.logger.addHandler(handler)

    orig_commit = None
    if dry_run:
        orig_commit = db.session.commit
        def _noop_commit():
            logger.info("DRY-RUN: db.session.commit() suppressed")
            return None
        db.session.commit = _noop_commit

    try:
        with flask_app.app_context():
            s = AutoScheduler(year, month)
            logger.debug(f"Loaded AutoScheduler for {month}/{year} with {len(s.doctors)} doctors")

            for doc in s.doctors:
                logger.debug(
                    f"Doctor: id={getattr(doc,'id',None)}, username={getattr(doc,'username',None)}, "
                    f"role={getattr(doc,'role',None)}, work_percentage={getattr(doc,'work_percentage',None)}"
                )

            from datetime import datetime
            test_date = datetime(year, month, 1)
            avail = s.get_available_doctors(test_date, DutyType.DIENST)
            logger.debug(f"Available doctors for {test_date.date()} DIENST: {[d.username for d in avail]}")

            logger.info(f"Running distribute_duties() (dry_run={dry_run}) — this WILL attempt to create duties")
            duties = s.distribute_duties()
            logger.info(f"distribute_duties returned {len(duties)} duties")

            for d in duties:
                try:
                    username = d.user.username
                except Exception:
                    username = getattr(d, 'user_id', None)
                logger.debug(f"Duty: date={d.date}, type={getattr(d,'duty_type',None)}, user={username}")

    except Exception:
        logger.exception("Exception while running scheduler")
        raise
    finally:
        if dry_run and orig_commit is not None:
            db.session.commit = orig_commit
        try:
            scheduling_module.logger.removeHandler(handler)
        except Exception:
            pass
        try:
            logger.removeHandler(handler)
        except Exception:
            pass

def main(argv):
    parser = argparse.ArgumentParser(description="Run AutoScheduler in debug mode")
    parser.add_argument('year', type=int, help='Year e.g. 2025')
    parser.add_argument('month', type=int, help='Month (1-12)')
    parser.add_argument('--dry-run', action='store_true', help='Do not commit DB changes')
    args = parser.parse_args(argv)

    run_scheduler(args.year, args.month, args.dry_run)

if __name__ == '__main__':
    main(sys.argv[1:])
