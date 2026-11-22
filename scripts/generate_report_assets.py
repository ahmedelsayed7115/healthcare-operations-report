"""Generate publication-grade SVG charts from data/analysis_summary.json.

All text attributes are inlined directly on <text> elements (no <style> blocks)
so GitHub's SVG sanitizer renders labels cleanly in README.md and GitHub Pages.
"""
import html
import json
import math
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
ASSETS_DIR = os.path.join(REPO_ROOT, "assets")
DATA_DIR = os.path.join(REPO_ROOT, "data")
SUMMARY_PATH = os.path.join(DATA_DIR, "analysis_summary.json")

os.makedirs(ASSETS_DIR, exist_ok=True)

with open(SUMMARY_PATH, encoding="utf-8") as f:
    summary = json.load(f)

FONT = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

STYLE_TITLE = f'font-family="{FONT}" font-size="18" font-weight="700" fill="#0f172a"'
STYLE_SUB = f'font-family="{FONT}" font-size="12" fill="#64748b"'
STYLE_AXIS = f'font-family="{FONT}" font-size="11" fill="#475569"'
STYLE_LABEL = f'font-family="{FONT}" font-size="11" font-weight="600" fill="#1e293b"'
STYLE_SMALL = f'font-family="{FONT}" font-size="10" fill="#64748b"'


def esc(s):
    return html.escape(str(s))


def svg_header(w, h, title):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-label="{esc(title)}">\n'
        f'<rect width="{w}" height="{h}" rx="12" fill="#ffffff" stroke="#e2e8f0" stroke-width="1"/>\n'
    )


