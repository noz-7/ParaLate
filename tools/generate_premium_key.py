"""Interactively issue ParaLate Premium licenses with the installed issuer key."""
from __future__ import annotations

import sys
import os
from datetime import date
from pathlib import Path
from typing import Callable

DURATIONS = (
    ("1", "7gün", "7 gün"),
    ("2", "14gün", "14 gün"),
    ("3", "1ay", "1 ay"),
    ("4", "3ay", "3 ay"),
    ("5", "6ay", "6 ay"),
    ("6", "1yıl", "1 yıl"),
)


def _project_root() -> Path:
    script_dir = Path(__file__).resolve().parent
    configured_root = os.environ.get("PARALATE_SOURCE_DIR")
    candidates = (
        *((Path(configured_root).expanduser(),) if configured_root else ()),
        script_dir.parent,
        script_dir.parent / "Paralate-free",
        script_dir.parent.parent / "Paralate-free",
    )
    for candidate in candidates:
        if (candidate / "licensing" / "issue_license.py").is_file():
            return candidate
    raise FileNotFoundError(
        "ParaLate source was not found next to this tool. Keep the "
        "'Paralate Generator' and 'Paralate-free' folders side by side."
    )


def generate_key(
    start: date,
    duration: str,
    private_key_path: Path,
    *,
    today: date | None = None,
) -> str:
    current_day = today or date.today()
    if abs((start - current_day).days) > 2:
        raise ValueError(
            "The app only accepts activation dates within two days of today."
        )
    if not private_key_path.is_file():
        raise FileNotFoundError(
            f"Issuer private key not found at: {private_key_path}"
        )

    root = _project_root()
    sys.path.insert(0, str(root))
    try:
        from licensing.issue_license import issue_license
        from licensing.offline_provider import OfflineLicenseProvider

        code = issue_license(start, duration, private_key_path)
        OfflineLicenseProvider().verify(code, activation_date=current_day)
        return code
    finally:
        try:
            sys.path.remove(str(root))
        except ValueError:
            pass


def _prompt_start(input_fn: Callable[[str], str], today: date) -> date:
    answer = input_fn(f"Başlangıç tarihi (YYYY-AA-GG, boş = {today}): ").strip()
    try:
        start = date.fromisoformat(answer) if answer else today
    except ValueError as error:
        raise ValueError("Tarih YYYY-AA-GG biçiminde olmalı.") from error
    if abs((start - today).days) > 2:
        raise ValueError("Başlangıç tarihi bugünden en fazla 2 gün farklı olabilir.")
    return start


def _prompt_duration(input_fn: Callable[[str], str]) -> str:
    print("\nPremium süresi:")
    for number, _duration, label in DURATIONS:
        print(f"  {number}) {label}")
    answer = input_fn("Seçiminiz [1-6]: ").strip()
    for number, duration, _label in DURATIONS:
        if answer == number:
            return duration
    raise ValueError("Süre seçimi 1 ile 6 arasında olmalı.")


def main() -> int:
    today = date.today()
    key_path = (
        Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        / "ParaLate"
        / "issuer"
        / "issuer_ed25519_private.pem"
    )
    print("ParaLate Premium lisans üreticisi")
    print("Lisans yalnızca uygulamadaki Ed25519 açık anahtarıyla doğrulanır.")
    print(f"İmzalama anahtarı: {key_path}")
    try:
        start = _prompt_start(input, today)
        duration = _prompt_duration(input)
        code = generate_key(start, duration, key_path, today=today)
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"\nHata: {error}", file=sys.stderr)
        return 1
    print(f"\nBaşlangıç: {start.isoformat()}")
    duration_label = next(label for _number, value, label in DURATIONS if value == duration)
    print(f"Süre: {duration_label}")
    print("\nAktivasyon kodu:")
    print(code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
