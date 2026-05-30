"""
Локализация всех изображений магазина:

1. Генерирует фирменную заглушку static/img/placeholder.png ("нет изображения").
2. Оптимизирует слайды 1.jpg / 2.jpg / 3.jpg из корня проекта в static/img/slider/.
3. Скачивает изображения всех товаров (внешние URL из БД) в
   static/uploads/products/ и переписывает products.image_url на локальное имя файла.

Запуск:  python scripts/localize_images.py
Скрипт идемпотентен: повторный запуск пропускает уже локализованные товары.
"""
import io
import os
import sqlite3

import requests
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(BASE, "static")
PRODUCTS_DIR = os.path.join(STATIC, "uploads", "products")
SLIDER_DIR = os.path.join(STATIC, "img", "slider")
IMG_DIR = os.path.join(STATIC, "img")
DB_PATH = os.path.join(BASE, "instance", "planeta_shop.db")
FONT_DIR = os.path.join(STATIC, "fonts")
HEADERS = {"User-Agent": "Mozilla/5.0 (image-fetcher)"}

MAX_PRODUCT_SIDE = 1000   # макс. сторона изображения товара, px
MAX_SLIDER_WIDTH = 1920   # макс. ширина слайда, px


def ensure_dirs():
    for d in (PRODUCTS_DIR, SLIDER_DIR, IMG_DIR):
        os.makedirs(d, exist_ok=True)


def load_font(name, size):
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except Exception:
        return ImageFont.load_default()


# --------------------------------------------------------------------------
# 1. Фирменная заглушка
# --------------------------------------------------------------------------
def make_placeholder():
    w, h = 600, 750
    img = Image.new("RGB", (w, h))
    top = (102, 126, 234)      # #667eea
    bottom = (118, 75, 162)    # #764ba2
    px = img.load()
    for y in range(h):
        t = y / (h - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)

    draw = ImageDraw.Draw(img)
    icon_font = load_font("Inter-Bold.ttf", 150)
    title_font = load_font("Inter-SemiBold.ttf", 40)
    sub_font = load_font("Inter-Regular.ttf", 26)

    def centered(text, font, y, fill=(255, 255, 255)):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) / 2, y), text, font=font, fill=fill)

    centered("П", icon_font, 250)  # буква П в круге-логотипе
    centered("Планета", title_font, 440)
    centered("Нет изображения", sub_font, 510, fill=(235, 235, 245))

    out = os.path.join(IMG_DIR, "placeholder.png")
    img.save(out, "PNG")
    print(f"  placeholder.png создан ({os.path.getsize(out)} bytes)")


# --------------------------------------------------------------------------
# 2. Слайды
# --------------------------------------------------------------------------
def process_slider():
    for n in (1, 2, 3):
        src = os.path.join(BASE, f"{n}.jpg")
        dst = os.path.join(SLIDER_DIR, f"slide{n}.jpg")
        if not os.path.exists(src):
            if os.path.exists(dst):
                print(f"  slide{n}.jpg уже на месте")
            else:
                print(f"  ВНИМАНИЕ: {n}.jpg не найден в корне проекта")
            continue
        img = Image.open(src).convert("RGB")
        if img.width > MAX_SLIDER_WIDTH:
            ratio = MAX_SLIDER_WIDTH / img.width
            img = img.resize((MAX_SLIDER_WIDTH, int(img.height * ratio)), Image.LANCZOS)
        img.save(dst, "JPEG", quality=85, optimize=True)
        print(f"  slide{n}.jpg: {os.path.getsize(src)} -> {os.path.getsize(dst)} bytes")


# --------------------------------------------------------------------------
# 3. Изображения товаров
# --------------------------------------------------------------------------
def normalize_and_save(content, article):
    img = Image.open(io.BytesIO(content))
    img.load()
    has_alpha = img.mode in ("RGBA", "LA", "P")
    side = max(img.size)
    if side > MAX_PRODUCT_SIDE:
        ratio = MAX_PRODUCT_SIDE / side
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)

    if has_alpha:
        img = img.convert("RGBA")
        fname = f"{article}.png"
        img.save(os.path.join(PRODUCTS_DIR, fname), "PNG", optimize=True)
    else:
        img = img.convert("RGB")
        fname = f"{article}.jpg"
        img.save(os.path.join(PRODUCTS_DIR, fname), "JPEG", quality=85, optimize=True)
    return fname


def process_products():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = cur.execute("SELECT id, article, image_url FROM products ORDER BY id").fetchall()

    done = skipped = failed = 0
    failures = []
    for row in rows:
        pid, article, image_url = row["id"], row["article"], row["image_url"]

        # Уже локализовано (имя файла без схемы http) и файл существует — пропускаем.
        if image_url and not image_url.startswith(("http://", "https://")):
            if os.path.exists(os.path.join(PRODUCTS_DIR, image_url)):
                skipped += 1
                continue

        if not image_url:
            continue

        try:
            r = requests.get(image_url, headers=HEADERS, timeout=30)
            if r.status_code != 200 or len(r.content) < 200:
                raise ValueError(f"HTTP {r.status_code}, {len(r.content)} bytes")
            fname = normalize_and_save(r.content, article)
            cur.execute("UPDATE products SET image_url = ? WHERE id = ?", (fname, pid))
            conn.commit()
            done += 1
            print(f"  [{pid:>2}] {article:<12} -> {fname}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            failures.append((pid, article, str(e)[:60]))
            # Чтобы не показывать «битую» внешнюю ссылку — сбрасываем в NULL
            cur.execute("UPDATE products SET image_url = NULL WHERE id = ?", (pid,))
            conn.commit()
            print(f"  [{pid:>2}] {article:<12} -> FAIL ({str(e)[:50]})")

    conn.close()
    print(f"\nТовары: скачано {done}, пропущено {skipped}, ошибок {failed}")
    if failures:
        print("Не удалось скачать (показывается заглушка):")
        for pid, article, err in failures:
            print(f"   #{pid} {article}: {err}")


def main():
    ensure_dirs()
    print("1) Заглушка:")
    make_placeholder()
    print("2) Слайды:")
    process_slider()
    print("3) Изображения товаров:")
    process_products()
    print("\nГотово.")


if __name__ == "__main__":
    main()
