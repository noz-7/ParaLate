"""Branded, per-user Windows installer for ParaLate."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QFont, QFontDatabase, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

APP_NAME = "ParaLate"
PUBLISHER = "NOZ-7 Software"
CONTACT_EMAIL = "yorulmazoguzhan306@gmail.com"
APP_VERSION = "1.0.0"
INSTALL_PARENT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs"
INSTALL_DIR = INSTALL_PARENT / APP_NAME
START_MENU_DIR = Path(os.environ.get("APPDATA", Path.home())) / (
    "Microsoft/Windows/Start Menu/Programs/ParaLate"
)
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ParaLate"

_STYLE = """
QWidget { color: #f2f4f8; background: #111318; font-family: "Segoe UI"; }
QWidget#brandPanel { background: #09264d; }
QWidget#contentPanel { background: #111318; }
QLabel, QCheckBox { background: transparent; }
QLabel#appTitle { color: #ffffff; font-size: 36px; font-weight: 700; }
QLabel#installerTitle { color: #f6f7fb; font-size: 27px; font-weight: 700; }
QLabel#subtitle { color: #a8b1c2; font-size: 12px; }
QLabel#developer { color: #f0c84b; font-size: 12px; font-weight: 700; }
QLabel#author { color: #dce3ee; font-size: 12px; }
QPlainTextEdit {
  background: #191c23; color: #d9deea; border: 1px solid #353b48;
  border-radius: 5px; padding: 10px; selection-background-color: #24589b;
}
QCheckBox { color: #e8ebf2; font-size: 11px; font-weight: 600; spacing: 10px; }
QCheckBox::indicator { width: 18px; height: 18px; }
QPushButton {
  background: #183f75; color: white; border: 1px solid #2c5b98;
  border-radius: 4px; padding: 12px 22px; font-size: 12px; font-weight: 700;
}
QPushButton:hover:enabled { background: #245693; }
QPushButton:disabled { background: #30343d; color: #818896; border-color: #3c414b; }
QPushButton#cancelButton { background: #191c23; border: 1px solid #697181; }
QPushButton#cancelButton:hover { background: #282c35; }
QProgressBar { border: 1px solid #353b48; border-radius: 3px; height: 7px; text-align: center; }
QProgressBar::chunk { background: #e3b832; }
"""

_TEXT = {
    "tr": {
        "window_title": "ParaLate Kurulum",
        "language_title": "Kurulum dilini seçin",
        "title": "ParaLate Kurulumu",
        "subtitle": "Devam etmek için lisans bildirimlerini okuyup kabul edin.",
        "accept": "Lisans bildirimlerini okudum; açık kaynak bileşenlerin kendi lisans koşullarını kabul ediyorum.",
        "status": "Kurulum, kullanıcı hesabınıza yapılır; belgeleriniz korunur.",
        "installing": "Uygulama dosyaları kopyalanıyor…",
        "registering": "Başlat menüsü ve kaldırma kaydı hazırlanıyor…",
        "install": "Yükle",
        "cancel": "İptal",
        "already_installed": "ParaLate zaten kurulu",
        "replace_question": "Mevcut uygulama dosyaları güncellensin mi? Belgeleriniz ve ayarlarınız korunur.",
        "install_complete": "Kurulum başarıyla tamamlandı.",
        "success_title": "ParaLate kuruldu",
        "launch_question": "ParaLate başarıyla kuruldu. Şimdi başlatılsın mı?",
        "install_failed": "Kurulum tamamlanamadı.",
        "error_title": "Kurulum hatası",
        "error_message": "ParaLate kurulamadı.\n\n{details}",
        "install_running_title": "Kurulum sürüyor",
        "install_running_message": "Kurulum tamamlanana kadar bu pencereyi kapatmayın.",
        "uninstall_title": "ParaLate kaldırma",
        "uninstall_question": "ParaLate kaldırılsın mı? Çevrilmiş belgeleriniz ve ayarlarınız silinmeden bırakılacaktır.",
        "uninstall_error_title": "Kaldırma hatası",
        "uninstall_failed": "Kaldırma tamamlanamadı. ParaLate açıksa kapatıp yeniden deneyin.\n\n{error}",
        "platform_error_title": "ParaLate Kurulum",
        "platform_error": "Bu kurulum yalnızca Windows'ta çalışır.",
        "license_heading": "ParaLate — Yazılım Lisans Bildirimi",
        "license_body": (
            "Bu kurulum paketi, ParaLate kaynak kodunu GPL-3.0-only koşullarıyla ve "
            "PyQt6/PyMuPDF gibi üçüncü taraf bileşenleri kendi lisanslarına göre içerir. "
            "Paketteki PyMuPDF, GNU Affero General Public License v3.0 (AGPL-3.0) "
            "veya Artifex ticari lisansı altındadır. PyQt6 GPL-3.0; Qt kütüphaneleri "
            "ise ilgili LGPL/GPL lisansları altındadır.\n\n"
            "ParaLate'in kendi telif hakları NOZ-7 Software / Oğuzhan YORULMAZ'a aittir. "
            "ParaLate GPL-3.0 altında kullanılabilir. GPL'den ayrı kapalı kaynak/ticari "
            "ParaLate lisansı için {email} adresinden görüşülmesi gerekir. Bu izin "
            "PyQt6, PyMuPDF veya diğer üçüncü taraf lisanslarını kapsamaz; gerekli "
            "ticari izinler alınmadan kapalı kaynak/ticari dağıtım yapılamaz.\n\n"
            "Onayınız, bu lisans bildirimlerini okuduğunuzu ve açık kaynak bileşenlerin "
            "kendi lisans koşullarını kabul ettiğinizi belirtir. Bu özet, asıl lisans "
            "metinlerinin yerine geçmez. Tam GPL-3.0 ve AGPL-3.0 metinleri aşağıdadır. "
            "Qt lisansları ve diğer bildirimler kurulumdan sonra ThirdPartyLicenses "
            "klasöründe bulunur."
        ),
    },
    "en": {
        "window_title": "ParaLate Setup",
        "language_title": "Choose setup language",
        "title": "ParaLate Setup",
        "subtitle": "Read and accept the license notices to continue.",
        "accept": "I have read the license notices and accept the respective terms of the open-source components.",
        "status": "Installs for your user account; your documents are preserved.",
        "installing": "Copying application files…",
        "registering": "Creating Start menu and uninstall entries…",
        "install": "Install",
        "cancel": "Cancel",
        "already_installed": "ParaLate is already installed",
        "replace_question": "Update the existing application files? Your documents and settings will be preserved.",
        "install_complete": "Installation completed successfully.",
        "success_title": "ParaLate installed",
        "launch_question": "ParaLate was installed successfully. Launch it now?",
        "install_failed": "Installation could not be completed.",
        "error_title": "Installation error",
        "error_message": "ParaLate could not be installed.\n\n{details}",
        "install_running_title": "Installation in progress",
        "install_running_message": "Please wait for the installation to finish before closing this window.",
        "uninstall_title": "Uninstall ParaLate",
        "uninstall_question": "Uninstall ParaLate? Your translated documents and settings will be kept.",
        "uninstall_error_title": "Uninstall error",
        "uninstall_failed": "Could not finish uninstalling. Close ParaLate if it is running and try again.\n\n{error}",
        "platform_error_title": "ParaLate Setup",
        "platform_error": "This installer only runs on Windows.",
        "license_heading": "ParaLate — Software License Notice",
        "license_body": (
            "This installer contains ParaLate source code under GPL-3.0-only and third-party "
            "components such as PyQt6 and PyMuPDF under their respective licenses. The included "
            "PyMuPDF is licensed under GNU AGPL version 3.0 or an Artifex commercial license. "
            "PyQt6 is GPL-3.0; Qt libraries are subject to their applicable LGPL/GPL licenses.\n\n"
            "ParaLate's original code is copyrighted by NOZ-7 Software / Oğuzhan YORULMAZ. "
            "ParaLate is available under GPL-3.0. A separate commercial/proprietary license "
            "for ParaLate may be discussed at {email}. That permission does not cover PyQt6, "
            "PyMuPDF, or other third-party software. All required third-party commercial "
            "permissions must be obtained before a proprietary/commercial distribution.\n\n"
            "By accepting, you confirm that you have read these notices and accept the "
            "applicable terms of the open-source components. This summary does not replace "
            "the original license texts. The complete GPL-3.0 and AGPL-3.0 texts follow. "
            "Qt licenses and other notices are included in ThirdPartyLicenses after installation."
        ),
    },
    "ru": {
        "window_title": "Установка ParaLate",
        "language_title": "Выберите язык установки",
        "title": "Установка ParaLate",
        "subtitle": "Для продолжения прочитайте уведомления о лицензиях и примите их.",
        "accept": "Я прочитал(а) уведомления о лицензиях и принимаю условия лицензий компонентов с открытым исходным кодом.",
        "status": "Установка для вашей учётной записи; ваши документы сохраняются.",
        "installing": "Копирование файлов приложения…",
        "registering": "Создание ярлыков и записи удаления…",
        "install": "Установить",
        "cancel": "Отмена",
        "already_installed": "ParaLate уже установлено",
        "replace_question": "Обновить файлы приложения? Ваши документы и настройки будут сохранены.",
        "install_complete": "Установка успешно завершена.",
        "success_title": "ParaLate установлено",
        "launch_question": "ParaLate успешно установлено. Запустить сейчас?",
        "install_failed": "Не удалось завершить установку.",
        "error_title": "Ошибка установки",
        "error_message": "Не удалось установить ParaLate.\n\n{details}",
        "install_running_title": "Идёт установка",
        "install_running_message": "Не закрывайте это окно до завершения установки.",
        "uninstall_title": "Удаление ParaLate",
        "uninstall_question": "Удалить ParaLate? Переведённые документы и настройки останутся.",
        "uninstall_error_title": "Ошибка удаления",
        "uninstall_failed": "Не удалось завершить удаление. Закройте ParaLate, если он запущен, и повторите попытку.\n\n{error}",
        "platform_error_title": "Установка ParaLate",
        "platform_error": "Эта программа установки работает только в Windows.",
        "license_heading": "ParaLate — Уведомление о лицензии",
        "license_body": (
            "Этот установщик содержит исходный код ParaLate на условиях GPL-3.0-only и сторонние "
            "компоненты, например PyQt6 и PyMuPDF, на условиях их собственных лицензий. "
            "PyMuPDF распространяется по GNU AGPL версии 3.0 или коммерческой лицензии Artifex. "
            "PyQt6 распространяется по GPL-3.0; для библиотек Qt действуют соответствующие "
            "лицензии LGPL/GPL.\n\n"
            "Авторские права на собственный код ParaLate принадлежат NOZ-7 Software / Огузхану Йорулмазу. "
            "ParaLate доступен по GPL-3.0. Отдельную коммерческую/проприетарную лицензию на ParaLate "
            "можно обсудить по адресу {email}. Она не распространяется на PyQt6, PyMuPDF и другие "
            "сторонние компоненты. Для проприетарного/коммерческого распространения необходимо "
            "получить все требуемые коммерческие разрешения третьих сторон.\n\n"
            "Принимая условия, вы подтверждаете, что прочитали уведомления и принимаете применимые "
            "условия лицензий компонентов с открытым исходным кодом. Это краткое изложение не заменяет "
            "оригинальные тексты лицензий. Далее приведены полные тексты GPL-3.0 и AGPL-3.0. "
            "Лицензии Qt и прочие уведомления доступны в ThirdPartyLicenses после установки."
        ),
    },
    "fr": {
        "window_title": "Installation de ParaLate",
        "language_title": "Choisissez la langue d’installation",
        "title": "Installation de ParaLate",
        "subtitle": "Lisez et acceptez les notices de licence pour continuer.",
        "accept": "J’ai lu les notices de licence et j’accepte les conditions applicables aux composants open source.",
        "status": "Installation pour votre compte utilisateur ; vos documents sont conservés.",
        "installing": "Copie des fichiers de l’application…",
        "registering": "Création du menu Démarrer et de l’entrée de désinstallation…",
        "install": "Installer",
        "cancel": "Annuler",
        "already_installed": "ParaLate est déjà installé",
        "replace_question": "Mettre à jour les fichiers de l’application ? Vos documents et paramètres seront conservés.",
        "install_complete": "Installation terminée avec succès.",
        "success_title": "ParaLate installé",
        "launch_question": "ParaLate a été installé. Voulez-vous le lancer maintenant ?",
        "install_failed": "L’installation n’a pas pu être terminée.",
        "error_title": "Erreur d’installation",
        "error_message": "Impossible d’installer ParaLate.\n\n{details}",
        "install_running_title": "Installation en cours",
        "install_running_message": "Veuillez attendre la fin de l’installation avant de fermer cette fenêtre.",
        "uninstall_title": "Désinstaller ParaLate",
        "uninstall_question": "Désinstaller ParaLate ? Vos documents traduits et vos paramètres seront conservés.",
        "uninstall_error_title": "Erreur de désinstallation",
        "uninstall_failed": "La désinstallation n’a pas abouti. Fermez ParaLate s’il est ouvert, puis réessayez.\n\n{error}",
        "platform_error_title": "Installation de ParaLate",
        "platform_error": "Ce programme d’installation ne fonctionne que sous Windows.",
        "license_heading": "ParaLate — Avis de licence logicielle",
        "license_body": (
            "Ce programme d’installation contient le code source de ParaLate sous GPL-3.0-only "
            "ainsi que des composants tiers, tels que PyQt6 et PyMuPDF, soumis à leurs licences "
            "respectives. PyMuPDF est distribué sous GNU AGPL version 3.0 ou sous licence "
            "commerciale Artifex. PyQt6 relève de GPL-3.0 ; les bibliothèques Qt relèvent de "
            "leurs licences LGPL/GPL applicables.\n\n"
            "Les droits d’auteur sur le code propre à ParaLate appartiennent à NOZ-7 Software / "
            "Oğuzhan YORULMAZ. ParaLate est disponible sous GPL-3.0. Une licence commerciale/"
            "propriétaire distincte pour ParaLate peut être discutée à l’adresse {email}. "
            "Cette autorisation ne couvre pas PyQt6, PyMuPDF ni les autres composants tiers. "
            "Toutes les autorisations commerciales tierces nécessaires doivent être obtenues "
            "avant toute distribution propriétaire/commerciale.\n\n"
            "En acceptant, vous confirmez avoir lu ces avis et accepter les conditions applicables "
            "aux composants open source. Ce résumé ne remplace pas les textes originaux des licences. "
            "Les textes complets GPL-3.0 et AGPL-3.0 suivent. Les licences Qt et autres avis sont "
            "fournis dans ThirdPartyLicenses après l’installation."
        ),
    },
}

_LANGUAGE_LABELS = {
    "tr": "Türkçe",
    "en": "English",
    "ru": "Русский",
    "fr": "Français",
}


def _resource_path(relative: str) -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / relative
    return Path(__file__).resolve().parents[1] / relative


def _register_windows_ui_font() -> None:
    if sys.platform != "win32":
        return
    font_path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeui.ttf"
    if font_path.is_file():
        QFontDatabase.addApplicationFont(str(font_path))


def _payload_path() -> Path:
    if getattr(sys, "frozen", False):
        return _resource_path("payload/ParaLate")
    return Path(__file__).resolve().parents[1] / "dist" / "ParaLate"


def _agreement_text_for_language(language: str) -> str:
    text = _TEXT[language]
    license_text = text["license_heading"] + "\n\n" + text["license_body"].format(
        email=CONTACT_EMAIL
    )
    license_files = (
        ("GPL-3.0.txt", "GNU GENERAL PUBLIC LICENSE v3.0"),
        ("AGPL-3.0.txt", "GNU AFFERO GENERAL PUBLIC LICENSE v3.0"),
        ("Qt-LICENSE.txt", "Qt third-party license"),
    )
    sections = [license_text, "\n\n--- THIRD-PARTY LICENSE TEXTS (official texts) ---"]
    for filename, title in license_files:
        path = _resource_path(f"installer/licenses/{filename}")
        if path.is_file():
            sections.extend((f"\n\n--- {title} ---\n", path.read_text(encoding="utf-8")))
    notices = _resource_path("installer/THIRD_PARTY_NOTICES.md")
    if notices.is_file():
        sections.extend(
            ("\n\n--- THIRD-PARTY NOTICES ---\n", notices.read_text(encoding="utf-8"))
        )
    return "".join(sections)


class LanguageDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.language = ""
        self.setWindowTitle("ParaLate Setup")
        self.setWindowIcon(QIcon(str(_resource_path("icon.png"))))
        self.setFixedSize(360, 250)
        self.setStyleSheet(_STYLE)
        layout = QVBoxLayout(self)
        title = QLabel("Dil / Language / Язык / Langue")
        title.setObjectName("installerTitle")
        layout.addWidget(title)
        for language, label in _LANGUAGE_LABELS.items():
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, code=language: self._choose(code))
            layout.addWidget(button)

    def _choose(self, language: str) -> None:
        self.language = language
        self.accept()


class InstallWorker(QObject):
    finished = pyqtSignal()
    failed = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, language: str) -> None:
        super().__init__()
        self.language = language

    def run(self) -> None:
        staging: Path | None = None
        backup: Path | None = None
        replaced = False
        had_previous_install = INSTALL_DIR.exists()
        try:
            if sys.platform != "win32":
                raise OSError("ParaLate Setup can only install on Windows.")
            payload = _payload_path()
            executable = payload / "ParaLate.exe"
            if not executable.is_file():
                raise FileNotFoundError(f"Missing application payload: {executable}")
            if not getattr(sys, "frozen", False):
                raise RuntimeError("Run the packaged Setup.exe to install ParaLate.")

            INSTALL_PARENT.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".ParaLate-install-", dir=INSTALL_PARENT))
            self.status.emit("installing")
            shutil.copytree(payload, staging, dirs_exist_ok=True)
            shutil.copy2(sys.executable, staging / "ParaLateUninstall.exe")

            if INSTALL_DIR.exists():
                backup = INSTALL_PARENT / f".ParaLate-backup-{uuid.uuid4().hex}"
                os.replace(INSTALL_DIR, backup)
            os.replace(staging, INSTALL_DIR)
            staging = None
            replaced = True

            self.status.emit("registering")
            _create_shortcuts()
            _register_installation(self.language)

            if backup is not None:
                shutil.rmtree(backup)
            self.finished.emit()
        except Exception as error:
            logging.exception("ParaLate installation failed")
            if replaced and INSTALL_DIR.exists():
                shutil.rmtree(INSTALL_DIR, ignore_errors=True)
            if backup is not None and backup.exists():
                try:
                    os.replace(backup, INSTALL_DIR)
                except OSError:
                    logging.exception("Could not restore previous installation")
            try:
                if had_previous_install and INSTALL_DIR.exists():
                    _create_shortcuts()
                    _register_installation(self.language)
                else:
                    _remove_installation_registration()
                    shutil.rmtree(START_MENU_DIR, ignore_errors=True)
                    desktop_link = (
                        Path(os.environ.get("USERPROFILE", Path.home()))
                        / "Desktop"
                        / "ParaLate.lnk"
                    )
                    desktop_link.unlink(missing_ok=True)
            except Exception:
                logging.exception("Could not restore the previous installation registration")
            self.failed.emit(str(error))
        finally:
            if staging is not None and staging.exists():
                shutil.rmtree(staging, ignore_errors=True)


def _create_shortcut(path: Path, target: Path) -> None:
    script = (
        "$w=New-Object -ComObject WScript.Shell;"
        "$s=$w.CreateShortcut($env:PL_SHORTCUT);"
        "$s.TargetPath=$env:PL_TARGET;"
        "$s.WorkingDirectory=$env:PL_WORKDIR;"
        "$s.IconLocation=$env:PL_ICON;"
        "$s.Save()"
    )
    env = os.environ.copy()
    env.update(
        {
            "PL_SHORTCUT": str(path),
            "PL_TARGET": str(target),
            "PL_WORKDIR": str(target.parent),
            "PL_ICON": str(target),
        }
    )
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise OSError(f"Could not create ParaLate shortcut: {result.stderr.strip()}")


def _create_shortcuts() -> None:
    target = INSTALL_DIR / "ParaLate.exe"
    START_MENU_DIR.mkdir(parents=True, exist_ok=True)
    _create_shortcut(START_MENU_DIR / "ParaLate.lnk", target)
    desktop = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    _create_shortcut(desktop / "ParaLate.lnk", target)


def _register_installation(language: str) -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
        values = {
            "DisplayName": APP_NAME,
            "DisplayVersion": APP_VERSION,
            "Publisher": PUBLISHER,
            "InstallLocation": str(INSTALL_DIR),
            "DisplayIcon": str(INSTALL_DIR / "ParaLate.exe"),
            "UninstallString": f'"{INSTALL_DIR / "ParaLateUninstall.exe"}" --uninstall',
            "SetupLanguage": language,
            "NoModify": 1,
            "NoRepair": 1,
        }
        for name, value in values.items():
            kind = winreg.REG_DWORD if isinstance(value, int) else winreg.REG_SZ
            winreg.SetValueEx(key, name, 0, kind, value)


def _remove_installation_registration() -> None:
    import winreg

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except FileNotFoundError:
        pass


class InstallerWindow(QWidget):
    def __init__(self, language: str) -> None:
        super().__init__()
        _register_windows_ui_font()
        self.language = language
        self.text = _TEXT[language]
        self._thread: QThread | None = None
        self._worker: InstallWorker | None = None
        self.setWindowTitle(self.text["window_title"])
        self.setWindowIcon(QIcon(str(_resource_path("icon.png"))))
        self.setFixedSize(1000, 660)
        self.setStyleSheet(_STYLE)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._brand_panel())
        root.addWidget(self._content_panel(), 1)

    def _brand_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("brandPanel")
        panel.setFixedWidth(295)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(28, 34, 28, 26)
        layout.setSpacing(8)
        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(str(_resource_path("icon.png")))
        if not pixmap.isNull():
            logo.setPixmap(
                pixmap.scaled(
                    150,
                    150,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(14)
        title = QLabel("ParaLate")
        title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addStretch(1)
        developer = QLabel("Developed by NOZ-7 Software")
        developer.setObjectName("developer")
        developer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author = QLabel("Oğuzhan YORULMAZ")
        author.setObjectName("author")
        author.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(developer)
        layout.addWidget(author)
        return panel

    def _content_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("contentPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(34, 30, 34, 26)
        layout.setSpacing(12)
        title = QLabel(self.text["title"])
        title.setObjectName("installerTitle")
        subtitle = QLabel(self.text["subtitle"])
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.license_text = QPlainTextEdit()
        self.license_text.setReadOnly(True)
        self.license_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.license_text.setFont(QFont("Segoe UI", 9))
        self.license_text.setPlainText(_agreement_text_for_language(self.language))
        layout.addWidget(self.license_text, 1)

        self.accept_checkbox = QCheckBox(self.text["accept"])
        layout.addWidget(self.accept_checkbox)

        self.status_label = QLabel(self.text["status"])
        self.status_label.setObjectName("subtitle")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)

        buttons = QHBoxLayout()
        buttons.setSpacing(14)
        self.install_button = QPushButton(self.text["install"])
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self._install)
        self.cancel_button = QPushButton(self.text["cancel"])
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.clicked.connect(self.close)
        buttons.addWidget(self.install_button, 1)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)
        self.accept_checkbox.toggled.connect(self.install_button.setEnabled)
        return panel

    def _install(self) -> None:
        if not self.accept_checkbox.isChecked():
            return
        if INSTALL_DIR.exists():
            answer = QMessageBox.question(
                self,
                self.text["already_installed"],
                self.text["replace_question"],
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.install_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.progress.show()
        self._thread = QThread(self)
        self._worker = InstallWorker(self.language)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.status.connect(self._set_status)
        self._worker.finished.connect(self._install_succeeded)
        self._worker.failed.connect(self._install_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

    def _set_status(self, status: str) -> None:
        if status == "installing":
            self.status_label.setText(self.text["installing"])
        elif status == "registering":
            self.status_label.setText(self.text["registering"])
        else:
            self.status_label.setText(status)

    def _install_succeeded(self) -> None:
        self.progress.hide()
        self.status_label.setText(self.text["install_complete"])
        answer = QMessageBox.question(
            self,
            self.text["success_title"],
            self.text["launch_question"],
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            subprocess.Popen([str(INSTALL_DIR / "ParaLate.exe")], cwd=INSTALL_DIR)
        self.close()

    def _install_failed(self, details: str) -> None:
        self.progress.hide()
        self.cancel_button.setEnabled(True)
        self.install_button.setEnabled(self.accept_checkbox.isChecked())
        self.status_label.setText(self.text["install_failed"])
        QMessageBox.critical(
            self,
            self.text["error_title"],
            self.text["error_message"].format(details=details),
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._thread is not None and self._thread.isRunning():
            event.ignore()
            QMessageBox.information(
                self,
                self.text["install_running_title"],
                self.text["install_running_message"],
            )
            return
        event.accept()


def _begin_uninstall() -> int:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            language = winreg.QueryValueEx(key, "SetupLanguage")[0]
    except (FileNotFoundError, OSError):
        language = "tr"
    if language not in _TEXT:
        language = "tr"
    text = _TEXT[language]
    answer = QMessageBox.question(
        None,
        text["uninstall_title"],
        text["uninstall_question"],
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return 0
    try:
        _remove_installation_registration()
        shutil.rmtree(START_MENU_DIR, ignore_errors=True)
        desktop_link = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop" / "ParaLate.lnk"
        desktop_link.unlink(missing_ok=True)
        helper = Path(tempfile.gettempdir()) / f"ParaLateUninstall-{uuid.uuid4().hex}.exe"
        shutil.copy2(sys.executable, helper)
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        subprocess.Popen(
            [str(helper), "--uninstall-worker", str(INSTALL_DIR), str(helper)],
            creationflags=flags,
            close_fds=True,
        )
        return 0
    except OSError as error:
        logging.exception("Could not start ParaLate uninstaller")
        QMessageBox.critical(None, text["uninstall_error_title"], str(error))
        return 1


def _uninstall_worker(target: Path, helper: Path) -> int:
    time.sleep(1.5)
    try:
        shutil.rmtree(target)
        if sys.platform == "win32":
            import ctypes

            ctypes.windll.kernel32.MoveFileExW(str(helper), None, 0x4)
        return 0
    except OSError as error:
        app = QApplication.instance() or QApplication([])
        QMessageBox.critical(
            None,
            text["uninstall_error_title"],
            text["uninstall_failed"].format(error=error),
        )
        return 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "NOZ7.ParaLate.Setup"
        )
    app = QApplication([sys.argv[0]])
    app.setApplicationName("ParaLate Setup")
    app.setWindowIcon(QIcon(str(_resource_path("icon.png"))))
    _register_windows_ui_font()
    if args and args[0] == "--uninstall":
        return _begin_uninstall()
    if args and args[0] == "--uninstall-worker" and len(args) == 3:
        return _uninstall_worker(Path(args[1]), Path(args[2]))
    if sys.platform != "win32":
        QMessageBox.critical(
            None, _TEXT["en"]["platform_error_title"], _TEXT["en"]["platform_error"]
        )
        return 1
    language_dialog = LanguageDialog()
    if language_dialog.exec() != QDialog.DialogCode.Accepted:
        return 0
    window = InstallerWindow(language_dialog.language)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
