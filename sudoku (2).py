import json
import random
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from logic_engine import TECHNIQUES as LOGIC_TECHNIQUES, solve_logically

APP_DIR = Path.home() / ".portable_sudoku"
SAVE_FILE = APP_DIR / "game.json"

TECHNIQUES = [
    "Box Hidden Single", "Line Hidden Single", "Naked Single",
    "Locked Candidate", "Naked Pair", "Hidden Pair", "Naked Triple",
    "Hidden Triple", "BUG+1", "X-Wing", "Skyscraper", "2-String Kite",
    "Turbot Fish", "Unique Rectangle Type 1", "Finned X-Wing", "Swordfish",
    "Y-Wing", "XYZ-Wing", "W-Wing", "Simple Coloring", "X-Chain",
    "Finned Swordfish", "XY-Chain", "3D Medusa", "AICs",
]

DIFFICULTIES = {
    "Easy": (1, 3), "Medium": (4, 9), "Hard": (10, 19),
    "Expert": (20, 22), "Insane": (23, 25),
    "Almost Impossible": (1, 25), "Custom": (1, 25),
}

COLORS = {
    "window": "#0f172a", "panel": "#111c31", "cell": "#17233b",
    "given": "#dbeafe", "user": "#67e8f9", "wrong": "#fda4af",
    "selected": "#164e63", "related": "#172554", "line": "#52627d",
    "boxline": "#d5deed", "note": "#93a4bf", "text": "#f8fafc",
}


def copy_board(board):
    return [row[:] for row in board]


