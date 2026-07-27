#!/usr/bin/env python3
"""
Automatic GitHub Profile README Updater
Analyzes all repositories and updates profile README with latest stats
"""

import itertools
import json
import math
import subprocess
import sys
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from collections import defaultdict
from typing import Dict, List, Tuple

# Donut colors. A language owns its hue, so a shuffle in the ranking never
# repaints the ring — the reader who learned "Go is blue" stays right. Ring
# ORDER is the colorblind-safety mechanism: only neighbouring segments touch,
# so the palette is checked pair-by-pair along the ring (no set of six hues
# clears an all-pairs gate, which is why the order carries the weight).
#
# These hues and the checks below are the data-viz skill's, verified with:
#   node scripts/validate_palette.js \
#     "#3987e5,#d95926,#199e70,#c98500,#9085e9,#6E7681" --mode dark --surface "#0d1117"
# → lightness band, CVD separation (worst adjacent ΔE 8.4, target 8), the
#   normal-vision floor (16.7, floor 15) and contrast all pass. Its one FAIL is
#   the chroma floor on the Others gray, which is deliberate: Others is the
#   de-emphasis color, not an identity hue.
#
# Nothing here needs hand-tending when a new language shows up. It claims a
# spare hue, and order_ring() re-measures the ring and re-orders it if the
# newcomer lands next to something it is too close to.
LANGUAGE_COLORS = {
    "Go": "#3987e5",          # blue
    "TypeScript": "#d95926",  # orange
    "Python": "#199e70",      # aqua
    "Kotlin": "#c98500",      # yellow
    "Swift": "#9085e9",       # violet
}
SPARE_COLORS = ["#d55181", "#008300", "#e66767"]  # magenta, green, red
OTHERS_COLOR = "#6E7681"

# OKLab ΔE ×100 floors, from the same skill: below these two neighbouring
# segments stop being tellable apart — the first for red/green colorblindness,
# the second for everyone else.
CVD_FLOOR, NORMAL_FLOOR = 6.0, 15.0

# Machado, Oliveira & Fernandes (2009) at severity 1.0, on linear RGB. The
# thresholds above are calibrated to this simulation, so it comes with them.
MACHADO = {
    "protan": ((0.152286, 1.052583, -0.204868),
               (0.114503, 0.786281, 0.099216),
               (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968),
               (0.280085, 0.672501, 0.047413),
               (-0.011820, 0.042940, 0.968881)),
}

LANG_DESCRIPTIONS = {
    'Python': 'AI/ML, FastAPI, Django',
    'TypeScript': 'Next.js, React, Node.js',
    'JavaScript': 'Frontend, Web',
    'Go': 'Backend, single-binary services',
    'Java': 'Backend, Spring',
    'Kotlin': 'Android, JVM services',
    'Swift': 'iOS, SwiftUI, macOS',
    'R': 'Data Analysis',
    'CSS': 'Styling',
    'Shell': 'Automation',
    'HTML': 'Web',
}


