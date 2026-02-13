#!/usr/bin/env python3
"""
Generate a custom dinosaur-themed contribution SVG.

Outputs:
- dist/github-contribution-grid-dino.svg
- dist/github-contribution-grid-dino-dark.svg
"""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.request


COLS = 53
ROWS = 7
CELL = 12
GAP = 3
PAD_X = 28
PAD_TOP = 78
PAD_BOTTOM = 28
WIDTH = PAD_X * 2 + COLS * CELL + (COLS - 1) * GAP
HEIGHT = PAD_TOP + ROWS * CELL + (ROWS - 1) * GAP + PAD_BOTTOM


THEMES = {
    "light": {
        "background": "#f6fbff",
        "panel": "#edf7ff",
        "title": "#0f172a",
        "subtitle": "#155e75",
        "meta": "#334155",
        "empty": "#dbe7f4",
        "empty_opacity": "0.64",
        "ground": "#8a6b34",
        "accent": "#0ea5e9",
        "palettes": {
            "dino": ["#dbffe9", "#8df0c8", "#43d9a4", "#12b981", "#047857"],
            "spike": ["#ffeecb", "#ffd27e", "#ffb347", "#f59e0b", "#b45309"],
            "roar": ["#e3f5ff", "#bae6fd", "#7dd3fc", "#38bdf8", "#0284c7"],
            "meteor": ["#ffe7cc", "#ffcc8a", "#ff9f4a", "#f97316", "#c2410c"],
            "cactus": ["#e3fbe8", "#b9f6ca", "#74e59f", "#22c55e", "#15803d"],
            "ground": ["#eadfc4", "#dbc59a", "#c7a66d", "#a9843f", "#7c5d2b"],
            "eye": ["#ffffff", "#fde68a", "#facc15", "#eab308", "#ca8a04"],
            "trail": ["#efe9ff", "#ddd1ff", "#bca7ff", "#9876ff", "#6d4aff"],
        },
    },
    "dark": {
        "background": "#06131b",
        "panel": "#0b2230",
        "title": "#d8fff0",
        "subtitle": "#7cf0c3",
        "meta": "#b7d4e6",
        "empty": "#173348",
        "empty_opacity": "0.70",
        "ground": "#d3a650",
        "accent": "#40d6ff",
        "palettes": {
            "dino": ["#1e4c3a", "#1f9d6a", "#35c78d", "#67f0b8", "#c5ffe8"],
            "spike": ["#4a3515", "#84560f", "#c47f14", "#f59e0b", "#ffd58a"],
            "roar": ["#153042", "#1f536d", "#1e90b8", "#22b7f5", "#97e8ff"],
            "meteor": ["#422816", "#844317", "#c55f19", "#f97316", "#ffc085"],
            "cactus": ["#123924", "#175d35", "#1f8d4a", "#31c76c", "#94ffc3"],
            "ground": ["#3f331f", "#6b542a", "#8f6f35", "#ba9143", "#e0b760"],
            "eye": ["#eefcff", "#d9fbff", "#baf9ff", "#9cf1ff", "#68e6ff"],
            "trail": ["#231b45", "#3d2c79", "#5e40bb", "#7c58e4", "#b89fff"],
        },
    },
}


DINO_BODY_PATTERN = [
    "...........DDD...............",
    ".........DDDDDDD.............",
    "......DDDDDDDDDDDDDD.........",
    "....DDDDDDDDDDDDDDDDDDD......",
    "...DDDDDDDDDD..DDDDDD........",
    ".....DDD...DD....DD..........",
    "..DDDDD....DD....DD..DDD.....",
]

DINO_SPIKE_PATTERN = [
    ".......S.S.S.S...............",
    ".....S.......S...............",
    "...S...........S.............",
    ".............................",
    ".............................",
    ".............................",
    ".............................",
]

ROAR_PATTERN = [
    "....RRR........",
    "..RRRRRRR......",
    "RRRRRRRRRRRR...",
    "..RRRRRRR......",
    "....RRR........",
]

METEOR_PATTERN = [
    "..M....",
    ".MMM...",
    "..M..M.",
]

CACTUS_PATTERN = [
    "..C..",
    ".CCC.",
    "..C..",
    ".CCC.",
    ".C.C.",
    ".C.C.",
    "CCCCC",
]

TRAIL_PATTERN = [
    "T..T..T..",
    ".T..T..T.",
]


