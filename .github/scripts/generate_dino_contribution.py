#!/usr/bin/env python3
"""
Generate a custom dinosaur-themed contribution SVG.

Outputs:
- dist/github-contribution-grid-dino.svg
- dist/github-contribution-grid-dino-dark.svg
- dist/github-contribution-grid-dino.gif
- dist/github-contribution-grid-dino-dark.gif
"""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.request

try:
    from PIL import Image, ImageDraw

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


COLS = 53
ROWS = 7
CELL = 12
GAP = 3
PAD_X = 28
PAD_TOP = 78
PAD_BOTTOM = 28
WIDTH = PAD_X * 2 + COLS * CELL + (COLS - 1) * GAP
HEIGHT = PAD_TOP + ROWS * CELL + (ROWS - 1) * GAP + PAD_BOTTOM
RUN_BOUNCE_Y = (0, -1, 0, 1)
METEOR_OFFSETS = ((0, 0), (1, -1), (2, -1), (1, 0), (0, 1), (-1, 1), (0, 0), (1, -1))
ROAR_ALPHA = [0.35, 1.0, 0.5, 1.0, 0.35, 0.85, 0.45, 0.95]
GIF_FRAME_COUNT = 24
GIF_DURATION_MS = 90
GIF_DOWNSCALE = 0.72
GIF_PALETTE_COLORS = 88


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

DINO_LEG_A_PATTERN = [
    ".............................",
    ".............................",
    ".............................",
    ".............................",
    ".............................",
    ".................A...A.......",
    "................AA..AA.......",
]

DINO_LEG_B_PATTERN = [
    ".............................",
    ".............................",
    ".............................",
    ".............................",
    ".............................",
    "................A.....A......",
    "...............AA....AA......",
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
    pattern: list[str],
    offset_x: int,
    offset_y: int,
    token: str,
) -> set[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    for dy, row in enumerate(pattern):
        for dx, ch in enumerate(row):
            if ch != token:
                continue
            x = offset_x + dx
            y = offset_y + dy
            if 0 <= x < COLS and 0 <= y < ROWS:
                cells.add((x, y))
    return cells


def build_scene() -> dict[str, set[tuple[int, int]]]:
    scene: dict[str, set[tuple[int, int]]] = {
        "ground": {(x, ROWS - 1) for x in range(COLS)},
        "meteor": stamp(METEOR_PATTERN, 6, 0, "M") | stamp(METEOR_PATTERN, 1, 1, "M"),
        "cactus": stamp(CACTUS_PATTERN, 3, 0, "C") | stamp(CACTUS_PATTERN, 12, 0, "C"),
        "trail": stamp(TRAIL_PATTERN, 18, 4, "T"),
        "dino": stamp(DINO_BODY_PATTERN, 20, 0, "D"),
        "spike": stamp(DINO_SPIKE_PATTERN, 19, 0, "S"),
        "leg_a": stamp(DINO_LEG_A_PATTERN, 20, 0, "A"),
        "leg_b": stamp(DINO_LEG_B_PATTERN, 20, 0, "A"),
        "roar": stamp(ROAR_PATTERN, 38, 1, "R"),
        "eye": {(46, 2)},
    }
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


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))


def rgba(color: str, alpha: float = 1.0) -> tuple[int, int, int, int]:
    r, g, b = hex_to_rgb(color)
    a = max(0, min(255, int(alpha * 255)))
    return (r, g, b, a)


def lerp_color(color_a: str, color_b: str, t: float) -> tuple[int, int, int, int]:
    ar, ag, ab = hex_to_rgb(color_a)
    br, bg, bb = hex_to_rgb(color_b)
    return (
        int(ar + (br - ar) * t),
        int(ag + (bg - ag) * t),
        int(ab + (bb - ab) * t),
        255,
    )