def run_command(cmd: List[str]) -> str:
    """Run shell command and return output"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(cmd)}")
        print(f"Error: {e.stderr}")
        sys.exit(1)


def get_all_repos() -> List[Dict]:
    """Fetch all repositories with language and update info"""
    print("🔍 Fetching all repositories...")

    cmd = [
        "gh", "repo", "list", "coldzero94",
        "--limit", "100",
        "--json", "name,description,primaryLanguage,languages,updatedAt,pushedAt,stargazerCount,isPrivate,isFork"
    ]

    output = run_command(cmd)
    repos = json.loads(output)

    print(f"✅ Found {len(repos)} repositories")
    return repos


def analyze_language_stats(repos: List[Dict]) -> Dict[str, int]:
    """Aggregate language statistics across all repos"""
    print("📊 Analyzing language statistics...")

    language_totals = defaultdict(int)

    for repo in repos:
        if repo.get('isFork'):
            continue  # upstream code isn't ours
        languages = repo.get('languages', [])
        for lang in languages:
            lang_name = lang['node']['name']
            lang_size = lang['size']
            language_totals[lang_name] += lang_size

    # Sort by size
    sorted_langs = dict(sorted(language_totals.items(), key=lambda x: x[1], reverse=True))

    total_size = sum(sorted_langs.values())
    print(f"✅ Total code: {total_size / 1_000_000:.1f} MB")

    return sorted_langs


def _oklab(hex_color: str, cvd: str = None) -> Tuple[float, float, float]:
    """OKLab coordinates of a hex color, optionally as a dichromat sees it"""
    raw = hex_color.lstrip("#")
    srgb = [int(raw[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    r, g, b = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]

    if cvd:
        m = MACHADO[cvd]
        r, g, b = [min(1.0, max(0.0, row[0] * r + row[1] * g + row[2] * b)) for row in m]

    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (
        0.2104542553 * l + 0.7936177850 * m_ - 0.0040720468 * s,
        1.9779984951 * l - 2.4285922050 * m_ + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m_ - 0.8086757660 * s,
    )


def _delta_e(a: str, b: str, cvd: str = None) -> float:
    """Perceptual distance between two colors — OKLab Euclidean, ×100"""
    return 100 * math.dist(_oklab(a, cvd), _oklab(b, cvd))


def ring_score(colors: List[str]) -> Tuple[float, float]:
    """Worst (colorblind, normal-vision) separation across the ring's seams.

    Only touching segments are compared, and the ring wraps, so the last
    segment is measured against the first.
    """
    if len(colors) < 2:
        return (99.0, 99.0)
    seams = [(colors[i], colors[(i + 1) % len(colors)]) for i in range(len(colors))]
    return (
        min(min(_delta_e(a, b, k) for k in MACHADO) for a, b in seams),
        min(_delta_e(a, b) for a, b in seams),
    )


def order_ring(segments: List[Dict]) -> List[Dict]:
    """Keep largest-first order while it is readable; re-order it when it is not.

    This is what keeps a new language from needing a hand re-validation: it is
    dropped in, the seams it creates get measured, and the ring gives up its
    natural order only when one of those seams is too close to call.
    """
    cvd, normal = ring_score([s["color"] for s in segments])
    if cvd >= CVD_FLOOR and normal >= NORMAL_FLOOR:
        print(f"   ring seams ok — worst ΔE {cvd:.1f} colorblind / {normal:.1f} normal")
        return segments

    best, best_score = segments, (cvd, normal)
    for candidate in itertools.permutations(segments):
        score = ring_score([s["color"] for s in candidate])
        if score > best_score:
            best, best_score = list(candidate), score

    print(f"   ⚠️  ring re-ordered: worst ΔE {cvd:.1f}/{normal:.1f} "
          f"→ {best_score[0]:.1f}/{best_score[1]:.1f} (floors {CVD_FLOOR}/{NORMAL_FLOOR})")
    return best


def build_language_segments(lang_stats: Dict[str, int]) -> List[Dict]:
    """Top 5 languages + Others, largest first, each with its own color.

    Position follows size, which is what a reader expects; the hue follows the
    language, so a shuffle in the ranking moves a segment without repainting it.
    """
    total = sum(lang_stats.values())
    if not total:
        return []

    top = dict(list(lang_stats.items())[:5])
    # A language nobody reserved a hue for claims a spare one — starting with
    # the hue freed by whichever reserved language it displaced.
    spares = [c for name, c in LANGUAGE_COLORS.items() if name not in top] + SPARE_COLORS

    segments = []
    for name, size in top.items():
        color = LANGUAGE_COLORS.get(name) or (spares.pop(0) if spares else OTHERS_COLOR)
        segments.append({
            "name": name,
            "color": color,
            "pct": size / total * 100,
            "desc": LANG_DESCRIPTIONS.get(name, "Development"),
        })

    tail = list(lang_stats.items())[5:]
    others_size = sum(size for _, size in tail)
    if others_size > 0:
        named = ", ".join(name for name, _ in tail[:3])
        segments.append({
            "name": "Others",
            "color": OTHERS_COLOR,
            "pct": others_size / total * 100,
            "desc": f"{named}, +{len(tail) - 3} more" if len(tail) > 3 else named,
        })

    return order_ring(segments)


def render_language_donut(segments: List[Dict], total_mb: float, repo_count: int) -> str:
    """Donut + legend as a standalone SVG.

    The hole holds the headline the chart is actually making — which language
    most of this code is — rather than a file size, which is a fact about disk
    and not about the work. The ring is the at-a-glance part-to-whole; the
    exact share is never left to the eye, since every segment is
    direct-labelled in the legend beside it.
    """
    cx, cy, r, width = 132, 125, 66, 22
    circumference = 2 * math.pi * r
    gap = 3.0  # surface gap between segments, not a border around them

    arcs = []
    cursor = 0.0
    for seg in segments:
        length = seg["pct"] / 100 * circumference
        arcs.append(
            f'  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{seg["color"]}"'
            f' stroke-width="{width}" stroke-dasharray="{max(length - gap, 1.5):.2f} {circumference:.2f}"'
            f' stroke-dashoffset="{-cursor:.2f}" transform="rotate(-90 {cx} {cy})"/>'
        )
        cursor += length

    rows = []
    for i, seg in enumerate(segments):
        y = 42 + i * 32
        rows.append(
            f'  <rect x="272" y="{y - 10}" width="12" height="12" rx="3" fill="{seg["color"]}"/>\n'
            f'  <text class="name" x="294" y="{y}">{seg["name"]}</text>\n'
            f'  <text class="pct" x="452" y="{y}">{seg["pct"]:.1f}%</text>\n'
            f'  <text class="desc" x="470" y="{y}">{seg["desc"]}</text>'
        )

    # The headline is the biggest named language — Others is a bucket, never
    # the answer to "what does he write?".
    named = [s for s in segments if s["name"] != "Others"]
    lead = max(named, key=lambda s: s["pct"]) if named else segments[0]

    label = " · ".join(f'{s["name"]} {s["pct"]:.1f}%' for s in segments)
    updated = datetime.now().strftime("%Y-%m-%d")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 840 250" width="840" height="250" role="img" aria-label="Share of code by language across coldzero94's {repo_count} non-fork repositories, {total_mb:.1f} MB in total. {lead["name"]} leads at {lead["pct"]:.1f}%. Full breakdown: {label}. Auto-updated {updated}.">
  <style>
    text {{ font: 13px ui-monospace, 'SF Mono', Menlo, Consolas, monospace; }}
    .name  {{ fill: #e6edf3; }}
    .pct   {{ fill: #e6edf3; text-anchor: end; font-variant-numeric: tabular-nums; }}
    .desc  {{ fill: #8b949e; font-size: 12px; }}
    .lead  {{ fill: #e6edf3; font-size: 20px; font-weight: 600; text-anchor: middle; }}
    .share {{ fill: #e6edf3; font-size: 13px; text-anchor: middle; }}
    .of    {{ fill: #8b949e; font-size: 10.5px; text-anchor: middle; }}
    .foot  {{ fill: #6e7681; font-size: 11.5px; }}
  </style>
  <rect x="0.5" y="0.5" width="839" height="249" rx="12" fill="#0d1117" stroke="#30363d"/>

  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#21262d" stroke-width="{width}"/>
{chr(10).join(arcs)}
  <text class="lead" x="{cx}" y="{cy - 11}">{lead["name"]}</text>
  <text class="share" x="{cx}" y="{cy + 7}">{lead["pct"]:.1f}%</text>
  <text class="of" x="{cx}" y="{cy + 23}">of my code</text>

{chr(10).join(rows)}
  <text class="foot" x="272" y="230">auto-updated {updated} · {total_mb:.1f} MB across {repo_count} repos, forks excluded</text>
</svg>
"""


