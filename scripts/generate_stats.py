import json
import os
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


USERNAME = "vmose"
API = "https://api.github.com"

TOKEN = os.environ["GITHUB_TOKEN"]

OUTPUT = Path("profile/stats")
OUTPUT.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# GitHub API
# ---------------------------------------------------------

def github_get(url):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "vmose-profile-stats",
        },
    )

    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def github_graphql(query, variables):
    payload = json.dumps({
        "query": query,
        "variables": variables,
    }).encode()

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "vmose-profile-stats",
        },
    )

    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read())

    if "errors" in result:
        raise RuntimeError(result["errors"])

    return result["data"]


# ---------------------------------------------------------
# Data collection
# ---------------------------------------------------------

def get_user():
    return github_get(f"{API}/users/{USERNAME}")


def get_repositories():
    repositories = []

    page = 1

    while True:
        repos = github_get(
            f"{API}/users/{USERNAME}/repos"
            f"?per_page=100&page={page}&type=owner"
        )

        if not repos:
            break

        repositories.extend(repos)

        if len(repos) < 100:
            break

        page += 1

    return repositories


def get_languages(repositories):

    languages = Counter()

    for repo in repositories:

        if repo["fork"]:
            continue

        data = github_get(repo["languages_url"])

        for language, amount in data.items():
            languages[language] += amount

    return languages


def get_contributions():

    query = """
    query($login: String!) {
      user(login: $login) {

        contributionsCollection {

          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions

          contributionCalendar {

            totalContributions

            weeks {

              contributionDays {
                contributionCount
                date
              }

            }
          }
        }
      }
    }
    """

    data = github_graphql(
        query,
        {"login": USERNAME},
    )

    return data["user"]["contributionsCollection"]


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def esc(value):

    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def svg_start(width, height):

    return f"""
<svg xmlns="http://www.w3.org/2000/svg"
     width="{width}"
     height="{height}"
     viewBox="0 0 {width} {height}">

<rect
    width="100%"
    height="100%"
    rx="14"
    fill="#0d1117"
    stroke="#30363d"/>
"""


def svg_end():

    return "</svg>"


def text(x, y, value, size=14, color="#f0f6fc",
         weight="normal"):

    return f"""
<text
    x="{x}"
    y="{y}"
    font-family="Arial, Helvetica, sans-serif"
    font-size="{size}px"
    font-weight="{weight}"
    fill="{color}">
    {esc(value)}
</text>
"""


# ---------------------------------------------------------
# Overview card
# ---------------------------------------------------------

def generate_overview(user, contributions):

    width = 800
    height = 270

    svg = svg_start(width, height)

    svg += text(
        35,
        45,
        "GitHub Activity",
        26,
        "#f0f6fc",
        "bold",
    )

    stats = [

        (
            "Repositories",
            user["public_repos"],
        ),

        (
            "Contributions",
            contributions["contributionCalendar"]
            ["totalContributions"],
        ),

        (
            "Pull Requests",
            contributions["totalPullRequestContributions"],
        ),

        (
            "Code Reviews",
            contributions["totalPullRequestReviewContributions"],
        ),

        (
            "Issues",
            contributions["totalIssueContributions"],
        ),

        (
            "Commits",
            contributions["totalCommitContributions"],
        ),

        (
            "Followers",
            user["followers"],
        ),

        (
            "Following",
            user["following"],
        ),
    ]

    positions = [

        (45, 105),
        (240, 105),
        (435, 105),
        (630, 105),

        (45, 195),
        (240, 195),
        (435, 195),
        (630, 195),
    ]

    for (label, value), (x, y) in zip(stats, positions):

        svg += text(
            x,
            y,
            value,
            30,
            "#58a6ff",
            "bold",
        )

        svg += text(
            x,
            y + 25,
            label,
            12,
            "#8b949e",
        )

    svg += text(
        35,
        250,
        "Generated from GitHub data",
        11,
        "#6e7681",
    )

    svg += svg_end()

    (OUTPUT / "overview.svg").write_text(
        svg,
        encoding="utf-8",
    )