def build_colored_parts(
    grid: list[list[int]],
    theme: dict,
    scene: dict[str, set[tuple[int, int]]],
    t1: int,
    t2: int,
    t3: int,
    t4: int,
) -> dict[str, list[tuple[int, int, str, int]]]:
    parts: dict[str, list[tuple[int, int, str, int]]] = {}
    for part_key, cells in scene.items():
        items: list[tuple[int, int, str, int]] = []
        for x, y in sorted(cells, key=lambda pos: (pos[1], pos[0])):
            level = level_for(grid[y][x], t1, t2, t3, t4)
            color = color_for(theme, part_key, level)
            items.append((x, y, color, level))
        parts[part_key] = items
    return parts


def draw_cells(
    draw: "ImageDraw.ImageDraw",
    cells: list[tuple[int, int, str, int]],
    dx: int = 0,
    dy: int = 0,
    alpha: float = 1.0,
) -> None:
    for x, y, color, _level in cells:
        px = PAD_X + (x + dx) * (CELL + GAP)
        py = PAD_TOP + (y + dy) * (CELL + GAP)
        if px > WIDTH or py > HEIGHT or px + CELL < 0 or py + CELL < 0:
            continue
        draw.rectangle((px, py, px + CELL, py + CELL), fill=rgba(color, alpha))


def build_gif_frames(
    grid: list[list[int]],
    theme_key: str,
    frame_count: int = GIF_FRAME_COUNT,
) -> list["Image.Image"]:
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow is required to build GIF frames")

    theme = THEMES[theme_key]
    scene = build_scene()
    occupied: set[tuple[int, int]] = set()
    for cells in scene.values():
        occupied |= cells

    scene_counts = [grid[y][x] for (x, y) in occupied]
    t1, t2, t3, t4 = thresholds_for(scene_counts)
    part_data = build_colored_parts(grid, theme, scene, t1, t2, t3, t4)

    frames: list["Image.Image"] = []

    resampling = getattr(Image, "Resampling", Image).LANCZOS
    runner_parts = ("dino", "spike", "eye", "leg_a", "leg_b", "roar")
    runner_cells = [
        cell
        for part_name in runner_parts
        for cell in part_data.get(part_name, [])
    ]
    runner_min_x = min(cell[0] for cell in runner_cells)
    runner_max_x = max(cell[0] for cell in runner_cells)
    runner_width = runner_max_x - runner_min_x + 1
    run_path_start = -runner_width - 3
    run_path_end = COLS + 3
    run_path_span = run_path_end - run_path_start
    runner_phases = (0.0, 0.5)

    for frame_idx in range(frame_count):
        image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image, "RGBA")

        # Vertical gradient background for a premium look with GIF-safe rendering.
        denom = max(1, HEIGHT - 1)
        for y in range(HEIGHT):
            t = y / denom
            draw.line((0, y, WIDTH, y), fill=lerp_color(theme["background"], theme["panel"], t))

        draw.text((PAD_X, 14), "DINO MODE: I BREAK THROUGH EVERY OBSTACLE", fill=rgba(theme["title"]))
        draw.text((PAD_X, 34), "No brakes. No excuses. Just relentless shipping.", fill=rgba(theme["subtitle"]))

        for x in range(COLS):
            if x % 4 != 0:
                continue
            px = PAD_X + x * (CELL + GAP)
            draw.line(
                (px, PAD_TOP - 12, px, HEIGHT - PAD_BOTTOM + 4),
                fill=rgba(theme["empty"], 0.18),
                width=1,
            )

        for y in range(ROWS):
            for x in range(COLS):
                if (x, y) in occupied:
                    continue
                px = PAD_X + x * (CELL + GAP)
                py = PAD_TOP + y * (CELL + GAP)
                draw.rectangle(
                    (px, py, px + CELL, py + CELL),
                    fill=rgba(theme["empty"], float(theme["empty_opacity"])),
                )

        meteor_dx, meteor_dy = METEOR_OFFSETS[frame_idx % len(METEOR_OFFSETS)]

        for part in ("ground", "cactus", "trail"):
            draw_cells(draw, part_data.get(part, []))

        draw_cells(draw, part_data.get("meteor", []), dx=meteor_dx, dy=meteor_dy, alpha=0.95)
        for runner_idx, phase in enumerate(runner_phases):
            progress = ((frame_idx / frame_count) + phase) % 1.0
            runner_front_x = int(round(run_path_start + progress * run_path_span))
            run_dx = runner_front_x - runner_min_x
            run_dy = RUN_BOUNCE_Y[(frame_idx + runner_idx * 2) % len(RUN_BOUNCE_Y)]
            runner_alpha = 1.0 if runner_idx == 0 else 0.9

            draw_cells(draw, part_data.get("dino", []), dx=run_dx, dy=run_dy, alpha=runner_alpha)
            draw_cells(draw, part_data.get("spike", []), dx=run_dx, dy=run_dy, alpha=runner_alpha)
            draw_cells(draw, part_data.get("eye", []), dx=run_dx, dy=run_dy, alpha=runner_alpha)

            use_leg_a = (frame_idx + runner_idx) % 2 == 0
            if use_leg_a:
                draw_cells(draw, part_data.get("leg_a", []), dx=run_dx, dy=run_dy, alpha=runner_alpha)
            else:
                draw_cells(draw, part_data.get("leg_b", []), dx=run_dx, dy=run_dy, alpha=runner_alpha)

            if runner_idx == 0 and 0.20 <= progress <= 0.82:
                roar_alpha = ROAR_ALPHA[frame_idx % len(ROAR_ALPHA)]
                roar_shift_x = run_dx + (1 if frame_idx % 3 == 0 else 0)
                draw_cells(
                    draw,
                    part_data.get("roar", []),
                    dx=roar_shift_x,
                    dy=run_dy,
                    alpha=roar_alpha,
                )

        ground_y = PAD_TOP + (ROWS - 1) * (CELL + GAP) + CELL + 8
        draw.line((PAD_X, ground_y, WIDTH - PAD_X, ground_y), fill=rgba(theme["ground"]), width=2)
        draw.ellipse(
            (WIDTH - PAD_X - 13, PAD_TOP - 13, WIDTH - PAD_X - 3, PAD_TOP - 3),
            fill=rgba(theme["accent"]),
        )
        draw.text((WIDTH - 390, 34), "CONTINUOUS FORWARD LOOP + DUAL DINO STREAM", fill=rgba(theme["subtitle"]))

        generated_at = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        draw.text((PAD_X, HEIGHT - 18), f"Generated {generated_at}", fill=rgba(theme["meta"]))

        if GIF_DOWNSCALE < 1.0:
            target_size = (
                max(1, int(WIDTH * GIF_DOWNSCALE)),
                max(1, int(HEIGHT * GIF_DOWNSCALE)),
            )
            image = image.resize(target_size, resample=resampling)

        image = image.convert("P", palette=Image.ADAPTIVE, colors=GIF_PALETTE_COLORS)
        frames.append(image)

    return frames


