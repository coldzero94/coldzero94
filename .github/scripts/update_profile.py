#!/usr/bin/env python3
"""
Automatic GitHub Profile README Updater
Analyzes all repositories and updates profile README with latest stats
"""

import json
import subprocess
import sys
import re
from datetime import datetime, timedelta
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
        "--json", "name,description,primaryLanguage,languages,updatedAt,pushedAt,stargazerCount,isPrivate"
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


def update_readme_simple(lang_stats: Dict):
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
    update_readme_simple(lang_stats)

    print("\n✨ Profile update complete!")
    print(f"📊 Languages: {len(lang_stats)}")


if __name__ == "__main__":
    main()
