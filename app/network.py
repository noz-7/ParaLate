"""Connectivity probe used for FREE-mode rules and provider pre-checks."""
from __future__ import annotations

import logging
import socket
import time

import requests

from app.constants import NETWORK_CACHE_TTL, NETWORK_CHECK_TIMEOUT

logger = logging.getLogger(__name__)

_PROBE_URL = "https://www.google.com/generate_204"
_PROBE_HOST = "8.8.8.8"
_PROBE_PORT = 53


class NetworkStatus:
    def __init__(self, ttl: float = NETWORK_CACHE_TTL) -> None:
        self._ttl = ttl
        self._last_check = 0.0
        self._online = True

    @property
    def online(self) -> bool:
        now = time.monotonic()
        if now - self._last_check < self._ttl:
            return self._online
        self._online = self._probe()
        self._last_check = now
        return self._online

    def force_refresh(self) -> bool:
        self._last_check = 0.0
        return self.online

    @staticmethod
    def _probe() -> bool:
        try:
            response = requests.get(_PROBE_URL, timeout=NETWORK_CHECK_TIMEOUT)
            if response.status_code < 500:
                return True
        except requests.RequestException:
            logger.debug("http probe failed, trying socket", exc_info=True)
        try:
            with socket.create_connection((_PROBE_HOST, _PROBE_PORT), timeout=NETWORK_CHECK_TIMEOUT):
                return True
        except OSError:
            return False
