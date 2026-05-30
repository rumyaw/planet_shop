"""
Скачивание всех внешних ресурсов (CSS, JS, шрифты, иконки) в папку static/,
чтобы приложение работало полностью локально, без обращения к CDN.

Запуск:  python scripts/setup_assets.py
Скрипт идемпотентен — можно запускать повторно.
"""
import os
import sys

import requests

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(BASE, "static")
HEADERS = {"User-Agent": "Mozilla/5.0 (asset-fetcher)"}

# (url, относительный путь внутри static/).
# Для каждого ресурса можно указать список зеркал — берётся первое успешное.
ASSETS = [
    (
        ["https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css"],
        "vendor/bootstrap/bootstrap.min.css",
    ),
    (
        ["https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"],
        "vendor/bootstrap/bootstrap.bundle.min.js",
    ),
    (
        ["https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css"],
        "vendor/bootstrap-icons/bootstrap-icons.css",
    ),
    (
        ["https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/fonts/bootstrap-icons.woff2"],
        "vendor/bootstrap-icons/fonts/bootstrap-icons.woff2",
    ),
    (
        ["https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/fonts/bootstrap-icons.woff"],
        "vendor/bootstrap-icons/fonts/bootstrap-icons.woff",
    ),
    (
        [
            "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js",
            "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js",
            "https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.js",
        ],
        "vendor/chartjs/chart.umd.min.js",
    ),
    # Шрифт Inter (статические TTF) — используется и на сайте, и для генерации PDF.
    (
        ["https://cdn.jsdelivr.net/npm/@expo-google-fonts/inter@0.2.3/Inter_400Regular.ttf"],
        "fonts/Inter-Regular.ttf",
    ),
    (
        ["https://cdn.jsdelivr.net/npm/@expo-google-fonts/inter@0.2.3/Inter_500Medium.ttf"],
        "fonts/Inter-Medium.ttf",
    ),
    (
        ["https://cdn.jsdelivr.net/npm/@expo-google-fonts/inter@0.2.3/Inter_600SemiBold.ttf"],
        "fonts/Inter-SemiBold.ttf",
    ),
    (
        ["https://cdn.jsdelivr.net/npm/@expo-google-fonts/inter@0.2.3/Inter_700Bold.ttf"],
        "fonts/Inter-Bold.ttf",
    ),
]


def fetch(urls, dest_rel):
    dest = os.path.join(STATIC, dest_rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    last_err = None
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=40)
            if r.status_code == 200 and len(r.content) > 200:
                with open(dest, "wb") as f:
                    f.write(r.content)
                print(f"  OK   {dest_rel:<48} {len(r.content):>9} bytes")
                return True
            last_err = f"HTTP {r.status_code}, {len(r.content)} bytes"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
    print(f"  FAIL {dest_rel:<48} {last_err}")
    return False


def main():
    print(f"Скачивание ресурсов в {STATIC}")
    ok = 0
    for urls, dest_rel in ASSETS:
        if fetch(urls, dest_rel):
            ok += 1
    print(f"\nГотово: {ok}/{len(ASSETS)} ресурсов скачано.")
    if ok != len(ASSETS):
        sys.exit(1)


if __name__ == "__main__":
    main()
