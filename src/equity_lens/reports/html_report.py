"""Styled HTML rendition of each research report.

The markdown remains the canonical content; this wraps it in the visual
language of an institutional research note — masthead, rating banner,
metrics strip, styled tables, serif display headings — and is what gets
linked from the website and printed to PDF. Output: reports/html/.
"""

import re
from pathlib import Path

import markdown as md

REPO_ROOT = Path(__file__).parents[3]
HTML_DIR = REPO_ROOT / "reports" / "html"

RATING_COLORS = {"BUY": "#0a7d33", "HOLD": "#a07400", "SELL": "#b3261e",
                 "NR": "#6e6e73"}

CSS = """
:root {
  --ink: #1d1d1f; --muted: #6e6e73; --hair: #e5e5e2; --accent: #2a78d6;
  --paper: #ffffff; --wash: #f5f5f7;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--wash); color: var(--ink);
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "SF Pro Text",
        "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
.sheet {
  max-width: 860px; margin: 24px auto; background: var(--paper);
  padding: 48px 56px 40px; border: 1px solid var(--hair);
  border-radius: 6px; box-shadow: 0 2px 6px rgba(0,0,0,.05),
                                  0 12px 32px rgba(0,0,0,.05);
}
.masthead {
  display: flex; justify-content: space-between; align-items: baseline;
  border-bottom: 3px solid var(--ink); padding-bottom: 10px;
  margin-bottom: 22px;
}
.masthead .brand {
  font-family: 'Source Serif 4', Georgia, serif; font-size: 21px;
  font-weight: 700; letter-spacing: .01em;
}
.masthead .kind { color: var(--muted); font-size: 12.5px;
  text-transform: uppercase; letter-spacing: .14em; }
.titleblock h1 {
  font-family: 'Source Serif 4', Georgia, serif; font-size: 30px;
  line-height: 1.15; margin: 0 0 4px;
}
.titleblock .sub { color: var(--muted); font-size: 13.5px; margin-bottom: 18px; }
.banner {
  display: flex; gap: 0; border: 1px solid var(--hair); border-radius: 10px;
  overflow: hidden; margin: 0 0 26px;
}
.banner .cell {
  flex: 1; padding: 12px 16px; border-right: 1px solid var(--hair);
}
.banner .cell:last-child { border-right: 0; }
.banner .label { font-size: 10.5px; text-transform: uppercase;
  letter-spacing: .12em; color: var(--muted); margin-bottom: 3px; }
.banner .value { font-size: 19px; font-weight: 650; }
.banner .rating-cell { color: #fff; }
.banner .rating-cell .label { color: rgba(255,255,255,.75); }
h2 {
  font-family: 'Source Serif 4', Georgia, serif; font-size: 20px;
  margin: 34px 0 10px; padding-top: 18px; border-top: 1px solid var(--hair);
}
h3 { font-size: 15.5px; margin: 22px 0 8px; }
p, li { max-width: 72ch; }
a { color: var(--accent); text-decoration: none; }
img { max-width: 100%; border: 1px solid var(--hair); border-radius: 8px;
      margin: 8px 0 4px; }
table { border-collapse: collapse; width: 100%; font-size: 13px;
        margin: 12px 0 6px; }
th { text-align: left; font-size: 11px; text-transform: uppercase;
     letter-spacing: .08em; color: var(--muted); font-weight: 600;
     padding: 7px 10px; border-bottom: 2px solid var(--ink); }
td { padding: 7px 10px; border-bottom: 1px solid var(--hair);
     font-variant-numeric: tabular-nums; }
tr:hover td { background: #fafafa; }
.footer { margin-top: 36px; padding-top: 14px; border-top: 1px solid
          var(--hair); color: var(--muted); font-size: 12px; }
@media print {
  body { background: #fff; }
  .sheet { box-shadow: none; border: 0; margin: 0; padding: 24px 8px;
           max-width: 100%; }
  .banner { break-inside: avoid; }
  h2 { break-after: avoid; }
  img, table { break-inside: avoid; }
}
"""


def _banner(a: dict) -> str:
    s = a["snapshot"]
    color = RATING_COLORS.get(a["rating"], "#6e6e73")
    street = (f"${s['street_target_mean']:,.2f}" if s["street_target_mean"]
              else "n/a")
    cells = [
        ("rating-cell", "Rating", a["rating"], f"background:{color}"),
        ("", "Price", f"${s['price']:,.2f}", ""),
        ("", "Our target", f"${a['target_price']:,.2f}", ""),
        ("", "Implied", f"{a['upside']:+.1%}", ""),
        ("", "Street", street, ""),
        ("", "Within coverage", a.get("relative_rating", "n/a"), ""),
    ]
    html = ['<div class="banner">']
    for cls, label, value, style in cells:
        html.append(f'<div class="cell {cls}" style="{style}">'
                    f'<div class="label">{label}</div>'
                    f'<div class="value">{value}</div></div>')
    html.append("</div>")
    return "".join(html)


def render(a: dict, report_md: str) -> str:
    """Full standalone HTML document from the analysis + markdown report."""
    p = a["profile"]
    # Drop the markdown's own H1/header table; HTML builds its own header.
    body_md = re.sub(r"^# .*?\n", "", report_md, count=1)
    body_md = re.sub(r"^\*\*Equity Research.*?\n", "", body_md, count=1,
                     flags=re.M)
    # First markdown table (the header key-facts table) is replaced by banner.
    body_md = re.sub(r"\n\| \|  ?\|\n(\|.*\n)+", "\n", body_md, count=1)
    # Image paths: html/ lives one level below reports/, assets stays sibling.
    body_md = body_md.replace("](assets/", "](../assets/")
    body_html = md.markdown(body_md, extensions=["tables"])

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{p['name']} ({a['ticker']}) — Equity-Lens Research</title>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body><div class="sheet">
<div class="masthead"><span class="brand">EQUITY-LENS</span>
<span class="kind">Equity Research</span></div>
<div class="titleblock">
<h1>{p['name']} <span style="color:var(--muted)">({a['ticker']})</span></h1>
<div class="sub">{p['sector']} — {p['industry']} &middot; {a['as_of']} &middot;
computed from SEC EDGAR, Yahoo Finance, and FRED</div></div>
{_banner(a)}
{body_html}
<div class="footer">Equity-Lens — independent equity research, computed
rather than opined. Educational project; not investment advice.
Methodology and source code:
<a href="https://github.com/Jamesheidbreder/equity-lens">github.com/Jamesheidbreder/equity-lens</a></div>
</div></body></html>"""


def write_html(a: dict, report_md: str, date_str: str) -> Path:
    HTML_DIR.mkdir(exist_ok=True)
    path = HTML_DIR / f"{a['ticker']}_{date_str}.html"
    path.write_text(render(a, report_md))
    return path
