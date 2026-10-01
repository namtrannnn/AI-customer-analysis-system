"""
Chart Service — Tạo biểu đồ matplotlib nhúng vào PDF
Style: Clean, Executive Modern, Font Arial, High DPI (200), Card Containers
"""
import io
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
from matplotlib.ticker import MaxNLocator
import numpy as np

from app.schemas.report_schema import ReportDataDTO

# ─── Palette ──────────────────────────────────────────────────────────────────
COLOR_PRIMARY   = "#3b82f6"  # Blue 500
COLOR_SUCCESS   = "#10b981"  # Emerald 500
COLOR_PURPLE    = "#8b5cf6"  # Violet 500
COLOR_AMBER     = "#f59e0b"  # Amber 500
COLOR_ROSE      = "#f43f5e"  # Rose 500
COLOR_CYAN      = "#06b6d4"  # Cyan 500
COLOR_INDIGO    = "#6366f1"  # Indigo 500

PALETTE = [COLOR_PRIMARY, COLOR_SUCCESS, COLOR_PURPLE, COLOR_AMBER, COLOR_ROSE, COLOR_CYAN, COLOR_INDIGO]
BG      = "#ffffff"
CARD_BG = "#f8fafc"
GRID    = "#e2e8f0"
TEXT    = "#0f172a"
MUTED   = "#64748b"

# Load Arial font if available
_FONT_NAME = "sans-serif"
_curr_dir = os.path.dirname(os.path.abspath(__file__))
_font_path = os.path.normpath(os.path.join(_curr_dir, "..", "utils", "fonts", "arial.ttf"))
if os.path.exists(_font_path):
    try:
        fm.fontManager.addfont(_font_path)
        _prop = fm.FontProperties(fname=_font_path)
        _FONT_NAME = _prop.get_name()
    except Exception:
        pass


def _setup():
    plt.rcParams.update({
        "font.family":       _FONT_NAME,
        "figure.facecolor":  BG,
        "axes.facecolor":    BG,
        "text.color":        TEXT,
        "axes.labelcolor":   MUTED,
        "xtick.color":       MUTED,
        "ytick.color":       MUTED,
        "axes.grid":         True,
        "grid.color":        GRID,
        "grid.linewidth":    0.6,
        "grid.linestyle":    "--",
        "axes.spines.top":   False,
        "axes.spines.right": False,
        "axes.spines.left":  False,
        "axes.spines.bottom": True,
        "axes.edgecolor":    GRID,
        "font.size": 8.5,
        "axes.titlesize": 10.5,
        "axes.titleweight": "bold",
        "axes.titlecolor": TEXT,
    })


def _save(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight",
                facecolor=BG, edgecolor="none", pad_inches=0.1)
    buf.seek(0)
    data = buf.read()
    plt.close(fig)
    return data


# ─── Donut helper ─────────────────────────────────────────────────────────────
def _donut(ax, sizes, colors, center_text: str, center_sub: str = ""):
    """Vẽ donut chart với lỗ lớn ở giữa và viền trắng sang trọng."""
    ax.pie(
        sizes,
        colors=colors,
        startangle=90,
        wedgeprops={"width": 0.44, "edgecolor": "white", "linewidth": 2.5},
        radius=1.0,
        counterclock=False,
    )
    # Inner center text
    ax.text(0, 0.06, center_text, ha="center", va="center",
            fontsize=15, fontweight="bold", color=TEXT)
    if center_sub:
        ax.text(0, -0.20, center_sub, ha="center", va="center",
                fontsize=8, color=MUTED, fontweight="medium")
    ax.set_aspect("equal")


def _legend_rows(ax_legend, items, colors):
    """Vẽ legend dạng danh sách đẹp mắt: Dot ● Tên nhóm | Giá trị | Tỷ lệ %."""
    ax_legend.axis("off")
    n = len(items)
    total = sum(v for _, v in items)
    row_h = 1.0 / max(n + 0.2, 1)
    for i, ((label, val), color) in enumerate(zip(items, colors)):
        y = 1.0 - (i + 0.65) * row_h
        pct = f"{val/total*100:.1f}%" if total else "0%"
        # Dot badge
        ax_legend.add_patch(mpatches.Circle((0.04, y), 0.026, color=color, transform=ax_legend.transAxes, clip_on=False))
        # Label
        ax_legend.text(0.11, y, label[:30], va="center", ha="left",
                       transform=ax_legend.transAxes, fontsize=8.5, color=TEXT, fontweight="medium")
        # Value formatted
        val_str = f"{val:,.0f}" if isinstance(val, (int, float)) else str(val)
        ax_legend.text(0.70, y, val_str, va="center", ha="right",
                       transform=ax_legend.transAxes, fontsize=8.5, color=MUTED)
        # Pct badge bold
        ax_legend.text(0.98, y, pct, va="center", ha="right",
                       transform=ax_legend.transAxes, fontsize=8.5,
                       fontweight="bold", color=color)