def update_language_donut(lang_stats: Dict[str, int], repos: List[Dict]):
    """Regenerate assets/languages-donut.svg from the language totals"""
    print("🍩 Updating language donut...")
    segments = build_language_segments(lang_stats)
    if not segments:
        print("⚠️  No language data; keeping previous donut")
        return

    # Count the repos the byte totals actually came from — analyze_language_stats
    # skips forks, so counting everything would overstate the footer.
    repo_count = sum(1 for r in repos if not r.get("isFork"))
    total_mb = sum(lang_stats.values()) / 1_000_000
    with open("assets/languages-donut.svg", "w", encoding="utf-8") as f:
        f.write(render_language_donut(segments, total_mb, repo_count))
    print(f"✅ languages-donut.svg updated ({len(segments)} segments, "
          f"{total_mb:.1f} MB across {repo_count} repos)")


def update_readme_section(content: str, section_marker: str, new_content: str) -> str:
    """Update a specific section in README marked by comments"""
    start_marker = f"<!-- AUTO-UPDATE:{section_marker}:START -->"
    end_marker = f"<!-- AUTO-UPDATE:{section_marker}:END -->"

    # Check if markers exist
    if start_marker not in content or end_marker not in content:
        print(f"⚠️  Markers for {section_marker} not found")
        return content

    # Find positions
    start_idx = content.find(start_marker) + len(start_marker)
    end_idx = content.find(end_marker)

    if end_idx <= start_idx:
        print(f"❌ Invalid markers for {section_marker}")
        return content

    # Replace section
    updated = content[:start_idx] + "\n" + new_content + "\n" + content[end_idx:]

    return updated


