"""F4D3R by HIGHBAUD — rainbow text prog, recreated for 2026.

Run: python fader.py

Pipeline: input -> case -> unicode style -> zalgo -> scroller -> color -> emit.

Emits in three flavors:
  - AOL HTML  (classic <FONT COLOR="#XXX"> soup, optional BACK via inline STYLE,
               wrapped in <B>/<I>/<U> per the format checkboxes)
  - Discord ANSI  (```ansi block with bold/underline + nearest-of-8 fg/bg colors)
  - Plain  (transformed Unicode text only, no color — for Twitter, Discord names,
            anywhere that strips formatting)
"""

import colorsys
import os
import random
import sys
import tkinter as tk
import unicodedata
from tkinter import ttk


def _resource_path(name):
    """Resolve a data file's runtime path. PyInstaller's --onefile bundles extract
    to sys._MEIPASS at startup; otherwise files live next to this script."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)

try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


# --- Color palettes ----------------------------------------------------------

# Discord ANSI foreground codes mapped to the RGB Discord actually renders.
DISCORD_ANSI_FG = [
    (30, (79, 84, 92)),
    (31, (220, 50, 47)),
    (32, (133, 153, 0)),
    (33, (181, 137, 0)),
    (34, (38, 139, 210)),
    (35, (211, 54, 130)),
    (36, (42, 161, 152)),
    (37, (238, 232, 213)),
]

# Discord ANSI background codes. Discord renders these as Solarized base tones —
# mostly grays with a few accents — so a bg fade in Discord looks more muted
# than the AOL HTML version.
DISCORD_ANSI_BG = [
    (40, (0, 43, 54)),
    (41, (203, 75, 22)),
    (42, (88, 110, 117)),
    (43, (101, 123, 131)),
    (44, (131, 148, 150)),
    (45, (108, 113, 196)),
    (46, (147, 161, 161)),
    (47, (253, 246, 227)),
]


PRESETS = {
    "Rainbow":      {"hue_start": 0.00, "hue_range": 1.00, "sat": 1.00, "val": 1.00},
    "Fire":         {"hue_start": 0.00, "hue_range": 0.15, "sat": 1.00, "val": 1.00},
    "Ocean":        {"hue_start": 0.48, "hue_range": 0.18, "sat": 1.00, "val": 0.95},
    "Forest":       {"hue_start": 0.20, "hue_range": 0.18, "sat": 1.00, "val": 0.80},
    "Sunset":       {"hue_start": 0.95, "hue_range": 0.18, "sat": 0.90, "val": 1.00},
    "Cotton Candy": {"hue_start": 0.80, "hue_range": 0.30, "sat": 0.50, "val": 1.00},
    "Toxic":        {"hue_start": 0.20, "hue_range": 0.25, "sat": 1.00, "val": 1.00},
    "Vaporwave":    {"hue_start": 0.78, "hue_range": 0.20, "sat": 0.70, "val": 1.00},
    "AOL Classic":  {"hue_start": 0.00, "hue_range": 1.00, "sat": 1.00, "val": 1.00},
}


# --- Case transforms ---------------------------------------------------------

def _spongebob(text):
    out = []
    letter_idx = 0
    for c in text:
        if c.isalpha():
            out.append(c.upper() if letter_idx % 2 else c.lower())
            letter_idx += 1
        else:
            out.append(c)
    return "".join(out)


def _random_case(text):
    out = []
    for i, c in enumerate(text):
        if c.isalpha():
            r = random.Random(i * 7919 + ord(c))
            out.append(c.upper() if r.random() < 0.5 else c.lower())
        else:
            out.append(c)
    return "".join(out)


CASE_MODES = {
    "None":      lambda t: t,
    "lower":     str.lower,
    "UPPER":     str.upper,
    "Title":     str.title,
    "sPoNgEbOb": _spongebob,
    "RaNdOm":    _random_case,
}


# --- Unicode style transforms ------------------------------------------------

def _styled(char, base_upper, base_lower, base_digit=None, overrides=None):
    overrides = overrides or {}
    if char in overrides:
        return overrides[char]
    if base_upper is not None and "A" <= char <= "Z":
        return chr(base_upper + (ord(char) - ord("A")))
    if base_lower is not None and "a" <= char <= "z":
        return chr(base_lower + (ord(char) - ord("a")))
    if base_digit is not None and "0" <= char <= "9":
        return chr(base_digit + (ord(char) - ord("0")))
    return char


# Math Alphanumeric blocks have known holes — letters already encoded elsewhere
# in the BMP. These tables fill them in.
SCRIPT_HOLES = {
    "B": "ℬ", "E": "ℰ", "F": "ℱ", "H": "ℋ",
    "I": "ℐ", "L": "ℒ", "M": "ℳ", "R": "ℛ",
    "e": "ℯ", "g": "ℊ", "o": "ℴ",
}
FRAKTUR_HOLES = {
    "C": "ℭ", "H": "ℌ", "I": "ℑ", "R": "ℜ", "Z": "ℨ",
}
DOUBLE_STRUCK_HOLES = {
    "C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ",
    "Q": "ℚ", "R": "ℝ", "Z": "ℤ",
}
CIRCLED_DIGITS = {
    "0": "⓪", "1": "①", "2": "②", "3": "③",
    "4": "④", "5": "⑤", "6": "⑥", "7": "⑦",
    "8": "⑧", "9": "⑨",
}

UNICODE_STYLES = {
    "None":          lambda c: c,
    "Bold":          lambda c: _styled(c, 0x1D400, 0x1D41A, 0x1D7CE),
    "Italic":        lambda c: _styled(c, 0x1D434, 0x1D44E, None, {"h": "ℎ"}),
    "Bold Italic":   lambda c: _styled(c, 0x1D468, 0x1D482),
    "Script":        lambda c: _styled(c, 0x1D49C, 0x1D4B6, None, SCRIPT_HOLES),
    "Bold Script":   lambda c: _styled(c, 0x1D4D0, 0x1D4EA),
    "Fraktur":       lambda c: _styled(c, 0x1D504, 0x1D51E, None, FRAKTUR_HOLES),
    "Double-struck": lambda c: _styled(c, 0x1D538, 0x1D552, 0x1D7D8, DOUBLE_STRUCK_HOLES),
    "Sans-serif":    lambda c: _styled(c, 0x1D5A0, 0x1D5BA, 0x1D7E2),
    "Sans Bold":     lambda c: _styled(c, 0x1D5D4, 0x1D5EE, 0x1D7EC),
    "Mono":          lambda c: _styled(c, 0x1D670, 0x1D68A, 0x1D7F6),
    "Circled":       lambda c: _styled(c, 0x24B6, 0x24D0, None, CIRCLED_DIGITS),
    "Fullwidth":     lambda c: _styled(c, 0xFF21, 0xFF41, 0xFF10),
}


def apply_unicode_style(text, style):
    fn = UNICODE_STYLES[style]
    return "".join(fn(c) for c in text)


# --- Zalgo -------------------------------------------------------------------

ZALGO_UP   = [chr(c) for c in range(0x0300, 0x0315)]
ZALGO_MID  = [chr(c) for c in range(0x0334, 0x0338)]
ZALGO_DOWN = [chr(c) for c in range(0x0316, 0x033F)]


def apply_zalgo(text, intensity):
    """Add combining diacritics. Intensity 0 = off; ~10 = chaos. Deterministic."""
    if intensity <= 0:
        return text
    out = []
    for i, c in enumerate(text):
        out.append(c)
        if not c.isalpha():
            continue
        r = random.Random(i * 7919 + ord(c))
        for pool in (ZALGO_UP, ZALGO_MID, ZALGO_DOWN):
            for _ in range(r.randint(0, intensity)):
                out.append(r.choice(pool))
    return "".join(out)


# --- Scroller ---------------------------------------------------------------

def apply_scroller(text, width, lines):
    """Pad with spaces and emit `lines` left-shifted copies for a marquee feel."""
    if lines < 2:
        return text
    pad = " " * width
    full = pad + text + pad
    out = []
    max_offset = max(len(full) - width, 1)
    for i in range(lines):
        if lines == 1:
            t = 0
        else:
            t = int(i * max_offset / (lines - 1))
        out.append(full[t:t + width])
    return "\n".join(out)


# --- Grapheme clustering + coloring -----------------------------------------

def grapheme_clusters(text):
    """Split text into clusters: each is one base codepoint + any trailing combining marks."""
    clusters = []
    current = ""
    for c in text:
        if current and unicodedata.category(c).startswith("M"):
            current += c
        else:
            if current:
                clusters.append(current)
            current = c
    if current:
        clusters.append(current)
    return clusters


def _is_color_unit(cluster):
    """A cluster gets a color iff its base is not whitespace/newline."""
    base = cluster[0]
    return not (base.isspace() or base == "\n")


def char_colors(text, hue_start, hue_range, sat, val, per_word=False):
    """Return [(cluster_text, rgb_or_None), ...]. None means no color (whitespace)."""
    clusters = grapheme_clusters(text)

    indices = []
    if per_word:
        word_idx = -1
        in_word = False
        for cl in clusters:
            if _is_color_unit(cl):
                if not in_word:
                    word_idx += 1
                    in_word = True
                indices.append(word_idx)
            else:
                in_word = False
                indices.append(None)
        total = word_idx + 1
    else:
        idx = 0
        for cl in clusters:
            if _is_color_unit(cl):
                indices.append(idx)
                idx += 1
            else:
                indices.append(None)
        total = idx

    if total <= 1:
        denom = 1
    elif hue_range >= 0.999:
        denom = total
    else:
        denom = total - 1

    out = []
    for cl, i in zip(clusters, indices):
        if i is None:
            out.append((cl, None))
        else:
            t = i / denom if total > 1 else 0.0
            h = (hue_start + t * hue_range) % 1.0
            r, g, b = colorsys.hsv_to_rgb(h, sat, val)
            out.append((cl, (int(r * 255), int(g * 255), int(b * 255))))
    return out


def _shift_hue(rgb, amount):
    h, s, v = colorsys.rgb_to_hsv(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
    h = (h + amount) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def add_backgrounds(colored, mode):
    """Take [(cluster, fg)] and return [(cluster, fg, bg)] per the bg mode."""
    if mode == "None":
        return [(cl, fg, None) for cl, fg in colored]
    if mode == "Opposite hue":
        return [(cl, fg, _shift_hue(fg, 0.5) if fg else None) for cl, fg in colored]
    if mode == "Reverse fade":
        fgs = [fg for _, fg in colored]
        rev = list(reversed([f for f in fgs if f is not None]))
        ri = 0
        result = []
        for cl, fg in colored:
            if fg is None:
                result.append((cl, fg, None))
            else:
                result.append((cl, fg, rev[ri]))
                ri += 1
        return result
    if mode == "Dark contrast":
        return [(cl, fg, (20, 20, 30) if fg else None) for cl, fg in colored]
    return [(cl, fg, None) for cl, fg in colored]


# --- Emitters ----------------------------------------------------------------

def rgb_to_hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def to_aol_html(triples, bold, italic, underline, size):
    """Classic per-char <FONT> soup. BG via inline STYLE for modern renderers."""
    parts = []
    for cluster, fg, bg in triples:
        if fg is None and bg is None:
            parts.append(cluster.replace("\n", "<BR>"))
            continue
        attrs = []
        if fg is not None:
            attrs.append(f'COLOR="{rgb_to_hex(fg)}"')
        if size and size != "3":
            attrs.append(f'SIZE="{size}"')
        if bg is not None:
            attrs.append(f'STYLE="background-color:{rgb_to_hex(bg)}"')
        body = cluster.replace("\n", "<BR>")
        parts.append(f'<FONT {" ".join(attrs)}>{body}</FONT>')
    inner = "".join(parts)
    if bold:
        inner = f"<B>{inner}</B>"
    if italic:
        inner = f"<I>{inner}</I>"
    if underline:
        inner = f"<U>{inner}</U>"
    return inner


def nearest_ansi(rgb, palette):
    best_code, best_dist = palette[0][0], float("inf")
    for code, target in palette:
        d = (rgb[0] - target[0]) ** 2 + (rgb[1] - target[1]) ** 2 + (rgb[2] - target[2]) ** 2
        if d < best_dist:
            best_dist = d
            best_code = code
    return best_code


def to_discord_ansi(triples, bold, underline):
    """Discord renders ansi blocks. Italic (3) doesn't render so we skip it.
    Only emit a new escape when the state changes."""
    out = ["```ansi\n"]
    last_state = None
    for cluster, fg, bg in triples:
        if fg is None and bg is None:
            if last_state is not None:
                out.append("[0m")
                last_state = None
            out.append(cluster)
            continue
        codes = []
        if bold:
            codes.append("1")
        if underline:
            codes.append("4")
        if fg is not None:
            codes.append(str(nearest_ansi(fg, DISCORD_ANSI_FG)))
        if bg is not None:
            codes.append(str(nearest_ansi(bg, DISCORD_ANSI_BG)))
        state = tuple(codes)
        if state != last_state:
            out.append("[" + ";".join(codes) + "m")
            last_state = state
        out.append(cluster)
    out.append("[0m\n```")
    return "".join(out)


def to_plain(triples):
    return "".join(cl for cl, _, _ in triples)


# --- Transform pipeline ------------------------------------------------------

def transform_text(text, case, style, zalgo, scroller_on, scroller_width, scroller_lines):
    text = CASE_MODES[case](text)
    text = apply_unicode_style(text, style)
    text = apply_zalgo(text, zalgo)
    if scroller_on:
        text = apply_scroller(text, scroller_width, scroller_lines)
    return text


# --- GUI ---------------------------------------------------------------------

BG    = "#15082E"
BG2   = "#0A041A"
FG    = "white"
ACCENT_Y = "#FFFF00"
ACCENT_G = "#00FF00"
ACCENT_M = "#FF1AFF"
ACCENT_C = "#00FFFF"
BG_IMAGE_PATH = _resource_path("background.png")
SPLASH_IMAGE_PATH = _resource_path("splash.png")


class FaderApp:
    def __init__(self, root):
        self.root = root
        root.title("F4D3R by HIGHBAUD")
        root.geometry("880x840")
        root.configure(bg=BG)
        root.minsize(720, 700)

        self._install_bg_image()
        self._build_header()

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=(70, 12))

        self._build_input(body)
        self._build_transforms(body)
        self._build_color(body)
        self._build_format(body)
        self._build_previews(body)
        self._build_buttons(body)
        self._build_status()

        self.update_preview()
        self.input.focus_set()

    # ----- background image

    def _install_bg_image(self):
        """Place the cityscape image as the window backdrop. Stays at the bottom
        of the stacking order because it's created first and uses .place() so it
        doesn't consume pack space."""
        self._bg_label = None
        self._bg_src = None
        self._bg_photo = None
        self._last_bg_size = (0, 0)
        if not _PIL_OK or not os.path.exists(BG_IMAGE_PATH):
            return
        try:
            self._bg_src = Image.open(BG_IMAGE_PATH).convert("RGB")
        except Exception:
            self._bg_src = None
            return
        self._bg_label = tk.Label(self.root, borderwidth=0, bg=BG)
        self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        self.root.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        if event.widget is not self.root or self._bg_src is None:
            return
        size = (max(event.width, 1), max(event.height, 1))
        if size == self._last_bg_size:
            return
        self._last_bg_size = size
        resized = self._bg_src.resize(size, Image.LANCZOS)
        self._bg_photo = ImageTk.PhotoImage(resized)
        self._bg_label.configure(image=self._bg_photo)

    # ----- header / status

    def _build_header(self):
        tk.Label(
            self.root, text="F 4 D 3 R",
            font=("Courier New", 32, "bold"), bg=BG2, fg=ACCENT_M,
            padx=14, pady=4,
        ).pack(pady=(20, 0))
        tk.Label(
            self.root, text="b y   H I G H B A U D",
            font=("Courier New", 11, "bold"), bg=BG2, fg=ACCENT_C,
            padx=10, pady=2,
        ).pack(pady=(0, 4))

    def _build_status(self):
        self.status = tk.Label(
            self.root, text=" READY. type something and steal the show.",
            bg=BG2, fg=ACCENT_G, font=("Courier New", 9, "bold"), anchor="w",
        )
        self.status.pack(fill="x", side="bottom", ipady=3)

    # ----- input

    def _build_input(self, parent):
        tk.Label(parent, text="Your chat text:", bg=BG, fg=FG,
                 font=("Tahoma", 9, "bold")).pack(anchor="w")
        self.input = tk.Text(parent, height=2, font=("Tahoma", 12),
                             bg="white", fg="black", relief="sunken",
                             borderwidth=2, wrap="word")
        self.input.pack(fill="x", pady=(2, 8))
        self.input.insert("1.0", "hey what up :)")
        self.input.bind("<KeyRelease>", lambda e: self.update_preview())

    # ----- groups

    def _group(self, parent, title):
        f = tk.LabelFrame(parent, text=" " + title + " ", bg=BG, fg=ACCENT_Y,
                          font=("Tahoma", 9, "bold"), bd=2, relief="ridge",
                          labelanchor="nw")
        f.pack(fill="x", pady=4)
        inner = tk.Frame(f, bg=BG)
        inner.pack(fill="x", padx=8, pady=6)
        return inner

    def _slider(self, parent, var, lo, hi, res, length=110):
        return tk.Scale(parent, from_=lo, to=hi, resolution=res, orient="horizontal",
                        variable=var, bg=BG, fg=FG, highlightthickness=0,
                        length=length, troughcolor="#0000B0",
                        command=lambda v: self.update_preview())

    def _label(self, parent, text):
        return tk.Label(parent, text=text, bg=BG, fg=FG, font=("Tahoma", 9, "bold"))

    def _build_transforms(self, parent):
        g = self._group(parent, "Text Transforms")

        row1 = tk.Frame(g, bg=BG); row1.pack(fill="x")
        self._label(row1, "Case:").pack(side="left")
        self.case_var = tk.StringVar(value="None")
        ttk.Combobox(row1, textvariable=self.case_var, values=list(CASE_MODES),
                     state="readonly", width=11).pack(side="left", padx=(4, 14))

        self._label(row1, "Unicode Style:").pack(side="left")
        self.style_var = tk.StringVar(value="None")
        ttk.Combobox(row1, textvariable=self.style_var, values=list(UNICODE_STYLES),
                     state="readonly", width=14).pack(side="left", padx=(4, 14))

        self._label(row1, "Zalgo:").pack(side="left")
        self.zalgo_var = tk.IntVar(value=0)
        self._slider(row1, self.zalgo_var, 0, 10, 1, length=120).pack(side="left", padx=4)

        for v in (self.case_var, self.style_var):
            v.trace_add("write", lambda *a: self.update_preview())
        self.zalgo_var.trace_add("write", lambda *a: self.update_preview())

        row2 = tk.Frame(g, bg=BG); row2.pack(fill="x", pady=(6, 0))
        self.scroller_on = tk.BooleanVar(value=False)
        tk.Checkbutton(row2, text="Scroller mode", variable=self.scroller_on,
                       bg=BG, fg=FG, selectcolor=BG2, activebackground=BG,
                       activeforeground=FG, font=("Tahoma", 9, "bold"),
                       command=self.update_preview).pack(side="left")
        self._label(row2, "Width:").pack(side="left", padx=(12, 2))
        self.scroller_width = tk.IntVar(value=30)
        tk.Spinbox(row2, from_=10, to=80, textvariable=self.scroller_width, width=4,
                   command=self.update_preview).pack(side="left")
        self._label(row2, "Lines:").pack(side="left", padx=(12, 2))
        self.scroller_lines = tk.IntVar(value=6)
        tk.Spinbox(row2, from_=2, to=20, textvariable=self.scroller_lines, width=4,
                   command=self.update_preview).pack(side="left")

    def _build_color(self, parent):
        g = self._group(parent, "Color")

        row1 = tk.Frame(g, bg=BG); row1.pack(fill="x")
        self._label(row1, "Preset:").pack(side="left")
        self.preset_var = tk.StringVar(value="Rainbow")
        ttk.Combobox(row1, textvariable=self.preset_var, values=list(PRESETS),
                     state="readonly", width=13).pack(side="left", padx=(4, 14))

        self._label(row1, "Spread:").pack(side="left")
        self.spread_var = tk.DoubleVar(value=1.0)
        self._slider(row1, self.spread_var, 0.1, 3.0, 0.1).pack(side="left", padx=4)

        self._label(row1, "Shift:").pack(side="left")
        self.shift_var = tk.DoubleVar(value=0.0)
        self._slider(row1, self.shift_var, 0.0, 1.0, 0.01).pack(side="left", padx=4)

        self.preset_var.trace_add("write", lambda *a: self.update_preview())

        row2 = tk.Frame(g, bg=BG); row2.pack(fill="x", pady=(6, 0))
        self._label(row2, "Background:").pack(side="left")
        self.bg_var = tk.StringVar(value="None")
        ttk.Combobox(row2, textvariable=self.bg_var,
                     values=["None", "Opposite hue", "Reverse fade", "Dark contrast"],
                     state="readonly", width=14).pack(side="left", padx=(4, 14))
        self.bg_var.trace_add("write", lambda *a: self.update_preview())

        self.per_word = tk.BooleanVar(value=False)
        tk.Checkbutton(row2, text="Per-word coloring (one color per word)",
                       variable=self.per_word, bg=BG, fg=FG, selectcolor=BG2,
                       activebackground=BG, activeforeground=FG,
                       font=("Tahoma", 9, "bold"),
                       command=self.update_preview).pack(side="left", padx=12)

    def _build_format(self, parent):
        g = self._group(parent, "Format (AOL HTML / Discord ANSI wrappers)")
        row = tk.Frame(g, bg=BG); row.pack(fill="x")

        self.bold = tk.BooleanVar(value=False)
        self.italic = tk.BooleanVar(value=False)
        self.underline = tk.BooleanVar(value=False)

        for var, label in [(self.bold, "Bold"), (self.italic, "Italic (HTML only)"),
                            (self.underline, "Underline")]:
            tk.Checkbutton(row, text=label, variable=var, bg=BG, fg=FG,
                           selectcolor=BG2, activebackground=BG, activeforeground=FG,
                           font=("Tahoma", 9, "bold"),
                           command=self.update_preview).pack(side="left", padx=4)

        self._label(row, "Size (HTML):").pack(side="left", padx=(14, 2))
        self.size_var = tk.StringVar(value="3")
        ttk.Combobox(row, textvariable=self.size_var,
                     values=["1", "2", "3", "4", "5", "6", "7"],
                     state="readonly", width=3).pack(side="left")
        self.size_var.trace_add("write", lambda *a: self.update_preview())

    def _build_previews(self, parent):
        self._label(parent, "Preview (true color, what AOL HTML looks like):").pack(anchor="w", pady=(8, 2))
        self.preview = tk.Text(parent, height=4, font=("Segoe UI Symbol", 14, "bold"),
                               bg="white", fg="black", relief="sunken",
                               borderwidth=2, wrap="word", state="disabled")
        self.preview.pack(fill="x")

        self._label(parent, "Discord preview (quantized to 8 ANSI colors):").pack(anchor="w", pady=(8, 2))
        self.discord_preview = tk.Text(parent, height=4, font=("Consolas", 12, "bold"),
                                       bg="#2F3136", fg="#DCDDDE", relief="sunken",
                                       borderwidth=2, wrap="word", state="disabled")
        self.discord_preview.pack(fill="x")

    def _build_buttons(self, parent):
        btns = tk.Frame(parent, bg=BG)
        btns.pack(fill="x", pady=10)

        tk.Button(btns, text="Copy AOL HTML", font=("Tahoma", 10, "bold"),
                  bg="#C0C0C0", activebackground=ACCENT_Y, relief="raised",
                  command=self.copy_html, width=16).pack(side="left", padx=4)
        tk.Button(btns, text="Copy Discord ANSI", font=("Tahoma", 10, "bold"),
                  bg="#C0C0C0", activebackground="#7289DA", relief="raised",
                  command=self.copy_discord, width=18).pack(side="left", padx=4)
        tk.Button(btns, text="Copy Plain (Unicode)", font=("Tahoma", 10, "bold"),
                  bg="#C0C0C0", activebackground="#1DA1F2", relief="raised",
                  command=self.copy_plain, width=20).pack(side="left", padx=4)
        tk.Button(btns, text="Clear", font=("Tahoma", 10), bg="#C0C0C0",
                  relief="raised", command=self.clear, width=8).pack(side="left", padx=4)

    # ----- state computation

    def current_triples(self, discord_palette=False):
        raw = self.input.get("1.0", "end-1c")
        text = transform_text(
            raw,
            self.case_var.get(),
            self.style_var.get(),
            int(self.zalgo_var.get()),
            bool(self.scroller_on.get()),
            int(self.scroller_width.get()),
            int(self.scroller_lines.get()),
        )
        p = PRESETS[self.preset_var.get()]
        hue_start = (p["hue_start"] + float(self.shift_var.get())) % 1.0
        hue_range = p["hue_range"] * float(self.spread_var.get())
        colored = char_colors(text, hue_start, hue_range, p["sat"], p["val"],
                              per_word=bool(self.per_word.get()))
        triples = add_backgrounds(colored, self.bg_var.get())
        if discord_palette:
            triples = self._quantize_for_discord(triples)
        return triples

    def _quantize_for_discord(self, triples):
        out = []
        for cl, fg, bg in triples:
            qfg = qbg = None
            if fg is not None:
                code = nearest_ansi(fg, DISCORD_ANSI_FG)
                qfg = next(t for c, t in DISCORD_ANSI_FG if c == code)
            if bg is not None:
                code = nearest_ansi(bg, DISCORD_ANSI_BG)
                qbg = next(t for c, t in DISCORD_ANSI_BG if c == code)
            out.append((cl, qfg, qbg))
        return out

    # ----- rendering

    def _render(self, widget, triples):
        widget.configure(state="normal")
        for tag in widget.tag_names():
            if tag.startswith("c_"):
                widget.tag_delete(tag)
        widget.delete("1.0", "end")

        bold = bool(self.bold.get())
        italic = bool(self.italic.get())
        underline = bool(self.underline.get())

        font_family = widget.cget("font").split()[0] if isinstance(widget.cget("font"), str) else "Segoe UI Symbol"
        size = int(self.size_var.get()) if widget is self.preview else 12
        base_size = max(8, 6 + size * 2) if widget is self.preview else 12
        weight = "bold" if bold else "normal"
        slant = "italic" if (italic and widget is self.preview) else "roman"
        underline_flag = 1 if underline else 0
        font_spec = (font_family if widget is self.preview else "Consolas",
                     base_size, weight, slant)
        widget.configure(font=(font_spec[0], font_spec[1], weight,
                               "italic" if (italic and widget is self.preview) else "roman"))

        for i, (cluster, fg, bg) in enumerate(triples):
            tag = f"c_{i}"
            kwargs = {}
            if fg is not None:
                kwargs["foreground"] = rgb_to_hex(fg)
            if bg is not None:
                kwargs["background"] = rgb_to_hex(bg)
            if underline_flag:
                kwargs["underline"] = True
            if kwargs:
                widget.tag_configure(tag, **kwargs)
                widget.insert("end", cluster, tag)
            else:
                widget.insert("end", cluster)
        widget.configure(state="disabled")

    def update_preview(self):
        try:
            self._render(self.preview, self.current_triples(discord_palette=False))
            self._render(self.discord_preview, self.current_triples(discord_palette=True))
        except Exception as e:
            self.status.configure(text=f" Preview error: {e}")

    # ----- copy actions

    def _copy(self, text, label):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.status.configure(text=f" Copied {label} ({len(text)} chars).")

    def copy_html(self):
        triples = self.current_triples()
        html = to_aol_html(triples, self.bold.get(), self.italic.get(),
                           self.underline.get(), self.size_var.get())
        self._copy(html, "AOL HTML")

    def copy_discord(self):
        triples = self.current_triples()
        block = to_discord_ansi(triples, self.bold.get(), self.underline.get())
        self._copy(block, "Discord ANSI block")

    def copy_plain(self):
        triples = self.current_triples()
        self._copy(to_plain(triples), "plain Unicode")

    def clear(self):
        self.input.delete("1.0", "end")
        self.update_preview()
        self.status.configure(text=" Cleared.")


