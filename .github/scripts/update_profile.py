#!/usr/bin/env python3
"""
Automatic GitHub Profile README Updater
Analyzes all repositories and updates profile README with latest stats
"""

import json
import subprocess
import sys
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from collections import defaultdict
from typing import Dict, List, Tuple


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


def format_language_stats(lang_stats: Dict[str, int]) -> Tuple[str, str, str]:
    """Format language statistics for README"""
    total_size = sum(lang_stats.values())
    total_mb = total_size / 1_000_000

    # Top languages with percentages
    top_langs = list(lang_stats.items())[:5]

    # Python dict format
    python_lines = []
    for lang, size in top_langs:
        size_mb = size / 1_000_000
        percentage = (size / total_size) * 100
        python_lines.append(f"    '{lang}': {size_mb:5.1f},  # {percentage:4.1f}%")

    python_format = "# Real data from all my repositories\nlanguages = {\n" + "\n".join(python_lines) + "\n}"

    # Bar chart format
    bar_lines = []
    lang_descriptions = {
        'Python': 'AI/ML, FastAPI, Django',
        'TypeScript': 'Next.js, React, Node.js',
        'JavaScript': 'Frontend, Web',
        'Go': 'Backend, Microservices',
        'Java': 'Backend, Spring',
        'R': 'Data Analysis',
        'CSS': 'Styling',
        'Shell': 'Automation',
        'HTML': 'Web',
    }

    for lang, size in top_langs:
        percentage = (size / total_size) * 100
        bar_length = int(percentage / 100 * 36)  # 36 chars max
        bar = '█' * bar_length + '░' * (36 - bar_length)

        desc = lang_descriptions.get(lang, 'Development')
        bar_lines.append(f"{lang:<12} {bar} {percentage:4.1f}%  ({desc})")

    # Add others if more than 5 languages
    if len(lang_stats) > 5:
        others_size = sum(size for lang, size in list(lang_stats.items())[5:])
        others_pct = (others_size / total_size) * 100
        bar_length = int(others_pct / 100 * 36)
        bar = '█' * bar_length + '░' * (36 - bar_length)
        bar_lines.append(f"{'Others':<12} {bar} {others_pct:4.1f}%  (Shell, Docker, Config)")

    bar_format = "\n".join(bar_lines)

    return python_format, bar_format, f"{total_mb:.1f}"


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


def update_readme_simple(lang_stats: Dict, repos: List[Dict]):
    """Update README.md with new language stats using simple pattern matching"""
    print("📝 Updating README.md...")

    readme_path = "README.md"

    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ README.md not found!")
        sys.exit(1)

    # Format data
    python_langs, bar_langs, total_mb = format_language_stats(lang_stats)

    # Update 1: Total MB line
    content = re.sub(
        r'\*\*Total Code Across All Repositories: [\d.]+ MB\*\*(?: _\(Auto-updated: [0-9-]+\)_)?',
        f'**Total Code Across All Repositories: {total_mb} MB** _(Auto-updated: {datetime.now().strftime("%Y-%m-%d")})_',
        content
    )

    # Update 2: Python code block with language stats
    python_pattern = r'(```python\n# Real data from all my repositories\nlanguages = \{)(.*?)(\}\n```)'
    if re.search(python_pattern, content, re.DOTALL):
        # Extract just the dict content
        dict_content = "\n" + "\n".join(python_langs.split('\n')[2:-1]) + "\n"
        content = re.sub(python_pattern, r'\1' + dict_content + r'\3', content, flags=re.DOTALL)

    # Update 3: Bar chart
    bar_pattern = r'(<!-- Custom Language Stats with Animation -->\n```\n)(.*?)(```\n\n</div>)'
    if re.search(bar_pattern, content, re.DOTALL):
        content = re.sub(bar_pattern, r'\1' + bar_langs + '\n' + r'\3', content, flags=re.DOTALL)

    # Update 4: recent-pushes freshness line
    content = update_readme_section(content, "SHIPPING", format_recent_pushes(repos))

    # Update 5: latest writing from velog (section disappears when feed is stale)
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
    update_readme_simple(lang_stats, repos)

    # Update the hero's live status bar
    update_hero_stats()

    print("\n✨ Profile update complete!")
    print(f"📊 Languages: {len(lang_stats)}")


if __name__ == "__main__":
    main()
