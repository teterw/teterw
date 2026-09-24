"""Generate the Monkeytype-themed SVGs used in the profile README.

    GH_TOKEN=$(gh auth token) python assets/make_svgs.py

- header.svg      Monkeytype-style top bar + test config bar
- typing.svg      "about me" typing test, with live wpm and latest commit
- monkeytype.svg  live personal bests from the Monkeytype API
- nowplaying.svg  last played song from Last.fm (needs LASTFM_USER + LASTFM_API_KEY)
- activity.svg    GitHub contributions heatmap, streaks, and top languages
- footer.svg      Monkeytype's key-hint footer

The update workflow runs this on a schedule. If a data source is down, the SVGs that
depend on it are left untouched instead of being overwritten with empty cards.
Everything animates with SMIL, so it works inside GitHub's README <img> without JavaScript.
"""

import base64
import hashlib
import json
import os
import random
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

GITHUB_USER = "teterw"
MONKEYTYPE_USER = "teterw"

ABOUT = ("hello, i'm teterw, a student at assumption college thonburi. i'm into "
         "tech and always learning something new by building projects.")

FONT = "'Roboto Mono', 'Fira Code', Consolas, 'DejaVu Sans Mono', monospace"

WIDTH, PAD_X = 820, 40
HERE = Path(__file__).parent
BANGKOK = timezone(timedelta(hours=7))
TODAY = datetime.now(BANGKOK).date()

# Monkeytype "serika dark" theme. FLASH is the colour the reactive heatmap lights up to.
BG, BG_DARK, SUB, MAIN, TEXT_COLOR, FLASH = ("#323437", "#2c2e31", "#646669", "#e2b714",
                                             "#d1d0c5", "#ffd84a")


def mix(a, b, f):
    """Blend hex colour a toward b by fraction f."""
    ca, cb = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (a, b))
    return "#" + "".join(f"{round(x + (y - x) * f):02x}" for x, y in zip(ca, cb))
NEW_PB_DAYS = 3  # how long the "new pb" tag stays up


def svg(height, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="0 0 {WIDTH} {height}" width="{WIDTH}" height="{height}" font-family="{FONT}">\n'
            f'<rect width="{WIDTH}" height="{height}" rx="14" fill="{BG}"/>\n'
            + "\n".join(body) + "\n</svg>\n")


def label(x, y, text, size=13, fill=SUB, anchor="start", weight=None):
    w = f' font-weight="{weight}"' if weight else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}"{w}>{escape(str(text))}</text>')


def card_title(title, right=None):
    parts = [label(PAD_X, 44, title, 20, MAIN, weight=700)]
    if right:
        parts.append(label(WIDTH - PAD_X, 44, right, 15, SUB, "end"))
    return parts


def truncate(text, limit):
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


# ---------------------------------------------------------------- data sources