def show_splash(root, image_path, on_done, hold_ms=1500, fade_ms=500, max_size=(720, 480)):
    """Borderless splash with the given image, fades out before invoking on_done."""
    if not _PIL_OK or not os.path.exists(image_path):
        on_done()
        return
    src = Image.open(image_path).convert("RGB")
    src.thumbnail(max_size, Image.LANCZOS)
    w, h = src.size

    splash = tk.Toplevel(root)
    splash.overrideredirect(True)
    try:
        splash.attributes("-topmost", True)
        splash.attributes("-alpha", 1.0)
    except tk.TclError:
        pass

    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    splash.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    photo = ImageTk.PhotoImage(src)
    label = tk.Label(splash, image=photo, borderwidth=0, highlightthickness=0)
    label.image = photo  # prevent GC
    label.pack()

    def fade(step=0, steps=20):
        if step > steps:
            splash.destroy()
            on_done()
            return
        try:
            splash.attributes("-alpha", max(0.0, 1.0 - step / steps))
        except tk.TclError:
            pass
        splash.after(max(1, fade_ms // steps), fade, step + 1, steps)

    splash.after(hold_ms, fade)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()

    def start_main():
        FaderApp(root)
        root.deiconify()

    show_splash(root, SPLASH_IMAGE_PATH, start_main)
    root.mainloop()