# ─── Chart 1: Donut — Khách mới vs Quay lại ──────────────────────────────────
def make_visitor_pie_chart(data: ReportDataDTO) -> bytes:
    s = data.summary
    new_v, ret_v = s.new_visitors, s.returning_visitors
    if new_v + ret_v == 0:
        return b""
    _setup()

    fig = plt.figure(figsize=(6.4, 2.7), facecolor=BG)
    ax_donut = fig.add_axes([0.02, 0.02, 0.40, 0.90])
    ax_leg   = fig.add_axes([0.46, 0.02, 0.52, 0.90])

    colors = [COLOR_SUCCESS, COLOR_PURPLE]
    _donut(ax_donut, [new_v, ret_v], colors, f"{new_v + ret_v:,}", "tổng lượt")

    items = [("Khách mới", new_v), ("Khách quay lại", ret_v)]
    _legend_rows(ax_leg, items, colors)

    fig.suptitle("Phân loại lượt khách", fontsize=10.5, fontweight="bold",
                 color=TEXT, x=0.5, y=1.02)
    return _save(fig)


# ─── Chart 2: Donut — Phân nhóm AI ───────────────────────────────────────────
def make_segment_pie_chart(data: ReportDataDTO) -> bytes:
    segs = [s for s in data.segments if s.member_count > 0]
    if not segs:
        return b""
    _setup()

    colors = PALETTE[:len(segs)]
    sizes  = [s.member_count for s in segs]
    total  = sum(sizes)
    names  = []
    for s in segs:
        name = s.segment_name.split("(")[0].strip()
        if len(name) > 26: name = name[:24] + "…"
        names.append(name)

    fig = plt.figure(figsize=(6.8, max(2.8, len(segs) * 0.48 + 0.8)), facecolor=BG)
    ax_donut = fig.add_axes([0.02, 0.02, 0.42, 0.90])
    ax_leg   = fig.add_axes([0.46, 0.02, 0.52, 0.90])

    _donut(ax_donut, sizes, colors, f"{total:,}", "khách hàng")

    items = list(zip(names, sizes))
    _legend_rows(ax_leg, items, colors)

    fig.suptitle("Tỷ lệ phân bố nhóm khách hàng AI", fontsize=10.5, fontweight="bold",
                 color=TEXT, x=0.5, y=1.02)
    return _save(fig)


