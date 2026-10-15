# ParaLate

**ParaLate**, İngilizce (veya herhangi bir dildeki) bir ders PDF'ini **çevrimiçi** olarak sayfa sayfa çeviren, orijinal ve çevrilmiş sayfaları **gerçek biçimde interleave eden** (Orig1, Trans1, Orig2, Trans2, …) tek bir PDF üreten ve bunu **kendi PDF görüntüleyicisinde iki sayfa yan yana** gösteren modern bir masaüstü uygulamasıdır.

```
SOL (Orijinal)            SAĞ (Çeviri)
─────────────             ──────────────
Sayfa 1                   Sayfa 2
Sayfa 3                   Sayfa 4
Sayfa 5                   Sayfa 6
```

Davranış, Microsoft Edge PDF görüntüleyicisindeki **Sayfa görünümü → İki sayfa** modu ile aynıdır: tek sayfa değil, **çift sayfa (spread)** halinde, eşit hizalı, kaydırılabilir, zoom yapılabilir.

> **Temel amaç:** *İngilizce ders PDF'sini Türkçe çeviriyle yan yana, hızlı, stabil ve rahat şekilde okumak.*

---

## Özellikler

- **Gerçek interleave PDF**: Her orijinal sayfanın ardından çevirisi gelir (Orig1, Trans1, Orig2, Trans2, …). Tek PDF, tek dosya.
- **Kendi PDF görüntüleyicisi**: Orijinal solda, çeviri sağda; gerçek PDF metin katmanından kelime seçimi/kopyalama, sayfa sayfa gezinme, Ctrl+ yakınlaştırma, Ctrl+F arama ve tıklanabilir bağlantılar.
- **Online çeviri, OCR yok, offline AI yok**: Sağlayıcı zinciri `google → mymemory → microsoft → libretranslate`; hata/limit durumunda otomatik fallback, deneme + backoff.
- **Koruyucu çeviri sayfası üretimi**: Orijinal sayfanın metni redaction ile silinirken **görseller ve vektör çizimler korunur**; çeviride metnin span renkleri, kalın/italik stilleri ve PDF'deki highlight/altı çizili/üstü çizili çizimler korunur. Çeviri, Türkçe destekli sistem fontuyla (Segoe UI / DejaVu) aynı yerleşime yeniden yazılır. Kod/monospace blokları olduğu gibi bırakılır.
- **Şifreli belge deposu (`.plt`)**: Tüm belgeler AES ile şifrelenir; anahtar OS keyring + dosya kombinasyonuyla korunur.
- **Ücretsiz / Premium**: FREE = günde **3 PDF çevirisi**, PDF başına **30 sayfa**; silme kota geri **yüklemez**; FREE internet ister, **PREMIUM çevrimdışı açabilir** (indirilmiş/önbellekli belgeler). Premium imzalı aktivasyonla açılır; PDF indirme Premium özelliğidir.
- **Zamanlı Premium tanıtımı**: Ücretsiz kullanıcı PDF açınca ve oturum sırasında her 7 dakikada bir gösterilir; kapatıldığında görüntüleme sürer.
- **Çeviri + belge önbelleği**: Aynı PDF + dil çifti tekrar işlenmez ("yeniden kullanıldı").
- **Geçmiş**: Tüm çeviriler listelenir, tekrar açılır, silinir.
- **İlk çalıştırma dil seçimi** (Türkçe/English), tam koyu arayüz, yerelleştirme JSON tabanlı (`localization/tr.json`, `localization/en.json`).
- **Reklam soyutlaması**: Sağlayıcı arayüzü + yöneticisi; Premium'da devre dışı.
- **Güvenlik**: API anahtarları `.env`/keyring'de, asla loglanmaz (`RedactionFilter`), config'e yazılmaz.
- **Loglama**: dönen dosya (`logs/paralate.log`), kırmızı-aksiyon filtresi.
- **Testler**: PDF, depolama, kota, lisans ve GUI regresyon testleri (`pytest`).

## Lisans ve yeniden dağıtım

ParaLate'in özgün uygulama kaynak kodu © 2026 Oğuzhan YORULMAZ / NOZ-7
Software'dir ve kök dizindeki [`LICENSE`](./LICENSE) dosyasında bulunan
GPL-3.0-only lisansı altında sunulur. Hak sahibi, yalnızca ParaLate'e ait
kod için GPL lisansından ayrı ticari/kapalı kaynak lisansını e-posta üzerinden
görüşebilir: [yorulmazoguzhan306@gmail.com](mailto:yorulmazoguzhan306@gmail.com).
Bu ayrı lisans üçüncü taraf yazılımlarının haklarını kapsamaz.

