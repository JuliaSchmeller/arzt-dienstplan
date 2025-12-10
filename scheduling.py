#!/usr/bin/env python3
"""
Scheduling helpers and AutoScheduler (adapted to your models).

This version uses the model names exported from your models.py:
- Schedule  (used instead of Duty)
- DutyType
- User, UserRole
- db

It is defensive:
- lazy imports models and logs import traceback
- normalizes datetime/date values with to_date()
- initializes chosen_doc before use and handles "no candidate" cases cleanly
- supports working in-memory if DB models are unavailable (so debug_scheduler can still run)
"""
from __future__ import annotations

import calendar
import logging
import random
import traceback
from datetime import datetime, date, timedelta
from types import SimpleNamespace
from typing import List, Optional, Any

# Module logger
logger = logging.getLogger("scheduling")
logger.addHandler(logging.NullHandler())

# Model placeholders (populated by _import_models())
db = None
User = None
UserRole = None
Schedule = None
DutyType = None

_HAS_DB_MODELS = False
_IMPORT_TRACEBACK: Optional[str] = None


def _import_models() -> bool:
    """
    Lazy import of your project's models. Returns True if models are available.
    Records traceback text in _IMPORT_TRACEBACK on failure.
    """
    global db, User, UserRole, Schedule, DutyType, _HAS_DB_MODELS, _IMPORT_TRACEBACK
    if _HAS_DB_MODELS:
        return True
    try:
        # Import here to avoid top-level circular imports
        from models import db as _db, User as _User, UserRole as _UserRole, Schedule as _Schedule, DutyType as _DutyType  # type: ignore
        db, User, UserRole, Schedule, DutyType = _db, _User, _UserRole, _Schedule, _DutyType
        _HAS_DB_MODELS = True
        _IMPORT_TRACEBACK = None
        logger.debug("Scheduling: successfully imported DB models.")
        return True
    except Exception:
        _HAS_DB_MODELS = False
        _IMPORT_TRACEBACK = traceback.format_exc()
        logger.debug("Scheduling: failed to import DB models:\n" + _IMPORT_TRACEBACK)
        return False


def get_last_import_traceback() -> Optional[str]:
    """Return the last import traceback (if any) for debugging."""
    return _IMPORT_TRACEBACK


# ------------------------------
# Utilities
# ------------------------------
def to_date(dt: Optional[Any]) -> Optional[date]:
    """Normalize a datetime/date-like object to a datetime.date instance."""
    if dt is None:
        return None
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt
    if isinstance(dt, datetime):
        return dt.date()
    return dt


