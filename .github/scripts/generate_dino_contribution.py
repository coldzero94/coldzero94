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
        "background": "#f7fbff",
        "panel": "#ecf6ff",
        "title": "#0f172a",
        "subtitle": "#1e3a8a",
        "meta": "#334155",
        "empty": "#dbe7f4",
        "empty_opacity": "0.65",
        "levels": ["#d9ffe9", "#8af0c7", "#3fd5a0", "#10b981", "#047857"],
        "ground": "#7c5d2b",
        "accent": "#0891b2",
    },
    "dark": {
        "background": "#06131b",
        "panel": "#0d2230",
        "title": "#d8fff0",
        "subtitle": "#7cf0c3",
        "meta": "#b7d4e6",
        "empty": "#173348",
        "empty_opacity": "0.7",
        "levels": ["#1e4c3a", "#1f9d6a", "#35c78d", "#67f0b8", "#c5ffe8"],
        "ground": "#d3a650",
        "accent": "#40d6ff",
    },
}


DINO_PATTERN = [
    ".......####...................",
    ".....##########...............",
    "...###############............",
    "..###################.........",
    "...###########..#####.........",
    ".....###...##....##...........",
    "..#####....##....##..###......",
]

CACTUS_PATTERN = [
    "..#..",
    ".###.",
    "..#..",
    ".###.",
    ".#.#.",
    ".#.#.",
    "#####",
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


def build_mask() -> set[tuple[int, int]]:
    mask: set[tuple[int, int]] = set()

    dino_offset_x = 23
    dino_offset_y = 0
    for dy, row in enumerate(DINO_PATTERN):
        for dx, ch in enumerate(row):
            if ch == "#":
                x = dino_offset_x + dx
                y = dino_offset_y + dy
                if 0 <= x < COLS and 0 <= y < ROWS:
                    mask.add((x, y))

    cactus_offsets = [4, 13]
    for offset_x in cactus_offsets:
        for dy, row in enumerate(CACTUS_PATTERN):
            for dx, ch in enumerate(row):
                if ch == "#":
                    x = offset_x + dx
                    y = dy
                    if 0 <= x < COLS and 0 <= y < ROWS:
                        mask.add((x, y))

    for x in range(COLS):
        mask.add((x, ROWS - 1))

    return mask


def thresholds_for(mask_counts: list[int]) -> tuple[int, int, int, int]:
    positives = sorted([count for count in mask_counts if count > 0])
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


def build_svg(grid: list[list[int]], theme_key: str) -> str:
    theme = THEMES[theme_key]
    mask = build_mask()
    mask_counts = [grid[y][x] for (x, y) in mask]
    t1, t2, t3, t4 = thresholds_for(mask_counts)

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
    lines.append("      <feGaussianBlur stdDeviation=\"3\"/>")
    lines.append("    </filter>")
    lines.append("  </defs>")

    lines.append(f'  <rect width="{WIDTH}" height="{HEIGHT}" rx="14" fill="url(#bg-{theme_key})"/>')
    lines.append(
        f'  <text x="{PAD_X}" y="36" fill="{theme["title"]}" font-size="22" '
        'font-family="monospace" font-weight="700">Dino Contribution Grid</text>'
    )
    lines.append(
        f'  <text x="{PAD_X}" y="56" fill="{theme["subtitle"]}" font-size="13" '
        'font-family="monospace">custom engine by coldzero94</text>'
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
            if (x, y) in mask:
                level = level_for(count, t1, t2, t3, t4)
                color = theme["levels"][level]
                lines.append(
                    f'  <rect x="{x_pos}" y="{y_pos}" width="{CELL}" height="{CELL}" rx="2" fill="{color}" />'
                )
                if level >= 3:
                    lines.append(
                        f'  <rect x="{x_pos}" y="{y_pos}" width="{CELL}" height="{CELL}" rx="2" '
                        f'fill="{color}" opacity="0.32" filter="url(#glow-{theme_key})" />'
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
