"""Generates hero-light.svg / hero-dark.svg: hundreds of devices self-organise into regions
(what ScaFi's S + distanceTo + broadcast compute); a wave leaves every leader.
Run: python3 assets/hero.py  (stdlib only; needs network: fonts come from Google Fonts,
subset to the glyphs used, and get embedded since an SVG <img> cannot load external fonts)."""
import base64, heapq, math, random, re, urllib.parse, urllib.request
from collections import defaultdict
from pathlib import Path

W, H, SEED = 1200, 360, 11
CELL, JITTER, HOLES = 19, 7, 0.10      # device grid spacing, position noise, fraction of empty cells
RADIUS = 27                            # neighbourhood range (nbrRange)
GRAIN = 200                            # min distance between leaders (S grain)
PERIOD, SPREAD, BUCKETS = 5.0, 1.5, 14  # loop length, seconds a wave takes to cross a region, colour/time steps

NAME = "Gianluca Aguzzi"
ROLE = ["Postdoctoral Researcher & Adjunct Professor", "University of Bologna"]

THEMES = {
    "light": dict(bg=("#f8fafc", "#eef2ff"), far="#e2e8f0", text="#0f172a", muted="#475569",
                  zones=["#f59e0b", "#db2777", "#0284c7", "#7c3aed", "#059669", "#ea580c"]),
    "dark": dict(bg=("#080c18", "#141a36"), far="#1e2440", text="#f8fafc", muted="#94a3b8",
                 zones=["#fbbf24", "#f472b6", "#38bdf8", "#a78bfa", "#34d399", "#fb923c"]),
}


def font(family, weight, text):
    """Google Fonts serves a woff2 holding only the requested glyphs (the `text=` parameter)."""
    q = urllib.parse.urlencode({"family": f"{family}:wght@{weight}", "text": "".join(sorted(set(text)))})
    ua = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
    css = urllib.request.urlopen(urllib.request.Request(f"https://fonts.googleapis.com/css2?{q}", headers=ua)).read().decode()
    url = re.search(r"url\((https://[^)]+)\)", css).group(1)
    data = base64.b64encode(urllib.request.urlopen(urllib.request.Request(url, headers=ua)).read()).decode()
    return f"@font-face{{font-family:'{family}';font-weight:{weight};src:url(data:font/woff2;base64,{data}) format('woff2')}}"


