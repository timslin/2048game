
"""2048 clone with smooth animations and a secret cheat code.

Controls:
Arrow keys or WASD = Move
R = Restart
Esc = Quit
Type 2048 = Fill the board with 2048 tiles
"""

import json
import math
import os
import random
import time
import tkinter as tk

SIZE = 4
CELL = 100
GAP = 10
BOARD_PX = SIZE * CELL + (SIZE + 1) * GAP
HEADER_PX = 110
BEST_FILE = os.path.join(os.path.expanduser("~"), ".game_2048_best.json")

SLIDE_MS = 110
POP_MS = 130
FRAME_MS = 10

BG = "#faf8ef"
BOARD_BG = "#bbada0"
EMPTY = "#cdc1b4"

TILE_COLORS = {
    2: ("#32322C", "#776e65"),
    4: ("#32322C", "#776e65"),
    8: ("#13C4A3", "#f9f6f2"),
    16: ("#13C4A3", "#f9f6f2"),
    32: ("#13C4A3", "#f9f6f2"),
    64: ("#13C4A3", "#f9f6f2"),
    128: ("#36F1CD", "#f9f6f2"),
    256: ("#39A0ED", "#f9f6f2"),
    512: ("#39A0ED", "#f9f6f2"),
    1024: ("#39A0ED", "#f9f6f2"),
    2048: ("#4C6085", "#f9f6f2"),
}

SUPER_TILE = ("#3c3a32", "#f9f6f2")

KEYMAP = {
    "Left": "left", "a": "left", "A": "left",
    "Right": "right", "d": "right", "D": "right",
    "Up": "up", "w": "up", "W": "up",
    "Down": "down", "s": "down", "S": "down",
}


def ease_out_cubic(t):
    return 1 - (1 - t) ** 3


def ease_out_back(t):
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def slide_line(values):
    tiles = [(i, v) for i, v in enumerate(values) if v]
    out, moves, merged, points = [], [], set(), 0
    k = 0

    while k < len(tiles):
        i, v = tiles[k]
        dst = len(out)

        if k + 1 < len(tiles) and tiles[k + 1][1] == v:
            j = tiles[k + 1][0]
            out.append(v * 2)
            points += v * 2
            moves.append((i, dst, v))
            moves.append((j, dst, v))
            merged.add(dst)
            k += 2
        else:
            out.append(v)
            moves.append((i, dst, v))
            k += 1

    out.extend([0] * (SIZE - len(out)))
    return out, points, moves, merged


def lines_for(direction):
    rng = range(SIZE)

    if direction == "left":
        return [[(r, c) for c in rng] for r in rng]
    if direction == "right":
        return [[(r, c) for c in reversed(rng)] for r in rng]
    if direction == "up":
        return [[(r, c) for r in rng] for c in rng]

    return [[(r, c) for r in reversed(rng)] for c in rng]


class Game:

    def __init__(self):
        self.reset()

    def reset(self):
        self.board = [[0] * SIZE for _ in range(SIZE)]
        self.score = 0
        self.won = False
        self.keep_playing = False
        self.slides = []
        self.merged = set()
        self.spawned = None

        self.spawn()
        self.spawn()

    # SECRET CHEAT
    def cheat_2048(self):
        self.board = [[2048] * SIZE for _ in range(SIZE)]
        self.score = 0
        self.won = True
        self.keep_playing = False
        self.slides = []
        self.merged = set()
        self.spawned = None

    def spawn(self):
        empties = [
            (r, c)
            for r in range(SIZE)
            for c in range(SIZE)
            if not self.board[r][c]
        ]

        if not empties:
            return None

        r, c = random.choice(empties)
        self.board[r][c] = 4 if random.random() < 0.1 else 2
        self.spawned = (r, c)

        return self.spawned

    def move(self, direction):
        new_board = [[0] * SIZE for _ in range(SIZE)]
        slides, merged, gained = [], set(), 0

        for coords in lines_for(direction):
            values = [self.board[r][c] for r, c in coords]
            out, pts, moves, merged_dsts = slide_line(values)

            gained += pts

            for k, (r, c) in enumerate(coords):
                new_board[r][c] = out[k]

            for src, dst, v in moves:
                slides.append((coords[src], coords[dst], v))

            for d in merged_dsts:
                merged.add(coords[d])

        if new_board == self.board:
            return False

        self.board = new_board
        self.score += gained
        self.slides = slides
        self.merged = merged

        self.spawn()

        if not self.won and any(2048 in row for row in self.board):
            self.won = True

        return True

    def can_move(self):
        for r in range(SIZE):
            for c in range(SIZE):
                if self.board[r][c] == 0:
                    return True

                if c + 1 < SIZE and self.board[r][c] == self.board[r][c + 1]:
                    return True

                if r + 1 < SIZE and self.board[r][c] == self.board[r + 1][c]:
                    return True

        return False