# ---------------------------------------------------------------------------
# CHART 1: Annual Encounter Volume & 30-Day Readmission Rate (2011-2020)
# ---------------------------------------------------------------------------
def build_view1_svg():
    w, h = 920, 440
    data = summary["op_window_2011_2020"]["views"]["view1_annual"]
    ml, mr, mt, mb = 64, 68, 86, 62
    pw, ph = w - ml - mr, h - mt - mb

    max_vol = 500
    max_rate = 0.35

    out = [svg_header(w, h, "Annual Encounter Volume & 30-Day Inpatient Readmission Rate (2011-2020)")]
    out.append(f'<text x="28" y="34" {STYLE_TITLE}>Annual Encounter Volume &amp; 30-Day Inpatient Readmission Trend (2011–2020)</text>')
    out.append(f'<text x="28" y="54" {STYLE_SUB}>Stacked bars = acute encounters by class (left axis)  •  Crimson line = 30-day inpatient readmission rate (right axis)  •  Dashed = 15% target</text>')

    # Legend
    leg_y = 72
    legend_items = [
        ("#3b82f6", "Urgent Care", "rect"),
        ("#0f766e", "Inpatient", "rect"),
        ("#94a3b8", "Emergency", "rect"),
        ("#dc2626", "Readmission Rate (%)", "line"),
        ("#f59e0b", "15% Target", "dash"),
    ]
    lx = 28
    for color, lbl, kind in legend_items:
        if kind == "rect":
            out.append(f'<rect x="{lx}" y="{leg_y-9}" width="12" height="10" rx="2" fill="{color}"/>')
        elif kind == "line":
            out.append(f'<line x1="{lx}" y1="{leg_y-4}" x2="{lx+14}" y2="{leg_y-4}" stroke="{color}" stroke-width="2.5"/>')
            out.append(f'<circle cx="{lx+7}" cy="{leg_y-4}" r="3" fill="{color}"/>')
        else:
            out.append(f'<line x1="{lx}" y1="{leg_y-4}" x2="{lx+14}" y2="{leg_y-4}" stroke="{color}" stroke-width="1.8" stroke-dasharray="4 3"/>')
        out.append(f'<text x="{lx+19}" y="{leg_y}" {STYLE_AXIS}>{esc(lbl)}</text>')
        lx += 28 + len(lbl) * 6.8

    # Horizontal gridlines & left/right Y axes
    for i in range(6):
        v = i * 100
        y = mt + ph - (v / max_vol) * ph
        out.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{ml+pw}" y2="{y:.1f}" stroke="#f1f5f9" stroke-width="1"/>')
        out.append(f'<text x="{ml-10}" y="{y+4:.1f}" text-anchor="end" {STYLE_AXIS}>{v}</text>')
    for pct in [0, 7, 14, 21, 28, 35]:
        y = mt + ph - ((pct / 100.0) / max_rate) * ph
        out.append(f'<text x="{ml+pw+10}" y="{y+4:.1f}" text-anchor="start" {STYLE_AXIS}>{pct}%</text>')

    # 15% goal line
    gy = mt + ph - (0.15 / max_rate) * ph
    out.append(f'<line x1="{ml}" y1="{gy:.1f}" x2="{ml+pw}" y2="{gy:.1f}" stroke="#f59e0b" stroke-width="1.8" stroke-dasharray="6 4"/>')
    out.append(f'<text x="{ml+pw-4}" y="{gy-6:.1f}" text-anchor="end" font-family="{FONT}" font-size="10" font-weight="600" fill="#d97706">Goal: 15.0%</text>')

    # Bars
    n = len(data)
    step = pw / n
    bw = min(46, step * 0.56)
    pts = []
    for idx, d in enumerate(data):
        cx = ml + step * (idx + 0.5)
        bx = cx - bw / 2
        y_curr = mt + ph
        for cls_key, color in [("emergency", "#94a3b8"), ("inpatient", "#0f766e"), ("urgentcare", "#3b82f6")]:
            val = d[cls_key]
            bh = (val / max_vol) * ph
            y_curr -= bh
            out.append(f'<rect x="{bx:.1f}" y="{y_curr:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{color}" opacity="0.9"/>')
        out.append(f'<text x="{cx:.1f}" y="{y_curr-6:.1f}" text-anchor="middle" {STYLE_SMALL}>{d["total"]}</text>')
        yr_lbl = f'{d["year"]}*' if d["year"] == 2020 else str(d["year"])
        out.append(f'<text x="{cx:.1f}" y="{mt+ph+20}" text-anchor="middle" {STYLE_AXIS}>{yr_lbl}</text>')
        ry = mt + ph - (d["readmission_rate"] / max_rate) * ph
        pts.append((cx, ry, d["readmission_rate"]))

    # Readmission line
    path_d = " ".join(f'{"M" if i == 0 else "L"} {x:.1f} {y:.1f}' for i, (x, y, _) in enumerate(pts))
    out.append(f'<path d="{path_d}" fill="none" stroke="#dc2626" stroke-width="2.8" stroke-linejoin="round"/>')
    for x, y, r in pts:
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#ffffff" stroke="#dc2626" stroke-width="2.5"/>')
        out.append(f'<rect x="{x-20:.1f}" y="{y-23:.1f}" width="40" height="15" rx="4" fill="#fef2f2" stroke="#fecaca" stroke-width="0.8"/>')
        out.append(f'<text x="{x:.1f}" y="{y-12:.1f}" text-anchor="middle" font-family="{FONT}" font-size="10" font-weight="700" fill="#b91c1c">{r*100:.1f}%</text>')

    out.append(f'<text x="28" y="{h-14}" {STYLE_SMALL}>*2020 reflects partial-year data (133 encounters). Source: Healthcare_Operations_Readmission_Dashboard.twbx (Operational Window 2011–2020, n=3,814).</text>')
    out.append("</svg>")
    with open(os.path.join(ASSETS_DIR, "view1_annual_trend.svg"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))


