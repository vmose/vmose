import json
import os
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


USERNAME = "vmose"

API_URL = "https://api.github.com"

OUTPUT_DIR = Path("profile/stats")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TOKEN = os.environ.get("GITHUB_TOKEN")

if not TOKEN:
    raise RuntimeError("GITHUB_TOKEN is not available")


def github_request(url):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "vmose-github-stats",
        },
    )

    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def graphql_request(query, variables):
    payload = json.dumps({
        "query": query,
        "variables": variables
    }).encode("utf-8")

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "vmose-github-stats",
        },
    )

    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read())

    if "errors" in result:
        raise RuntimeError(result["errors"])

    return result["data"]


def get_user():
    return github_request(f"{API_URL}/users/{USERNAME}")


def get_repositories():
    repositories = []

    page = 1

    while True:
        url = (
            f"{API_URL}/users/{USERNAME}/repos"
            f"?per_page=100&page={page}&type=owner"
        )

        batch = github_request(url)

        if not batch:
            break

        repositories.extend(batch)

        if len(batch) < 100:
            break

        page += 1

    return repositories


def get_languages(repositories):
    languages = Counter()

    for repo in repositories:
        if repo.get("fork"):
            continue

        url = repo["languages_url"]
        data = github_request(url)

        for language, bytes_count in data.items():
            languages[language] += bytes_count

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

    data = graphql_request(
        query,
        {"login": USERNAME}
    )

    return data["user"]["contributionsCollection"]


def calculate_streak(calendar):
    days = []

    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append({
                "date": day["date"],
                "count": day["contributionCount"]
            })

    days.sort(key=lambda x: x["date"])

    longest = 0
    current = 0

    for day in days:
        if day["count"] > 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0

    # Current streak.
    today = datetime.now(timezone.utc).date()

    by_date = {
        datetime.strptime(day["date"], "%Y-%m-%d").date(): day["count"]
        for day in days
    }

    current_streak = 0
    date = today

    while by_date.get(date, 0) > 0:
        current_streak += 1
        date -= timedelta(days=1)

    return current_streak, longest


def escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def svg_header(width, height):
    return f'''<svg
    xmlns="http://www.w3.org/2000/svg"
    width="{width}"
    height="{height}"
    viewBox="0 0 {width} {height}"
>
'''


def generate_stats(user, contributions):
    width = 700
    height = 220

    stats = [
        ("Repositories", user["public_repos"]),
        ("Followers", user["followers"]),
        ("Following", user["following"]),
        ("Contributions", contributions["contributionCalendar"]["totalContributions"]),
    ]

    svg = svg_header(width, height)

    svg += '''
    <rect width="100%" height="100%" rx="12"
          fill="#0d1117"
          stroke="#30363d"/>
    '''

    svg += '''
    <text x="35" y="45"
          font-family="Arial, sans-serif"
          font-size="24"
          font-weight="bold"
          fill="#f0f6fc">
        GitHub Stats
    </text>
    '''

    x_positions = [40, 205, 370, 535]

    for (label, value), x in zip(stats, x_positions):
        svg += f'''
        <text x="{x}" y="105"
              font-family="Arial, sans-serif"
              font-size="28"
              font-weight="bold"
              fill="#58a6ff">
            {escape(value)}
        </text>

        <text x="{x}" y="135"
              font-family="Arial, sans-serif"
              font-size="13"
              fill="#8b949e">
            {escape(label)}
        </text>
        '''

    svg += '''
    <text x="35" y="185"
          font-family="Arial, sans-serif"
          font-size="12"
          fill="#8b949e">
        Generated automatically by GitHub Actions
    </text>
    '''

    svg += "</svg>"

    (OUTPUT_DIR / "stats.svg").write_text(svg, encoding="utf-8")


def generate_streak(contributions):
    calendar = contributions["contributionCalendar"]

    current, longest = calculate_streak(calendar)

    width = 700
    height = 220

    svg = svg_header(width, height)

    svg += '''
    <rect width="100%" height="100%" rx="12"
          fill="#0d1117"
          stroke="#30363d"/>
    '''

    svg += '''
    <text x="35" y="45"
          font-family="Arial, sans-serif"
          font-size="24"
          font-weight="bold"
          fill="#f0f6fc">
        Contribution Streak
    </text>
    '''

    svg += f'''
    <text x="40" y="105"
          font-family="Arial, sans-serif"
          font-size="38"
          font-weight="bold"
          fill="#58a6ff">
        {current}
    </text>

    <text x="40" y="135"
          font-family="Arial, sans-serif"
          font-size="13"
          fill="#8b949e">
        Current streak
    </text>

    <text x="350" y="105"
          font-family="Arial, sans-serif"
          font-size="38"
          font-weight="bold"
          fill="#58a6ff">
        {longest}
    </text>

    <text x="350" y="135"
          font-family="Arial, sans-serif"
          font-size="13"
          fill="#8b949e">
        Longest streak
    </text>
    '''

    svg += '''
    <text x="35" y="185"
          font-family="Arial, sans-serif"
          font-size="12"
          fill="#8b949e">
        Based on GitHub contribution activity
    </text>
    '''

    svg += "</svg>"

    (OUTPUT_DIR / "streak.svg").write_text(svg, encoding="utf-8")


def generate_languages(languages):
    width = 700
    height = 300

    top_languages = languages.most_common(8)

    total = sum(languages.values())

    svg = svg_header(width, height)

    svg += '''
    <rect width="100%" height="100%" rx="12"
          fill="#0d1117"
          stroke="#30363d"/>
    '''

    svg += '''
    <text x="35" y="45"
          font-family="Arial, sans-serif"
          font-size="24"
          font-weight="bold"
          fill="#f0f6fc">
        Top Languages
    </text>
    '''

    y = 85

    for language, bytes_count in top_languages:
        percentage = (bytes_count / total * 100) if total else 0

        bar_width = percentage * 4.5

        svg += f'''
        <text x="40" y="{y}"
              font-family="Arial, sans-serif"
              font-size="13"
              fill="#f0f6fc">
            {escape(language)}
        </text>

        <rect x="160" y="{y - 12}"
              width="450"
              height="12"
              rx="6"
              fill="#21262d"/>

        <rect x="160" y="{y - 12}"
              width="{bar_width}"
              height="12"
              rx="6"
              fill="#58a6ff"/>

        <text x="625" y="{y}"
              font-family="Arial, sans-serif"
              font-size="12"
              fill="#8b949e">
            {percentage:.1f}%
        </text>
        '''

        y += 27

    svg += "</svg>"

    (OUTPUT_DIR / "top-langs.svg").write_text(svg, encoding="utf-8")


def main():
    print("Fetching GitHub profile...")

    user = get_user()

    print("Fetching repositories...")

    repositories = get_repositories()

    print(f"Found {len(repositories)} repositories.")

    print("Calculating languages...")

    languages = get_languages(repositories)

    print("Fetching contribution data...")

    contributions = get_contributions()

    print("Generating SVGs...")

    generate_stats(user, contributions)
    generate_streak(contributions)
    generate_languages(languages)

    print("Stats generated successfully.")


if __name__ == "__main__":
    main()
