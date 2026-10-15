"""Ad provider interface. Ads live in dedicated UI areas only — never over
document content."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class AdInfo:
    title: str
    body: str
    action: str = ""
    url: str = ""


class AdProvider(ABC):
    name: str = "base"

    @abstractmethod
    def get_ad(self, context: str) -> AdInfo | None:
        """context: 'home' or 'viewer'. None means show nothing."""
