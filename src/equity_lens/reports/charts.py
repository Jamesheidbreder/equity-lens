"""Report charts: institutional-style PNGs embedded in the markdown reports.

Same design language as the dashboard: validated blue/aqua palette,
horizontal gridlines only, no chart junk. Files land in reports/assets/
and render on GitHub and in any markdown viewer.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).parents[3]
ASSETS_DIR = REPO_ROOT / "reports" / "assets"

C_BLUE, C_AQUA = "#2a78d6", "#1baf7a"
INK, INK_MUTED, GRID = "#1d1d1f", "#6e6e73", "#e9e9e6"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "font.size": 9,
    "text.color": INK,
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK_MUTED,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.titlecolor": INK,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
})


def _style(ax, ygrid=True):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    if ygrid:
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
    t = ax.get_title()          # center-slot title
    if t:
        ax.set_title("")            # clear center slot
        ax.set_title(t, loc="left", pad=10)


def _label_bars(ax, values, fmt="{:,.0f}"):
    """Direct value labels on bars; the y-axis then gets out of the way."""
    for rect, v in zip(ax.patches, values):
        neg = v < 0
        ax.annotate(fmt.format(v),
                    (rect.get_x() + rect.get_width() / 2, rect.get_height()),
                    ha="center", va="top" if neg else "bottom", fontsize=8,
                    color=INK_MUTED,
                    xytext=(0, -2 if neg else 2), textcoords="offset points")
    ax.set_yticks([])
    ax.grid(False)


def _save(fig, name: str) -> str:
    ASSETS_DIR.mkdir(exist_ok=True)
    path = ASSETS_DIR / name
    fig.savefig(path)
    plt.close(fig)
    return f"assets/{name}"   # relative to reports/, where the .md files live


def price_chart(ticker: str, hist: pd.Series, target: float,
                street: float) -> str:
    """5y price with our target and street consensus marked."""
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.plot(hist.index, hist.values, color=C_BLUE, linewidth=1.6)
    ax.fill_between(hist.index, hist.values, hist.values.min(),
                    color=C_BLUE, alpha=0.06)
    ax.plot([hist.index[-1]], [hist.values[-1]], "o", color=C_BLUE,
            markersize=4)
    ax.annotate(f" ${hist.values[-1]:,.0f}",
                (hist.index[-1], hist.values[-1]), fontsize=8.5,
                color=C_BLUE, fontweight="bold", va="center")
    ax.axhline(target, color=INK, linewidth=1.1, linestyle="--")
    ax.annotate(f"  our target ${target:,.0f}", (hist.index[-1], target),
                color=INK, fontsize=8, va="bottom", ha="right")
    if street:
        ax.axhline(street, color=INK_MUTED, linewidth=1.0, linestyle=":")
        ax.annotate(f"  street ${street:,.0f}", (hist.index[0], street),
                    color=INK_MUTED, fontsize=8, va="bottom")
    ax.set_title(f"{ticker} — share price, five years")
    _style(ax)
    return _save(fig, f"{ticker}_price.png")


def fundamentals_chart(ticker: str, per_year: dict) -> str:
    """Revenue bars + net margin line (own axis-free annotation style)."""
    years = sorted(per_year)[-6:]
    rev = [per_year[y].get("revenue") for y in years]
    fig, axes = plt.subplots(1, 2, figsize=(7, 2.6))

    ax = axes[0]
    vals = [r / 1e9 if r else 0 for r in rev]
    ax.bar([str(y) for y in years], vals, color=C_BLUE, width=0.55)
    ax.set_title("Revenue ($B)")
    _style(ax)
    _label_bars(ax, vals, "{:,.1f}" if max(vals, default=0) < 10 else "{:,.0f}")

    ax = axes[1]
    fcf = [(y, per_year[y]["free_cash_flow"] / 1e9) for y in years
           if per_year[y].get("free_cash_flow") is not None]
    if fcf:
        fvals = [v for _, v in fcf]
        ax.bar([str(y) for y, _ in fcf], fvals, color=C_AQUA, width=0.55)
        ax.set_title("Free cash flow ($B)")
        _style(ax)
        _label_bars(ax, fvals, "{:,.1f}")
    else:
        roe = [(y, per_year[y]["roe"]) for y in years
               if per_year[y].get("roe") is not None]
        ax.plot([str(y) for y, _ in roe], [v * 100 for _, v in roe],
                color=C_AQUA, linewidth=1.8, marker="o", markersize=3)
        ax.set_title("Return on equity (%)")
    _style(ax)
    fig.tight_layout(w_pad=2)
    return _save(fig, f"{ticker}_fundamentals.png")


def margins_chart(ticker: str, per_year: dict) -> str:
    years = sorted(per_year)[-6:]
    series = {"Net margin": [per_year[y].get("net_margin") for y in years],
              "Operating margin": [per_year[y].get("operating_margin")
                                   for y in years]}
    fig, ax = plt.subplots(figsize=(7, 2.4))
    plotted = False
    for (label, vals), color in zip(series.items(), (C_AQUA, C_BLUE)):
        pts = [(str(y), v * 100) for y, v in zip(years, vals) if v is not None]
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color,
                    linewidth=1.8, marker="o", markersize=3)
            ax.annotate(f" {label} {pts[-1][1]:.0f}%",
                        (pts[-1][0], pts[-1][1]), fontsize=8, color=color,
                        fontweight="bold", va="center")
            plotted = True
    if not plotted:
        plt.close(fig)
        return None
    ax.set_title("Profit margins (%)")
    ax.margins(x=0.14)
    _style(ax)
    return _save(fig, f"{ticker}_margins.png")


def sensitivity_heatmap(ticker: str, sens: dict) -> str:
    if not sens:
        return None
    grid = [[v if v else float("nan") for v in row] for row in sens["grid"]]
    fig, ax = plt.subplots(figsize=(5.6, 2.6))
    im = ax.imshow(grid, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(len(sens["coe_values"])),
                  [f"{c:.1%}" for c in sens["coe_values"]])
    ax.set_yticks(range(len(sens["x_values"])),
                  [f"{x:.1%}" for x in sens["x_values"]])
    ax.set_xlabel("cost of equity")
    ax.set_ylabel(sens["x_label"])
    for i, row in enumerate(grid):
        for j, v in enumerate(row):
            if v == v:  # not NaN
                ax.text(j, i, f"{v:,.0f}", ha="center", va="center",
                        fontsize=7.5, color=INK)
    ax.set_title("Target price under flexed assumptions ($)")
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    return _save(fig, f"{ticker}_sensitivity.png")


def macro_panel(fedfunds: pd.Series, dgs10: pd.Series, slope: pd.Series,
                cpi_yoy: pd.Series, unrate: pd.Series) -> str:
    """2x2 economic backdrop panel, shared by all reports in a run."""
    fig, axes = plt.subplots(2, 2, figsize=(7, 4.4))

    ax = axes[0][0]
    ax.plot(fedfunds.index, fedfunds.values, color=C_BLUE, linewidth=1.5,
            label="Fed funds")
    ax.plot(dgs10.index, dgs10.values, color=C_AQUA, linewidth=1.5,
            label="10-year Treasury")
    ax.set_title("Policy and long rates (%)")
    ax.legend(frameon=False, fontsize=7.5)
    _style(ax)

    ax = axes[0][1]
    ax.plot(slope.index, slope.values, color=C_BLUE, linewidth=1.5)
    ax.axhline(0, color=INK_MUTED, linewidth=0.9, linestyle="--")
    ax.set_title("Yield-curve slope, 10y minus 2y (%)")
    _style(ax)

    ax = axes[1][0]
    ax.plot(cpi_yoy.index, cpi_yoy.values, color=C_BLUE, linewidth=1.5)
    ax.set_title("Inflation, CPI % change y/y")
    _style(ax)

    ax = axes[1][1]
    ax.plot(unrate.index, unrate.values, color=C_BLUE, linewidth=1.5)
    ax.set_title("Unemployment rate (%)")
    _style(ax)

    fig.tight_layout(h_pad=1.6, w_pad=2)
    return _save(fig, "macro_panel.png")


def quarterly_chart(ticker: str, quarterly: dict) -> str:
    rev = quarterly.get("revenue", {})
    if len(rev) < 4:
        return None
    labels = [k[2:7] for k in rev]   # 'YY-MM' from ISO dates
    fig, ax = plt.subplots(figsize=(7, 2.3))
    qvals = [v / 1e9 for v in rev.values()]
    ax.bar(labels, qvals, color=C_BLUE, width=0.55)
    ax.set_title("Quarterly revenue, as filed ($B)")
    _style(ax)
    _label_bars(ax, qvals, "{:,.1f}" if max(qvals, default=0) < 10 else "{:,.0f}")
    return _save(fig, f"{ticker}_quarterly.png")