Mevcut Windows derlemesi PyMuPDF'i (AGPL-3.0 veya Artifex ticari lisansı),
PyQt6'yı (GPL-3.0) ve Qt bileşenlerini (bileşene göre LGPL/GPL) içerir.
Dolayısıyla bu bağımlılıklarla oluşturulan birleşik açık kaynak dağıtımı
üçüncü taraf koşullarına, özellikle AGPL-3.0'a uymalıdır. Kapalı kaynak/
ticari dağıtım için ParaLate koduna ek olarak PyQt6 ve PyMuPDF dahil gerekli
üçüncü taraf ticari izinler de alınmalıdır. Lisans metinleri, paket envanteri
ve kaynak konumları dağıtım klasöründeki `ThirdPartyLicenses` ve `Source`
alt klasörlerinde bulunur. Bu özet hukuki danışmanlık değildir.

---

## Gereksinimler

| | Windows | Linux |
|---|---|---|
| Python | 3.12+ | 3.12+ (python3.12) |
| GUI | Qt6 (pip ile gelir) | `libgl1 libegl1 libxkbcommon0 libdbus-1-3` vb. (headless ise `QT_QPA_PLATFORM=offscreen`) |
| Fontlar | Sistem fontları hazır (Segoe UI/Arial) | `fonts-dejavu` veya `fonts-liberation` |

---

## Kurulum

### Windows (Git Bash / PowerShell)

```bash
# Python 3.12 kurulu değilse:
winget install --id Python.Python.3.12

# Sanal ortam + bağımlılıklar
python -m venv .venv
source .venv/Scripts/activate      # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

### Linux (Debian/Ubuntu örneği)

```bash
sudo apt install python3.12 python3.12-venv \
     libgl1 libegl1 libxkbcommon0 libdbus-1-3 fonts-dejavu

python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

---

## API Key Kurulumu

Uygulama **anahtarsız da çalışır**: önce genel Google Translate ucuna, o reddederse **MyMemory**'ye düşer. Anahtar verirseniz daha stabil/ileri sağlayıcılar kullanılır.

1. Şablonu kopyalayın: `cp .env.example .env`
2. Kullanmak istediğiniz sağlayıcının anahtarını girin:

| Ortam değişkeni | Sağlayıcı | Nereden alınır |
|---|---|---|
| `GOOGLE_TRANSLATE_API_KEY` | Google Cloud Translation v2 | https://console.cloud.google.com/apis/credentials |
| `MICROSOFT_TRANSLATOR_API_KEY` + `MICROSOFT_TRANSLATOR_REGION` | Azure Translator | https://azure.microsoft.com/free/azure-ai-translator |
| `LIBRETRANSLATE_URL` + `LIBRETRANSLATE_API_KEY` | LibreTranslate | Kendi sunucunuz veya portal.libretranslate.com |
| — | MyMemory | Anahtar gerektirmez (otomatik fallback) |

`.env` örneği:

```dotenv
GOOGLE_TRANSLATE_API_KEY=AIza...
MICROSOFT_TRANSLATOR_API_KEY=xxxxxxxx
MICROSOFT_TRANSLATOR_REGION=westeurope
LIBRETRANSLATE_URL=https://libretranslate.example.com
LIBRETRANSLATE_API_KEY=xxxxxxxx
```

> Anahtarlar `.env` dosyasından okunur (`python-dotenv`), ortam değişkeni varsa ona öncelik verilir; ayrıca **OS keyring**'e yazılabilir. Loglarda anahtar değerleri `***` ile maskelenir. `.env` asla commit edilmez (`.gitignore` içinde).

### Sağlayıcı zinciri

`app/constants.py → PROVIDER_ORDER`:

1. **google** — anahtarsız genel uç; 429/limit olabilir → düşer.
2. **mymemory** — anahtarsız, cümlende iyi.
3. **microsoft** — anahtar + bölge gerekli.
4. **libretranslate** — URL (+isteğe bağlı anahtar) gerekli.

---

## Çalıştırma

```bash
# Windows
.venv/Scripts/python.exe main.py

# Linux
.venv/bin/python main.py
```