def format_recent_pushes(repos: List[Dict], limit: int = 3) -> str:
    """One-line freshness signal: latest public non-fork repos by push date"""
    candidates = [
        r for r in repos
        if not r.get("isPrivate") and not r.get("isFork")
        and r.get("name") != "coldzero94" and r.get("pushedAt")
    ]
    candidates.sort(key=lambda r: r["pushedAt"], reverse=True)

    parts = []
    for repo in candidates[:limit]:
        date = repo["pushedAt"][:10]
        parts.append(f"[{repo['name']}](https://github.com/coldzero94/{repo['name']}) `{date}`")

    if not parts:
        return ""
    return "🔨 **Recent pushes:** " + " · ".join(parts)


def fetch_velog_writing(max_posts: int = 5, max_age_days: int = 540) -> str:
    """Latest writing section from the velog RSS feed.

    Returns an empty string when there are no sufficiently recent posts,
    which collapses the section entirely (a stale feed is worse than none).
    """
    url = "https://v2.velog.io/rss/@coldzero"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            root = ET.fromstring(resp.read())
    except Exception as e:
        print(f"⚠️  Could not fetch velog RSS ({e}); leaving writing section as-is")
        raise

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    rows = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = item.findtext("pubDate")
        if not (title and link and pub):
            continue
        published = parsedate_to_datetime(pub)
        if published < cutoff:
            continue
        rows.append(f"| {published.strftime('%Y-%m-%d')} | [{title}]({link}) |")
        if len(rows) >= max_posts:
            break

    if not rows:
        return ""
    return "## ✍️ Latest writing\n\n| Date | Post |\n| --- | --- |\n" + "\n".join(rows)


