#!/usr/bin/env python3
"""One chart per lane for the spark-bench README, in light and dark.

Every number here is copied from the lane's dated report (linked in the README);
nothing is computed. Re-run after editing a number:

    python3 scripts/charts/make_lane_charts.py      # writes docs/images/lane-*.svg
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

OUT = Path(__file__).resolve().parents[2] / "docs" / "images"

for f in font_manager.findSystemFonts():
    if "/inter/" in f.lower():
        font_manager.fontManager.addfont(f)

THEMES = {
    "light": dict(bg="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#8a8984",
                  grid="#e6e5e0", new="#2a78d6", old="#b9b8b1", alt="#eb6834"),
    "dark": dict(bg="#1a1a19", ink="#ffffff", ink2="#c3c2b7", muted="#8f8e86",
                 grid="#33332f", new="#3987e5", old="#5b5a55", alt="#d95926"),
}


def style(t):
    plt.rcParams.update({
        "font.family": ["Inter", "DejaVu Sans"], "font.size": 12,
        "svg.fonttype": "path", "svg.hashsalt": "spark-bench", "axes.edgecolor": t["grid"],
        "axes.labelcolor": t["ink2"], "xtick.color": t["ink2"], "ytick.color": t["ink2"],
        "text.color": t["ink"],
    })


def frame(fig, t, title, sub):
    fig.patch.set_facecolor(t["bg"])
    fig.text(0.035, 0.93, title, fontsize=19, fontweight="bold", color=t["ink"], va="top")
    fig.text(0.035, 0.855, sub, fontsize=12, color=t["ink2"], va="top")


def axclean(ax, t, label):
    ax.set_facecolor(t["bg"])
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(t["grid"])
    ax.tick_params(length=0)
    ax.xaxis.grid(True, color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(label, loc="left", fontsize=13, fontweight="bold", color=t["ink"], pad=12)


def hbars(ax, t, cats, series, fmt="{:.0f}", xmax=None):
    """series: list of (name, values, colorkey, labels-or-None). Grouped horizontal bars."""
    n = len(series)
    h = 0.78 / n
    for i, (name, vals, ck, labels) in enumerate(series):
        ys = [c + (i - (n - 1) / 2) * h for c in range(len(cats))]
        ax.barh(ys, vals, height=h * 0.86, color=t[ck], label=name, edgecolor=t["bg"], linewidth=2)
        for y, v, k in zip(ys, vals, range(len(vals))):
            txt = labels[k] if labels else fmt.format(v)
            ax.text(v + (xmax or max(vals)) * 0.012, y, txt, va="center", fontsize=11,
                    color=t["ink"] if ck != "old" else t["ink2"],
                    fontweight="bold" if ck == "new" else "normal")
    ax.set_yticks(range(len(cats)))
    ax.set_yticklabels(cats, fontsize=12, color=t["ink"])
    ax.invert_yaxis()
    if xmax:
        ax.set_xlim(0, xmax)


def legend(fig, t, items, y=0.075):
    x = 0.035
    for name, ck in items:
        fig.patches.append(plt.Rectangle((x, y - 0.012), 0.014, 0.03, transform=fig.transFigure,
                                         color=t[ck], figure=fig))
        fig.text(x + 0.02, y, name, fontsize=11.5, color=t["ink2"], va="center")
        x += 0.03 + 0.0085 * len(name)


def save(fig, name, theme):
    fig.savefig(OUT / f"lane-{name}-{theme}.svg", facecolor=fig.get_facecolor(), metadata={"Date": None})
    plt.close(fig)


def two_panel(t):
    fig, (a, b) = plt.subplots(1, 2, figsize=(12, 5.2))
    fig.subplots_adjust(left=0.14, right=0.97, top=0.70, bottom=0.2, wspace=0.42)
    return fig, a, b


# ---- lanes -------------------------------------------------------------

def tensorfold(t, theme):
    fig, a, b = two_panel(t)
    frame(fig, t, "DeepSeek V4.1 Flash · TensorFold · 4× Spark",
          "Uncensored 2.9-bit EXL3 · 420K context · images · G19 + RoCE, live 2026-10-07")
    axclean(a, t, "Writing speed  (tok/s, higher is better)")
    hbars(a, t, ["Prose, 1k–160k", "Code, 1k–160k", "Code, short prompt", "4 users", "4 users, steady"],
          [("TensorFold", [66.5, 104.1, 123.2, 122.2, 199.8], "new", None),
           ("SGLang TP4/EP2", [37.8, 57.4, 0, 75.7, 0], "old", ["38", "57", "—", "76", "—"])], xmax=235)
    axclean(b, t, "Cold 160k-token prompt  (s, lower is better)")
    hbars(b, t, ["2026-10-04", "10-05 pipelined", "10-07 G19 (live)", "SGLang"],
          [("", [98.6, 39.1, 35.9, 50.1], "new", ["97–100 s", "39 s", "36 s", "48–52 s"])], xmax=125)
    for i in (0, 1, 3):
        b.patches[i].set_color(t["old"]); b.texts[i].set_color(t["ink2"]); b.texts[i].set_fontweight("normal")
    legend(fig, t, [("TensorFold (ours, 4 Sparks)", "new"), ("SGLang TP4/EP2 · earlier build", "old")])
    fig.text(0.97, 0.075, "1k–160k: geometric mean · short prompt / steady: m2bench, 2026-10-07", fontsize=10.5,
             color=t["muted"], ha="right", va="center")
    save(fig, "dsv41-tensorfold", theme)


def sglang(t, theme):
    fig, a, b = two_panel(t)
    fig.subplots_adjust(left=0.08)
    frame(fig, t, "DeepSeek V4.1 Flash · SGLang TP4 · 4× Spark",
          "Uncensored FP8 · Mia's kit · EP4 → EP2 depth sweep, 2026-10-02 · now the rollback")
    depths = ["1k", "20k", "40k", "80k", "160k"]
    for ax, name, ep4, ep2 in ((a, "Prose  (tok/s)", [35.9, 35.5, 34.5, 34.6, 34.1], [37.7, 38.0, 38.1, 37.1, 38.3]),
                               (b, "Code  (tok/s)", [55.7, 58.1, 52.9, 50.3, 47.5], [62.2, 56.9, 53.8, 59.9, 54.6])):
        axclean(ax, t, name)
        ax.yaxis.grid(True, color=t["grid"], linewidth=0.8); ax.xaxis.grid(False)
        ax.plot(depths, ep4, color=t["old"], lw=2, marker="o", ms=8, mec=t["bg"], mew=2)
        ax.plot(depths, ep2, color=t["new"], lw=2, marker="o", ms=8, mec=t["bg"], mew=2)
        ax.text(4.12, ep2[-1], f"EP2 {ep2[-1]:.1f}", va="center", fontsize=11, color=t["ink"], fontweight="bold")
        ax.text(4.12, ep4[-1], f"EP4 {ep4[-1]:.1f}", va="center", fontsize=11, color=t["ink2"])
        ax.set_xlim(-0.2, 4.9)
        lo = min(ep4 + ep2); ax.set_ylim(lo - 8 if lo > 40 else 30, max(ep4 + ep2) + 4)
        ax.set_xlabel("prompt depth", fontsize=11)
    legend(fig, t, [("TP4 / EP2 (selected)", "new"), ("TP4 / EP4", "old")], y=0.045)
    save(fig, "dsv41-sglang", theme)


def vllm(t, theme):
    fig, ax = plt.subplots(figsize=(12, 5.2))
    fig.subplots_adjust(left=0.14, right=0.97, top=0.70, bottom=0.12)
    frame(fig, t, "DeepSeek V4.1 Flash · vLLM TP4 champion · 4× Spark",
          "FP4 experts / FP8 dense · DSpark k=5 · 420k context · 2026-09-10 · staged fallback")
    axclean(ax, t, "One user, by task  (tok/s)  ·  4 users: 109 tok/s total  ·  6 users: 137")
    cats = ["Coding", "Format", "Math", "Reasoning", "JSON", "Prose", "Summary", "Narrative"]
    vals = [71.4, 71.2, 70.0, 58.6, 45.3, 31.7, 27.9, 27.7]
    hbars(ax, t, cats, [("C1", vals, "new", [f"{v:.1f}" for v in vals])], xmax=85)
    ax.set_yticklabels(cats, fontsize=11.5, color=t["ink"])
    save(fig, "dsv41-vllm", theme)


def qwen(t, theme):
    fig, a, b = two_panel(t)
    frame(fig, t, "Qwen 3.8 Flash Next · vLLM TP4 · 4× Spark",
          "Official NVIDIA NVFP4 · MTP k=4 + GEMV · 262k context · 2026-09-06 · stopped")
    axclean(a, t, "One user  (tok/s)")
    hbars(a, t, ["Code", "Prose"], [("k4 + GEMV", [91.3, 49.2], "new", None),
                                    ("k2 baseline", [70.7, 53.4], "old", None)], xmax=112)
    axclean(b, t, "Many users, total  (tok/s)")
    hbars(b, t, ["4 users", "8 users", "16 users"],
          [("k4 + GEMV", [247.9, 404.3, 600.5], "new", None),
           ("k2 baseline", [198.6, 344.4, 526.8], "old", None)], xmax=730)
    legend(fig, t, [("MTP k=4 + GEMV (served)", "new"), ("k=2 baseline, same campaign", "old")])
    save(fig, "qwen38", theme)


def glm(t, theme):
    fig, a, b = two_panel(t)
    frame(fig, t, "GLM 5.3 Flash · vLLM EXL3 TP4 · 4× Spark",
          "EXL3 4bpw · DFlash2 k=7 · 1M context · tuning 2026-09-02 → 03 · stopped")
    steps = ["before E2", "+ E2 kernel", "A", "C", "C, verified"]
    axclean(a, t, "Cold 100k-token prompt  (tok/s read)")
    hbars(a, t, steps, [("", [773, 1110, 1240, 1562, 1560], "new", None)], xmax=1900)
    a.patches[0].set_color(t["old"]); a.texts[0].set_color(t["ink2"]); a.texts[0].set_fontweight("normal")
    axclean(b, t, "4 users, total writing  (tok/s)")
    hbars(b, t, ["A", "B", "C", "C, verified"], [("", [107.9, 115.7, 117.0, 128.9], "new",
                                                  ["107.9", "115.7", "117.0", "128.9"])], xmax=155)
    b.patches[0].set_color(t["old"]); b.texts[0].set_color(t["ink2"]); b.texts[0].set_fontweight("normal")
    fig.text(0.035, 0.075, "A async scheduling + DFlash k=5   ·   B + mixed-prefill guard   ·   C + DFlash k=7",
             fontsize=11, color=t["muted"], va="center")
    save(fig, "glm53", theme)


def dsv4(t, theme):
    fig, ax = plt.subplots(figsize=(12, 5.2))
    fig.subplots_adjust(left=0.27, right=0.97, top=0.70, bottom=0.12)
    frame(fig, t, "DeepSeek V4 Flash · vLLM TP4 · 4× Spark",
          "Abliterated NVFP4 · MTP k=7 · 2026-08-16 · the original recipe, not serving")
    axclean(ax, t, "What speed you actually get  (tok/s, one user)  ·  4 users: 182 total")
    cats = ["Best case: short prompt, code", "5–10k prompt, code", "5–10k prompt, chat", "~50k prompt, deep session"]
    lo = [136.25, 79, 72, 66]; hi = [145.5, 93, 89, 74]
    mid = [(l + h) / 2 for l, h in zip(lo, hi)]
    hbars(ax, t, cats, [("", lo, "new", ["136 median · 145.5 peak", "79–93", "72–89", "66–74"])], xmax=200)
    for txt, h in zip(ax.texts, hi):
        txt.set_x(h + 3)
    for i, (l, h) in enumerate(zip(lo, hi)):
        ax.barh(i, h - l, left=l, height=0.78 * 0.86, color=t["new"], alpha=0.35, edgecolor=t["bg"], linewidth=2)
    ax.set_yticklabels(cats, fontsize=11.5, color=t["ink"])
    save(fig, "dsv4", theme)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for theme, t in THEMES.items():
        style(t)
        for fn in (tensorfold, sglang, vllm, qwen, glm, dsv4):
            fn(t, theme)
    print("wrote", sorted(p.name for p in OUT.glob("lane-*.svg")))