# ---------------------------------------------------------
# Contribution heatmap
# ---------------------------------------------------------

def generate_contributions(contributions):

    calendar = contributions["contributionCalendar"]

    width = 900
    height = 220

    svg = svg_start(width, height)

    svg += text(
        35,
        40,
        "Contribution Activity",
        24,
        "#f0f6fc",
        "bold",
    )

    days = []

    for week in calendar["weeks"]:

        for day in week["contributionDays"]:

            days.append(day)

    days.sort(
        key=lambda x: x["date"]
    )

    cell = 12
    gap = 3

    start_x = 35
    start_y = 70

    max_count = max(
        day["contributionCount"]
        for day in days
    )

    for index, day in enumerate(days):

        date = datetime.strptime(
            day["date"],
            "%Y-%m-%d",
        )

        week = index // 7
        weekday = date.weekday()

        x = start_x + week * (cell + gap)
        y = start_y + weekday * (cell + gap)

        count = day["contributionCount"]

        if count == 0:
            fill = "#161b22"

        elif count <= max_count * 0.25:
            fill = "#0e4429"

        elif count <= max_count * 0.50:
            fill = "#006d32"

        elif count <= max_count * 0.75:
            fill = "#26a641"

        else:
            fill = "#39d353"

        svg += f"""
<rect
    x="{x}"
    y="{y}"
    width="{cell}"
    height="{cell}"
    rx="2"
    fill="{fill}">
    <title>{esc(day["date"])}: {count} contributions</title>
</rect>
"""

    svg += text(
        35,
        190,
        f"{calendar['totalContributions']} contributions in the last year",
        12,
        "#8b949e",
    )

    svg += svg_end()

    (OUTPUT / "contributions.svg").write_text(
        svg,
        encoding="utf-8",
    )


# ---------------------------------------------------------
# Languages
# ---------------------------------------------------------

def generate_languages(languages):

    width = 800
    height = 340

    svg = svg_start(width, height)

    svg += text(
        35,
        45,
        "Top Languages",
        25,
        "#f0f6fc",
        "bold",
    )

    top = languages.most_common(8)

    total = sum(
        languages.values()
    )

    bar_x = 40
    bar_y = 70

    bar_width = 720
    bar_height = 16

    # Language bar

    current_x = bar_x

    language_colors = [
        "#3178c6",
        "#f1e05a",
        "#3572A5",
        "#e34c26",
        "#563d7c",
        "#89e051",
        "#DA5B0B",
        "#384d54",
    ]

    for index, (language, amount) in enumerate(top):

        percentage = amount / total

        width = bar_width * percentage

        color = language_colors[
            index % len(language_colors)
        ]

        svg += f"""
<rect
    x="{current_x}"
    y="{bar_y}"
    width="{width}"
    height="{bar_height}"
    fill="{color}"/>
"""

        current_x += width

    # Labels

    y = 125

    for index, (language, amount) in enumerate(top):

        percentage = (
            amount / total * 100
        )

        color = language_colors[
            index % len(language_colors)
        ]

        svg += f"""
<circle
    cx="48"
    cy="{y - 5}"
    r="5"
    fill="{color}"/>
"""

        svg += text(
            65,
            y,
            language,
            14,
            "#f0f6fc",
            "bold",
        )

        svg += text(
            300,
            y,
            f"{percentage:.1f}%",
            13,
            "#8b949e",
        )

        y += 27

    svg += svg_end()

    (OUTPUT / "languages.svg").write_text(
        svg,
        encoding="utf-8",
    )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    print("Fetching profile...")

    user = get_user()

    print("Fetching repositories...")

    repositories = get_repositories()

    print(
        f"Found {len(repositories)} repositories."
    )

    print("Calculating languages...")

    languages = get_languages(
        repositories
    )

    print("Fetching contributions...")

    contributions = get_contributions()

    print("Generating overview...")

    generate_overview(
        user,
        contributions,
    )

    print("Generating contribution heatmap...")

    generate_contributions(
        contributions
    )

    print("Generating language statistics...")

    generate_languages(
        languages
    )

    print("Done.")


if __name__ == "__main__":
    main()