class SudokuEngine:
    def __init__(self):
        self.solution = [[0] * 9 for _ in range(9)]
        self.puzzle = [[0] * 9 for _ in range(9)]

    @staticmethod
    def candidates(board, row, col):
        if board[row][col]:
            return set()
        used = set(board[row]) | {board[r][col] for r in range(9)}
        br, bc = (row // 3) * 3, (col // 3) * 3
        used |= {board[r][c] for r in range(br, br + 3) for c in range(bc, bc + 3)}
        return set(range(1, 10)) - used

    def solve_one(self, board):
        cell = self._best_empty(board)
        if cell is None:
            return True
        row, col, options = cell
        for value in sorted(options):
            board[row][col] = value
            if self.solve_one(board):
                return True
        board[row][col] = 0
        return False

    def count_solutions(self, board, limit=2):
        cell = self._best_empty(board)
        if cell is None:
            return 1
        row, col, options = cell
        total = 0
        for value in options:
            board[row][col] = value
            total += self.count_solutions(board, limit)
            board[row][col] = 0
            if total >= limit:
                return total
        return total

    def _best_empty(self, board):
        best = None
        for row in range(9):
            for col in range(9):
                if board[row][col] == 0:
                    options = self.candidates(board, row, col)
                    if not options:
                        return row, col, set()
                    if best is None or len(options) < len(best[2]):
                        best = (row, col, options)
        return best

    def generate_unique(self, blanks=45):
        solved = [[0] * 9 for _ in range(9)]
        self._random_solve(solved)
        puzzle = copy_board(solved)
        positions = list(range(81))
        random.shuffle(positions)
        removed = 0
        for position in positions:
            if removed >= blanks:
                break
            row, col = divmod(position, 9)
            saved = puzzle[row][col]
            puzzle[row][col] = 0
            test = copy_board(puzzle)
            if self.count_solutions(test, 2) == 1:
                removed += 1
            else:
                puzzle[row][col] = saved
        self.solution, self.puzzle = solved, puzzle

    def _random_solve(self, board):
        cell = self._best_empty(board)
        if cell is None:
            return True
        row, col, options = cell
        values = list(options)
        random.shuffle(values)
        for value in values:
            board[row][col] = value
            if self._random_solve(board):
                return True
        board[row][col] = 0
        return False

    def load_import(self, text):
        cleaned = text.strip().replace(".", "0").replace(" ", "")
        if len(cleaned) != 81 or any(ch not in "0123456789" for ch in cleaned):
            raise ValueError("Use exactly 81 digits; use 0 or . for blanks.")
        board = [[int(cleaned[r * 9 + c]) for c in range(9)] for r in range(9)]
        if any(len(self.candidates(board, r, c)) == 0 for r in range(9) for c in range(9) if board[r][c] == 0):
            raise ValueError("The givens contain a contradiction.")
        solutions = copy_board(board)
        if self.count_solutions(solutions, 2) != 1:
            raise ValueError("The puzzle must have exactly one solution.")
        self.puzzle = board
        self.solution = copy_board(board)
        self.solve_one(self.solution)


class SudokuApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Portable Sudoku")
        self.root.configure(bg=COLORS["window"])
        self.root.minsize(620, 760)
        self.engine = SudokuEngine()
        self.difficulty = tk.StringVar(value="Medium")
        self.minimum_technique = tk.IntVar(value=1)
        self.maximum_technique = tk.IntVar(value=25)
        self.selected = None
        self.notes = [[set() for _ in range(9)] for _ in range(9)]
        self.givens = [[False] * 9 for _ in range(9)]
        self.history = []
        self.note_mode = False
        self.started_at = time.time()
        self.elapsed_before = 0
        self.hint_cells = set()
        self._build_ui()
        self.new_game()
        self._tick()

    def _build_ui(self):
        tk.Label(self.root, text="PORTABLE SUDOKU", fg=COLORS["text"], bg=COLORS["window"],
                 font=("Segoe UI", 23, "bold")).pack(anchor="w", padx=26, pady=(20, 0))
        tk.Label(self.root, text="Offline • unique puzzles • technique-based hints", fg="#94a3b8",
                 bg=COLORS["window"], font=("Segoe UI", 10)).pack(anchor="w", padx=28)

        toolbar = tk.Frame(self.root, bg=COLORS["window"])
        toolbar.pack(fill="x", padx=26, pady=14)
        ttk.Label(toolbar, text="Difficulty:").pack(side="left")
        box = ttk.Combobox(toolbar, textvariable=self.difficulty, values=list(DIFFICULTIES),
                           state="readonly", width=17)
        box.pack(side="left", padx=(8, 12))
        box.bind("<<ComboboxSelected>>", lambda _e: self.update_custom_controls())
        ttk.Button(toolbar, text="New game", command=self.new_game).pack(side="left")
        ttk.Button(toolbar, text="Import 81 digits", command=self.import_puzzle).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Save", command=self.save_game).pack(side="right")
        ttk.Button(toolbar, text="Resume", command=self.load_game).pack(side="right", padx=6)

        self.custom_frame = tk.Frame(self.root, bg=COLORS["window"])
        self.custom_frame.pack(fill="x", padx=26)
        self.min_label = tk.Label(self.custom_frame, fg="#94a3b8", bg=COLORS["window"], font=("Segoe UI", 9))
        self.min_label.pack(side="left")
        self.min_scale = tk.Scale(self.custom_frame, from_=1, to=25, orient="horizontal", variable=self.minimum_technique,
                                  showvalue=False, length=150, bg=COLORS["window"], fg="#cbd5e1", highlightthickness=0,
                                  command=lambda _v: self.update_custom_labels())
        self.min_scale.pack(side="left", padx=7)
        self.max_label = tk.Label(self.custom_frame, fg="#94a3b8", bg=COLORS["window"], font=("Segoe UI", 9))
        self.max_label.pack(side="left")
        self.max_scale = tk.Scale(self.custom_frame, from_=1, to=25, orient="horizontal", variable=self.maximum_technique,
                                  showvalue=False, length=150, bg=COLORS["window"], fg="#cbd5e1", highlightthickness=0,
                                  command=lambda _v: self.update_custom_labels())
        self.max_scale.pack(side="left", padx=7)
        self.update_custom_controls()

        status = tk.Frame(self.root, bg=COLORS["window"])
        status.pack(fill="x", padx=26, pady=(8, 4))
        self.timer_label = tk.Label(status, fg="#cbd5e1", bg=COLORS["window"], font=("Segoe UI", 11, "bold"))
        self.timer_label.pack(side="left")
        self.message_label = tk.Label(status, fg="#94a3b8", bg=COLORS["window"], font=("Segoe UI", 10),
                                      wraplength=470, justify="right")
        self.message_label.pack(side="right")

        self.canvas = tk.Canvas(self.root, width=540, height=540, bg=COLORS["cell"], highlightthickness=0)
        self.canvas.pack(padx=26, pady=9)
        self.canvas.bind("<Button-1>", self.canvas_click)

        controls = tk.Frame(self.root, bg=COLORS["window"])
        controls.pack(pady=(6, 0))
        self.note_button = ttk.Button(controls, text="Notes: OFF", command=self.toggle_note_mode)
        self.note_button.grid(row=0, column=0, columnspan=3, padx=5)
        ttk.Button(controls, text="Undo", command=self.undo).grid(row=0, column=3, columnspan=2, padx=5)
        ttk.Button(controls, text="Hint", command=self.hint).grid(row=0, column=5, columnspan=2, padx=5)
        ttk.Button(controls, text="Check", command=self.check).grid(row=0, column=7, columnspan=2, padx=5)
        self.number_buttons = []
        for value in range(1, 10):
            button = ttk.Button(controls, text=str(value), width=4, command=lambda v=value: self.enter(v))
            button.grid(row=1, column=value - 1, pady=10, padx=2)
            self.number_buttons.append(button)
        ttk.Button(controls, text="Clear", command=self.clear).grid(row=1, column=9, padx=4)
        self.root.bind("<Key>", self.keypress)

    def new_game(self):
        level = self.difficulty.get()
        if level == "Almost Impossible":
            self.set_message("Almost Impossible is reserved for imported puzzles. Paste one with Import 81 digits.", "#fbbf24")
            return
        low, high = DIFFICULTIES.get(level, (1, 3))
        if level == "Custom":
            low, high = sorted((self.minimum_technique.get(), self.maximum_technique.get()))
        if high > 9:
            self.set_message("This range requires advanced logical detectors that are not enabled yet; no misleading puzzle was generated.", "#fbbf24")
            return
        rated = self.generate_rated(low, high)
        if rated is None:
            self.set_message("No puzzle in this exact logical range was found within the retry budget.", "#fbbf24")
            return
        self.engine, result = rated
        self.givens = [[bool(self.engine.puzzle[r][c]) for c in range(9)] for r in range(9)]
        self.notes = [[set() for _ in range(9)] for _ in range(9)]
        self.history.clear(); self.selected = None; self.hint_cells.clear()
        self.started_at = time.time(); self.elapsed_before = 0
        self.set_message(f"Generated as {result.highest_technique_number}: {result.highest_technique}. Notes are independent toggles.", "#94a3b8")
        self.draw_board()

    def generate_rated(self, minimum, maximum, attempts=160):
        """Generate only a unique puzzle whose logical solve rating fits the range."""
        blank_targets = list(range(24, 51))
        for _ in range(attempts):
            candidate = SudokuEngine()
            candidate.generate_unique(random.choice(blank_targets))
            result = solve_logically(candidate.puzzle)
            if result.solved and minimum <= result.highest_technique_number <= maximum:
                return candidate, result
        return None

    def canvas_click(self, event):
        size = self.canvas.winfo_width() / 9
        col, row = min(8, int(event.x / size)), min(8, int(event.y / size))
        self.selected = (row, col)
        self.draw_board()

    def draw_board(self):
        self.canvas.delete("all")
        size = self.canvas.winfo_width() / 9
        selected = self.selected
        for r in range(9):
            for c in range(9):
                x0, y0, x1, y1 = c * size, r * size, (c + 1) * size, (r + 1) * size
                bg = COLORS["cell"]
                if selected == (r, c): bg = COLORS["selected"]
                elif selected and (selected[0] == r or selected[1] == c or (selected[0] // 3, selected[1] // 3) == (r // 3, c // 3)): bg = COLORS["related"]
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=bg, outline="")
                value = self.engine.puzzle[r][c]
                if value:
                    correct = value == self.engine.solution[r][c]
                    color = COLORS["given"] if self.givens[r][c] else (COLORS["user"] if correct else COLORS["wrong"])
                    self.canvas.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=str(value), fill=color,
                                            font=("Segoe UI", 25, "bold"))
                else:
                    for n in sorted(self.notes[r][c]):
                        nr, nc = divmod(n - 1, 3)
                        self.canvas.create_text(x0 + (nc + .5) * size / 3, y0 + (nr + .5) * size / 3,
                                                text=str(n), fill=COLORS["note"], font=("Segoe UI", 10, "bold"))
        for i in range(10):
            width = 3 if i % 3 == 0 else 1
            color = COLORS["boxline"] if i % 3 == 0 else COLORS["line"]
            self.canvas.create_line(i * size, 0, i * size, size * 9, fill=color, width=width)
            self.canvas.create_line(0, i * size, size * 9, i * size, fill=color, width=width)
        for r, c in self.hint_cells:
            self.canvas.create_rectangle(c * size + 4, r * size + 4, (c + 1) * size - 4, (r + 1) * size - 4,
                                         outline="#facc15", width=3)

    def enter(self, value):
        if self.selected is None: return self.set_message("Select a cell first.", "#fbbf24")
        r, c = self.selected
        if self.givens[r][c]: return self.set_message("That clue cannot be changed.", "#fbbf24")
        if self.note_mode:
            if self.engine.puzzle[r][c]: return self.set_message("Clear the cell before adding notes.", "#fbbf24")
            self.notes[r][c].symmetric_difference_update({value})
        else:
            old = self.engine.puzzle[r][c]
            self.history.append((r, c, old, self.notes[r][c].copy()))
            self.engine.puzzle[r][c] = value
            self.notes[r][c].clear()
        self.hint_cells.clear(); self.draw_board()

    def clear(self):
        if self.selected is None: return
        r, c = self.selected
        if self.givens[r][c]: return
        self.history.append((r, c, self.engine.puzzle[r][c], self.notes[r][c].copy()))
        self.engine.puzzle[r][c] = 0
        self.draw_board()

    def toggle_note_mode(self):
        self.note_mode = not self.note_mode
        self.note_button.config(text=f"Notes: {'ON' if self.note_mode else 'OFF'}")
        self.set_message("Click numbers to toggle notes on/off." if self.note_mode else "Normal entry mode.", "#67e8f9")

    def undo(self):
        if not self.history: return
        r, c, value, notes = self.history.pop()
        self.engine.puzzle[r][c], self.notes[r][c] = value, notes
        self.draw_board()

    def check(self):
        wrong = sum(1 for r in range(9) for c in range(9) if self.engine.puzzle[r][c] and self.engine.puzzle[r][c] != self.engine.solution[r][c])
        self.set_message("All entries are correct so far." if not wrong else f"{wrong} incorrect cell(s).", "#86efac" if not wrong else "#fda4af")

    def hint(self):
        try:
            result = solve_logically(self.engine.puzzle, max_steps=1)
        except ValueError:
            self.set_message("Hints need a valid current grid; use Check to find a conflicting entry first.", "#fbbf24")
            return
        if not result.steps:
            self.set_message("No supported logical step found. This puzzle needs a technique not implemented in the engine yet.", "#fbbf24")
            return
        step = result.steps[0]
        cells = [cell for cell, _value in step.placements] + [cell for cell, _value in step.eliminations]
        self.hint_cells = set(cells)
        if cells:
            self.selected = cells[0]
        self.set_message(f"Technique {step.technique_number}: {step.technique}. {step.explanation}", "#fde68a")
        self.draw_board()

    def find_hint(self):
        board = self.engine.puzzle
        candidates = [[SudokuEngine.candidates(board, r, c) for c in range(9)] for r in range(9)]
        # 1: Box Hidden Single, intentionally checked before line singles and naked singles.
        for br in range(0, 9, 3):
            for bc in range(0, 9, 3):
                for n in range(1, 10):
                    cells = [(r, c) for r in range(br, br + 3) for c in range(bc, bc + 3) if n in candidates[r][c]]
                    if len(cells) == 1:
                        r, c = cells[0]
                        return "Box Hidden Single", cells, f"In this 3×3 box, {n} can only go in row {r + 1}, column {c + 1}."
        # 2: Line Hidden Single, rows then columns.
        for r in range(9):
            for n in range(1, 10):
                cells = [(r, c) for c in range(9) if n in candidates[r][c]]
                if len(cells) == 1:
                    _, c = cells[0]
                    return "Line Hidden Single", cells, f"In row {r + 1}, {n} has only one possible position: column {c + 1}."
        for c in range(9):
            for n in range(1, 10):
                cells = [(r, c) for r in range(9) if n in candidates[r][c]]
                if len(cells) == 1:
                    r, _ = cells[0]
                    return "Line Hidden Single", cells, f"In column {c + 1}, {n} has only one possible position: row {r + 1}."
        # 3: Naked Single.
        for r in range(9):
            for c in range(9):
                if len(candidates[r][c]) == 1:
                    n = next(iter(candidates[r][c]))
                    return "Naked Single", [(r, c)], f"This cell has only one candidate: {n}."
        return None

    def import_puzzle(self):
        value = simpledialog.askstring("Import Sudoku", "Paste exactly 81 digits. Use 0 or . for blanks:")
        if value is None: return
        try:
            self.engine.load_import(value)
        except ValueError as error:
            messagebox.showerror("Invalid puzzle", str(error)); return
        rating = solve_logically(self.engine.puzzle)
        self.givens = [[bool(self.engine.puzzle[r][c]) for c in range(9)] for r in range(9)]
        self.notes = [[set() for _ in range(9)] for _ in range(9)]
        self.history.clear(); self.selected = None; self.hint_cells.clear()
        self.started_at = time.time(); self.elapsed_before = 0
        if rating.solved:
            self.set_message(f"Unique puzzle imported. Highest supported technique: {rating.highest_technique_number} — {rating.highest_technique}.", "#86efac")
        else:
            self.set_message("Unique puzzle imported, but its rating needs an advanced technique detector.", "#fbbf24")
        self.draw_board()

    def keypress(self, event):
        if event.char in "123456789": self.enter(int(event.char))
        elif event.keysym in ("BackSpace", "Delete"): self.clear()

    def set_message(self, text, color): self.message_label.config(text=text, fg=color)
    def elapsed(self): return self.elapsed_before + int(time.time() - self.started_at)
    def _tick(self):
        self.timer_label.config(text=f"Time {self.elapsed() // 60:02d}:{self.elapsed() % 60:02d}")
        self.root.after(1000, self._tick)

    def update_custom_controls(self):
        enabled = self.difficulty.get() == "Custom"
        self.min_scale.config(state="normal" if enabled else "disabled")
        self.max_scale.config(state="normal" if enabled else "disabled")
        self.update_custom_labels()

    def update_custom_labels(self):
        low, high = self.minimum_technique.get(), self.maximum_technique.get()
        self.min_label.config(text=f"Min {low}: {TECHNIQUES[low - 1]}")
        self.max_label.config(text=f"Max {high}: {TECHNIQUES[high - 1]}")

    def save_game(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        data = {"solution": self.engine.solution, "puzzle": self.engine.puzzle, "givens": self.givens,
                "difficulty": self.difficulty.get(), "notes": [[sorted(x) for x in row] for row in self.notes],
                "elapsed": self.elapsed()}
        SAVE_FILE.write_text(json.dumps(data), encoding="utf-8")
        self.set_message("Game saved locally.", "#86efac")

    def load_game(self):
        if not SAVE_FILE.exists(): return self.set_message("No saved game found.", "#fbbf24")
        try:
            data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
            self.engine.solution, self.engine.puzzle = data["solution"], data["puzzle"]
            self.givens = data.get("givens", [[bool(self.engine.puzzle[r][c]) for c in range(9)] for r in range(9)])
            self.difficulty.set(data.get("difficulty", "Medium"))
            self.notes = [[set(x) for x in row] for row in data.get("notes", [[[] for _ in range(9)] for _ in range(9)])]
            self.elapsed_before = data.get("elapsed", 0); self.started_at = time.time(); self.history.clear()
            self.update_custom_controls(); self.draw_board(); self.set_message("Saved game restored.", "#86efac")
        except (OSError, ValueError, KeyError):
            messagebox.showerror("Load error", "The saved game could not be read.")


if __name__ == "__main__":
    root = tk.Tk()
    SudokuApp(root)
    root.mainloop()
