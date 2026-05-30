import io
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Paragraph,
    PageTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---- Палитра бренда -------------------------------------------------------
BRAND1 = colors.HexColor("#667eea")
BRAND2 = colors.HexColor("#764ba2")
INK = colors.HexColor("#1d1d1f")
MUTED = colors.HexColor("#86868b")
LIGHT = colors.HexColor("#f5f5f7")
LINE = colors.HexColor("#e6e6ea")

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "fonts")

# Имена зарегистрированных шрифтов
F_REG, F_MED, F_SEMI, F_BOLD = "Inter", "Inter-Med", "Inter-Semi", "Inter-Bold"
_fonts_ready = False


def register_fonts():
    """Регистрирует Inter в reportlab (однократно)."""
    global _fonts_ready
    if _fonts_ready:
        return
    pairs = [
        (F_REG, "Inter-Regular.ttf"),
        (F_MED, "Inter-Medium.ttf"),
        (F_SEMI, "Inter-SemiBold.ttf"),
        (F_BOLD, "Inter-Bold.ttf"),
    ]
    for name, filename in pairs:
        path = os.path.join(FONT_DIR, filename)
        pdfmetrics.registerFont(TTFont(name, path))
    pdfmetrics.registerFontFamily(F_REG, normal=F_REG, bold=F_BOLD, italic=F_REG, boldItalic=F_BOLD)
    _fonts_ready = True