def fetch_contributions(user_name: str, token: str) -> list[list[int]]:
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    payload = json.dumps(
        {"query": query, "variables": {"login": user_name}},
        separators=(",", ":"),
    ).encode("utf-8")

    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "coldzero94-dino-generator",
        },
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        body = json.loads(response.read().decode("utf-8"))

    if "errors" in body:
        raise RuntimeError(f"GraphQL error: {body['errors']}")

    weeks = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    week_counts: list[list[int]] = []
    for week in weeks:
        week_counts.append([day["contributionCount"] for day in week["contributionDays"]])

    recent = week_counts[-COLS:]
    if len(recent) < COLS:
        recent = [[0] * ROWS for _ in range(COLS - len(recent))] + recent

    grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]
    for x, week in enumerate(recent):
        for y in range(min(ROWS, len(week))):
            grid[y][x] = week[y]
    return grid


def fallback_contributions() -> list[list[int]]:
    today = dt.date.today().toordinal()
    grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]
    for y in range(ROWS):
        for x in range(COLS):
            value = (x * 19 + y * 31 + today) % 17
            grid[y][x] = max(0, value - 8)
    return grid


def stamp(
    scene: dict[tuple[int, int], str],
    pattern: list[str],
    offset_x: int,
    offset_y: int,
    part_key: str,
    token: str,
) -> None:
    for dy, row in enumerate(pattern):
        for dx, ch in enumerate(row):
            if ch != token:
                continue
            x = offset_x + dx
            y = offset_y + dy
            if 0 <= x < COLS and 0 <= y < ROWS:
                scene[(x, y)] = part_key


def build_scene() -> dict[tuple[int, int], str]:
    scene: dict[tuple[int, int], str] = {}

    for x in range(COLS):
        scene[(x, ROWS - 1)] = "ground"

    stamp(scene, METEOR_PATTERN, 6, 0, "meteor", "M")
    stamp(scene, METEOR_PATTERN, 1, 1, "meteor", "M")

    stamp(scene, CACTUS_PATTERN, 3, 0, "cactus", "C")
    stamp(scene, CACTUS_PATTERN, 12, 0, "cactus", "C")

    stamp(scene, TRAIL_PATTERN, 18, 4, "trail", "T")

    stamp(scene, DINO_BODY_PATTERN, 20, 0, "dino", "D")
    stamp(scene, DINO_SPIKE_PATTERN, 19, 0, "spike", "S")
    stamp(scene, ROAR_PATTERN, 38, 1, "roar", "R")

    scene[(46, 2)] = "eye"

    return scene


def thresholds_for(scene_counts: list[int]) -> tuple[int, int, int, int]:
    positives = sorted([count for count in scene_counts if count > 0])
    if not positives:
        return (1, 2, 3, 4)

    def pick(quantile: float) -> int:
        idx = int((len(positives) - 1) * quantile)
        return positives[idx]

    return (pick(0.25), pick(0.5), pick(0.75), pick(0.9))


def level_for(count: int, t1: int, t2: int, t3: int, t4: int) -> int:
    if count <= 0:
        return 0
    if count <= t1:
        return 1
    if count <= t2:
        return 2
    if count <= t3:
        return 3
    if count <= t4:
        return 4
    return 4


def color_for(theme: dict, part_key: str, level: int) -> str:
    palettes = theme["palettes"]
    palette = palettes.get(part_key, palettes["dino"])
    return palette[level]


