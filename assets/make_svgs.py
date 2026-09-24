"""Generate the Monkeytype-themed SVGs used in the profile README.

    python assets/make_svgs.py

- header.svg  the Monkeytype-style top bar + test config bar
- typing.svg  a typing test that types TEXT (the "About me")
- footer.svg  Monkeytype's key-hint footer

Everything animates with SMIL, so it works inside GitHub's README <img> without JavaScript.
"""

import random
from pathlib import Path
from xml.sax.saxutils import escape

TEXT = ("hello, i'm teterw, a student at assumption college thonburi. i'm into "
        "tech and always learning something new by building projects. "
        "currently hitting 193 wpm on the 10 word test.")

# Monkeytype "serika dark" theme
BG, BG_DARK, SUB, MAIN, TEXT_COLOR = "#323437", "#2c2e31", "#646669", "#e2b714", "#d1d0c5"
FONT = "'Roboto Mono', 'Fira Code', Consolas, 'DejaVu Sans Mono', monospace"

WIDTH, PAD_X = 820, 40
HERE = Path(__file__).parent


def svg(height, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" '
            f'width="{WIDTH}" height="{height}" font-family="{FONT}">\n'
            f'<rect width="{WIDTH}" height="{height}" rx="14" fill="{BG}"/>\n'
            + "\n".join(body) + "\n</svg>\n")


def keyboard_icon(x, y):
    """Monkeytype's keyboard logo, roughly."""
    parts = [f'<rect x="{x}" y="{y}" width="52" height="34" rx="7" fill="none" '
             f'stroke="{MAIN}" stroke-width="3.5"/>']
    for row, keys in enumerate([(0, 1, 2, 3), (0, 1, 2, 3)]):
        for k in keys:
            parts.append(f'<rect x="{x + 9 + k * 9.5}" y="{y + 8 + row * 8}" width="5" '
                         f'height="4" rx="1" fill="{MAIN}"/>')
    parts.append(f'<rect x="{x + 13}" y="{y + 24}" width="26" height="4" rx="1" fill="{MAIN}"/>')
    return parts


def header():
    height = 150
    body = keyboard_icon(PAD_X, 32)
    body += [
        f'<text x="{PAD_X + 66}" y="38" font-size="11" fill="{SUB}">student see</text>',
        f'<text x="{PAD_X + 64}" y="66" font-size="34" fill="{TEXT_COLOR}">teterw</text>',
        f'<text x="{WIDTH - PAD_X}" y="58" font-size="15" fill="{SUB}" text-anchor="end">'
        f'act · thailand · always building</text>',
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
        for i, (icon, label, on) in enumerate(group):
            text = f"{icon} {label}" if icon else label
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
            body.append(f'<text x="{x:.1f}" y="118" font-size="{font}" '
                        f'fill="{MAIN if on else SUB}">{escape(text)}</text>')
    return svg(height, body)


def typing():
    random.seed(7)  # deterministic output, so re-running doesn't create a git diff
    top, char_w, line_h, font = 92, 14.4, 40, 24
    max_chars, hold = int((WIDTH - 2 * PAD_X) / char_w), 3.0

    lines, line = [], ""
    for word in TEXT.split(" "):
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
            t += random.uniform(0.045, 0.09) + (0.12 if ch in ",.?!" else 0)
            chars.append((ch, PAD_X + col * char_w, top + row * line_h, t))
    total = t + hold
    kt = lambda s: f"{s / total:.4f}"

    body = [f'<text x="{PAD_X}" y="44" font-size="20" fill="{MAIN}" font-weight="700">about me</text>',
            f'<text x="{WIDTH - PAD_X}" y="44" font-size="15" fill="{SUB}" text-anchor="end">'
            f'english · words 10 · 193 wpm</text>']
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


def footer():
    height = 92
    font, char_w = 13, 13 * 0.6

    def key(x, y, label):
        w = len(label) * char_w + 12
        return w, [f'<rect x="{x:.1f}" y="{y - 15}" width="{w:.1f}" height="21" rx="4" fill="{SUB}"/>',
                   f'<text x="{x + 6:.1f}" y="{y}" font-size="{font}" fill="{BG}">{label}</text>']

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


if __name__ == "__main__":
    for name, build in (("header", header), ("typing", typing), ("footer", footer)):
        (HERE / f"{name}.svg").write_text(build())
        print(f"wrote assets/{name}.svg")
