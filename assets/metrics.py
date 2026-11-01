"""Renders assets/metrics-{light,dark}.svg from the public GitHub GraphQL data of USER.
Refreshed weekly by .github/workflows/metrics.yml.
Local run: GITHUB_TOKEN=$(gh auth token) python3 assets/metrics.py"""
import datetime, json, os, string, urllib.request
from collections import Counter
from html import escape
from pathlib import Path

from banners import SANS, THEMES, W, font

USER = "cric96"
# one hue per chart (contributions, languages), validated with the dataviz palette checker
ACCENT = {"light": ("#7c3aed", "#0284c7"), "dark": ("#9061f9", "#0b9fd6")}
GRID = {"light": "#dbe1ea", "dark": "#262f4d"}


def gql(query, **variables):
    req = urllib.request.Request("https://api.github.com/graphql", json.dumps({"query": query, "variables": variables}).encode(),
                                 {"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}"})
    data = json.load(urllib.request.urlopen(req))
    if "errors" in data:
        raise SystemExit(data["errors"])
    return data["data"]["user"]


def fetch():
    u = gql("""query($l:String!){user(login:$l){createdAt pullRequests{totalCount}
        repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,ISSUE,PULL_REQUEST_REVIEW]){totalCount}
        repositories(privacy:PUBLIC, ownerAffiliations:OWNER){totalCount}}}""", l=USER)
    first, now = int(u["createdAt"][:4]), datetime.date.today().year
    years = " ".join(f'y{y}: contributionsCollection(from:"{y}-01-01T00:00:00Z", to:"{y}-12-31T23:59:59Z")'
                     "{contributionCalendar{totalContributions}}" for y in range(first, now + 1))
    per_year = {int(k[1:]): v["contributionCalendar"]["totalContributions"]
                for k, v in gql(f"query($l:String!){{user(login:$l){{{years}}}}}", l=USER).items()}
    langs, cursor = Counter(), None
    while True:
        r = gql("""query($l:String!,$c:String){user(login:$l){repositories(privacy:PUBLIC, ownerAffiliations:OWNER,
            isFork:false, first:100, after:$c){pageInfo{hasNextPage endCursor} nodes{primaryLanguage{name}}}}}""", l=USER, c=cursor)["repositories"]
        langs.update(n["primaryLanguage"]["name"] for n in r["nodes"] if n["primaryLanguage"])
        if not r["pageInfo"]["hasNextPage"]:
            break
        cursor = r["pageInfo"]["endCursor"]
    return dict(since=first, prs=u["pullRequests"]["totalCount"], contributed=u["repositoriesContributedTo"]["totalCount"],
                repos=u["repositories"]["totalCount"], per_year=per_year, langs=langs.most_common(6))


def compact(n):
    return f"{n / 1000:.1f}K" if n >= 10_000 else f"{n:,}"


def render(theme, m, fonts, h=510):
    c, (acc_years, acc_langs), grid = THEMES[theme], ACCENT[theme], GRID[theme]
    txt = lambda x, y, s, size, fill, weight=400, anchor="start": (
        f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(str(s))}</text>')
    out = []

    tiles = [(compact(sum(m["per_year"].values())), f"Contributions since {m['since']}"), (compact(m["prs"]), "Pull requests"),
             (compact(m["contributed"]), "Repos contributed to"), (compact(m["repos"]), "Public repos")]
    for i, (value, label) in enumerate(tiles):
        x = 48 + i * 282
        out += [txt(x, 104, value, 58, c["text"], 700), txt(x, 142, label, 21, c["muted"])]
    out.append(f'<path d="M48 186H{W - 48}" stroke="{grid}"/>')

    # contributions per year: columns, single hue, square at the baseline and rounded at the cap
    years = [y for y in sorted(m["per_year"]) if y > max(m["per_year"]) - 10]
    this_year, peak = max(years), max(years, key=m["per_year"].get)
    top = -(-max(m["per_year"][y] for y in years) // 1000) * 1000
    x0, x1, base, plot_h = 124, 700, 420, 140
    out.append(txt(48, 240, "Contributions per year", 24, c["text"], 700))
    for t in range(0, top + 1, 1000):
        y = base - t / top * plot_h
        out += [f'<path d="M{x0} {y:.1f}H{x1}" stroke="{grid}"/>', txt(x0 - 12, y + 6, f"{t:,}", 17, c["muted"], anchor="end")]
    slot = (x1 - x0) / len(years)
    for k, yr in enumerate(years):
        v, cx = m["per_year"][yr], x0 + slot * (k + 0.5)
        hgt, x = v / top * plot_h, cx - 12
        if hgt > 0:
            r = min(4, hgt)
            out.append(f'<path d="M{x:.1f} {base}V{base - hgt + r:.1f}Q{x:.1f} {base - hgt:.1f} {x + r:.1f} {base - hgt:.1f}H{x + 24 - r:.1f}'
                       f'Q{x + 24:.1f} {base - hgt:.1f} {x + 24:.1f} {base - hgt + r:.1f}V{base}Z" fill="{acc_years}"'
                       f'{" fill-opacity=\".45\"" if yr == this_year else ""}/>')
        if yr in (peak, this_year):
            out.append(txt(cx, base - hgt - 9, f"{v:,}", 18, c["text"], 700, "middle"))
        out.append(txt(cx, base + 26, yr, 17, c["muted"], anchor="middle"))
    out.append(txt(x0 + slot * (len(years) - 0.5), base + 47, "so far", 16, c["muted"], anchor="middle"))

    # repositories by primary language: ranked bars, single hue, value at the tip
    lx, bx, bmax = 770, 948, 170
    out.append(txt(lx, 240, "Repositories by language", 24, c["text"], 700))
    most = m["langs"][0][1]
    for k, (name, n) in enumerate(m["langs"]):
        cy, w = 284 + k * 33, max(4, n / most * bmax)
        out += [txt(lx, cy + 6, name, 19, c["text"]),
                f'<path d="M{bx} {cy - 6}H{bx + w - 4:.1f}Q{bx + w:.1f} {cy - 6} {bx + w:.1f} {cy - 2}V{cy + 2}Q{bx + w:.1f} {cy + 6} {bx + w - 4:.1f} {cy + 6}H{bx}Z" fill="{acc_langs}"/>',
                txt(bx + w + 10, cy + 6, n, 18, c["muted"])]

    out.append(txt(W - 48, h - 22, f"Public GitHub data · updated {datetime.date.today():%d %b %Y}", 16, c["muted"], anchor="end"))
    desc = "; ".join(f"{label}: {value}" for value, label in tiles) + "; contributions per year: " + \
        ", ".join(f"{y} {m['per_year'][y]}" for y in years) + "; repositories by language: " + ", ".join(f"{n} {k}" for n, k in m["langs"])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" role="img" aria-labelledby="t d">
<title id="t">GitHub activity of {USER}</title>
<desc id="d">{escape(desc)}</desc>
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c['bg'][0]}"/><stop offset="1" stop-color="{c['bg'][1]}"/></linearGradient></defs>
<style>{fonts}</style>
<rect width="{W}" height="{h}" rx="18" fill="url(#bg)"/>
<g font-family="{SANS}">
{chr(10).join(out)}
</g>
</svg>
"""


if __name__ == "__main__":
    m = fetch()
    ascii_text = string.ascii_letters + string.digits + string.punctuation + " ·"
    fonts = font("Space Grotesk", 700, ascii_text) + font("Space Grotesk", 400, ascii_text)
    for theme in THEMES:
        (Path(__file__).parent / f"metrics-{theme}.svg").write_text(render(theme, m, fonts))
    print(m)