# ------------------------------
# AutoScheduler
# ------------------------------
class AutoScheduler:
    """
    Scheduler that can generate Schedule entries (or in-memory duty objects)
    for a given year/month.

    The code is defensive and adapts to the presence/absence of real DB models.
    """

    def __init__(self, year: int, month: int):
        self.year = int(year)
        self.month = int(month)
        self._first_day = date(self.year, self.month, 1)
        _, ndays = calendar.monthrange(self.year, self.month)
        self._last_day = date(self.year, self.month, ndays)

        # Attempt to import models on init
        _import_models()
        if not _HAS_DB_MODELS:
            logger.debug("No DB users loaded; using empty doctors list")
        self.doctors = self._load_doctors()
        logger.debug(f"AutoScheduler initialized for {self.month}/{self.year}")

    def _load_doctors(self) -> List[Any]:
        """
        Load doctors from DB if possible; otherwise return empty list.
        Expects User and UserRole to exist in models.py.
        """
        if _import_models() and User is not None and UserRole is not None:
            try:
                # Try to use a query property typical in Flask-SQLAlchemy
                q = getattr(User, "query", None)
                if q is not None:
                    users = list(User.query.filter(User.role == UserRole.USER).all())
                    logger.debug(f"Loaded {len(users)} doctors from DB")
                    return users
            except Exception as e:
                logger.debug(f"Failed to query User model: {e}\nTraceback:\n{traceback.format_exc()}")
        logger.debug("No DB users loaded; using empty doctors list")
        return []

    def get_days(self) -> List[date]:
        days = []
        current = self._first_day
        while current <= self._last_day:
            days.append(current)
            current += timedelta(days=1)
        return days

    def get_available_doctors(self, when: Any, duty_type: Any = None) -> List[Any]:
        """
        Return doctors available on a given day.

        If Schedule model exists, exclude doctors who already have a schedule entry that day.
        """
        day = to_date(when)
        if day is None:
            return []

        if _import_models() and Schedule is not None:
            try:
                existing = list(Schedule.query.filter(Schedule.date == day).all())
                occupied_user_ids = {
                    getattr(s, "user_id", getattr(getattr(s, "user", None), "id", None)) for s in existing
                }
                available = [d for d in self.doctors if getattr(d, "id", None) not in occupied_user_ids]
                return available
            except Exception as e:
                logger.debug(f"Error querying Schedule for availability: {e}\nTraceback:\n{traceback.format_exc()}")

        return list(self.doctors)

    def _doctor_has_conflict(self, doctor: Any, on_date: date, duty_type: Any) -> bool:
        """
        Conservative conflict check: if DB available, check whether doctor already has an entry
        on on_date. If check fails, treat as conflict to be safe.
        """
        if doctor is None:
            return True
        on_date = to_date(on_date)
        if on_date is None:
            return True

        if _import_models() and Schedule is not None:
            try:
                q = Schedule.query.filter(Schedule.date == on_date)
                if hasattr(Schedule, "user_id"):
                    q = q.filter(Schedule.user_id == getattr(doctor, "id", None))
                else:
                    q = q.filter(Schedule.user == doctor)
                return q.count() > 0
            except Exception as e:
                logger.debug(f"Conflict check DB query failed: {e}\nTraceback:\n{traceback.format_exc()}")
                return True

        # no DB -> assume no conflict
        return False

    def _create_schedule_obj(self, duty_date: date, duty_type: Any, doctor: Any) -> Any:
        """
        Create a Schedule (DB) instance when available, otherwise return a SimpleNamespace
        representing the duty.
        """
        duty_date = to_date(duty_date)
        if _import_models() and Schedule is not None and db is not None:
            try:
                # Create Schedule instance; try to set user relationship or user_id
                sched = Schedule(date=duty_date, duty_type=duty_type)
                if hasattr(sched, "user"):
                    sched.user = doctor
                elif hasattr(sched, "user_id"):
                    sched.user_id = getattr(doctor, "id", None)
                db.session.add(sched)
                return sched
            except Exception as e:
                logger.debug(f"Failed to construct DB Schedule instance: {e}\nTraceback:\n{traceback.format_exc()}")

        # Fallback in-memory object
        username = getattr(doctor, "username", getattr(doctor, "name", None))
        return SimpleNamespace(date=duty_date, duty_type=duty_type, user=doctor, user_id=getattr(doctor, "id", None), username=username)

    def distribute_duties(self) -> List[Any]:
        """
        Simple scheduling algorithm that:
         - assigns a DIENST and a RUFDIENST for each day
         - sometimes assigns a VISITE on weekdays (heuristic)
        """
        duties: List[Any] = []
        days = self.get_days()
        rng = random.Random(0)

        # If DutyType is missing, create a fallback sentinel with expected attrs
        if DutyType is None:
            class _DT:
                DIENST = "DIENST"
                RUFDIENST = "RUFDIENST"
                VISITE = "VISITE"
            dtype = _DT
        else:
            dtype = DutyType

        for current in days:
            current = to_date(current)
            weekday = current.weekday()
            is_weekend = weekday >= 5

            logger.debug(f"Scheduling for {current} (weekend={is_weekend})")

            def pick_doctor(candidates: List[Any]) -> Optional[Any]:
                if not candidates:
                    return None
                filtered = [d for d in candidates if not self._doctor_has_conflict(d, current, None)]
                if not filtered:
                    return None
                return rng.choice(filtered)

            # DIENST
            chosen_doc = None
            try:
                candidates = self.get_available_doctors(current, getattr(dtype, "DIENST", "DIENST"))
                chosen_doc = pick_doctor(candidates)
            except Exception as e:
                logger.warning(f"Error while choosing DIENST doctor for {current}: {e}\nTraceback:\n{traceback.format_exc()}")
                chosen_doc = None

            if chosen_doc is None:
                logger.warning(f"No DIENST candidate found for {current}; skipping DIENST assignment.")
            else:
                sched = self._create_schedule_obj(current, getattr(dtype, "DIENST", "DIENST"), chosen_doc)
                duties.append(sched)
                logger.info(f"Dienst zugewiesen: {getattr(chosen_doc, 'username', getattr(chosen_doc, 'name', str(getattr(chosen_doc, 'id', 'unknown'))))} - {sched.date} - dienst")

            # RUFDIENST
            chosen_doc = None
            try:
                candidates = self.get_available_doctors(current, getattr(dtype, "RUFDIENST", "RUFDIENST"))
                if candidates and len(duties) > 0:
                    last_user_id = getattr(duties[-1], "user_id", getattr(getattr(duties[-1], "user", None), "id", None))
                    candidates = [c for c in candidates if getattr(c, "id", None) != last_user_id]
                chosen_doc = pick_doctor(candidates)
            except Exception as e:
                logger.warning(f"Error while choosing RUFDIENST doctor for {current}: {e}\nTraceback:\n{traceback.format_exc()}")
                chosen_doc = None

            if chosen_doc is None:
                logger.warning(f"No RUFDIENST candidate found for {current}; skipping RUFDIENST assignment.")
            else:
                sched = self._create_schedule_obj(current, getattr(dtype, "RUFDIENST", "RUFDIENST"), chosen_doc)
                duties.append(sched)
                logger.info(f"Dienst zugewiesen: {getattr(chosen_doc, 'username', getattr(chosen_doc, 'name', str(getattr(chosen_doc, 'id', 'unknown'))))} - {sched.date} - rufdienst")

            # VISITE heuristic (weekday pattern)
            if not is_weekend and (weekday % 3 == 1):
                chosen_doc = None
                try:
                    candidates = self.get_available_doctors(current, getattr(dtype, "VISITE", "VISITE"))
                    chosen_doc = pick_doctor(candidates)
                except Exception as e:
                    logger.warning(f"Error while choosing VISITE doctor for {current}: {e}\nTraceback:\n{traceback.format_exc()}")
                    chosen_doc = None

                if chosen_doc is None:
                    logger.info(f"No VISITE assigned for {current}")
                else:
                    sched = self._create_schedule_obj(current, getattr(dtype, "VISITE", "VISITE"), chosen_doc)
                    duties.append(sched)
                    logger.info(f"Dienst zugewiesen: {getattr(chosen_doc, 'username', getattr(chosen_doc, 'name', str(getattr(chosen_doc, 'id', 'unknown'))))} - {sched.date} - visite")

        return duties