İlk açılışta **dil seçimi** penceresi gelir; ardından ana pencere açılır. PDF seç → hedef dil → Çevir; işlem bitince **ParaLate Viewer** interleave PDF'i iki sayfa yan yana gösterir.

Veri dizini (config, SQLite, şifreli belgeler, loglar, önbellek):

- Windows: `%APPDATA%\ParaLate\`
- Linux: `~/.local/share/paralate/`
- Geçersiz kılmak için: `PARA_LATE_DATA_DIR=/tmp/pl python main.py`

### Testler

```bash
QT_QPA_PLATFORM=offscreen python -m pytest        # Windows: set QT_QPA_PLATFORM=offscreen
```

GUI testleri offscreen koşar; ekran gerekmez.

### Geliştirme / Premium denemesi

### Çevrimdışı Premium lisans üretimi

Lisans biçimi üç CRC32 kontrol alanı ve bunları doğrulayan Ed25519 imzasından oluşur:
`XXXXXXXX-XXXXXXXX-XXXXXXXX-<128 hex imza>`. Uygulama yalnızca açık doğrulama anahtarını içerir; imzalama anahtarı kaynak koda veya uygulama paketine konmaz.

Windows'ta bu geliştirme ortamı için imzalama anahtarı `%APPDATA%\ParaLate\issuer\issuer_ed25519_private.pem` konumunda tutulur. Anahtarı gizli ve yedekli tutun; kaybedilirse yeni açık anahtar ile yeni bir uygulama dağıtımı gerekir. Lisans üretimi:

```powershell
.venv\Scripts\python.exe -m licensing.issue_license `
  --key "$env:APPDATA\ParaLate\issuer\issuer_ed25519_private.pem" `
  --duration 1ay
```

Desteklenen süreler `7gün`, `14gün`, `1ay`, `3ay`, `6ay`, `1yıl`; başlangıç tarihini sabitlemek için isteğe bağlı `--start YYYY-MM-DD` kullanın. Bitiş tarihi lisansın geçerli olmadığı ilk gündür; başlangıç tarihi gelecekteyse Premium o tarihte etkinleşir. Üretim aracı özel anahtarı hiçbir zaman ekrana yazmaz; yalnızca oluşturduğu aktivasyon kodunu verir. Uygulama sistem tarihi ilerlediğinde son görülen tarihi kaydederek saat geri alma girişimini tespit etmeye çalışır. Tamamen çevrimdışı ve saldırganın yerel veritabanı/saati değiştirebildiği bir ortamda bu önlem kesin değildir. Belgeleri paylaşma özelliği uygulamada bulunmadığından Premium avantajı olarak sunulmaz.

---

## Windows dağıtım paketi

Windows kurulum dosyasını ve lisans/kaynak eşlikçilerini üretmek için:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe scripts\build_release.py
```

Dağıtım klasörü `release` olur. Kökünde yalnızca `Setup.exe`,
`Source` ve `ThirdPartyLicenses` klasörleri bulunur. Kullanıcı `Setup.exe`'yi
çalıştırınca önce Türkçe, İngilizce, Rusça veya Fransızca kurulum dilini seçer;
lisans bildiriminin açıklayıcı bölümü seçilen dilde, GPL/AGPL'in resmi tam
metinleri özgün İngilizce metinleriyle gösterilir. Bildirimleri kabul ederek
uygulamayı kullanıcı hesabına kurar; Başlat menüsüne ve masaüstüne kısayol eklenir. Windows uygulama
listesinde kaldırma girdisi ve ParaLate simgesi kaydedilir. Kaldırma işlemi
kullanıcı belgelerini ve ayarlarını korur. Kaynak klasörü aynı sürümün
uygulama kaynaklarını ve bağımlılık kilidini içerir.

Sürüm, simge, PyInstaller spec'i veya bağımlılıklar değiştirildikten sonra
paket yeniden oluşturulmalıdır. `PyInstaller` derleme bağımlılığı
`requirements-dev.txt` içinde yer alır.

### Premium anahtarı üretimi

Windows'ta [`tools`](./tools) içindeki `generate_premium_key.py` aracı başlangıç
tarihini ve süreyi sorar, anahtarı mevcut imzalama anahtarıyla üretir ve
uygulamanın açık anahtarıyla doğrular. Kullanıcıya hazır kopya
`C:\Users\<kullanıcı>\Projeler\Paralate Generator` klasörüne konur.
İmzalama anahtarı `%APPDATA%\ParaLate\issuer` içinde tutulur ve araca
kopyalanmaz. Uygulama başlangıç tarihini aktivasyon gününün ±2 günüyle
sınırladığı için üretici de bu aralığın dışındaki tarihleri reddeder.