def fetch_json(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": GITHUB_USER, **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def fetch_github():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("no GH_TOKEN, skipping GitHub data")
        return None
    # PUBLIC only, so private repo names and commit messages never end up on the profile.
    query = """query($login: String!) { user(login: $login) {
      contributionsCollection { contributionCalendar { totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } } } }
      repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC,
                   orderBy: {field: PUSHED_AT, direction: DESC}) {
        totalCount
        nodes { name stargazerCount
          languages(first: 10, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } }
          defaultBranchRef { target { ... on Commit { history(first: 1) { nodes { messageHeadline } } } } }
        } } } }"""
    try:
        body = json.dumps({"query": query, "variables": {"login": GITHUB_USER}}).encode()
        data = fetch_json("https://api.github.com/graphql", body, {"Authorization": f"bearer {token}"})
        return data["data"]["user"]
    except Exception as e:  # noqa: BLE001 - any failure just means "keep the old SVGs"
        print(f"GitHub fetch failed: {e}")
        return None


def fetch_monkeytype():
    try:
        return fetch_json(f"https://api.monkeytype.com/users/{MONKEYTYPE_USER}/profile")["data"]
    except Exception as e:  # noqa: BLE001
        print(f"Monkeytype fetch failed: {e}")
        return None


def fetch_lastfm():
    user, key = os.environ.get("LASTFM_USER"), os.environ.get("LASTFM_API_KEY")
    if not (user and key):
        return None
    try:
        q = urllib.parse.urlencode({"method": "user.getrecenttracks", "user": user, "api_key": key,
                                    "format": "json", "limit": 1})
        track = fetch_json(f"https://ws.audioscrobbler.com/2.0/?{q}")["recenttracks"]["track"][0]
        art = next((i["#text"] for i in reversed(track.get("image", [])) if i["#text"]), None)
        art_data = None
        if art:
            with urllib.request.urlopen(art, timeout=20) as resp:
                art_data = base64.b64encode(resp.read()).decode()
        return {"title": track["name"], "artist": track["artist"]["#text"],
                "now": track.get("@attr", {}).get("nowplaying") == "true", "art": art_data}
    except Exception as e:  # noqa: BLE001
        print(f"Last.fm fetch failed: {e}")
        return None


def best(mt, mode, length):
    """Best english/normal/no-punctuation personal best for e.g. ("words", "10")."""
    runs = [r for r in mt["personalBests"].get(mode, {}).get(length, [])
            if r["language"] == "english" and r["difficulty"] == "normal"
            and not r["punctuation"] and not r["numbers"]]
    return max(runs, key=lambda r: r["wpm"]) if runs else None


def latest_commit(gh):
    for repo in gh["repositories"]["nodes"]:
        if repo["name"] == GITHUB_USER or not repo["defaultBranchRef"]:
            continue
        commits = repo["defaultBranchRef"]["target"]["history"]["nodes"]
        if commits:
            return repo["name"], commits[0]["messageHeadline"]
    return None


# ---------------------------------------------------------------- cards

def keyboard_icon(x, y):
    """Monkeytype's keyboard logo, roughly."""
    parts = [f'<rect x="{x}" y="{y}" width="52" height="34" rx="7" fill="none" '
             f'stroke="{MAIN}" stroke-width="3.5"/>']
    for row in range(2):
        for k in range(4):
            parts.append(f'<rect x="{x + 9 + k * 9.5}" y="{y + 8 + row * 8}" width="5" '
                         f'height="4" rx="1" fill="{MAIN}"/>')
    parts.append(f'<rect x="{x + 13}" y="{y + 24}" width="26" height="4" rx="1" fill="{MAIN}"/>')
    return parts


def header():
    height = 150
    body = keyboard_icon(PAD_X, 32)
    body += [
        f'<text x="{PAD_X + 66}" y="38" font-size="11" fill="{SUB}">you see</text>',
        f'<text x="{PAD_X + 64}" y="66" font-size="34" fill="{TEXT_COLOR}">teterw</text>',
        f'<text x="{WIDTH - PAD_X}" y="58" font-size="15" fill="{SUB}" text-anchor="end">'
        f'act · thailand · will continue building</text>',
    ]

    # Config bar, e.g. "@ punctuation  # numbers | time words quote | 15 30 60"
    groups = [
        [("@", "python", True), ("#", "next.js", True)],
        [(None, "web", True), (None, "automation", False), (None, "side projects", True)],
        [(None, "kotlin", False), (None, "arduino", False)],
    ]
    font, gap, sep = 13, 22, 26
    char_w = font * 0.62
    items, total = [], 0
    for gi, group in enumerate(groups):
        if gi:
            items.append(("sep", total))
            total += sep
        for i, (icon, text, on) in enumerate(group):
            text = f"{icon} {text}" if icon else text
            items.append(((text, on), total))
            total += len(text) * char_w + (gap if i < len(group) - 1 else 0)
    bar_w = total + 48
    bx = (WIDTH - bar_w) / 2
    body.append(f'<rect x="{bx:.1f}" y="96" width="{bar_w:.1f}" height="34" rx="8" fill="{BG_DARK}"/>')
    for item, offset in items:
        x = bx + 24 + offset
        if item == "sep":
            body.append(f'<rect x="{x + sep / 2 - 2:.1f}" y="104" width="4" height="18" rx="2" fill="{BG}"/>')
        else:
            text, on = item
            body.append(label(x, 118, text, font, MAIN if on else SUB))
    return svg(height, body)


def typing(text, right):
    random.seed(7)  # deterministic output, so re-running doesn't create a git diff
    top, char_w, line_h, font = 92, 14.4, 40, 24
    max_chars, hold = int((WIDTH - 2 * PAD_X) / char_w), 3.0

    lines, line = [], ""
    for word in text.split(" "):
        candidate = f"{line} {word}" if line else word
        if len(candidate) > max_chars:
            lines.append(line + " ")
            line = word
        else:
            line = candidate
    lines.append(line)
    height = top + line_h * len(lines) + 12

    # Position of every character, plus a human-ish keystroke timeline.
    chars, t = [], 0.8
    for row, line in enumerate(lines):
        for col, ch in enumerate(line):
            t += random.uniform(0.045, 0.09) + (0.12 if ch in ",.?!:" else 0)
            chars.append((ch, PAD_X + col * char_w, top + row * line_h, t))
    total = t + hold
    kt = lambda s: f"{s / total:.4f}"

    body = card_title("about me", right)
    for ch, x, y, at in chars:
        if ch == " ":
            continue
        body.append(
            f'<text x="{x:.1f}" y="{y}" font-size="{font}" fill="{SUB}">{escape(ch)}'
            f'<animate attributeName="fill" values="{SUB};{TEXT_COLOR};{SUB}" '
            f'keyTimes="0;{kt(at)};{kt(total - 0.05)}" calcMode="discrete" '
            f'dur="{total:.2f}s" repeatCount="indefinite"/></text>')

    # Caret: sits before the next character to type.
    xs = [chars[0][1]] + [x + char_w for _, x, _, _ in chars]
    ys = [chars[0][2]] + [y for _, _, y, _ in chars]
    times = ";".join(["0"] + [kt(at) for *_, at in chars])
    anim = f'keyTimes="{times}" calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite"'
    body.append(
        f'<rect width="2.5" height="{font + 4}" rx="1" fill="{MAIN}">'
        f'<animate attributeName="x" values="{";".join(f"{x:.1f}" for x in xs)}" {anim}/>'
        f'<animate attributeName="y" values="{";".join(str(y - font + 1) for y in ys)}" {anim}/>'
        f'<animate attributeName="opacity" values="1;0;1" dur="1s" repeatCount="indefinite"/>'
        f'</rect>')
    return svg(height, body)


def pb_date(run):
    return datetime.fromtimestamp(run["timestamp"] / 1000, BANGKOK).date()


def is_new_pb(run):
    return run is not None and (TODAY - pb_date(run)).days < NEW_PB_DAYS


def monkeytype(mt):
    modes = (("time", ("15", "30", "60", "120")), ("words", ("10", "25", "50", "100")))
    fresh = [(pb_date(run), mode, length) for mode, lengths in modes for length in lengths
             if is_new_pb(run := best(mt, mode, length))]
    if fresh:
        when, mode, length = max(fresh)
        body = [label(PAD_X, 44, "monkeytype", 20, MAIN, weight=700),
                label(WIDTH - PAD_X, 44, f"new pb! {mode} {length} · {when.strftime('%b %-d').lower()}",
                      15, MAIN, "end")]
    else:
        since = datetime.fromtimestamp(mt["addedAt"] / 1000, timezone.utc).strftime("%b %Y").lower()
        body = card_title("monkeytype", f"{mt['name']} · joined {since}")

    stats = mt["typingStats"]
    minutes = int(stats["timeTyping"] // 60)
    columns = [("tests completed", f"{stats['completedTests']:,}"),
               ("time typing", f"{minutes // 60}h {minutes % 60:02d}m"),
               ("streak", f"{mt.get('streak', 0)}d (best {mt.get('maxStreak', 0)}d)")]
    lb = mt.get("allTimeLbs", {}).get("time", {}).get("15", {}).get("english")
    if lb and lb.get("rank") and lb.get("count"):
        columns.append(("15s leaderboard", f"top {100 * lb['rank'] / lb['count']:.1f}%"))
    col_w = (WIDTH - 2 * PAD_X) / len(columns)
    for i, (name, value) in enumerate(columns):
        x = PAD_X + i * col_w
        body += [label(x, 82, name, 12), label(x, 110, value, 20, TEXT_COLOR)]

    panel_w, top, panel_h = (WIDTH - 2 * PAD_X - 20) / 2, 132, 140
    for p, (mode, lengths) in enumerate(modes):
        px = PAD_X + p * (panel_w + 20)
        body.append(f'<rect x="{px:.1f}" y="{top}" width="{panel_w:.1f}" height="{panel_h}" rx="10" fill="{BG_DARK}"/>')
        body.append(label(px + 18, top + 24, mode, 13, MAIN))
        cw = (panel_w - 36) / 4
        for i, length in enumerate(lengths):
            x = px + 18 + i * cw + cw / 2
            run = best(mt, mode, length)
            body.append(label(x, top + 48, f"{length}{'s' if mode == 'time' else ''}", 12, SUB, "middle"))
            body.append(label(x, top + 84, int(run["wpm"]) if run else "-", 30, MAIN, "middle"))
            body.append(label(x, top + 104, f"{run['acc']:.0f}% acc" if run else "", 11, SUB, "middle"))
            if is_new_pb(run):
                # Pulsing "new pb" pill, like Monkeytype's crown on a fresh personal best.
                body.append(f'<g><rect x="{x - 26:.1f}" y="{top + 113}" width="52" height="17" rx="8.5" fill="{MAIN}"/>'
                            f'{label(x, top + 125.5, "new pb", 11, "#323437", "middle", 700)}'
                            f'<animate attributeName="opacity" values="1;0.55;1" dur="1.6s" repeatCount="indefinite"/></g>')
    return svg(top + panel_h + 28, body)


def equalizer(x, y, animated):
    bars = []
    for i, (lo, hi, dur) in enumerate(((6, 26, 0.9), (10, 30, 0.7), (4, 22, 1.1), (8, 28, 0.8))):
        h = hi if not animated else lo
        bar = (f'<rect x="{x + i * 9}" y="{y - h}" width="5" height="{h}" rx="2" fill="{MAIN}">')
        if animated:
            bar += (f'<animate attributeName="height" values="{lo};{hi};{lo}" dur="{dur}s" repeatCount="indefinite"/>'
                    f'<animate attributeName="y" values="{y - lo};{y - hi};{y - lo}" dur="{dur}s" repeatCount="indefinite"/>')
        bars.append(bar + "</rect>")
    return bars


def nowplaying(track):
    height, art = 124, 76
    ay = (height - art) / 2
    body = [f'<clipPath id="art"><rect x="{PAD_X}" y="{ay}" width="{art}" height="{art}" rx="10"/></clipPath>']
    if track and track["art"]:
        body.append(f'<image x="{PAD_X}" y="{ay}" width="{art}" height="{art}" clip-path="url(#art)" '
                    f'preserveAspectRatio="xMidYMid slice" href="data:image/png;base64,{track["art"]}"/>')
    else:
        body.append(f'<rect x="{PAD_X}" y="{ay}" width="{art}" height="{art}" rx="10" fill="{BG_DARK}"/>')
        body += equalizer(PAD_X + 22, ay + art / 2 + 14, animated=False)

    tx = PAD_X + art + 24
    if track:
        status = "now playing" if track["now"] else "last played"
        title, artist = track["title"], track["artist"]
    else:
        status, title, artist = "on repeat", "favorite artist", "malcolm todd"
    body += [label(tx, 42, status, 12), label(tx, 72, truncate(title, 42), 22, TEXT_COLOR),
             label(tx, 98, truncate(artist, 50), 15, MAIN)]
    body += equalizer(WIDTH - PAD_X - 32, 76, animated=track is None or track["now"])
    return svg(height, body)


def streaks(days):
    counts = [d["contributionCount"] for d in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    current = 0
    for i, c in enumerate(reversed(counts)):
        if c:
            current += 1
        elif i:  # today not counted yet is fine, a gap before that ends the streak
            break
    return current, longest


TAP_START, TAP_SPAN, TAP_SETTLE, TAP_HOLD = 0.4, 6.0, 0.4, 3.5


def tap_times(weeks):
    """When each active day "gets tapped": in date order, spread over TAP_SPAN seconds."""
    active = [(wi, date.fromisoformat(d["date"]).isoweekday() % 7)
              for wi, w in enumerate(weeks) for d in w["contributionDays"] if d["contributionCount"]]
    gap = TAP_SPAN / max(len(active), 1)
    return {cell: TAP_START + i * gap for i, cell in enumerate(active)}


def tap(base, t, loop):
    """Cell taps in at t (flash, settle to its shade), holds, then taps out in the same order."""
    out = t + TAP_SPAN + TAP_SETTLE + TAP_HOLD
    frames = [(0, BG_DARK), (t, BG_DARK), (t + 0.05, FLASH), (t + TAP_SETTLE, base),
              (out, base), (out + 0.05, FLASH), (out + TAP_SETTLE, BG_DARK), (loop, BG_DARK)]
    return (f'<animate attributeName="fill" values="{";".join(c for _, c in frames)}" '
            f'keyTimes="{";".join(f"{f / loop:.4f}" for f, _ in frames)}" '
            f'dur="{loop:.1f}s" repeatCount="indefinite"/>')


def activity(gh):
    cal = gh["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    body = card_title("github activity", f"{cal['totalContributions']:,} contributions in the last year")

    shades = {"NONE": BG_DARK, "FIRST_QUARTILE": mix(BG_DARK, MAIN, 0.3),
              "SECOND_QUARTILE": mix(BG_DARK, MAIN, 0.5), "THIRD_QUARTILE": mix(BG_DARK, MAIN, 0.75),
              "FOURTH_QUARTILE": MAIN}
    step = (WIDTH - 2 * PAD_X + 3) / len(weeks)
    cell, gx, gy = step - 3, PAD_X, 86
    taps = tap_times(weeks)
    loop = TAP_START + 2 * (TAP_SPAN + TAP_SETTLE) + TAP_HOLD + 0.6  # in, hold, out, short pause
    last_month = None
    for wi, week in enumerate(weeks):
        x = gx + wi * step
        first = date.fromisoformat(week["contributionDays"][0]["date"])
        if first.month != last_month and first.day <= 7 and wi < len(weeks) - 2:
            body.append(label(x, gy - 8, first.strftime("%b").lower(), 11))
        last_month = first.month
        for d in week["contributionDays"]:
            row = date.fromisoformat(d["date"]).isoweekday() % 7
            y = gy + row * step
            base = shades.get(d["contributionLevel"], BG_DARK)
            body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" height="{cell:.1f}" rx="2" '
                        f'fill="{base}">{tap(base, taps[wi, row], loop) if (wi, row) in taps else ""}</rect>')

    current, longest = streaks(days)
    repos = gh["repositories"]
    stars = sum(r["stargazerCount"] for r in repos["nodes"])
    columns = [("public repos", repos["totalCount"]), ("stars", stars),
               ("current streak", f"{current}d"), ("longest streak", f"{longest}d")]
    sy = gy + 7 * step + 34
    col_w = (WIDTH - 2 * PAD_X) / len(columns)
    for i, (name, value) in enumerate(columns):
        body += [label(PAD_X + i * col_w, sy, name, 12), label(PAD_X + i * col_w, sy + 28, value, 22, TEXT_COLOR)]

    # Top languages as one stacked bar, like a result chart.
    sizes = {}
    for r in repos["nodes"]:
        for e in r["languages"]["edges"]:
            sizes[e["node"]["name"]] = sizes.get(e["node"]["name"], 0) + e["size"]
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:6]
    total = sum(s for _, s in top) or 1
    colors = [MAIN, TEXT_COLOR, mix(BG, MAIN, 0.75), mix(BG, TEXT_COLOR, 0.55), mix(BG, MAIN, 0.5), SUB]
    ly = sy + 58
    body.append(label(PAD_X, ly, "top languages", 12))
    x, bar_w = PAD_X, WIDTH - 2 * PAD_X
    body.append(f'<clipPath id="bar"><rect x="{PAD_X}" y="{ly + 12}" width="{bar_w}" height="10" rx="5"/></clipPath>')
    legend_x = PAD_X
    for (name, size), color in zip(top, colors):
        w = bar_w * size / total
        body.append(f'<rect x="{x:.1f}" y="{ly + 12}" width="{w + 0.5:.1f}" height="10" fill="{color}" clip-path="url(#bar)"/>')
        x += w
        text = f"{name.lower()} {100 * size / total:.0f}%"
        body.append(f'<rect x="{legend_x:.1f}" y="{ly + 36}" width="9" height="9" rx="2" fill="{color}"/>')
        body.append(label(legend_x + 14, ly + 45, text, 12, TEXT_COLOR))
        legend_x += 14 + len(text) * 12 * 0.62 + 22
    return svg(ly + 66, body)


def footer():
    height = 92
    font, char_w = 13, 13 * 0.6

    def key(x, y, text):
        w = len(text) * char_w + 12
        return w, [f'<rect x="{x:.1f}" y="{y - 15}" width="{w:.1f}" height="21" rx="4" fill="{SUB}"/>',
                   label(x + 6, y, text, font, BG)]

    body = []
    for y, parts in ((40, ["tab", " + ", "enter", " - view my repositories"]),
                     (70, ["esc", " or ", "ctrl", " + ", "shift", " + ", "p", " - command line"])):
        width = sum(len(p) * char_w + (12 if i % 2 == 0 else 0) for i, p in enumerate(parts))
        x = (WIDTH - width) / 2
        for i, part in enumerate(parts):
            if i % 2 == 0:
                w, shapes = key(x, y, part)
                body += shapes
            else:
                w = len(part) * char_w
                body.append(f'<text x="{x:.1f}" y="{y}" font-size="{font}" fill="{SUB}" '
                            f'xml:space="preserve">{escape(part)}</text>')
            x += w
    return svg(height, body)


def main():
    gh, mt = fetch_github(), fetch_monkeytype()

    out = {"header": header(), "footer": footer()}
    track = fetch_lastfm()
    if track or not os.environ.get("LASTFM_API_KEY"):
        out["nowplaying"] = nowplaying(track)
    if mt:
        out["monkeytype"] = monkeytype(mt)
    if gh:
        out["activity"] = activity(gh)
    if gh and mt:
        text, right = ABOUT, "english"
        run = best(mt, "words", "10")
        if run:
            text += f" currently hitting {int(run['wpm'])} wpm on the 10 word test."
            right = f"english · words 10 · {int(run['wpm'])} wpm"
        commit = latest_commit(gh)
        if commit:
            repo, message = commit
            text += f" right now i'm working on {repo}: {truncate(message.lower().rstrip('.'), 60)}."
        out["typing"] = typing(text, right)

    for name, content in out.items():
        (HERE / f"{name}.svg").write_text(content)
        print(f"wrote assets/{name}.svg")
    bust_cache()


def bust_cache():
    """GitHub caches README images by URL, so add ?v=<content hash> to force a refresh on change."""
    readme = HERE.parent / "README.md"

    def versioned(m):
        svg_file = HERE / f"{m.group(1)}.svg"
        if not svg_file.exists():
            return m.group(0)
        return f"assets/{m.group(1)}.svg?v={hashlib.sha1(svg_file.read_bytes()).hexdigest()[:8]}"

    readme.write_text(re.sub(r"assets/(\w+)\.svg(?:\?v=\w+)?", versioned, readme.read_text()))


if __name__ == "__main__":
    main()
