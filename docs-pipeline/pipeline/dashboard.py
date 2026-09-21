#!/usr/bin/env python3
"""Render the monitor's history as a self-contained HTML report.

A CMS-hosted docs set has no pull request to annotate, so the findings have to
go somewhere a team will actually look. This writes one file with no external
dependencies: open it, attach it to a scheduled run, or serve it from anywhere.

Encoding choices, so they can be argued with:

* Severity is a **status** encoding, not a categorical one, so it uses the
  reserved status palette rather than series hues. Status colour never carries
  meaning alone here - every severity appears with a glyph and a written label,
  in the tiles, the legend and the table.
* The by-check chart is a single series, so it takes one validated hue and no
  legend; the title names it.
* Both charts get a hover layer, and a table view exists for everything the
  charts show.

    pipeline/dashboard.py --history history --out reports/dashboard.html
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import pathlib

# Palette roles. Light and dark are separately chosen steps, not a flip.
TOKENS_LIGHT = {
    "surface": "#fcfcfb", "plane": "#f9f9f7", "ink": "#0b0b0b",
    "ink-2": "#52514e", "muted": "#898781", "grid": "#e1e0d9",
    "axis": "#c3c2b7", "border": "rgba(11,11,11,0.10)",
    "series-1": "#2a78d6", "good": "#006300",
}
TOKENS_DARK = {
    "surface": "#1a1a19", "plane": "#0d0d0d", "ink": "#ffffff",
    "ink-2": "#c3c2b7", "muted": "#898781", "grid": "#2c2c2a",
    "axis": "#383835", "border": "rgba(255,255,255,0.10)",
    "series-1": "#3987e5", "good": "#0ca30c",
}
# Fixed across both modes, by the palette's own rule.
STATUS = {"error": "#d03b3b", "warning": "#fab219", "suggestion": "#898781"}
GLYPH = {"error": "◆", "warning": "▲", "suggestion": "●"}
LEVELS = ("error", "warning", "suggestion")


def load_history(directory: pathlib.Path) -> list[dict]:
    runs = []
    for path in sorted(directory.glob("*.json")):
        try:
            runs.append(json.loads(path.read_text()))
        except json.JSONDecodeError:
            continue
    return runs


def compact(n: int) -> str:
    if n >= 10_000:
        return f"{n/1000:.1f}K".replace(".0K", "K")
    return f"{n:,}"


def _short_time(stamp: str) -> str:
    try:
        return dt.datetime.fromisoformat(stamp).strftime("%d %b %H:%M")
    except ValueError:
        return stamp[:16]


def _nice_ceiling(peak: int, divisions: int = 4) -> int:
    """Round up to a bound whose quarter-steps are whole, readable numbers.

    Scaling straight to the data's maximum gave an axis of 0/188/375/562/750.
    Stepping by 1, 2 or 5 x 10^n keeps every tick round.
    """
    import math

    if peak <= 0:
        return divisions
    rough = peak / divisions
    magnitude = 10 ** math.floor(math.log10(rough))
    for multiple in (1, 2, 2.5, 5, 10):
        step = magnitude * multiple
        if step >= rough:
            return int(step * divisions)
    return int(magnitude * 10 * divisions)


def svg_trend(runs: list[dict], width: int = 720, height: int = 260) -> str:
    """Multi-series line: one line per severity across runs."""
    if len(runs) < 2:
        return (
            '<p class="empty">A trend needs at least two runs. '
            f'This report has {len(runs)}.</p>'
        )

    # Right padding is derived from the longest end label, not guessed. At a
    # guessed 96px the "suggestion 423" label was clipped by the section edge.
    end_labels = [f"{GLYPH[l]} {l} {runs[-1]['by_level'].get(l, 0)}" for l in LEVELS]
    pad_l, pad_t, pad_b = 48, 16, 34
    pad_r = 24 + int(max(len(t) for t in end_labels) * 7.0)
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b

    peak = max((r["by_level"].get(l, 0) for r in runs for l in LEVELS), default=1) or 1
    top = _nice_ceiling(peak)

    def x(i: int) -> float:
        return pad_l + (plot_w * i / (len(runs) - 1))

    def y(v: int) -> float:
        return pad_t + plot_h - (plot_h * v / top)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" '
             f'aria-label="Findings by severity across {len(runs)} runs" class="chart">']

    # Recessive gridlines and value ticks.
    for frac in (0, 0.25, 0.5, 0.75, 1):
        value = int(top * frac)
        gy = y(value)
        parts.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l+plot_w}" y2="{gy:.1f}" '
                     f'class="grid"/>')
        parts.append(f'<text x="{pad_l-10}" y="{gy+4:.1f}" class="tick tick-y">{value}</text>')

    for i, run in enumerate(runs):
        label = run.get("label") or _short_time(run["timestamp"])
        parts.append(f'<text x="{x(i):.1f}" y="{height-12}" class="tick tick-x">'
                     f'{html.escape(label)}</text>')

    for level in LEVELS:
        colour = STATUS[level]
        points = [(x(i), y(r["by_level"].get(level, 0))) for i, r in enumerate(runs)]
        path = " ".join(f"{'M' if i == 0 else 'L'}{px:.1f},{py:.1f}"
                        for i, (px, py) in enumerate(points))
        parts.append(f'<path d="{path}" fill="none" stroke="{colour}" stroke-width="2" '
                     f'stroke-linecap="round" stroke-linejoin="round"/>')
        for px, py in points:
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" fill="{colour}" '
                         f'stroke="var(--surface)" stroke-width="2"/>')
        # Direct end label, so identity never depends on hue alone.
        last_x, last_y = points[-1]
        value = runs[-1]["by_level"].get(level, 0)
        parts.append(f'<text x="{last_x+12:.1f}" y="{last_y+4:.1f}" class="endlabel" '
                     f'fill="{colour}">{GLYPH[level]} {level} {value}</text>')

    # Hover layer: one full-height band per run, driving a shared tooltip.
    for i, run in enumerate(runs):
        band = plot_w / max(1, len(runs) - 1)
        bx = x(i) - band / 2
        payload = html.escape(json.dumps({
            "label": run.get("label") or _short_time(run["timestamp"]),
            "time": _short_time(run["timestamp"]),
            "levels": {l: run["by_level"].get(l, 0) for l in LEVELS},
            "total": run["total"],
        }), quote=True)
        parts.append(f'<rect x="{bx:.1f}" y="{pad_t}" width="{band:.1f}" height="{plot_h}" '
                     f'class="hit" data-point="{payload}"/>')
        parts.append(f'<line x1="{x(i):.1f}" y1="{pad_t}" x2="{x(i):.1f}" '
                     f'y2="{pad_t+plot_h}" class="crosshair" data-for="{i}"/>')

    parts.append("</svg>")
    return "".join(parts)


def svg_breakdown(counts: dict[str, int], limit: int = 12,
                  width: int = 720, row: int = 26) -> str:
    """Horizontal bars, single series, magnitude by check."""
    items = list(counts.items())[:limit]
    if not items:
        return '<p class="empty">No findings.</p>'
    label_w, value_w = 210, 56
    bar_w = width - label_w - value_w
    peak = max(v for _, v in items) or 1
    height = row * len(items)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" '
             f'aria-label="Findings by check" class="chart">']
    for i, (name, value) in enumerate(items):
        # 2px surface gap between adjacent bars.
        y = i * row + 3
        h = row - 8
        w = max(3, bar_w * value / peak)
        payload = html.escape(json.dumps({"label": name, "value": value}), quote=True)
        parts.append(f'<text x="{label_w-12}" y="{y+h/2+4:.1f}" class="tick tick-y">'
                     f'{html.escape(name)}</text>')
        parts.append(f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="{h}" rx="4" '
                     f'fill="var(--series-1)" class="bar" data-point="{payload}"/>')
        parts.append(f'<text x="{label_w + w + 10:.1f}" y="{y+h/2+4:.1f}" class="value">'
                     f'{value}</text>')
    parts.append("</svg>")
    return "".join(parts)


def tile(label: str, value: str, delta: str = "", tone: str = "", glyph: str = "") -> str:
    mark = f'<span class="glyph" style="color:{STATUS[tone]}">{GLYPH[tone]}</span>' if tone else ""
    delta_html = f'<div class="delta {"down" if delta.startswith("-") else "up"}">{delta}</div>' if delta else ""
    return (f'<div class="tile"><div class="tile-label">{mark}{html.escape(label)}</div>'
            f'<div class="tile-value">{value}</div>{delta_html}</div>')


def render(runs: list[dict], out: pathlib.Path) -> str:
    latest = runs[-1]
    previous = runs[-2] if len(runs) > 1 else None
    delta = latest.get("delta") or {}

    def level_delta(level: str) -> str:
        if not previous:
            return ""
        d = latest["by_level"].get(level, 0) - previous["by_level"].get(level, 0)
        return f"{d:+d} vs previous run" if d else "no change"

    tiles = "".join([
        tile("Errors", compact(latest["by_level"].get("error", 0)), level_delta("error"), "error"),
        tile("Warnings", compact(latest["by_level"].get("warning", 0)), level_delta("warning"), "warning"),
        tile("Suggestions", compact(latest["by_level"].get("suggestion", 0)), level_delta("suggestion"), "suggestion"),
        tile("Pages checked", compact(latest["pages"])),
    ])

    by_kind = "".join(
        f'<li><span class="k">{html.escape(k)}</span><span class="v">{v}</span></li>'
        for k, v in sorted(latest.get("by_kind", {}).items(), key=lambda kv: -kv[1])
    )

    rows = []
    for f in latest.get("findings", [])[:300]:
        rows.append(
            f'<tr data-level="{f["level"]}"><td><span class="glyph" '
            f'style="color:{STATUS.get(f["level"], "#898781")}">{GLYPH.get(f["level"], "")}</span>'
            f'{f["level"]}</td>'
            f'<td><code>{html.escape(f["page"])}</code></td><td class="num">{f["line"]}</td>'
            f'<td><code>{html.escape(f["check"])}</code></td>'
            f'<td>{html.escape(f["message"])[:160]}</td></tr>'
        )
    omitted = max(0, len(latest.get("findings", [])) - 300)

    if delta.get("first_run"):
        movement = "First run — no baseline to compare against."
    else:
        movement = (f'{len(delta.get("new", []))} new · {len(delta.get("fixed", []))} fixed '
                    f'· {delta.get("total_delta", 0):+d} overall since '
                    f'{_short_time(delta.get("previous_timestamp", ""))}')

    def tokens(mapping: dict) -> str:
        return "".join(f"--{k}:{v};" for k, v in mapping.items())

    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Documentation health</title>
<style>
  :root {{ color-scheme: light; {tokens(TOKENS_LIGHT)} }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{ color-scheme: dark; {tokens(TOKENS_DARK)} }}
  }}
  :root[data-theme="dark"] {{ color-scheme: dark; {tokens(TOKENS_DARK)} }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background: var(--plane); color: var(--ink);
    font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
  .wrap {{ max-width: 980px; margin: 0 auto; padding: 32px 16px 64px; }}
  header {{ margin-bottom: 28px; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; letter-spacing: -0.01em; }}
  .sub {{ color: var(--ink-2); font-size: 13px; }}
  .hero {{ font-size: 56px; font-weight: 600; line-height: 1.05; margin: 22px 0 2px;
    letter-spacing: -0.02em; }}
  .hero-label {{ color: var(--ink-2); font-size: 13px; margin-bottom: 22px; }}
  .tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px,1fr));
    gap: 10px; margin-bottom: 30px; }}
  .tile {{ background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px 16px; }}
  .tile-label {{ color: var(--ink-2); font-size: 12px; display:flex; align-items:center; gap:6px; }}
  .tile-value {{ font-size: 28px; font-weight: 600; margin-top: 4px; letter-spacing: -0.01em; }}
  .delta {{ font-size: 11px; color: var(--ink-2); margin-top: 2px; }}
  .delta.down {{ color: var(--good); }}
  .glyph {{ font-size: 11px; }}
  section {{ background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 18px 20px; margin-bottom: 18px; }}
  h2 {{ font-size: 14px; margin: 0 0 2px; }}
  .note {{ color: var(--ink-2); font-size: 12px; margin: 0 0 14px; }}
  .chart {{ width: 100%; height: auto; display: block; }}
  .grid {{ stroke: var(--grid); stroke-width: 1; }}
  .tick {{ fill: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }}
  .tick-y {{ text-anchor: end; }}
  .tick-x {{ text-anchor: middle; }}
  .endlabel {{ font-size: 11px; font-weight: 600; }}
  .value {{ fill: var(--ink-2); font-size: 11px; font-variant-numeric: tabular-nums; }}
  .hit {{ fill: transparent; }}
  .crosshair {{ stroke: var(--axis); stroke-width: 1; stroke-dasharray: 3 3; opacity: 0; }}
  .bar {{ transition: opacity .12s; }}
  .bar:hover {{ opacity: .82; }}
  ul.kinds {{ list-style:none; padding:0; margin:0; display:flex; gap:22px; flex-wrap:wrap; }}
  ul.kinds .k {{ color: var(--ink-2); font-size:12px; margin-right:6px; }}
  ul.kinds .v {{ font-weight:600; font-variant-numeric: tabular-nums; }}
  .scroll {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
  table {{ width:100%; border-collapse: collapse; font-size: 12.5px; min-width: 520px; }}
  th, td {{ text-align:left; padding: 7px 8px; border-bottom: 1px solid var(--grid);
    vertical-align: top; }}
  th {{ color: var(--ink-2); font-weight: 600; font-size: 11px; text-transform: uppercase;
    letter-spacing: .04em; }}
  td.num {{ text-align:right; font-variant-numeric: tabular-nums; color: var(--ink-2); }}
  code {{ font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
    overflow-wrap: anywhere; }}
  html, body {{ overflow-x: hidden; }}
  .empty {{ color: var(--ink-2); font-size: 13px; margin: 8px 0 0; }}
  #tip {{ position: fixed; pointer-events: none; opacity: 0; transition: opacity .1s;
    background: var(--surface); color: var(--ink); border: 1px solid var(--border);
    border-radius: 8px; padding: 8px 10px; font-size: 12px; box-shadow: 0 6px 20px rgba(0,0,0,.14);
    z-index: 10; }}
  #tip b {{ display:block; margin-bottom:4px; }}
  #tip .r {{ display:flex; justify-content:space-between; gap:16px; }}
  @media (max-width: 640px) {{ .wrap {{ padding: 20px 16px 48px; }} .hero {{ font-size: 44px; }} }}
</style></head>
<body><div class="wrap">
<header>
  <h1>Documentation health</h1>
  <div class="sub">Source: <code>{html.escape(latest.get("source", "?"))}</code> ·
    {latest["pages"]} pages · generated {html.escape(_short_time(latest["timestamp"]))}</div>
  <div class="hero">{compact(latest["total"])}</div>
  <div class="hero-label">open findings · {html.escape(movement)}</div>
</header>

<div class="tiles">{tiles}</div>

<section>
  <h2>Findings by severity, across runs</h2>
  <p class="note">Each severity is labelled directly at its line end; colour is never the
    only cue.</p>
  {svg_trend(runs)}
</section>

<section>
  <h2>Findings by check</h2>
  <p class="note">Top {min(12, len(latest.get("by_check", {})))} checks in the latest run.</p>
  {svg_breakdown(latest.get("by_check", {}))}
</section>

<section>
  <h2>By tool</h2>
  <p class="note">Which layer produced the findings.</p>
  <ul class="kinds">{by_kind}</ul>
</section>

<section>
  <h2>Findings</h2>
  <p class="note">The table view of everything above.{
    f" Showing the first 300 of {latest['total']}; {omitted} omitted." if omitted else ""}</p>
  <div class="scroll"><table><thead><tr><th>Severity</th><th>Page</th><th>Line</th><th>Check</th><th>Message</th></tr>
  </thead><tbody>{"".join(rows)}</tbody></table></div>
</section>
</div>
<div id="tip" role="status" aria-live="polite"></div>
<script>
(function () {{
  var tip = document.getElementById('tip');
  function show(evt, html_) {{
    tip.innerHTML = html_;
    tip.style.opacity = '1';
    var r = tip.getBoundingClientRect();
    var x = Math.min(evt.clientX + 14, window.innerWidth - r.width - 8);
    var y = Math.min(evt.clientY + 14, window.innerHeight - r.height - 8);
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }}
  function hide() {{ tip.style.opacity = '0'; }}

  document.querySelectorAll('.hit').forEach(function (el) {{
    el.addEventListener('mousemove', function (e) {{
      var d = JSON.parse(el.dataset.point);
      var rows = Object.keys(d.levels).map(function (k) {{
        return '<div class="r"><span>' + k + '</span><span>' + d.levels[k] + '</span></div>';
      }}).join('');
      show(e, '<b>' + d.label + '</b>' + rows +
        '<div class="r"><span>total</span><span>' + d.total + '</span></div>');
      var line = el.nextElementSibling;
      if (line) line.style.opacity = '1';
    }});
    el.addEventListener('mouseleave', function () {{
      hide();
      var line = el.nextElementSibling;
      if (line) line.style.opacity = '0';
    }});
  }});

  document.querySelectorAll('.bar').forEach(function (el) {{
    el.addEventListener('mousemove', function (e) {{
      var d = JSON.parse(el.dataset.point);
      show(e, '<b>' + d.label + '</b><div class="r"><span>findings</span><span>' +
        d.value + '</span></div>');
    }});
    el.addEventListener('mouseleave', hide);
  }});
}})();
</script>
</body></html>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--history", type=pathlib.Path, default=pathlib.Path("history"))
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("reports/dashboard.html"))
    args = ap.parse_args()

    runs = load_history(args.history)
    if not runs:
        raise SystemExit(f"no run snapshots in {args.history}; run pipeline/run.py first")
    render(runs, args.out)
    size = args.out.stat().st_size
    print(f"wrote {args.out} ({size/1024:.0f} KB, {len(runs)} run(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
