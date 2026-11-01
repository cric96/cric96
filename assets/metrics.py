"""Renders the data cards from public GitHub and Stack Overflow data:
assets/metrics-{light,dark}.svg (GitHub activity) and assets/community-{light,dark}.svg.
Refreshed weekly by .github/workflows/metrics.yml.
Local run: GITHUB_TOKEN=$(gh auth token) python3 assets/metrics.py"""
import datetime, gzip, json, os, string, urllib.parse, urllib.request
from collections import Counter
from html import escape
from pathlib import Path

from banners import SANS, THEMES, W, font

USER, SO_USER = "cric96", 10295847
# one hue per chart, validated with the dataviz palette checker (lightness band, chroma, CVD, contrast)
ACCENT = {"light": dict(years="#7c3aed", langs="#0284c7", tags="#ea580c", repos="#059669"),
          "dark": dict(years="#9061f9", langs="#0b9fd6", tags="#e8590c", repos="#0d9b6c")}
GRID = {"light": "#dbe1ea", "dark": "#262f4d"}
OUT = Path(__file__).parent


def gql(query, **variables):
    req = urllib.request.Request("https://api.github.com/graphql", json.dumps({"query": query, "variables": variables}).encode(),
                                 {"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}"})
    data = json.load(urllib.request.urlopen(req))
    if "errors" in data:
        raise SystemExit(data["errors"])
    return data["data"]["user"]


def stack(path, **params):
    with urllib.request.urlopen(f"https://api.stackexchange.com/2.3/{path}?{urllib.parse.urlencode({'site': 'stackoverflow', **params})}") as r:
        body = r.read()
        return json.loads(gzip.decompress(body) if r.headers.get("Content-Encoding") == "gzip" else body)


def fetch_github():
    u = gql("""query($l:String!){user(login:$l){createdAt pullRequests{totalCount} followers{totalCount} organizations{totalCount}
        repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,ISSUE,PULL_REQUEST_REVIEW]){totalCount}
        recent: repositoriesContributedTo(first:100, contributionTypes:[COMMIT,PULL_REQUEST]){nodes{name stargazerCount isPrivate}}
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
    public = sorted((n for n in u["recent"]["nodes"] if not n["isPrivate"]), key=lambda n: -n["stargazerCount"])
    return dict(since=first, prs=u["pullRequests"]["totalCount"], contributed=u["repositoriesContributedTo"]["totalCount"],
                repos=u["repositories"]["totalCount"], per_year=per_year, langs=langs.most_common(6),
                followers=u["followers"]["totalCount"], orgs=u["organizations"]["totalCount"],
                upstream=[(n["name"], n["stargazerCount"]) for n in public[:5]])


def fetch_stackoverflow():
    me = stack(f"users/{SO_USER}")["items"][0]
    tags = stack(f"users/{SO_USER}/top-answer-tags", pagesize=5)["items"]
    return dict(rep=me["reputation"], badges=me["badge_counts"], answers=stack(f"users/{SO_USER}/answers", filter="total")["total"],
                tags=sorted(((t["tag_name"], t["answer_count"]) for t in tags), key=lambda t: -t[1]))


def compact(n):
    return f"{n / 1000:.1f}K" if n >= 10_000 else f"{n:,}"


def txt(x, y, s, size, fill, weight=400, anchor="start"):
    return f'<text x="{x:.0f}" y="{y:.0f}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(str(s))}</text>'


def tiles(c, items):
    """Stat tiles: big value, label below, optional third line."""
    out = []
    for i, (value, label, *extra) in enumerate(items):
        x = 48 + i * 282
        out += [txt(x, 104, value, 58, c["text"], 700), txt(x, 142, label, 21, c["muted"])]
        out += [txt(x, 172, e, 18, c["muted"]) for e in extra]
    return out


def hbars(c, x, title, rows, colour, name_w, bmax, top=240):
    """Ranked horizontal bars: one hue, square at the baseline, rounded data-end, value at the tip."""
    out, most = [txt(x, top, title, 24, c["text"], 700)], max(n for _, n in rows)
    bx = x + name_w
    for k, (name, n) in enumerate(rows):
        cy, w = top + 44 + k * 33, max(4, n / most * bmax)
        out += [txt(x, cy + 6, name, 19, c["text"]),
                f'<path d="M{bx} {cy - 6}H{bx + w - 4:.1f}Q{bx + w:.1f} {cy - 6} {bx + w:.1f} {cy - 2}V{cy + 2}Q{bx + w:.1f} {cy + 6} {bx + w - 4:.1f} {cy + 6}H{bx}Z" fill="{colour}"/>',
                txt(bx + w + 10, cy + 6, n, 18, c["muted"])]
    return out


def card(theme, title, desc, body, footer, h):
    c = THEMES[theme]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" role="img" aria-labelledby="t d">
<title id="t">{escape(title)}</title>
<desc id="d">{escape(desc)}</desc>
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c['bg'][0]}"/><stop offset="1" stop-color="{c['bg'][1]}"/></linearGradient></defs>
<style>{FONTS}</style>
<rect width="{W}" height="{h}" rx="18" fill="url(#bg)"/>
<g font-family="{SANS}">
{chr(10).join(body)}
{txt(W - 48, h - 22, f"{footer} · updated {datetime.date.today():%d %b %Y}", 16, c["muted"], anchor="end")}
</g>
</svg>
"""


def activity(theme, m, h=510):
    c, acc, grid = THEMES[theme], ACCENT[theme], GRID[theme]
    stats = [(compact(sum(m["per_year"].values())), f"Contributions since {m['since']}"), (compact(m["prs"]), "Pull requests"),
             (compact(m["contributed"]), "Repos contributed to"), (compact(m["repos"]), "Public repos")]
    out = tiles(c, stats) + [f'<path d="M48 186H{W - 48}" stroke="{grid}"/>']

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
                       f'Q{x + 24:.1f} {base - hgt:.1f} {x + 24:.1f} {base - hgt + r:.1f}V{base}Z" fill="{acc["years"]}"'
                       f'{" fill-opacity=\".45\"" if yr == this_year else ""}/>')
        if yr in (peak, this_year):
            out.append(txt(cx, base - hgt - 9, f"{v:,}", 18, c["text"], 700, "middle"))
        out.append(txt(cx, base + 26, yr, 17, c["muted"], anchor="middle"))
    out.append(txt(x0 + slot * (len(years) - 0.5), base + 47, "so far", 16, c["muted"], anchor="middle"))
    out += hbars(c, 770, "Repositories by language", m["langs"], acc["langs"], 178, 170)

    desc = "; ".join(f"{label}: {value}" for value, label in stats) + "; contributions per year: " + \
        ", ".join(f"{y} {m['per_year'][y]}" for y in years) + "; repositories by language: " + ", ".join(f"{n} {k}" for n, k in m["langs"])
    return card(theme, f"GitHub activity of {USER}", desc, out, "Public GitHub data", h)