## Linux Build (PyInstaller → `ParaLate`)

```bash
.venv/bin/python -m PyInstaller --noconfirm --windowed \
  --name ParaLate \
  --collect-all pymupdf \
  --add-data "localization:localization" \
  main.py
```

Çıktı: `dist/ParaLate/ParaLate`. Not: `--add-data` ayraçları platforma özgüdür — Windows'ta `;`, Linux'ta `:` kullanır.

---

## Proje Yapısı

```
Paralate-free/
├── main.py                     # Giriş noktası
├── requirements.txt            # Runtime bağımlılıkları
├── requirements-dev.txt        # + pytest, pyinstaller
├── pytest.ini
├── .env.example                # API key şablonu
│
├── app/                        # Bootstrap & genel ayarlar
│   ├── application.py          # Başlangıç sırası, servisler, logging, first-run
│   ├── config.py               # config.json (ui_language, first_run_completed, …)
│   ├── constants.py            # Tüm sabitler (limitler, dil listesi, viewer ayarları)
│   ├── network.py              # NetworkStatus (çevrimiçi/çevrimdışı algılama)
│   └── services.py             # AppServices dataclass (tek bağımlılık taşıyıcı)
│
├── pdf/                        # PDF çekirdeği
│   ├── extractor.py            # Metin bloğu/paragraf çıkarma, kod bloğu algılama
│   ├── renderer.py             # Türkçe destekli TTF font, wrap, satır çizimi
│   ├── translator_renderer.py  # Redaction tabanlı çeviri sayfası (görsel/vektör korumalı)
│   ├── interleaver.py          # Orig1,Trans1,Orig2,Trans2 … birleştirme
│   ├── loader.py               # Bellekten PDF açma/yükleme
│   └── metadata.py             # font subset + sıkıştırma (boyut optimizasyonu)
│
├── translation/                # Çeviri katmanı
│   ├── base.py                 # TranslationProvider arayüzü, TranslationCancelled
│   ├── manager.py              # Zincir, retry/backoff, chunking, build_default_providers()
│   ├── google.py               # Google (anahtar opsiyonel)
│   ├── mymemory.py             # MyMemory (anahtarsız çalışan fallback)
│   ├── microsoft.py            # Azure Translator (anahtar+bölge)
│   ├── libretranslate.py       # LibreTranslate (URL+anahtar)
│   └── cache.py                # Çeviri önbelleği (SQLite)
│
├── storage/                    # Kalıcı depolama
│   ├── paths.py                # AppData/XDG yolları, PARA_LATE_DATA_DIR
│   ├── database.py             # SQLite şema (documents, daily_usage, cache, state)
│   ├── models.py               # Belge/kota/lisans veri sınıfları
│   ├── repository.py           # CRUD, cleanup_incomplete, find_by_cache_key
│   └── encrypted_document.py   # .plt okuma/yazma (AES, magic+header)
│
├── security/                   # Kripto & sırlar
│   ├── encryption.py           # DocumentCipher (master key, keyring+dosya)
│   ├── hashing.py              # Belge parmak izi (önbellek anahtarı)
│   └── secrets.py              # .env/keyring okuma, maskeleme
│
├── licensing/                  # FREE/PREMIUM
│   ├── base.py                 # LicenseProvider arayüzü, LicenseError
│   ├── license_manager.py      # İmzalı çevrimdışı lisans, süre ve saat kontrolü
│   ├── offline_provider.py     # CRC32 alanları + Ed25519 doğrulaması
│   ├── issue_license.py        # Harici özel anahtarla lisans üretim aracı
│   └── limits.py               # QuotaService (3 çeviri/gün, 30 sayfa/dosya)
│
├── ads/                        # Reklam soyutlaması (arayüz + yönetici)
│
├── workers/                    # QThread işçileri
│   ├── translation_worker.py   # hash→cache→quota→extract→translate→render→interleave→encrypt→store
│   └── pdf_worker.py           # Belge listesi/yükleme işleri
│
├── ui/                         # PyQt6 arayüzü (koyu tema)
│   ├── style.py                 # APP_QSS (tam koyu stil)
│   ├── language_dialog.py       # FirstRunDialog (ilk açılış dil seçimi)
│   ├── home_window.py           # Ana pencere: PDF seç, çevir, durum
│   ├── history_widget.py        # Geçmiş listesi (aç/sil)
│   ├── translation_window.py    # İşlem ilerleme penceresi
│   ├── pdf_viewer.py            # ViewerWindow + SpreadCanvas (iki sayfa) + Ctrl+F + zoom
│   ├── ad_banner.py             # Reklam alanı (FREE)
│   └── dialogs/premium_dialog.py# Premium tanıtım + lisans aktivasyonu + Download kapısı
│
├── localization/
│   ├── tr.json / en.json        # Tüm UI metinleri + hata kodları
│
└── tests/
    ├── conftest.py              # make_pdf(), app_paths/db/quota/services fixture'ları
    ├── test_hashing.py
    ├── test_storage.py          # CRUD, cleanup, cache
    ├── test_limits.py           # QuotaService: reset/refund, saat geri alma
    ├── test_interleave.py       # Orig/Trans sırası, link yaşatma
    ├── test_pdf.py              # Extractor, renderer (Türkçe glyph), redaction
    ├── test_translation.py      # Zincir, fallback, cache, chunking
    ├── test_licenses.py         # CRC32, imza, tarih ve saat kontrolü
    └── test_gui_smoke.py        # Offscreen GUI, seçim, tanıtım
```