# ─── Chart 3: Area line — Xu hướng lượt khách ────────────────────────────────
def make_visitor_trend_chart(data: ReportDataDTO) -> bytes:
    daily = data.daily_stats
    if not daily:
        return b""
    _setup()

    labels     = [d.statistic_date.strftime("%d/%m") for d in daily]
    totals     = [d.total_visitors     for d in daily]
    news       = [d.new_visitors       for d in daily]
    returnings = [d.returning_visitors for d in daily]
    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(7.2, 2.7), facecolor=BG)
    ax.set_facecolor(BG)

    # Area fills
    ax.fill_between(x, totals, alpha=0.10, color=COLOR_PRIMARY)
    ax.fill_between(x, news,       alpha=0.08, color=COLOR_SUCCESS)
    ax.fill_between(x, returnings, alpha=0.08, color=COLOR_PURPLE)

    # Lines
    ax.plot(x, totals,     color=COLOR_PRIMARY, linewidth=2.2, marker="o",
            markersize=4.0, label="Tổng lượt khách", zorder=4, markerfacecolor="white", markeredgewidth=1.8)
    ax.plot(x, news,       color=COLOR_SUCCESS, linewidth=1.6, marker="s",
            markersize=3.2, label="Khách mới",  linestyle="--", zorder=3)
    ax.plot(x, returnings, color=COLOR_PURPLE, linewidth=1.6, marker="^",
            markersize=3.2, label="Quay lại",   linestyle="--", zorder=3)

    step = max(1, len(labels) // 10)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(labels[::step], rotation=0, ha="center", fontsize=8)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=5))
    ax.set_title("Xu hướng lượt khách theo ngày", pad=8)
    ax.legend(loc="upper right", fontsize=8, framealpha=0.95,
              edgecolor=GRID, fancybox=True)
    ax.spines["bottom"].set_color(GRID)
    fig.tight_layout()
    return _save(fig)


# ─── Chart 4: Bar chart — Doanh thu theo ngày ────────────────────────────────
def make_revenue_bar_chart(data: ReportDataDTO) -> bytes:
    daily = data.daily_stats
    if not daily or all(d.total_revenue == 0 for d in daily):
        return b""
    _setup()

    labels   = [d.statistic_date.strftime("%d/%m") for d in daily]
    max_rev  = max(d.total_revenue for d in daily)

    # Determine unit: Triệu VNĐ vs Nghìn VNĐ
    use_million = max_rev >= 1_000_000
    if use_million:
        revenues = [d.total_revenue / 1_000_000 for d in daily]
        unit_lbl = "Triệu VNĐ"
        fmt_val  = lambda v: f"{v:.1f}M" if v >= 1 else f"{v*1000:.0f}K"
    else:
        revenues = [d.total_revenue / 1_000 for d in daily]
        unit_lbl = "Nghìn VNĐ"
        fmt_val  = lambda v: f"{v:.0f}K"

    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(7.2, 2.7), facecolor=BG)
    ax.set_facecolor(BG)

    bars = ax.bar(x, revenues, color=COLOR_INDIGO, width=0.60,
                  alpha=0.85, zorder=3, edgecolor="white", linewidth=0.8)

    # Annotations on bars
    if len(daily) <= 18:
        for bar, val in zip(bars, revenues):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + max(revenues) * 0.02,
                        fmt_val(val), ha="center", va="bottom", fontsize=7.5, color=TEXT, fontweight="bold")

    step = max(1, len(labels) // 10)
    ax.set_xticks(x[::step])
    ax.set_xticklabels(labels[::step], rotation=0, ha="center", fontsize=8)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
    ax.set_title(f"Doanh thu theo ngày ({unit_lbl})", pad=8)
    ax.set_ylabel(unit_lbl, fontsize=8)
    ax.spines["bottom"].set_color(GRID)
    ax.set_ylim(0, max(revenues) * 1.18 if revenues else 1)
    fig.tight_layout()
    return _save(fig)


# ─── Chart 5: Horizontal bar — Lượt ghé theo zone ────────────────────────────
def make_zone_bar_chart(data: ReportDataDTO) -> bytes:
    zones = data.zones
    if not zones:
        return b""
    _setup()

    names  = [z.zone_name[:22] for z in zones]
    visits = [z.total_visits   for z in zones]
    zcolors = [z.color if z.color else PALETTE[i % len(PALETTE)]
               for i, z in enumerate(zones)]

    fig, ax = plt.subplots(figsize=(7.0, max(2.4, len(zones) * 0.48 + 0.8)), facecolor=BG)
    ax.set_facecolor(BG)

    y = np.arange(len(names))
    bars = ax.barh(y, visits, color=zcolors, height=0.50,
                   alpha=0.88, edgecolor="white", linewidth=0.8, zorder=3)

    max_v = max(visits) if visits else 1
    for bar, val, color in zip(bars, visits, zcolors):
        ax.text(val + max_v * 0.02, bar.get_y() + bar.get_height() / 2,
                f"{val:,} lượt", va="center", fontsize=8.5, color=color, fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8.5, fontweight="medium")
    ax.invert_yaxis()
    ax.set_title("Lượt ghé theo vùng theo dõi", pad=8)
    ax.set_xlabel("Lượt ghé", fontsize=8)
    ax.spines["bottom"].set_color(GRID)
    ax.spines["left"].set_visible(False)
    ax.tick_params(left=False)
    ax.set_xlim(0, max_v * 1.20)
    fig.tight_layout()
    return _save(fig)


# ─── Chart 6: Donut — Phân phối thời gian lưu trú ────────────────────────────
def make_duration_histogram(data: ReportDataDTO) -> bytes:
    buckets = [b for b in data.duration_buckets if b.count > 0]
    if not buckets:
        return b""
    _setup()

    colors = [COLOR_SUCCESS, COLOR_CYAN, COLOR_AMBER, COLOR_ROSE, COLOR_PURPLE][:len(buckets)]
    sizes  = [b.count for b in buckets]
    total  = sum(sizes)

    fig = plt.figure(figsize=(6.4, max(2.8, len(buckets) * 0.48 + 0.8)), facecolor=BG)
    ax_donut = fig.add_axes([0.02, 0.02, 0.40, 0.90])
    ax_leg   = fig.add_axes([0.46, 0.02, 0.52, 0.90])

    _donut(ax_donut, sizes, colors, f"{total:,}", "lượt khách")

    items = [(b.label, b.count) for b in buckets]
    _legend_rows(ax_leg, items, colors)

    fig.suptitle("Phân phối thời gian lưu trú tại cửa hàng", fontsize=10.5, fontweight="bold",
                 color=TEXT, x=0.5, y=1.02)
    return _save(fig)