# ---------------------------------------------------------------------------
# CHART 2: Top 10 Clinical Drivers of Inpatient Readmissions
# ---------------------------------------------------------------------------
def build_view2_svg():
    w, h = 920, 470
    data = summary["all_data"]["views"]["view2_drivers_top15"][:10]
    ml, mr, mt, mb = 325, 165, 76, 46
    pw, ph = w - ml - mr, h - mt - mb
    max_val = 380

    out = [svg_header(w, h, "Top 10 Clinical Drivers of Inpatient 30-Day Readmissions")]
    out.append(f'<text x="28" y="34" {STYLE_TITLE}>Top 10 Clinical Drivers of Inpatient 30-Day Readmissions</text>')
    out.append(f'<text x="28" y="54" {STYLE_SUB}>Bar length = 30-day readmission count  •  Color indicates oncology (crimson) vs. non-oncology (slate)  •  Full historical dataset (n=439 readmissions)</text>')

    for v in [0, 100, 200, 300]:
        x = ml + (v / max_val) * pw
        out.append(f'<line x1="{x:.1f}" y1="{mt}" x2="{x:.1f}" y2="{mt+ph}" stroke="#f1f5f9" stroke-width="1"/>')
        out.append(f'<text x="{x:.1f}" y="{mt+ph+18}" text-anchor="middle" {STYLE_AXIS}>{v}</text>')

    row_h = ph / len(data)
    bh = row_h * 0.62
    for idx, d in enumerate(data):
        y = mt + idx * row_h + (row_h - bh) / 2
        drv = d["driver"]
        short_drv = drv if len(drv) <= 46 else drv[:43] + "..."
        is_onc = any(k in drv.lower() for k in ["oncology", "malignant", "malignancy", "breast", "lung", "colon"])
        fill = "#dc2626" if is_onc else "#475569"
        bw = max(3.0, (d["readmissions"] / max_val) * pw)

        out.append(f'<text x="{ml-10}" y="{y+bh*0.68:.1f}" text-anchor="end" {STYLE_AXIS}>{esc(short_drv)}</text>')
        out.append(f'<rect x="{ml}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="4" fill="{fill}" opacity="0.9"/>')
        lbl = f'{d["readmissions"]} readm  ({d["inpatient"]} stays, {d["readmission_rate"]*100:.1f}%)'
        out.append(f'<text x="{ml+bw+8:.1f}" y="{y+bh*0.68:.1f}" {STYLE_LABEL}>{esc(lbl)}</text>')

    out.append(f'<text x="28" y="{h-12}" {STYLE_SMALL}>Oncology-related drivers account for 430 of 439 total readmissions (97.9%). Top 3 drivers alone represent 96.1%.</text>')
    out.append("</svg>")
    with open(os.path.join(ASSETS_DIR, "view2_clinical_drivers.svg"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))


# ---------------------------------------------------------------------------
# CHART 3: Risk Tier x Age Cohort Heatmap
# ---------------------------------------------------------------------------
def build_view3_svg():
    w, h = 920, 390
    raw = summary["all_data"]["views"]["view3_heatmap"]
    lookup = {(r["risk_tier"], r["age_cohort"]): r for r in raw}
    tiers = ["High Risk", "Moderate Risk", "Low Risk"]
    cohorts = ["Pediatric", "Young Adult", "Middle-Aged", "Senior"]

    ml, mr, mt, mb = 150, 40, 96, 54
    pw, ph = w - ml - mr, h - mt - mb
    cw, ch = pw / len(cohorts), ph / len(tiers)

    def rate_color(rate):
        if rate is None:
            return "#f8fafc", "#94a3b8"
        if rate == 0:
            return "#f1f5f9", "#475569"
        if rate < 0.10:
            return "#fee2e2", "#991b1b"
        if rate < 0.22:
            return "#fca5a5", "#7f1d1d"
        if rate < 0.30:
            return "#ef4444", "#ffffff"
        return "#991b1b", "#ffffff"

    out = [svg_header(w, h, "30-Day Readmission Rate by Clinical Risk Tier & Age Cohort")]
    out.append(f'<text x="28" y="34" {STYLE_TITLE}>30-Day Inpatient Readmission Rate by Clinical Risk Tier &amp; Age Cohort</text>')
    out.append(f'<text x="28" y="54" {STYLE_SUB}>Darker crimson = higher readmission rate  •  Cell shows rate, readmissions / inpatient stays (n)  •  Full historical dataset</text>')

    for j, c in enumerate(cohorts):
        cx = ml + j * cw + cw / 2
        out.append(f'<text x="{cx:.1f}" y="{mt-14}" text-anchor="middle" font-family="{FONT}" font-size="13" font-weight="700" fill="#0f172a">{esc(c)}</text>')

    for i, t in enumerate(tiers):
        ry = mt + i * ch
        out.append(f'<text x="{ml-16}" y="{ry+ch/2+4:.1f}" text-anchor="end" font-family="{FONT}" font-size="13" font-weight="700" fill="#0f172a">{esc(t)}</text>')
        for j, c in enumerate(cohorts):
            rx = ml + j * cw
            cell = lookup.get((t, c), {"inpatient": 0, "readmissions": 0, "readmission_rate": None})
            rate = cell["readmission_rate"]
            bg, fg = rate_color(rate)
            out.append(f'<rect x="{rx+4:.1f}" y="{ry+4:.1f}" width="{cw-8:.1f}" height="{ch-8:.1f}" rx="8" fill="{bg}" stroke="#e2e8f0" stroke-width="1"/>')
            cx, cy = rx + cw / 2, ry + ch / 2
            if rate is None:
                out.append(f'<text x="{cx:.1f}" y="{cy-2:.1f}" text-anchor="middle" font-family="{FONT}" font-size="14" font-weight="600" fill="{fg}">—</text>')
                out.append(f'<text x="{cx:.1f}" y="{cy+16:.1f}" text-anchor="middle" font-family="{FONT}" font-size="10" fill="{fg}">n = 0 stays</text>')
            else:
                out.append(f'<text x="{cx:.1f}" y="{cy-3:.1f}" text-anchor="middle" font-family="{FONT}" font-size="18" font-weight="700" fill="{fg}">{rate*100:.1f}%</text>')
                out.append(f'<text x="{cx:.1f}" y="{cy+16:.1f}" text-anchor="middle" font-family="{FONT}" font-size="11" fill="{fg}" opacity="0.9">{cell["readmissions"]} / {cell["inpatient"]} stays</text>')

    out.append(f'<text x="28" y="{h-14}" {STYLE_SMALL}>High-Risk Middle-Aged (39.0%) and High-Risk Senior (25.8%) drive 94.8% of all readmissions. Moderate-Risk Pediatric (20.4%) is the sole non-High-Risk outlier.</text>')
    out.append("</svg>")
    with open(os.path.join(ASSETS_DIR, "view3_risk_heatmap.svg"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))