---

## Mimari Notlar

- **İşlem hattı** (`workers/translation_worker.py`): belge hash → önbellek kontrolü → kota düşümü → metin çıkarma → blok bazlı çeviri (kod blokları atlanır) → çeviri sayfası üretimi → interleave → `.plt` şifreleyip depolama. Hata olursa kota **geri iade edilir**, yarım belge temizlenir.
- **Çeviri sayfası stratejisi**: PyMuPDF redaction (`apply_redactions` görseller/vektör sanatı **silmeden**) ile orijinal metin kaldırılır, kalan tuval üzerine çeviri Türkçe fontla yazılır; render hatasında **bozulmamış kopyaya** düşülür.
- **Font**: Base-14 `helv` Türkçe glyph'leri bozar → sistem TTF zorunlu (Windows: Segoe UI, Linux: DejaVu/Liberation). `insert_textbox` taşmada hiçbir şey yazmaz → manuel word-wrap + kademeli boyut küçültme.
- **Kota sıfırlama**: Yalnızca kayıtlı gün **bugünden kesin önceyse** sıfırlanır (saat geri alma kota geri getirmez). Silme iade yapmaz.
- **Çökme direnci**: Viewer kapatılırken `begin_shutdown()` → pixmap/link/arama temizlenir → `doc.close()`; `sizeHint` önbellekli sayfa sayısını kullanır (kapalı döküman hatası yok).
- **Qt6 tuzakları** (çözülmüş): `QStandardKey` yok → `QKeySequence.StandardKey.*`; `QTimer.singleShot` yalnız `(msec, slot)`.

---

## Bilinen Sınırlamalar

- Genel Google uçucu IP bazlı **429** verebilir → MyMemory'ye düşer (kelime tekil karşılıklarda kalite düşebilir). Anahtarlı sağlayıcı kullanın.
- Ödeme akışı yerine Telegram iletişimi kullanılır. Belge paylaşma özelliği uygulamada bulunmadığı için tanıtımda vaat edilmez.
- PDF seçimi gerçek metin katmanı olan sayfalarda çalışır; taranmış/görüntü tabanlı PDF'lere OCR uygulanmaz.
- Reklam alanı soyutlama katmanıdır; gerçek reklam ağı bağlanmadı.
- Çevrimdışı lisansın saat geri alma tespiti uygulama verisindeki son görülen tarihi kullanır; yerel veritabanı/sistem saati üzerinde tam kontrolü olan saldırgana karşı kesin koruma sağlamaz.

---

## Sorun Giderme

- Log: `<veri dizini>/logs/paralate.log`
- GUI açılmıyorsa (Linux ssh/headless): `QT_QPA_PLATFORM=offscreen` (bu modda pencereler görünmez, testler içindir)
- Çeviri hiç çalışmıyorsa: `.env` anahtarlarını kontrol edin, `logs/paralate.log` içinde `fallback`/`provider` kayıtlarına bakın.
