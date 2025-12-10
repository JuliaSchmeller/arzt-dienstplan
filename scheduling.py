#!/usr/bin/env python3
"""
Scheduling helpers and AutoScheduler (adapted to your models, with weekend-RUFDIENST,
post-DIENST rest-day rules, and Friday->Sunday DIENST preference).

New rule implemented:
 - Prefer to assign the same doctor who had DIENST on Friday to the DIENST on Sunday,
   when possible and respecting other hard constraints (week limit, blocked days).
"""
from __future__ import annotations

import calendar
import logging
import random
import traceback
from collections import Counter, defaultdict
from datetime import datetime, date, timedelta
from types import SimpleNamespace
from typing import List, Optional, Any, Dict

# Configurable policy values (tweak as needed)
MAX_PER_WEEK = 3
MAX_WEEKENDS = 2

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
    global db, User, UserRole, Schedule, DutyType, _HAS_DB_MODELS, _IMPORT_TRACEBACK
    if _HAS_DB_MODELS:
        return True
    try:
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
    return _IMPORT_TRACEBACK


def to_date(dt: Optional[Any]) -> Optional[date]:
    if dt is None:
        return None
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt
    if isinstance(dt, datetime):
        return dt.date()
    return dt


class AutoScheduler:
    def __init__(self, year: int, month: int):
        self.year = int(year)
        self.month = int(month)
        self._first_day = date(self.year, self.month, 1)
        _, ndays = calendar.monthrange(self.year, self.month)
        self._last_day = date(self.year, self.month, ndays)

        _import_models()
        self.doctors = self._load_doctors()
        # in-memory list of already created duties during this run (prevents duplicates)
        self._assigned_in_memory: List[Any] = []
        logger.debug(f"AutoScheduler initialized for {self.month}/{self.year}")

    def _load_doctors(self) -> List[Any]:
        if _import_models() and User is not None and UserRole is not None:
            try:
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

    def _mark_assigned_in_memory(self, sched_obj: Any) -> None:
        """Record assigned duty in-memory so availability checks in the current run see it."""
        self._assigned_in_memory.append(sched_obj)

    def get_available_doctors(self, when: Any, duty_type: Any = None) -> List[Any]:
        """
        Return doctors available on a given day.

        This now considers both the persistent DB schedule (if available) and any
        duties already assigned in this scheduler run (self._assigned_in_memory).
        """
        day = to_date(when)
        if day is None:
            return []

        occupied_user_ids = set()

        # DB existing entries
        if _import_models() and Schedule is not None:
            try:
                existing_db = list(Schedule.query.filter(Schedule.date == day).all())
                for s in existing_db:
                    uid = getattr(s, "user_id", getattr(getattr(s, "user", None), "id", None))
                    if uid is not None:
                        occupied_user_ids.add(uid)
            except Exception as e:
                logger.debug(f"Error querying Schedule for availability: {e}\nTraceback:\n{traceback.format_exc()}")

        # In-memory entries created during this run
        try:
            for s in getattr(self, "_assigned_in_memory", []):
                s_date = to_date(getattr(s, "date", None))
                if s_date == day:
                    uid = getattr(s, "user_id", getattr(getattr(s, "user", None), "id", None))
                    if uid is not None:
                        occupied_user_ids.add(uid)
        except Exception:
            # be conservative: if we can't introspect, don't block
            logger.debug("Failed to inspect in-memory assigned duties for availability")

        available = [d for d in self.doctors if getattr(d, "id", None) not in occupied_user_ids]
        return available

    def _doctor_has_conflict(self, doctor: Any, on_date: date, duty_type: Any) -> bool:
        if doctor is None:
            return True
        on_date = to_date(on_date)
        if on_date is None:
            return True

        # Check DB
        if _import_models() and Schedule is not None:
            try:
                q = Schedule.query.filter(Schedule.date == on_date)
                if hasattr(Schedule, "user_id"):
                    q = q.filter(Schedule.user_id == getattr(doctor, "id", None))
                else:
                    q = q.filter(Schedule.user == doctor)
                if q.count() > 0:
                    return True
            except Exception as e:
                logger.debug(f"Conflict check DB query failed: {e}\nTraceback:\n{traceback.format_exc()}")
                # fall through to in-memory check

        # Check in-memory duties
        try:
            for s in getattr(self, "_assigned_in_memory", []):
                s_date = to_date(getattr(s, "date", None))
                if s_date == on_date:
                    uid = getattr(s, "user_id", getattr(getattr(s, "user", None), "id", None))
                    if uid is not None and uid == getattr(doctor, "id", None):
                        return True
        except Exception:
            logger.debug("Failed to inspect in-memory assigned duties for conflict check")
            return True

        return False

    def _create_schedule_obj(self, duty_date: date, duty_type: Any, doctor: Any) -> Any:
        duty_date = to_date(duty_date)
        if _import_models() and Schedule is not None and db is not None:
            try:
                sched = Schedule(date=duty_date, duty_type=duty_type)
                if hasattr(sched, "user"):
                    sched.user = doctor
                elif hasattr(sched, "user_id"):
                    sched.user_id = getattr(doctor, "id", None)
                # Add to DB session (commit is left to caller / debug runner)
                db.session.add(sched)
                return sched
            except Exception as e:
                logger.debug(f"Failed to construct DB Schedule instance: {e}\nTraceback:\n{traceback.format_exc()}")

        username = getattr(doctor, "username", getattr(doctor, "name", None))
        return SimpleNamespace(date=duty_date, duty_type=duty_type, user=doctor, user_id=getattr(doctor, "id", None), username=username)

    def distribute_duties(self) -> List[Any]:
        duties: List[Any] = []
        days = self.get_days()
        rng = random.Random(0)

        if DutyType is None:
            class _DT:
                DIENST = "DIENST"
                RUFDIENST = "RUFDIENST"
                VISITE = "VISITE"
            dtype = _DT
        else:
            dtype = DutyType

        # Precompute map of user_id -> work_percentage (best-effort)
        user_work_pct: Dict[Optional[int], int] = {}
        try:
            if _import_models() and User is not None:
                for u in getattr(User).query.all():
                    user_work_pct[getattr(u, "id", None)] = getattr(u, "work_percentage", None) or 100
        except Exception:
            user_work_pct = {}

        # blocked_dates: user_id -> set(dates) where the user must not be assigned any duty
        blocked_dates: Dict[Optional[int], set] = defaultdict(set)

        def assigned_counts():
            """Return maps for assigned counts so far (dienst counts, weekend counts, per-week counts)."""
            dienst_count = Counter()
            weekend_count = Counter()
            per_week = defaultdict(Counter)  # per_week[user][(year,week)] = count
            # Count duties both from DB (only within this month) and in-memory assigned
            # DB duties
            if _import_models() and Schedule is not None:
                try:
                    db_entries = list(Schedule.query.filter(Schedule.date >= self._first_day, Schedule.date <= self._last_day).all())
                except Exception:
                    db_entries = []
            else:
                db_entries = []

            all_entries = db_entries + list(getattr(self, "_assigned_in_memory", []))
            for s in all_entries:
                ddate = to_date(getattr(s, "date", None))
                if ddate is None:
                    continue
                uid = getattr(s, "user_id", getattr(getattr(s, "user", None), "id", None))
                dtype_val = str(getattr(s, "duty_type", getattr(s, "type", "")))
                if dtype_val and (dtype_val.upper().endswith("DIENST") or dtype_val.upper() == "DIENST"):
                    dienst_count[uid] += 1
                if ddate.weekday() >= 5 and ddate.year == self.year and ddate.month == self.month:
                    weekend_count[uid] += 1
                wk = ddate.isocalendar()[:2]
                per_week[uid][wk] += 1
            return dienst_count, weekend_count, per_week

        def users_with_dienst_on(day_: date) -> List[int]:
            """Return user ids who have a DIENST on the given day (DB + in-memory)."""
            uids = []
            # DB
            if _import_models() and Schedule is not None:
                try:
                    db_entries = Schedule.query.filter(Schedule.date == day_).all()
                except Exception:
                    db_entries = []
                for s in db_entries:
                    dtype_val = str(getattr(s, "duty_type", getattr(s, "type", "")))
                    if dtype_val and (dtype_val.upper().endswith("DIENST") or dtype_val.upper() == "DIENST"):
                        uid = getattr(s, "user_id", getattr(getattr(s, "user", None), "id", None))
                        if uid is not None:
                            uids.append(uid)
            # in-memory
            try:
                for s in getattr(self, "_assigned_in_memory", []):
                    s_date = to_date(getattr(s, "date", None))
                    if s_date == day_:
                        dtype_val = str(getattr(s, "duty_type", getattr(s, "type", "")))
                        if dtype_val and (dtype_val.upper().endswith("DIENST") or dtype_val.upper() == "DIENST"):
                            uid = getattr(s, "user_id", getattr(getattr(s, "user", None), "id", None))
                            if uid is not None:
                                uids.append(uid)
            except Exception:
                logger.debug("Failed to inspect in-memory assigned duties for dienst lookup")
            # unique
            return list(dict.fromkeys(uids))

        def pick_doctor(candidates: List[Any], current_date: date, duty_kind: Any) -> Optional[Any]:
            """
            Enhanced selection (robust duty_kind normalization)
            - respects blocked_dates: excludes candidates blocked for current_date
            - Enforces per-week and weekend limits with controlled fallback
            """
            if not candidates:
                return None

            # Normalize duty_kind to uppercase string safely
            if isinstance(duty_kind, str):
                dk = duty_kind.upper()
            else:
                if hasattr(duty_kind, "name") and isinstance(getattr(duty_kind, "name"), str):
                    dk = duty_kind.name.upper()
                elif hasattr(duty_kind, "value"):
                    dk = str(getattr(duty_kind, "value")).upper()
                else:
                    dk = str(duty_kind).upper()

            # filter out candidates blocked for current_date
            candidates = [c for c in candidates if current_date not in blocked_dates.get(getattr(c, "id", None), set())]
            if not candidates:
                return None

            # get current assigned counts snapshot
            dienst_count, weekend_count, per_week = assigned_counts()
            wk = current_date.isocalendar()[:2]
            is_weekend = current_date.weekday() >= 5

            # Filter helpers
            def filter_by_limits(cands, enforce_week=True, enforce_weekend=True):
                out = []
                for c in cands:
                    uid = getattr(c, "id", None)
                    if enforce_week and per_week.get(uid, {}).get(wk, 0) >= MAX_PER_WEEK:
                        continue
                    if enforce_weekend and is_weekend and weekend_count.get(uid, 0) >= MAX_WEEKENDS:
                        continue
                    out.append(c)
                return out

            # VISITE: strict — prefer doctors with zero duties in same week; do not relax
            if "VISITE" in dk:
                cands = [c for c in candidates if per_week.get(getattr(c, "id", None), {}).get(wk, 0) == 0]
                cands = filter_by_limits(cands, enforce_week=True, enforce_weekend=True)
                if cands:
                    return rng.choice(cands)
                return None  # strict: no relaxation

            # DIENST: enforce week limit strictly, only relax weekend limit if needed
            if "DIENST" in dk:
                # Special: if current day is Sunday, prefer someone who had DIENST on Friday
                preferred = []
                if current_date.weekday() == 6:  # Sunday
                    friday = current_date - timedelta(days=2)
                    pref_uids = users_with_dienst_on(friday)
                    if pref_uids:
                        preferred = [c for c in candidates if getattr(c, "id", None) in pref_uids]

                # Try preferred first (still obeying hard week/weekend filter)
                if preferred:
                    pref_cands = filter_by_limits(preferred, enforce_week=True, enforce_weekend=True)
                    if pref_cands:
                        # weight among preferred by work_percentage / current diensts to pick best
                        weights = []
                        for c in pref_cands:
                            uid = getattr(c, "id", None)
                            wp = user_work_pct.get(uid, 100) or 100
                            current = dienst_count.get(uid, 0)
                            weight = float(wp) / (1.0 + float(current))
                            weights.append(max(weight, 0.0001))
                        total = sum(weights)
                        pick = rng.random() * total
                        accum = 0.0
                        for c, w in zip(pref_cands, weights):
                            accum += w
                            if pick <= accum:
                                return c
                        return pref_cands[-1]

                # No preferred candidate or none available: fall back to regular DIENST selection
                cands = filter_by_limits(candidates, enforce_week=True, enforce_weekend=True)
                if not cands:
                    cands = filter_by_limits(candidates, enforce_week=True, enforce_weekend=False)
                if not cands:
                    return None
                # weight by work_percentage and current dienst count
                weights = []
                for c in cands:
                    uid = getattr(c, "id", None)
                    wp = user_work_pct.get(uid, 100) or 100
                    current = dienst_count.get(uid, 0)
                    weight = float(wp) / (1.0 + float(current))
                    weights.append(max(weight, 0.0001))
                total = sum(weights)
                pick = rng.random() * total
                accum = 0.0
                for c, w in zip(cands, weights):
                    accum += w
                    if pick <= accum:
                        return c
                return cands[-1]

            # RUFDIENST / other: enforce week limit strictly, but relax weekend if necessary
            cands = filter_by_limits(candidates, enforce_week=True, enforce_weekend=True)
            if not cands:
                cands = filter_by_limits(candidates, enforce_week=True, enforce_weekend=False)
            if not cands:
                return None
            return rng.choice(cands)

        # Main loop over days
        for current in days:
            current = to_date(current)
            weekday = current.weekday()
            is_weekend = weekday >= 5
            logger.debug(f"Scheduling for {current} (weekend={is_weekend})")

            # DIENST
            try:
                candidates = self.get_available_doctors(current, getattr(dtype, "DIENST", "DIENST"))
                chosen_doc = pick_doctor(candidates, current, getattr(dtype, "DIENST", "DIENST"))
            except Exception as e:
                logger.warning(f"Error while choosing DIENST doctor for {current}: {e}\nTraceback:\n{traceback.format_exc()}")
                chosen_doc = None

            if chosen_doc is None:
                logger.warning(f"No DIENST candidate found for {current}; skipping DIENST assignment.")
            else:
                sched = self._create_schedule_obj(current, getattr(dtype, "DIENST", "DIENST"), chosen_doc)
                duties.append(sched)
                self._mark_assigned_in_memory(sched)
                logger.info(f"Dienst zugewiesen: {getattr(chosen_doc, 'username', getattr(chosen_doc, 'name', str(getattr(chosen_doc, 'id', 'unknown'))))} - {sched.date} - dienst")
                # enforce rest-day: block doctor for next calendar day (no duties allowed)
                uid = getattr(chosen_doc, "id", None)
                if uid is not None:
                    rest_day = current + timedelta(days=1)
                    blocked_dates[uid].add(rest_day)

            # RUFDIENST
            try:
                candidates = self.get_available_doctors(current, getattr(dtype, "RUFDIENST", "RUFDIENST"))
                # avoid same-user-as-day-duty when possible
                if candidates and len(duties) > 0:
                    last_user_id = getattr(duties[-1], "user_id", getattr(getattr(duties[-1], "user", None), "id", None))
                    candidates = [c for c in candidates if getattr(c, "id", None) != last_user_id]
                chosen_doc = pick_doctor(candidates, current, getattr(dtype, "RUFDIENST", "RUFDIENST"))
            except Exception as e:
                logger.warning(f"Error while choosing RUFDIENST doctor for {current}: {e}\nTraceback:\n{traceback.format_exc()}")
                chosen_doc = None

            if chosen_doc is None:
                logger.warning(f"No RUFDIENST candidate found for {current}; skipping RUFDIENST assignment.")
            else:
                sched = self._create_schedule_obj(current, getattr(dtype, "RUFDIENST", "RUFDIENST"), chosen_doc)
                duties.append(sched)
                self._mark_assigned_in_memory(sched)
                logger.info(f"Dienst zugewiesen: {getattr(chosen_doc, 'username', getattr(chosen_doc, 'name', str(getattr(chosen_doc, 'id', 'unknown'))))} - {sched.date} - rufdienst")
                # If Friday RUFDIENST: assign same doctor for weekend RUFDIENST (Sat, Sun) and block them
                if weekday == 4:  # Friday
                    uid = getattr(chosen_doc, "id", None)
                    for delta in (1, 2):  # Saturday, Sunday
                        weekend_day = current + timedelta(days=delta)
                        # only create if within month range
                        if weekend_day >= self._first_day and weekend_day <= self._last_day:
                            # check in-memory and DB for that day's RUFDIENST
                            already = False
                            # check in-memory
                            for s in getattr(self, "_assigned_in_memory", []):
                                if to_date(getattr(s, "date", None)) == weekend_day and str(getattr(s, "duty_type", "")).upper().find("RUFDIENST") != -1:
                                    already = True
                                    break
                            # check DB
                            if not already and _import_models() and Schedule is not None:
                                try:
                                    db_existing = Schedule.query.filter(Schedule.date == weekend_day).all()
                                    for be in db_existing:
                                        if str(getattr(be, "duty_type", "")).upper().find("RUFDIENST") != -1:
                                            already = True
                                            break
                                except Exception:
                                    pass
                            if not already:
                                w_sched = self._create_schedule_obj(weekend_day, getattr(dtype, "RUFDIENST", "RUFDIENST"), chosen_doc)
                                duties.append(w_sched)
                                self._mark_assigned_in_memory(w_sched)
                                logger.info(f"Weekend-Rufdienst zugewiesen: {getattr(chosen_doc, 'username', getattr(chosen_doc, 'name', str(uid)))} - {w_sched.date}")
                            # block the doctor for weekend_day so they won't receive other duties
                            if uid is not None:
                                blocked_dates[uid].add(weekend_day)

            # VISITE heuristic (weekday pattern)
            if not is_weekend and (weekday % 3 == 1):
                try:
                    candidates = self.get_available_doctors(current, getattr(dtype, "VISITE", "VISITE"))
                    chosen_doc = pick_doctor(candidates, current, getattr(dtype, "VISITE", "VISITE"))
                except Exception as e:
                    logger.warning(f"Error while choosing VISITE doctor for {current}: {e}\nTraceback:\n{traceback.format_exc()}")
                    chosen_doc = None

                if chosen_doc is None:
                    logger.info(f"No VISITE assigned for {current}")
                else:
                    sched = self._create_schedule_obj(current, getattr(dtype, "VISITE", "VISITE"), chosen_doc)
                    duties.append(sched)
                    self._mark_assigned_in_memory(sched)
                    logger.info(f"Dienst zugewiesen: {getattr(chosen_doc, 'username', getattr(chosen_doc, 'name', str(getattr(chosen_doc, 'id', 'unknown'))))} - {sched.date} - visite")
                    # optionally: if you want VISITE to cause rest the next day, you can block here
                    # uid = getattr(chosen_doc, "id", None)
                    # if uid is not None:
                    #     blocked_dates[uid].add(current + timedelta(days=1))

        return duties