def fetch_contribution_days() -> List[Dict]:
    """Daily contribution counts for the past year via GraphQL"""
    query = (
        'query { user(login:"coldzero94") { contributionsCollection { '
        "contributionCalendar { totalContributions weeks { contributionDays "
        "{ date contributionCount } } } } } }"
    )
    output = run_command(["gh", "api", "graphql", "-f", f"query={query}"])
    calendar = json.loads(output)["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [d for w in calendar["weeks"] for d in w["contributionDays"]]
    days.sort(key=lambda d: d["date"])
    return days


def render_hero_stats(days: List[Dict]) -> str:
    """Render the status-bar contents of the terminal hero (text + sparkline)"""
    counts = [d["contributionCount"] for d in days]
    total = sum(counts)
    best_day = max(counts)
    avg = total / max(len(counts), 1)

    best_streak = streak = 0
    for c in counts:
        streak = streak + 1 if c > 0 else 0
        best_streak = max(best_streak, streak)

    # 30-day sparkline, right-aligned inside the status bar (y 314..334).
    # sqrt scale so a single huge day doesn't flatten every other bar.
    last30 = counts[-30:]
    max30 = max(max(last30), 1)
    greens = ["#0e4429", "#006d32", "#26a641", "#39d353"]
    bars = []
    for i, c in enumerate(last30):
        x = 609 + i * 7
        if c == 0:
            bars.append(f'<rect x="{x}" y="332" width="4" height="2" rx="1" fill="#30363d"/>')
        else:
            ratio = (c / max30) ** 0.5
            h = max(4, round(ratio * 20))
            color = greens[min(3, int(ratio * 4))]
            bars.append(f'<rect x="{x}" y="{334 - h}" width="4" height="{h}" rx="1" fill="{color}"/>')

    label = (
        f'<tspan class="n">{total:,}</tspan><tspan class="o"> contributions/yr</tspan>'
        f'<tspan class="o" dx="7">·</tspan>'
        f'<tspan class="n" dx="7">{best_day}</tspan><tspan class="o"> best day</tspan>'
        f'<tspan class="o" dx="7">·</tspan>'
        f'<tspan class="n" dx="7">{best_streak}d</tspan><tspan class="o"> streak</tspan>'
        f'<tspan class="o" dx="7">·</tspan>'
        f'<tspan class="n" dx="7">~{avg:.1f}</tspan><tspan class="o">/day</tspan>'
    )

    return (
        f'  <text class="st" x="24" y="328"><tspan class="p">❯</tspan><tspan dx="8">{label}</tspan></text>\n'
        f'  {"".join(bars)}\n'
    )


def update_hero_stats():
    """Refresh the live status bar inside assets/terminal-hero.svg"""
    print("📈 Updating hero status bar...")
    hero_path = "assets/terminal-hero.svg"
    try:
        days = fetch_contribution_days()
        stats = render_hero_stats(days)
    except Exception as e:
        print(f"⚠️  Could not build hero stats ({e}); keeping previous version")
        return

    with open(hero_path, "r", encoding="utf-8") as f:
        svg = f.read()

    pattern = r"(<!-- STATS:START -->\n)(.*?)(  <!-- STATS:END -->)"
    if not re.search(pattern, svg, re.DOTALL):
        print("⚠️  STATS markers not found in terminal-hero.svg")
        return
    svg = re.sub(pattern, r"\1" + stats + r"\3", svg, flags=re.DOTALL)

    with open(hero_path, "w", encoding="utf-8") as f:
        f.write(svg)
    print("✅ terminal-hero.svg status bar updated!")


def update_readme_simple(repos: List[Dict]):
    """Refresh the marker-delimited sections of README.md"""
    print("📝 Updating README.md...")

    readme_path = "README.md"

    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ README.md not found!")
        sys.exit(1)

    # Update 1: recent-pushes freshness line
    content = update_readme_section(content, "SHIPPING", format_recent_pushes(repos))

    # Update 2: latest writing from velog (section disappears when feed is stale)
    try:
        content = update_readme_section(content, "WRITING", fetch_velog_writing())
    except Exception:
        pass  # network hiccup: keep the previous section contents

    # Write back
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ README.md updated successfully!")


def main():
    """Main execution"""
    print("🚀 Starting automated profile update...")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Fetch and analyze
    repos = get_all_repos()
    lang_stats = analyze_language_stats(repos)

    # Update README
    update_readme_simple(repos)

    # Redraw the language donut
    update_language_donut(lang_stats, repos)

    # Update the hero's live status bar
    update_hero_stats()

    print("\n✨ Profile update complete!")
    print(f"📊 Languages: {len(lang_stats)}")


if __name__ == "__main__":
    main()
