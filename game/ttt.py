"""Issue-powered Tic-Tac-Toe for the profile README.

Visitors play X by opening an issue titled `ttt|move|<0-8>`.
The bot plays O, the board in README.md is redrawn, and the result is
written to $GITHUB_OUTPUT so the workflow can comment on the issue.
"""

import json
import os
import random
import re
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "game" / "state.json"
README = ROOT / "README.md"
REPO = os.environ.get("GITHUB_REPOSITORY", "teterw/teterw")

LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8),
         (0, 3, 6), (1, 4, 7), (2, 5, 8),
         (0, 4, 8), (2, 4, 6)]
EMOJI = {"X": "❌", "O": "⭕"}
START, END = "<!-- GAME:START -->", "<!-- GAME:END -->"


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"board": [" "] * 9, "moves": [],
            "stats": {"wins": 0, "losses": 0, "draws": 0},
            "players": {}, "last_result": None}


def winner(board):
    for a, b, c in LINES:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    if " " not in board:
        return "draw"
    return None


def bot_move(board):
    empty = [i for i, v in enumerate(board) if v == " "]
    # Win if possible, otherwise block, otherwise prefer center/corners.
    # Deliberately not perfect play, so visitors can actually win with a fork.
    for mark in ("O", "X"):
        for i in empty:
            trial = board.copy()
            trial[i] = mark
            if winner(trial) == mark:
                return i
    if 4 in empty:
        return 4
    corners = [i for i in empty if i in (0, 2, 6, 8)]
    return random.choice(corners or empty)


def cell(board, i):
    if board[i] != " ":
        return EMOJI[board[i]]
    title = quote(f"ttt|move|{i}")
    body = quote("Just press **Create** and wait ~30 seconds, the bot will answer here")
    return f'<a href="https://github.com/{REPO}/issues/new?title={title}&body={body}">⬜</a>'


def render(state):
    board = state["board"]
    rows = []
    for r in range(3):
        cells = "".join(f'<td align="center" width="64" height="64"><h2>{cell(board, r * 3 + c)}</h2></td>'
                        for c in range(3))
        rows.append(f"  <tr>{cells}</tr>")
    stats = state["stats"]
    top = sorted(state["players"].items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    leaderboard = "\n".join(f"| {n} | [@{u}](https://github.com/{u}) | {w} |"
                            for n, (u, w) in enumerate(top, 1)) or "| - | nobody yet, be the first! | 0 |"
    last = state.get("last_result") or "No finished games yet."
    return f"""{START}
<p align="center"><b>You are ❌, my bot is ⭕. Click an empty square to make your move!</b></p>
<table align="center">
{chr(10).join(rows)}
</table>
<p align="center">
  Visitor wins: <b>{stats['wins']}</b> &nbsp;·&nbsp; Bot wins: <b>{stats['losses']}</b> &nbsp;·&nbsp; Draws: <b>{stats['draws']}</b><br>
  <sub>Last game: {last}</sub>
</p>

<details>
<summary>Leaderboard & how it works</summary>

| # | Player | Wins |
|:-:|:------:|:----:|
{leaderboard}

Clicking a square opens an issue. A GitHub Action reads your move, the bot answers,
and this README gets redrawn. Refresh the page after ~30 seconds to see the new board.
</details>
{END}"""


def write_readme(state):
    text = README.read_text()
    pattern = re.compile(re.escape(START) + ".*?" + re.escape(END), re.S)
    README.write_text(pattern.sub(lambda _: render(state), text))


def output(message):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"message<<EOF\n{message}\nEOF\n")
    print(message)


def play(title, user):
    state = load_state()
    board = state["board"]

    m = re.fullmatch(r"ttt\|move\|([0-8])", title.strip())
    if not m:
        output("That doesn't look like a valid move. Click an empty square in the README to play!")
        return
    move = int(m.group(1))
    if board[move] != " ":
        output(f"Square {move} is already taken (someone probably moved at the same time). "
               "Check the README for the current board and try another square!")
        return

    board[move] = "X"
    state["moves"].append({"by": user, "cell": move})
    result = winner(board)
    bot_cell = None
    if result is None:
        bot_cell = bot_move(board)
        board[bot_cell] = "O"
        result = winner(board)

    msg = f"You played square **{move}**."
    if bot_cell is not None:
        msg += f" My bot answered with square **{bot_cell}**."

    if result is not None:
        players = sorted({mv["by"] for mv in state["moves"]})
        who = ", ".join(f"@{p}" for p in players)
        if result == "X":
            state["stats"]["wins"] += 1
            state["players"][user] = state["players"].get(user, 0) + 1
            state["last_result"] = f"X won, winning move by @{user}"
            msg += "\n\n**You won!** You're on the leaderboard now. A new game has started."
        elif result == "O":
            state["stats"]["losses"] += 1
            state["last_result"] = f"the bot won against {who}"
            msg += "\n\n**The bot won this one.** A new game has started, try again!"
        else:
            state["stats"]["draws"] += 1
            state["last_result"] = f"draw, played by {who}"
            msg += "\n\n**It's a draw!** A new game has started."
        state["board"] = [" "] * 9
        state["moves"] = []
    else:
        msg += "\n\nYour turn again (or anyone's!), go back to the README and pick a square."

    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")
    write_readme(state)
    output(msg + f"\n\n[Back to the board](https://github.com/{REPO.split('/')[0]})")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "render":
        write_readme(load_state())
    else:
        play(os.environ["ISSUE_TITLE"], os.environ["ISSUE_USER"])