class App:

    def __init__(self, root):
        self.root = root
        root.title("2048")
        root.configure(bg=BG)
        root.resizable(False, False)

        self.game = Game()
        self.best = self.load_best()

        self.animating = False
        self.pending = None
        self.after_id = None
        self.t0 = 0.0

        # Secret code input
        self.cheat_code = ""

        self.canvas = tk.Canvas(
            root,
            width=BOARD_PX,
            height=HEADER_PX + BOARD_PX,
            bg=BG,
            highlightthickness=0,
        )

        self.canvas.pack(padx=10, pady=10)

        root.bind("<Key>", self.on_key)
        self.canvas.bind("<Button-1>", self.on_click)

        self.draw()

    # PERSISTENCE

    def load_best(self):
        try:
            with open(BEST_FILE, "r") as f:
                return int(json.load(f).get("best", 0))
        except (OSError, ValueError, AttributeError):
            return 0

    def save_best(self):
        try:
            with open(BEST_FILE, "w") as f:
                json.dump({"best": self.best}, f)
        except OSError:
            pass

    # INPUT

    def on_key(self, event):
        if event.keysym == "Escape":
            self.root.destroy()
            return

        if event.keysym in ("r", "R"):
            self.restart()
            return

        # SECRET CHEAT CODE: TYPE 2048
        if event.char and event.char.isdigit():
            self.cheat_code += event.char

            if len(self.cheat_code) > 4:
                self.cheat_code = self.cheat_code[-4:]

            if self.cheat_code == "2048":

                if self.after_id is not None:
                    self.root.after_cancel(self.after_id)
                    self.after_id = None

                self.animating = False
                self.pending = None

                self.game.cheat_2048()

                self.draw()

                self.cheat_code = ""
                return

        direction = KEYMAP.get(event.keysym)

        if not direction:
            return

        if self.animating:
            self.pending = direction
            return

        self.handle_move(direction)

    def on_click(self, event):
        if BOARD_PX - 120 <= event.x <= BOARD_PX and 60 <= event.y <= 95:
            self.restart()

    def handle_move(self, direction):
        g = self.game

        if g.won and not g.keep_playing:
            g.keep_playing = True
            self.draw()
            return

        if not g.can_move():
            return

        if g.move(direction):

            if g.score > self.best:
                self.best = g.score
                self.save_best()

            self.start_animation()

    def restart(self):
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        self.animating = False
        self.pending = None
        self.cheat_code = ""

        self.game.reset()
        self.draw()

    # ANIMATION

    def start_animation(self):
        self.animating = True
        self.t0 = time.perf_counter()
        self.tick()

    def tick(self):
        t = (time.perf_counter() - self.t0) * 1000.0

        if t >= SLIDE_MS + POP_MS:
            self.animating = False
            self.after_id = None
            self.draw()

            if self.pending:
                direction, self.pending = self.pending, None
                self.handle_move(direction)

            return

        self.draw(t)
        self.after_id = self.root.after(FRAME_MS, self.tick)

    # DRAWING

    def rounded_rect(self, x1, y1, x2, y2, r, **kw):
        r = max(0.0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))

        pts = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]

        return self.canvas.create_polygon(pts, smooth=True, **kw)

    @staticmethod
    def cell_center(r, c):
        x = GAP + c * (CELL + GAP) + CELL / 2
        y = HEADER_PX + GAP + r * (CELL + GAP) + CELL / 2
        return x, y

    def draw_tile(self, r, c, value, scale=1.0):
        if scale <= 0.01:
            return

        cx, cy = self.cell_center(r, c)
        half = CELL * scale / 2

        bg, fg = TILE_COLORS.get(value, SUPER_TILE)

        self.rounded_rect(
            cx - half, cy - half,
            cx + half, cy + half,
            6 * scale,
            fill=bg
        )

        base = 36 if value < 100 else 30 if value < 1000 else 24
        size = int(base * scale)

        if size >= 6:
            self.canvas.create_text(
                cx, cy,
                text=str(value),
                font=("Helvetica", size, "bold"),
                fill=fg
            )

    def draw(self, t=None):
        c = self.canvas
        g = self.game

        c.delete("all")

        # HEADER
        c.create_text(
            0, 10,
            text="2048",
            anchor="nw",
            font=("Helvetica", 40, "bold"),
            fill="#776e65"
        )

        self.score_box(BOARD_PX - 170, 8, "SCORE", g.score)
        self.score_box(BOARD_PX - 85, 8, "BEST", self.best)

        self.rounded_rect(
            BOARD_PX - 120, 60,
            BOARD_PX, 95,
            6,
            fill="#8f7a66"
        )

        c.create_text(
            BOARD_PX - 60, 78,
            text="New Game",
            font=("Helvetica", 12, "bold"),
            fill="#f9f6f2"
        )

        c.create_text(
            0, 80,
            text="Arrows/WASD to move, R to restart",
            anchor="w",
            font=("Helvetica", 10),
            fill="#776e65"
        )

        # BOARD
        top = HEADER_PX

        self.rounded_rect(
            0, top,
            BOARD_PX, top + BOARD_PX,
            8,
            fill=BOARD_BG
        )

        for r in range(SIZE):
            for col in range(SIZE):
                cx, cy = self.cell_center(r, col)

                self.rounded_rect(
                    cx - CELL / 2,
                    cy - CELL / 2,
                    cx + CELL / 2,
                    cy + CELL / 2,
                    6,
                    fill=EMPTY
                )

        # TILES
        if t is None:
            for r in range(SIZE):
                for col in range(SIZE):
                    if g.board[r][col]:
                        self.draw_tile(r, col, g.board[r][col])

        elif t < SLIDE_MS:
            k = ease_out_cubic(t / SLIDE_MS)

            for (sr, sc), (dr, dc), v in g.slides:
                self.draw_tile(
                    sr + (dr - sr) * k,
                    sc + (dc - sc) * k,
                    v
                )

        else:
            p = min(1.0, (t - SLIDE_MS) / POP_MS)

            for r in range(SIZE):
                for col in range(SIZE):
                    v = g.board[r][col]

                    if not v:
                        continue

                    if (r, col) == g.spawned:
                        scale = ease_out_back(p)

                    elif (r, col) in g.merged:
                        scale = 1.0 + 0.18 * math.sin(math.pi * p)

                    else:
                        scale = 1.0

                    self.draw_tile(r, col, v, scale)

        # OVERLAYS
        if t is None:
            if not g.can_move():
                self.overlay(
                    "Game over!",
                    "Press R to try again",
                    "#776e65"
                )

            elif g.won and not g.keep_playing:
                self.overlay(
                    "You win!",
                    "Press any arrow to keep playing",
                    "#edc22e"
                )

    def score_box(self, x, y, label, value):
        self.rounded_rect(
            x, y,
            x + 80, y + 48,
            6,
            fill=BOARD_BG
        )

        self.canvas.create_text(
            x + 40, y + 12,
            text=label,
            font=("Helvetica", 9, "bold"),
            fill="#eee4da"
        )

        self.canvas.create_text(
            x + 40, y + 32,
            text=str(value),
            font=("Helvetica", 15, "bold"),
            fill="white"
        )

    def overlay(self, title, subtitle, color):
        top = HEADER_PX

        self.canvas.create_rectangle(
            0, top,
            BOARD_PX, top + BOARD_PX,
            fill="#faf8ef",
            stipple="gray50",
            outline=""
        )

        self.canvas.create_text(
            BOARD_PX / 2,
            top + BOARD_PX / 2 - 15,
            text=title,
            font=("Helvetica", 40, "bold"),
            fill=color
        )

        self.canvas.create_text(
            BOARD_PX / 2,
            top + BOARD_PX / 2 + 30,
            text=subtitle,
            font=("Helvetica", 13),
            fill="#776e65"
        )


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