def build_svg(grid: list[list[int]], theme_key: str) -> str:
    theme = THEMES[theme_key]
    scene = build_scene()
    scene_counts = [grid[y][x] for (x, y) in scene]
    t1, t2, t3, t4 = thresholds_for(scene_counts)

    lines: list[str] = []
    lines.append(
        f'<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" '
        'fill="none" xmlns="http://www.w3.org/2000/svg" role="img" '
        'aria-label="Dino contribution activity graph">'
    )
    lines.append("  <defs>")
    lines.append(
        f'    <linearGradient id="bg-{theme_key}" x1="0" y1="0" x2="{WIDTH}" y2="{HEIGHT}" '
        'gradientUnits="userSpaceOnUse">'
    )
    lines.append(f'      <stop stop-color="{theme["background"]}"/>')
    lines.append(f'      <stop offset="1" stop-color="{theme["panel"]}"/>')
    lines.append("    </linearGradient>")
    lines.append(f'    <filter id="glow-{theme_key}" x="-50%" y="-50%" width="200%" height="200%">')
    lines.append('      <feGaussianBlur stdDeviation="3"/>')
    lines.append("    </filter>")
    lines.append("  </defs>")

    lines.append(f'  <rect width="{WIDTH}" height="{HEIGHT}" rx="14" fill="url(#bg-{theme_key})"/>')
    lines.append(
        f'  <text x="{PAD_X}" y="36" fill="{theme["title"]}" font-size="22" '
        'font-family="monospace" font-weight="700">Dino Contribution: ROAR Edition</text>'
    )
    lines.append(
        f'  <text x="{PAD_X}" y="56" fill="{theme["subtitle"]}" font-size="13" '
        'font-family="monospace">custom silhouette engine by coldzero94</text>'
    )

    for x in range(COLS):
        if x % 4 == 0:
            x_pos = PAD_X + x * (CELL + GAP)
            lines.append(
                f'  <line x1="{x_pos}" y1="{PAD_TOP - 12}" x2="{x_pos}" y2="{HEIGHT - PAD_BOTTOM + 4}" '
                f'stroke="{theme["empty"]}" stroke-opacity="0.18" />'
            )

    for y in range(ROWS):
        for x in range(COLS):
            x_pos = PAD_X + x * (CELL + GAP)
            y_pos = PAD_TOP + y * (CELL + GAP)
            count = grid[y][x]
            part_key = scene.get((x, y))
            if part_key:
                level = level_for(count, t1, t2, t3, t4)
                color = color_for(theme, part_key, level)
                lines.append(
                    f'  <rect x="{x_pos}" y="{y_pos}" width="{CELL}" height="{CELL}" rx="2" fill="{color}" />'
                )
                if level >= 3 and part_key in {"dino", "spike", "roar", "meteor", "eye"}:
                    lines.append(
                        f'  <rect x="{x_pos}" y="{y_pos}" width="{CELL}" height="{CELL}" rx="2" '
                        f'fill="{color}" opacity="0.34" filter="url(#glow-{theme_key})" />'
                    )
            else:
                lines.append(
                    f'  <rect x="{x_pos}" y="{y_pos}" width="{CELL}" height="{CELL}" rx="2" '
                    f'fill="{theme["empty"]}" opacity="{theme["empty_opacity"]}" />'
                )

    ground_y = PAD_TOP + (ROWS - 1) * (CELL + GAP) + CELL + 8
    lines.append(
        f'  <line x1="{PAD_X}" y1="{ground_y}" x2="{WIDTH - PAD_X}" y2="{ground_y}" '
        f'stroke="{theme["ground"]}" stroke-width="2.4" stroke-linecap="round" />'
    )
    lines.append(
        f'  <circle cx="{WIDTH - PAD_X - 8}" cy="{PAD_TOP - 8}" r="5" fill="{theme["accent"]}" opacity="0.9" />'
    )
    lines.append(
        f'  <text x="{WIDTH - 248}" y="56" fill="{theme["subtitle"]}" font-size="12" '
        'font-family="monospace">OPEN-MOUTH T-REX + METEOR TRAIL</text>'
    )

    generated_at = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines.append(
        f'  <text x="{PAD_X}" y="{HEIGHT - 10}" fill="{theme["meta"]}" font-size="11" '
        f'font-family="monospace">Generated {generated_at}</text>'
    )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def write_svg(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)


def main() -> None:
    user_name = (
        os.getenv("GITHUB_USER_NAME")
        or os.getenv("GITHUB_REPOSITORY_OWNER")
        or os.getenv("GITHUB_REPOSITORY", "").split("/")[0]
        or "coldzero94"
    )
    token = os.getenv("GITHUB_TOKEN", "")

    try:
        if token and user_name:
            print(f"Fetching contribution data for: {user_name}")
            grid = fetch_contributions(user_name, token)
        else:
            raise RuntimeError("Missing token or user name")
    except (RuntimeError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"Falling back to local synthetic data: {exc}")
        grid = fallback_contributions()

    light_svg = build_svg(grid, "light")
    dark_svg = build_svg(grid, "dark")
    write_svg("dist/github-contribution-grid-dino.svg", light_svg)
    write_svg("dist/github-contribution-grid-dino-dark.svg", dark_svg)
    print("Generated dist/github-contribution-grid-dino.svg")
    print("Generated dist/github-contribution-grid-dino-dark.svg")


if __name__ == "__main__":
    main()