def place_devices():
    rnd = random.Random(SEED)
    return [(x + rnd.uniform(-JITTER, JITTER), y + rnd.uniform(-JITTER, JITTER))
            for x in range(CELL // 2, W, CELL) for y in range(CELL // 2, H, CELL) if rnd.random() > HOLES]


def self_organise(pts):
    """What ScaFi's building blocks converge to: sparse leaders, distance to the nearest one, its id."""
    cell = defaultdict(list)
    for i, (x, y) in enumerate(pts):
        cell[int(x // RADIUS), int(y // RADIUS)].append(i)
    nbrs = [[j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in cell[int(x // RADIUS) + dx, int(y // RADIUS) + dy]
             if j != i and math.dist(pts[i], pts[j]) <= RADIUS] for i, (x, y) in enumerate(pts)]
    order, leaders = list(range(len(pts))), []
    random.Random(SEED).shuffle(order)
    for i in order:                                       # S(grain): leaders at least GRAIN apart
        if all(math.dist(pts[i], pts[l]) >= GRAIN for l in leaders):
            leaders.append(i)
    dist, zone = {l: 0.0 for l in leaders}, {l: z for z, l in enumerate(leaders)}
    todo = [(0.0, l) for l in leaders]
    while todo:                                           # distanceTo(leader) + broadcast(leader, mid())
        d, i = heapq.heappop(todo)
        if d > dist[i]:
            continue
        for j in nbrs[i]:
            nd = d + math.dist(pts[i], pts[j])
            if nd < dist.get(j, math.inf):
                dist[j], zone[j] = nd, zone[i]
                heapq.heappush(todo, (nd, j))
    return nbrs, leaders, dist, zone


def colour_zones(nbrs, zone, n_zones, n_colours):
    """Greedy colouring so that touching regions never share a colour."""
    adj = defaultdict(set)
    for i, js in enumerate(nbrs):
        for j in js:
            if i in zone and j in zone and zone[i] != zone[j]:
                adj[zone[i]].add(zone[j])
    colour = {}
    for z in range(n_zones):
        colour[z] = next(c for c in range(n_colours) if all(colour.get(o) != c for o in adj[z]))
    return colour


def mix(c1, c2, t):
    a, b = (int(c1[k:k + 2], 16) for k in (1, 3, 5)), (int(c2[k:k + 2], 16) for k in (1, 3, 5))
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def render(theme, pts, nbrs, leaders, dist, zone, colour, fonts):
    c, rnd = THEMES[theme], random.Random(SEED)
    offset = [rnd.uniform(0, PERIOD - SPREAD - 0.8) for _ in leaders]   # devices are not synchronised
    dmax = max(dist.values())
    bucket = {i: round(d / dmax * (BUCKETS - 1)) for i, d in dist.items()}
    col = lambda z, b: mix(c["zones"][colour[z]], c["far"], 0.6 * b / (BUCKETS - 1))
    delay = lambda z, b: f"{offset[z] + b / (BUCKETS - 1) * SPREAD:.2f}s"

    dots, links = defaultdict(list), defaultdict(list)    # grouped by (zone, bucket): one <path> each
    for i in dist:
        x, y = pts[i]
        dots[zone[i], bucket[i]].append(f"M{x:.0f} {y:.0f}h0")
        for j in nbrs[i]:
            if i < j and j in dist and zone[j] == zone[i] and max(x, pts[j][0]) > W * 0.38:
                links[zone[i], min(bucket[i], bucket[j])].append(f"M{x:.0f} {y:.0f}L{pts[j][0]:.0f} {pts[j][1]:.0f}")
    paths = [f'<path class="e" stroke="{col(z, b)}" style="animation-delay:{delay(z, b)}" d="{"".join(d)}"/>' for (z, b), d in sorted(links.items())]
    paths += [f'<path class="n" stroke="{col(z, b)}" style="animation-delay:{delay(z, b)}" d="{"".join(d)}"/>' for (z, b), d in sorted(dots.items())]
    for z, l in enumerate(leaders):
        x, y = pts[l]
        paths.append(f'<circle class="p" cx="{x:.0f}" cy="{y:.0f}" r="7" stroke="{col(z, 0)}" style="animation-delay:{delay(z, 0)}"/>'
                     f'<circle cx="{x:.0f}" cy="{y:.0f}" r="5.5" fill="{col(z, 0)}" stroke="{c["bg"][0]}" stroke-width="2"/>')

    sans = "'Space Grotesk',-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t">
<title id="t">{NAME}: hundreds of devices self-organising into regions around elected leaders, in the spirit of aggregate computing</title>
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c['bg'][0]}"/><stop offset="1" stop-color="{c['bg'][1]}"/></linearGradient>
  <linearGradient id="fade" x1="0" x2="1"><stop offset=".44" stop-color="#fff" stop-opacity=".07"/><stop offset=".68" stop-color="#fff" stop-opacity="1"/></linearGradient>
  <mask id="m"><rect width="{W}" height="{H}" fill="url(#fade)"/></mask>
  <clipPath id="clip"><rect width="{W}" height="{H}" rx="18"/></clipPath>
</defs>
<style>
  {fonts}
  .e {{ fill:none; stroke-width:1; stroke-opacity:.22; animation:e {PERIOD}s ease-out infinite both; }}
  .n {{ fill:none; stroke-width:4.4; stroke-linecap:round; animation:n {PERIOD}s ease-out infinite both; }}
  .p {{ fill:none; stroke-width:1.6; opacity:0; transform-box:fill-box; transform-origin:center; animation:p {PERIOD}s ease-out infinite both; }}
  @keyframes e {{ 0% {{ stroke-opacity:.22 }} 4% {{ stroke-opacity:.7 }} 26%,100% {{ stroke-opacity:.22 }} }}
  @keyframes n {{ 0% {{ stroke-width:4.4 }} 4% {{ stroke-width:7 }} 22%,100% {{ stroke-width:4.4 }} }}
  @keyframes p {{ 0% {{ opacity:0; transform:scale(1) }} 2% {{ opacity:.9 }} 40%,100% {{ opacity:0; transform:scale(6) }} }}
  @media (prefers-reduced-motion: reduce) {{ * {{ animation:none !important; }} }}
</style>
<g clip-path="url(#clip)">
<rect width="{W}" height="{H}" fill="url(#bg)"/>
<g mask="url(#m)">
{chr(10).join(paths)}
</g>
<g font-family="{sans}">
  <text x="62" y="170" font-size="64" font-weight="700" fill="{c['text']}" letter-spacing="-1.5">{NAME}</text>
  <text x="64" y="210" font-size="21" fill="{c['muted']}">{ROLE[0].replace('&', '&amp;')}</text>
  <text x="64" y="237" font-size="21" fill="{c['muted']}">{ROLE[1]}</text>
</g>
</g>
</svg>
"""


if __name__ == "__main__":
    pts = place_devices()
    nbrs, leaders, dist, zone = self_organise(pts)
    assert len(dist) > 0.95 * len(pts), "network too sparse: most devices must reach a leader"
    colour = colour_zones(nbrs, zone, len(leaders), len(THEMES["dark"]["zones"]))
    fonts = "\n  ".join([font("Space Grotesk", 700, NAME), font("Space Grotesk", 400, "".join(ROLE))])
    out = Path(__file__).parent
    for theme in THEMES:
        (out / f"hero-{theme}.svg").write_text(render(theme, pts, nbrs, leaders, dist, zone, colour, fonts))
    print(f"{len(pts)} devices, {len(leaders)} leaders, {len(dist)} reached")