# ---------------------------------------------------------------------------
# CHART 4: Payer Quadrant Scatter (Coverage Rate vs Readmission Rate)
# ---------------------------------------------------------------------------
def build_view4_svg():
    w, h = 920, 480
    payers = summary["all_data"]["views"]["view4_payers"]
    ml, mr, mt, mb = 72, 46, 86, 66
    pw, ph = w - ml - mr, h - mt - mb

    max_cov = 0.45
    max_readm = 0.42
    bench_cov = 0.258
    goal_readm = 0.15

    out = [svg_header(w, h, "Payer Quadrant: Coverage Rate vs Inpatient Readmission Rate")]
    out.append(f'<text x="28" y="34" {STYLE_TITLE}>Payer Quadrant: Payer Coverage Rate vs. 30-Day Inpatient Readmission Rate</text>')
    out.append(f'<text x="28" y="54" {STYLE_SUB}>Bubble size = inpatient stays  •  Color intensity = uncovered claim cost (margin leakage)  •  Diamond = Self-Pay  •  Benchmarks: 25.8% coverage, 15.0% readmission</text>')

    bx = ml + (bench_cov / max_cov) * pw
    gy = mt + ph - (goal_readm / max_readm) * ph
    out.append(f'<rect x="{ml}" y="{mt}" width="{bx-ml:.1f}" height="{gy-mt:.1f}" fill="#fef2f2" opacity="0.55"/>')
    out.append(f'<rect x="{bx:.1f}" y="{gy:.1f}" width="{ml+pw-bx:.1f}" height="{mt+ph-gy:.1f}" fill="#f0fdf4" opacity="0.65"/>')

    out.append(f'<text x="{ml+10}" y="{mt+18}" font-family="{FONT}" font-size="10" font-weight="700" fill="#b91c1c">HIGH RISK / LOW COVERAGE</text>')
    out.append(f'<text x="{ml+pw-10}" y="{mt+18}" text-anchor="end" font-family="{FONT}" font-size="10" font-weight="700" fill="#b45309">HIGH READMISSION / ABOVE-AVG COVERAGE</text>')
    out.append(f'<text x="{ml+pw-10}" y="{mt+ph-10}" text-anchor="end" font-family="{FONT}" font-size="10" font-weight="700" fill="#15803d">OPTIMAL QUADRANT</text>')
    out.append(f'<text x="{ml+10}" y="{mt+ph-10}" font-family="{FONT}" font-size="10" font-weight="700" fill="#475569">LOW COVERAGE / LOW READMISSION</text>')

    for pct in [0, 10, 20, 30, 40]:
        x = ml + ((pct / 100.0) / max_cov) * pw
        out.append(f'<line x1="{x:.1f}" y1="{mt}" x2="{x:.1f}" y2="{mt+ph}" stroke="#e2e8f0" stroke-width="1"/>')
        out.append(f'<text x="{x:.1f}" y="{mt+ph+20}" text-anchor="middle" {STYLE_AXIS}>{pct}%</text>')
    for pct in [0, 10, 20, 30, 40]:
        y = mt + ph - ((pct / 100.0) / max_readm) * ph
        out.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{ml+pw}" y2="{y:.1f}" stroke="#e2e8f0" stroke-width="1"/>')
        out.append(f'<text x="{ml-10}" y="{y+4:.1f}" text-anchor="end" {STYLE_AXIS}>{pct}%</text>')

    out.append(f'<text x="{ml+pw/2:.1f}" y="{mt+ph+44}" text-anchor="middle" {STYLE_LABEL}>Payer Coverage Rate (% of Total Claim Cost)</text>')
    out.append(f'<text x="20" y="{mt+ph/2:.1f}" text-anchor="middle" {STYLE_LABEL} transform="rotate(-90 20 {mt+ph/2:.1f})">30-Day Inpatient Readmission Rate</text>')

    out.append(f'<line x1="{bx:.1f}" y1="{mt}" x2="{bx:.1f}" y2="{mt+ph}" stroke="#64748b" stroke-width="1.5" stroke-dasharray="5 4"/>')
    out.append(f'<text x="{bx+6:.1f}" y="{mt+34}" {STYLE_SMALL}>Avg Coverage: 25.8%</text>')
    out.append(f'<line x1="{ml}" y1="{gy:.1f}" x2="{ml+pw}" y2="{gy:.1f}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="5 4"/>')
    out.append(f'<text x="{ml+10}" y="{gy-6:.1f}" font-family="{FONT}" font-size="10" font-weight="600" fill="#d97706">Readmission Goal: 15.0%</text>')

    max_leak = max(p["margin_leakage"] for p in payers)

    offsets = {
        "Medicare": (18, -14),
        "Self-Pay / Uncompensated Care": (18, -10),
        "Blue Cross Blue Shield": (-16, -22),
        "Medicaid": (-10, -24),
        "Humana": (-12, -18),
        "Cigna Health": (14, 16),
        "UnitedHealthcare": (16, 4),
        "Aetna": (14, 4),
        "Dual Eligible": (12, -10),
        "Anthem": (12, -12),
    }

    for p in payers:
        rate = p["readmission_rate"] or 0.0
        cov = p["coverage_rate"]
        x = ml + (cov / max_cov) * pw
        y = mt + ph - (rate / max_readm) * ph
        r = 6 + math.sqrt(p["inpatient"]) * 0.95
        intensity = p["margin_leakage"] / max_leak
        if intensity > 0.7:
            fill = "#991b1b"
        elif intensity > 0.4:
            fill = "#dc2626"
        elif intensity > 0.2:
            fill = "#f97316"
        else:
            fill = "#64748b"

        if "Self-Pay" in p["payer_group"]:
            pts = f"{x:.1f},{y-r:.1f} {x+r:.1f},{y:.1f} {x:.1f},{y+r:.1f} {x-r:.1f},{y:.1f}"
            out.append(f'<polygon points="{pts}" fill="{fill}" fill-opacity="0.82" stroke="#1e293b" stroke-width="1.5"/>')
        else:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" fill-opacity="0.78" stroke="#1e293b" stroke-width="1.2"/>')

        dx, dy = offsets.get(p["payer_display"], (12, -8))
        short_name = "Self-Pay" if "Self-Pay" in p["payer_display"] else p["payer_display"]
        leak_k = f'${p["margin_leakage"]/1000:.1f}k'
        anchor = "end" if dx < 0 else "start"
        out.append(f'<text x="{x+dx:.1f}" y="{y+dy:.1f}" text-anchor="{anchor}" {STYLE_LABEL}>{esc(short_name)}</text>')
        out.append(f'<text x="{x+dx:.1f}" y="{y+dy+12:.1f}" text-anchor="{anchor}" {STYLE_SMALL}>{rate*100:.1f}% readm • {leak_k} uncov</text>')

    out.append(f'<text x="28" y="{h-12}" {STYLE_SMALL}>Medicare ($180.1k) and Self-Pay ($92.6k) account for 46.4% of total uncovered claim cost ($587.5k). Cigna &amp; UnitedHealthcare sit in the optimal quadrant.</text>')
    out.append("</svg>")
    with open(os.path.join(ASSETS_DIR, "view4_payer_quadrant.svg"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))


if __name__ == "__main__":
    build_view1_svg()
    build_view2_svg()
    build_view3_svg()
    build_view4_svg()
    print("Generated 4 SVG charts in", ASSETS_DIR)