def write_gif(path: str, frames: list["Image.Image"], duration_ms: int = GIF_DURATION_MS) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not frames:
        raise RuntimeError("No GIF frames to write")
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=duration_ms,
        disposal=2,
        optimize=True,
    )


def build_svg(grid: list[list[int]], theme_key: str) -> str:
    theme = THEMES[theme_key]
    scene = build_scene()
    occupied: set[tuple[int, int]] = set()
    for cells in scene.values():
        occupied |= cells

    scene_counts = [grid[y][x] for (x, y) in occupied]
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

    empty_cells: list[str] = []
    for y in range(ROWS):
        for x in range(COLS):
            if (x, y) in occupied:
                continue
            x_pos = PAD_X + x * (CELL + GAP)
            y_pos = PAD_TOP + y * (CELL + GAP)
            empty_cells.append(
                f'<rect x="{x_pos}" y="{y_pos}" width="{CELL}" height="{CELL}" rx="2" '
                f'fill="{theme["empty"]}" opacity="{theme["empty_opacity"]}" />'
            )

    part_rects: dict[str, list[str]] = {}
    for part_key, cells in scene.items():
        cells_svg: list[str] = []
        for x, y in sorted(cells, key=lambda pos: (pos[1], pos[0])):
            x_pos = PAD_X + x * (CELL + GAP)
            y_pos = PAD_TOP + y * (CELL + GAP)
            level = level_for(grid[y][x], t1, t2, t3, t4)
            color = color_for(theme, part_key, level)
            cells_svg.append(
                f'<rect x="{x_pos}" y="{y_pos}" width="{CELL}" height="{CELL}" rx="2" fill="{color}" />'
            )
            if level >= 3 and part_key in {"dino", "spike", "roar", "meteor", "eye", "leg_a", "leg_b"}:
                cells_svg.append(
                    f'<rect x="{x_pos}" y="{y_pos}" width="{CELL}" height="{CELL}" rx="2" '
                    f'fill="{color}" opacity="0.34" filter="url(#glow-{theme_key})" />'
                )
        part_rects[part_key] = cells_svg

    for cell in empty_cells:
        lines.append(f"  {cell}")

    lines.append('  <g id="terrain-layer">')
    for part in ("ground", "cactus", "trail"):
        for rect in part_rects.get(part, []):
            lines.append(f"    {rect}")
    lines.append("  </g>")

    lines.append('  <g id="meteor-layer">')
    for rect in part_rects.get("meteor", []):
        lines.append(f"    {rect}")
    lines.append(
        '    <animateTransform attributeName="transform" type="translate" '
        'values="0 0; 2 -1; 4 -1; 1 0; 0 1; -1 1; 0 0" dur="1.7s" repeatCount="indefinite" />'
    )
    lines.append("  </g>")

    lines.append('  <g id="dino-runner">')
    for part in ("dino", "spike", "eye"):
        for rect in part_rects.get(part, []):
            lines.append(f"    {rect}")
    lines.append(
        '    <animateTransform attributeName="transform" type="translate" '
        'values="-28 0; -18 -1; -8 0; 4 1; 16 0; 28 -1; 40 0; 52 1; -28 0" '
        'dur="2.2s" repeatCount="indefinite" />'
    )
    lines.append("  </g>")

    lines.append('  <g id="leg-a-layer">')
    for rect in part_rects.get("leg_a", []):
        lines.append(f"    {rect}")
    lines.append('    <animate attributeName="opacity" values="1;0;1" dur="0.39s" repeatCount="indefinite" />')
    lines.append(
        '    <animateTransform attributeName="transform" type="translate" '
        'values="-28 0; -18 -1; -8 0; 4 1; 16 0; 28 -1; 40 0; 52 1; -28 0" '
        'dur="2.2s" repeatCount="indefinite" />'
    )
    lines.append("  </g>")

    lines.append('  <g id="leg-b-layer" opacity="0">')
    for rect in part_rects.get("leg_b", []):
        lines.append(f"    {rect}")
    lines.append('    <animate attributeName="opacity" values="0;1;0" dur="0.39s" repeatCount="indefinite" />')
    lines.append(
        '    <animateTransform attributeName="transform" type="translate" '
        'values="-28 0; -18 -1; -8 0; 4 1; 16 0; 28 -1; 40 0; 52 1; -28 0" '
        'dur="2.2s" repeatCount="indefinite" />'
    )
    lines.append("  </g>")

    lines.append('  <g id="roar-layer">')
    for rect in part_rects.get("roar", []):
        lines.append(f"    {rect}")
    lines.append(
        '    <animate attributeName="opacity" values="0.35;1;0.5;1;0.35" '
        'dur="0.74s" repeatCount="indefinite" />'
    )
    lines.append("  </g>")

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
        'font-family="monospace">BREAKING LIMITS, SHATTERING OBSTACLES</text>'
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

    if PIL_AVAILABLE:
        light_frames = build_gif_frames(grid, "light")
        dark_frames = build_gif_frames(grid, "dark")
        write_gif("dist/github-contribution-grid-dino.gif", light_frames)
        write_gif("dist/github-contribution-grid-dino-dark.gif", dark_frames)
        print("Generated dist/github-contribution-grid-dino.gif")
        print("Generated dist/github-contribution-grid-dino-dark.gif")
    else:
        print("Pillow not installed. GIF outputs were skipped.")


if __name__ == "__main__":
    main()