def money(value):
    """Формат суммы: 1 290.00 ₽"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    return f"{v:,.2f} ₽".replace(",", " ")


# ---- Документ с фирменными колонтитулами ----------------------------------
class _BrandDoc(BaseDocTemplate):
    """A4-документ с цветной шапкой (градиент) и подвалом на каждой странице."""

    HEADER_H = 28 * mm

    def __init__(self, buffer, title, subtitle, **kw):
        self.brand_title = title
        self.brand_subtitle = subtitle
        super().__init__(
            buffer,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=self.HEADER_H + 12 * mm,
            bottomMargin=20 * mm,
            title=title,
        )
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="body",
        )
        self.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=self._decorate)])

    def _decorate(self, canvas, doc):
        w, h = A4
        # --- Градиентная шапка ---
        band_h = self.HEADER_H
        y0 = h - band_h
        strips = 160
        for i in range(strips):
            t = i / (strips - 1)
            r = BRAND1.red + (BRAND2.red - BRAND1.red) * t
            g = BRAND1.green + (BRAND2.green - BRAND1.green) * t
            b = BRAND1.blue + (BRAND2.blue - BRAND1.blue) * t
            canvas.setFillColorRGB(r, g, b)
            canvas.rect(w * t, y0, w / strips + 1, band_h, stroke=0, fill=1)

        # Логотип-кружок с буквой «П»
        cx, cy = 18 * mm + 9 * mm, y0 + band_h / 2
        canvas.setFillColor(colors.white)
        canvas.circle(cx, cy, 9 * mm, stroke=0, fill=1)
        canvas.setFillColor(BRAND2)
        canvas.setFont(F_BOLD, 20)
        canvas.drawCentredString(cx, cy - 7, "П")

        # Заголовок и подзаголовок
        tx = cx + 14 * mm
        canvas.setFillColor(colors.white)
        canvas.setFont(F_BOLD, 16)
        canvas.drawString(tx, cy + 2, self.brand_title)
        canvas.setFont(F_REG, 10)
        canvas.drawString(tx, cy - 12, self.brand_subtitle)

        # Маркер справа
        canvas.setFont(F_SEMI, 10)
        canvas.drawRightString(w - 18 * mm, cy - 4, "Книжная сеть «Планета»")

        # --- Подвал ---
        canvas.setFillColor(MUTED)
        canvas.setFont(F_REG, 8)
        canvas.drawString(18 * mm, 12 * mm, "planeta-shop.ru  •  Документ сформирован автоматически")
        canvas.drawRightString(w - 18 * mm, 12 * mm, f"Стр. {doc.page}")
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.6)
        canvas.line(18 * mm, 15 * mm, w - 18 * mm, 15 * mm)


# ---- Параграф-стили -------------------------------------------------------
def _styles():
    return {
        "h2": ParagraphStyle("h2", fontName=F_BOLD, fontSize=13, textColor=INK, spaceBefore=6, spaceAfter=6, leading=16),
        "label": ParagraphStyle("label", fontName=F_MED, fontSize=8.5, textColor=MUTED, leading=11),
        "th": ParagraphStyle("th", fontName=F_SEMI, fontSize=8.5, textColor=colors.white, leading=11),
        "value": ParagraphStyle("value", fontName=F_SEMI, fontSize=10.5, textColor=INK, leading=14),
        "cell": ParagraphStyle("cell", fontName=F_REG, fontSize=9.5, textColor=INK, leading=12),
        "cell_sub": ParagraphStyle("cell_sub", fontName=F_REG, fontSize=8, textColor=MUTED, leading=10),
        "cell_b": ParagraphStyle("cell_b", fontName=F_SEMI, fontSize=9.5, textColor=INK, leading=12),
        "small": ParagraphStyle("small", fontName=F_REG, fontSize=9, textColor=MUTED, leading=13),
    }


def _info_card(rows, st, col_widths):
    """Таблица «метка/значение» в виде аккуратной карточки."""
    data = []
    for label, value in rows:
        data.append([Paragraph(label, st["label"]), Paragraph(str(value), st["value"])])
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


# ==========================================================================
# ЧЕК ЗАКАЗА
# ==========================================================================
def build_receipt_pdf(order, status_name):
    register_fonts()
    st = _styles()
    buf = io.BytesIO()
    doc = _BrandDoc(buf, title=f"Чек заказа №{order.id}", subtitle="Чек оплаты")
    story = []

    full_w = doc.width
    # Блок «Заказ» и «Покупатель» рядом
    order_card = _info_card([
        ("НОМЕР ЗАКАЗА", f"№ {order.id}"),
        ("ДАТА ОФОРМЛЕНИЯ", order.created_at.strftime("%d.%m.%Y %H:%M")),
        ("СТАТУС", status_name),
    ], st, [38 * mm, full_w / 2 - 38 * mm])

    buyer_rows = [
        ("ПОКУПАТЕЛЬ", order.user.fio),
        ("EMAIL", order.user.email),
    ]
    if order.user.phone:
        buyer_rows.append(("ТЕЛЕФОН", order.user.phone))
    buyer_card = _info_card(buyer_rows, st, [28 * mm, full_w / 2 - 28 * mm])

    head = Table([[order_card, buyer_card]], colWidths=[full_w / 2 - 4, full_w / 2 - 4])
    head.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
    ]))
    story.append(head)
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph("Состав заказа", st["h2"]))
    story.append(Spacer(1, 2 * mm))

    # Таблица товаров
    header = [
        Paragraph("№", st["th"]),
        Paragraph("НАИМЕНОВАНИЕ", st["th"]),
        Paragraph("КОЛ-ВО", st["th"]),
        Paragraph("ЦЕНА", st["th"]),
        Paragraph("СУММА", st["th"]),
    ]
    data = [header]
    for i, item in enumerate(order.items, 1):
        name_cell = [
            Paragraph(item.product.name, st["cell_b"]),
            Paragraph(f"Артикул: {item.product.article}", st["cell_sub"]),
        ]
        data.append([
            Paragraph(str(i), st["cell"]),
            name_cell,
            Paragraph(f"{item.quantity} шт.", st["cell"]),
            Paragraph(money(item.price_per_unit), st["cell"]),
            Paragraph(money(item.get_subtotal()), st["cell_b"]),
        ])

    col_w = [10 * mm, full_w - 10 * mm - 22 * mm - 28 * mm - 30 * mm, 22 * mm, 28 * mm, 30 * mm]
    items = Table(data, colWidths=col_w, repeatRows=1)
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND1),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), F_SEMI),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (4, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(items)
    story.append(Spacer(1, 6 * mm))

    # Итог
    total_tbl = Table(
        [[Paragraph("ИТОГО К ОПЛАТЕ", ParagraphStyle("t", fontName=F_SEMI, fontSize=12, textColor=colors.white)),
          Paragraph(money(order.total_amount), ParagraphStyle("tv", fontName=F_BOLD, fontSize=15, textColor=colors.white, alignment=2))]],
        colWidths=[full_w - 55 * mm, 55 * mm],
    )
    total_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
    ]))
    story.append(total_tbl)
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph("Спасибо за покупку в книжной сети «Планета»!", st["h2"]))
    story.append(Paragraph(
        "Чек является подтверждением оформления заказа. По вопросам обращайтесь в службу поддержки.",
        st["small"]))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


# ==========================================================================
# ОТЧЁТ ПО СТАТИСТИКЕ
# ==========================================================================
def build_statistics_report_pdf(data):
    """
    data: dict с ключами:
      total_users, total_products, total_orders, total_revenue,
      orders_last_30_days, revenue_last_30_days,
      status_rows:  list[(status_name, count)],
      top_products: list[(name, sold, revenue)]
    """
    register_fonts()
    st = _styles()
    buf = io.BytesIO()
    doc = _BrandDoc(buf, title="Отчёт по статистике", subtitle="Аналитический отчёт магазина")
    story = []
    full_w = doc.width

    story.append(Paragraph(
        f"Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}", st["small"]))
    story.append(Spacer(1, 5 * mm))

    # --- KPI-плитки ---
    kpis = [
        (str(data["total_users"]), "Пользователей", BRAND1),
        (str(data["total_products"]), "Товаров", BRAND2),
        (str(data["total_orders"]), "Заказов", BRAND1),
        (money(data["total_revenue"]), "Выручка", BRAND2),
    ]
    cells = []
    for value, label, bg in kpis:
        inner = Table(
            [[Paragraph(str(value), ParagraphStyle("kv", fontName=F_BOLD, fontSize=13, textColor=colors.white, leading=16))],
             [Paragraph(label, ParagraphStyle("kl", fontName=F_MED, fontSize=8.5, textColor=colors.white, leading=11))]],
        )
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (0, 0), 12),
            ("BOTTOMPADDING", (-1, -1), (-1, -1), 12),
            ("TOPPADDING", (-1, -1), (-1, -1), 0),
        ]))
        cells.append(inner)
    kpi_row = Table([cells], colWidths=[full_w / 4] * 4)
    kpi_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(kpi_row)
    story.append(Spacer(1, 7 * mm))

    # --- Последние 30 дней ---
    story.append(Paragraph("За последние 30 дней", st["h2"]))
    story.append(_info_card([
        ("ЗАКАЗОВ", data["orders_last_30_days"]),
        ("ВЫРУЧКА", money(data["revenue_last_30_days"])),
    ], st, [45 * mm, full_w - 45 * mm]))
    story.append(Spacer(1, 7 * mm))

    # --- Статусы заказов ---
    story.append(Paragraph("Заказы по статусам", st["h2"]))
    sdata = [[Paragraph("СТАТУС", st["th"]), Paragraph("КОЛИЧЕСТВО", st["th"])]]
    for name, count in data["status_rows"]:
        sdata.append([Paragraph(name, st["cell"]), Paragraph(str(count), st["cell_b"])])
    stbl = Table(sdata, colWidths=[full_w - 40 * mm, 40 * mm], repeatRows=1)
    stbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND1),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), F_SEMI),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(stbl)
    story.append(Spacer(1, 7 * mm))

    # --- Топ товаров ---
    story.append(Paragraph("Топ-10 товаров по продажам", st["h2"]))
    tdata = [[
        Paragraph("№", st["th"]),
        Paragraph("ТОВАР", st["th"]),
        Paragraph("ПРОДАНО", st["th"]),
        Paragraph("ВЫРУЧКА", st["th"]),
    ]]
    for i, (name, sold, revenue) in enumerate(data["top_products"], 1):
        tdata.append([
            Paragraph(str(i), st["cell"]),
            Paragraph(name, st["cell_b"]),
            Paragraph(f"{sold} шт.", st["cell"]),
            Paragraph(money(revenue), st["cell_b"]),
        ])
    ttbl = Table(tdata, colWidths=[10 * mm, full_w - 10 * mm - 30 * mm - 35 * mm, 30 * mm, 35 * mm], repeatRows=1)
    ttbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND2),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), F_SEMI),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("ALIGN", (2, 0), (3, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(ttbl)

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()
