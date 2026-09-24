"""Generate typing/typing.svg: a Monkeytype-style animation that types a line of text.

Run `python typing/make_svg.py` after editing TEXT. The SVG uses SMIL so it animates
inside GitHub's README <img> without any JavaScript.
"""

import random
from pathlib import Path
from xml.sax.saxutils import escape

TEXT = ("hello, i'm teterw, a student at assumption college thonburi. i'm into "
        "tech and always learning something new by building projects. "
        "think you type faster than me? come race me on monkeytype!")

# Monkeytype "serika dark" theme
BG, SUB, MAIN, CARET, TEXT_COLOR = "#323437", "#646669", "#e2b714", "#e2b714", "#d1d0c5"

WIDTH, PAD_X, TOP = 820, 40, 92
CHAR_W, LINE_H, FONT_SIZE = 14.4, 40, 24
MAX_CHARS = int((WIDTH - 2 * PAD_X) / CHAR_W)
HOLD = 3.0  # seconds to show the finished line before looping

random.seed(7)  # deterministic output, so re-running doesn't create a git diff


def wrap(text):
    lines, line = [], ""
    for word in text.split(" "):
        candidate = f"{line} {word}" if line else word
        if len(candidate) > MAX_CHARS:
            lines.append(line + " ")
            line = word
        else:
            line = candidate
    return lines + [line]


def main():
    lines = wrap(TEXT)
    height = TOP + LINE_H * len(lines) + 12

    # Position of every character, plus a human-ish keystroke timeline.
    chars, t = [], 0.8
    for row, line in enumerate(lines):
        for col, ch in enumerate(line):
            t += random.uniform(0.045, 0.09) + (0.12 if ch in ",." else 0)
            chars.append((ch, PAD_X + col * CHAR_W, TOP + row * LINE_H, t))
    total = t + HOLD
    kt = lambda s: f"{s / total:.4f}"

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" '
           f'width="{WIDTH}" height="{height}" font-family="\'Roboto Mono\', \'Fira Code\', Consolas, '
           f'\'DejaVu Sans Mono\', monospace">',
           f'<rect width="{WIDTH}" height="{height}" rx="14" fill="{BG}"/>',
           f'<text x="{PAD_X}" y="44" font-size="20" fill="{MAIN}" font-weight="700">monkeytype</text>',
           f'<text x="{WIDTH - PAD_X}" y="44" font-size="15" fill="{SUB}" text-anchor="end">'
           f'english · punctuation · teterw</text>']

    for ch, x, y, at in chars:
        if ch == " ":
            continue
        out.append(
            f'<text x="{x:.1f}" y="{y}" font-size="{FONT_SIZE}" fill="{SUB}">{escape(ch)}'
            f'<animate attributeName="fill" values="{SUB};{TEXT_COLOR};{SUB}" '
            f'keyTimes="0;{kt(at)};{kt(total - 0.05)}" calcMode="discrete" '
            f'dur="{total:.2f}s" repeatCount="indefinite"/></text>')

    # Caret: sits before the next character to type, blinks while idle.
    xs = [chars[0][1]] + [x + CHAR_W for _, x, _, _ in chars]
    ys = [chars[0][2]] + [y for _, _, y, _ in chars]
    times = ["0"] + [kt(at) for *_, at in chars]
    out.append(
        f'<rect width="2.5" height="{FONT_SIZE + 4}" rx="1" fill="{CARET}">'
        f'<animate attributeName="x" values="{";".join(f"{x:.1f}" for x in xs)}" '
        f'keyTimes="{";".join(times)}" calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite"/>'
        f'<animate attributeName="y" values="{";".join(str(y - FONT_SIZE + 1) for y in ys)}" '
        f'keyTimes="{";".join(times)}" calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite"/>'
        f'<animate attributeName="opacity" values="1;0;1" dur="1s" repeatCount="indefinite"/>'
        f'</rect>')

    out.append("</svg>")

    Path(__file__).with_name("typing.svg").write_text("\n".join(out) + "\n")
    print(f"{len(lines)} lines, {len(chars)} chars, loop {total:.1f}s")


if __name__ == "__main__":
    main()
