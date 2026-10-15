"""FREE/PREMIUM rules: daily quota, page limit, offline access.

Deleting documents never refunds the daily quota: counters live in their
own table and are only advanced by consuming a translation slot.
"""
from __future__ import annotations

from datetime import date
from typing import Callable

from app.constants import FREE_DAILY_TRANSLATION_LIMIT, FREE_PAGE_LIMIT
from storage.models import DailyUsage, LimitResult
from storage.repository import UsageRepository


class LimitCode:
    DAILY = "daily_limit"
    PAGE = "page_limit"
    OFFLINE = "offline"


def can_open_offline(is_premium: bool) -> bool:
    """FREE needs internet even for previously translated documents."""
    return is_premium


def can_translate_new(is_premium: bool, online: bool, page_count: int) -> LimitResult:
    """Cheap pre-checks that do not consume quota (used before hashing)."""
    if not online:
        return LimitResult(False, LimitCode.OFFLINE)
    if is_premium:
        return LimitResult(True)
    if page_count > FREE_PAGE_LIMIT:
        return LimitResult(False, LimitCode.PAGE)
    return LimitResult(True)


class QuotaService:
    """Persisted per-calendar-day counter with tamper-resistance.

    Day resets only when the clock moves FORWARD past the stored day, so
    rolling the clock back cannot restore spent quota.
    """

    def __init__(self, usage_repo: UsageRepository, today: Callable[[], date] | None = None) -> None:
        self._repo = usage_repo
        self._today = today or date.today

    def _sync_day(self) -> DailyUsage:
        stored = self._repo.get()
        today_str = self._today().isoformat()
        if stored is None:
            usage = DailyUsage(day=today_str, count=0)
            self._repo.set(usage.day, usage.count)
            return usage
        if today_str > stored.day:  # strictly forward: new calendar day
            self._repo.set(today_str, 0)
            return DailyUsage(day=today_str, count=0)
        return stored  # same day, or clock rolled back: counts persist

    def current_usage(self) -> DailyUsage:
        return self._sync_day()

    def remaining(self, is_premium: bool) -> int | None:
        """None means unlimited (PREMIUM)."""
        if is_premium:
            return None
        usage = self._sync_day()
        return max(0, FREE_DAILY_TRANSLATION_LIMIT - usage.count)

    def can_translate(self, is_premium: bool, page_count: int = 0) -> LimitResult:
        if is_premium:
            return LimitResult(True)
        if page_count > FREE_PAGE_LIMIT:
            return LimitResult(False, LimitCode.PAGE)
        usage = self._sync_day()
        if usage.count >= FREE_DAILY_TRANSLATION_LIMIT:
            return LimitResult(False, LimitCode.DAILY)
        return LimitResult(True)

    def consume(self) -> str:
        """Reserve one translation slot; returns the day it was spent on."""
        usage = self._sync_day()
        self._repo.set(usage.day, usage.count + 1)
        return usage.day

    def refund(self, day: str) -> None:
        """Give a slot back only when the job produced no document."""
        usage = self._repo.get()
        if usage is None or usage.day != day or usage.count <= 0:
            return
        self._repo.set(usage.day, usage.count - 1)