def community(theme, m, so, h=510):
    c, acc, grid = THEMES[theme], ACCENT[theme], GRID[theme]
    b = so["badges"]
    stats = [(f"{so['rep']:,}", "Stack Overflow reputation", f"{b['gold']} gold · {b['silver']} silver · {b['bronze']} bronze"),
             (f"{so['answers']:,}", "Answers", "on Stack Overflow"), (f"{m['orgs']:,}", "Organizations", "on GitHub"), (f"{m['followers']:,}", "Followers", "on GitHub")]
    out = tiles(c, stats) + [f'<path d="M48 206H{W - 48}" stroke="{grid}"/>']
    out += hbars(c, 48, "Answers by tag", so["tags"], acc["tags"], 200, 230, top=258)
    out += hbars(c, 640, "Contributing to · by stars", m["upstream"], acc["repos"], 272, 180, top=258)
    desc = "; ".join(f"{label} {' '.join(extra[-1:])}: {value}" for value, label, *extra in stats[1:]) + f"; Stack Overflow reputation: {so['rep']} ({stats[0][2]})" + \
        "; Stack Overflow answers by tag: " + ", ".join(f"{t} {n}" for t, n in so["tags"]) + \
        "; open-source repositories contributed to, by stars: " + ", ".join(f"{r} {n}" for r, n in m["upstream"])
    return card(theme, f"Community activity of {USER}", desc, out, "Public Stack Overflow and GitHub data", h)


if __name__ == "__main__":
    ascii_text = string.ascii_letters + string.digits + string.punctuation + " ·"
    FONTS = font("Space Grotesk", 700, ascii_text) + font("Space Grotesk", 400, ascii_text)
    m = fetch_github()
    try:
        so = fetch_stackoverflow()
    except Exception as e:  # the anonymous Stack Exchange quota is per IP: keep last week's card rather than failing
        print(f"Stack Overflow unavailable, community card left as is: {e}")
        so = None
    for theme in THEMES:
        (OUT / f"metrics-{theme}.svg").write_text(activity(theme, m))
        if so:
            (OUT / f"community-{theme}.svg").write_text(community(theme, m, so))
    print(m, so)
