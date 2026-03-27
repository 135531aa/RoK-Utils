import sys
import re
import math
import os
import shutil
import json
import urllib.request
import urllib.parse
import urllib.error
import threading

# Windows taskbar icon fix
if sys.platform == "win32":
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ROKEditor.1.0")
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QTextEdit, QLabel,
    QLineEdit, QSpinBox, QPushButton, QScrollArea,
    QFrame, QSizePolicy, QMenu, QFileDialog, QSlider, QDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QPoint, QRect, QTimer, QDir, QRegularExpression, QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup, QParallelAnimationGroup, QObject, pyqtSignal
from PyQt6.QtGui import (
    QColor, QPainter, QBrush, QPen, QFont,
    QImage, QPixmap, QPalette, QLinearGradient,
    QSyntaxHighlighter, QTextCharFormat
)

# ── Palette ────────────────────────────────────────────────────────────────
DARK        = "#0a0a0a"
DARK2       = "#111111"
DARK3       = "#1a1a1a"
DARK4       = "#222222"
BORDER      = "#3a3a3a"
BORDER_GOLD = "#8a6800"
GOLD        = "#FFD700"
GOLD_DIM    = "#b89600"
GOLD_DARK   = "#6b4f00"
TEXT_MAIN   = "#e8e0cc"
TEXT_DIM    = "#7a7060"
RED         = "#c0392b"
ORANGE      = "#e67e22"
MAX_CHARS   = 2000

BG_IMAGE = None
FONT_SIZE = 13  # overridden by config at startup

def load_bg():
    global BG_IMAGE
    path = os.path.join(_APPDATA_DIR, "back.png")
    if os.path.exists(path):
        BG_IMAGE = QPixmap(path)

# ── Config (last directory) ───────────────────────────────────────────────
def _get_exe_dir():
    """Returns the directory where bundled data files are — works with PyInstaller --onefile."""
    if getattr(sys, 'frozen', False):
        # No PyInstaller --onefile, os dados estão em _MEIPASS (temp)
        # ficheiros editáveis (charmap, glossary) ficam ao lado do exe
        return getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

def _get_user_data_dir():
    """Pasta para ficheiros editáveis pelo utilizador (charmap, glossary)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# Store the original executable path once at startup (before any subprocess spawning)
_ORIGINAL_EXE = sys.executable

if sys.platform == "win32":
    _APPDATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ROKEditor")
else:
    _APPDATA_DIR = os.path.join(os.path.expanduser("~"), ".config", "ROKEditor")
os.makedirs(_APPDATA_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(_APPDATA_DIR, ".rok_config.json")

def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except:
        return {}

def save_config(data):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f)
    except:
        pass

def add_recent_remove(path):
    cfg = load_config()
    recents = cfg.get("recents", [])
    if path in recents:
        recents.remove(path)
    cfg["recents"] = recents
    save_config(cfg)

def add_recent(path):
    cfg = load_config()
    recents = cfg.get("recents", [])
    if path in recents:
        recents.remove(path)
    recents.insert(0, path)
    cfg["recents"] = recents[:3]
    save_config(cfg)

# ── ROK tag parser ─────────────────────────────────────────────────────────
def px_to_pt(px):
    return max(1, round(int(px) / 1.333))

def rok_to_html(text):
    for tag in ["s", "br", "sup", "sub"]:
        text = re.sub(rf"</?{tag}>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<size=(\d+)>(.*?)</size>",
                  lambda m: f'<span style="font-size:{px_to_pt(m.group(1))}pt">{m.group(2)}</span>',
                  text, flags=re.DOTALL)
    text = re.sub(r"<color=(#[0-9A-Fa-f]{6})>(.*?)</color>",
                  r'<span style="color:\1">\2</span>', text, flags=re.DOTALL)
    text = text.replace("\n", "<br>")
    return text

# ── Shared style helpers ───────────────────────────────────────────────────
def label_style(size=13):
    return f"color: {GOLD}; font-weight: bold; font-size: {size}px; letter-spacing: 1px;"

def textedit_style(border_color=BORDER):
    return f"""
        QTextEdit {{
            background: {DARK3};
            color: {TEXT_MAIN};
            border: 1px solid {border_color};
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 13px;
            padding: 10px;
            selection-background-color: {GOLD_DARK};
        }}
        QScrollBar:vertical {{
            background: {DARK2}; width: 8px; border: none;
        }}
        QScrollBar::handle:vertical {{
            background: {BORDER_GOLD}; border-radius: 4px; min-height: 20px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    """

def btn_gold_style():
    return f"""
        QPushButton {{
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 {GOLD}, stop:1 #c8a000);
            color: #0a0a0a;
            font-weight: bold; font-size: 13px;
            border: none; padding: 10px 20px;
            letter-spacing: 1px;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 #ffe033, stop:1 {GOLD});
        }}
        QPushButton:pressed {{ background: {GOLD_DIM}; }}
    """

def btn_dim_style():
    return f"""
        QPushButton {{
            background: {DARK4};
            color: {TEXT_MAIN};
            border: 1px solid {BORDER};
            padding: 6px 14px; font-size: 12px;
        }}
        QPushButton:hover {{ background: #2a2a2a; border-color: {GOLD_DIM}; color: {GOLD}; }}
    """

# ── Background-aware base widget ───────────────────────────────────────────
class BgWidget(QWidget):
    def paintEvent(self, e):
        painter = QPainter(self)
        if BG_IMAGE and not BG_IMAGE.isNull():
            scaled = BG_IMAGE.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            # Dark overlay for readability
            painter.fillRect(self.rect(), QColor(0, 0, 0, 180))
        else:
            cfg = load_config()
            bg = cfg.get("bg_color", DARK)
            painter.fillRect(self.rect(), QColor(bg))
        super().paintEvent(e)

# ── Color Wheel ────────────────────────────────────────────────────────────
class ColorWheelWidget(QWidget):
    SIZE = 300

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._image = None
        self._dots = []
        self._brightness = []  # per-dot brightness 0.0-1.0
        self._last_dragged = 0
        self._dragging = -1
        self.on_drag = None
        self._build_image()

    def _build_image(self):
        size = self.SIZE
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        cx = cy = size // 2
        r = cx - 4
        for y in range(size):
            for x in range(size):
                dx, dy = x - cx, y - cy
                dist = math.sqrt(dx*dx + dy*dy)
                if dist > r:
                    continue
                angle = math.degrees(math.atan2(dy, dx)) % 360
                sat = dist / r
                c = QColor.fromHsvF(angle / 360.0, sat, 1.0)
                img.setPixelColor(x, y, c)
        self._image = img

    def set_num_dots(self, n):
        cx = cy = self.SIZE // 2
        r = (self.SIZE // 2 - 4) * 0.62
        self._dots = []
        self._brightness = [1.0] * n
        self._last_dragged = 0
        for i in range(n):
            angle = (i / n) * 2 * math.pi - math.pi / 2
            x = int(cx + r * math.cos(angle))
            y = int(cy + r * math.sin(angle))
            self._dots.append(QPoint(x, y))
        self.update()

    def get_colors(self):
        colors = []
        for i, p in enumerate(self._dots):
            c = self._color_at(p.x(), p.y())
            b = self._brightness[i] if i < len(self._brightness) else 1.0
            h, s, v, a = c.getHsvF()
            colors.append(QColor.fromHsvF(h, s, v * b, a))
        return colors

    def set_dot_brightness(self, index, value):
        if 0 <= index < len(self._brightness):
            self._brightness[index] = value
            self.update()
            if self.on_drag:
                self.on_drag()

    def get_last_dragged(self):
        return self._last_dragged

    def _color_at(self, x, y):
        if self._image is None:
            return QColor("white")
        x = max(0, min(x, self.SIZE - 1))
        y = max(0, min(y, self.SIZE - 1))
        return QColor(self._image.pixel(x, y))

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._image:
            painter.drawImage(0, 0, self._image)

        cx = cy = self.SIZE // 2
        r = cx - 4

        # Gold ring border
        painter.setPen(QPen(QColor(GOLD_DIM), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPoint(cx, cy), r, r)

        for i, pt in enumerate(self._dots):
            color = self._color_at(pt.x(), pt.y())
            brightness = 0.299*color.red() + 0.587*color.green() + 0.114*color.blue()
            text_color = QColor("#000") if brightness > 128 else QColor("#fff")

            # Outer gold ring on dot
            painter.setPen(QPen(QColor(GOLD), 2))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(pt, 13, 13)

            painter.setPen(text_color)
            painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
            painter.drawText(QRect(pt.x()-13, pt.y()-13, 26, 26),
                             Qt.AlignmentFlag.AlignCenter, str(i+1))

    def mousePressEvent(self, e):
        pos = e.position().toPoint()
        for i, pt in enumerate(self._dots):
            if (pos - pt).manhattanLength() < 18:
                self._dragging = i
                self._last_dragged = i
                return

    def mouseMoveEvent(self, e):
        if self._dragging < 0:
            return
        pos = e.position().toPoint()
        cx = cy = self.SIZE // 2
        r = cx - 4
        dx, dy = pos.x()-cx, pos.y()-cy
        dist = math.sqrt(dx*dx + dy*dy)
        if dist > r:
            dx, dy = dx/dist*r, dy/dist*r
        self._dots[self._dragging] = QPoint(int(cx+dx), int(cy+dy))
        self.update()
        if self.on_drag:
            self.on_drag()

    def mouseReleaseEvent(self, e):
        self._dragging = -1

# ── Gold separator ─────────────────────────────────────────────────────────
class GoldSep(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(2)

    def paintEvent(self, e):
        painter = QPainter(self)
        grad = QLinearGradient(0, 0, self.width(), 0)
        grad.setColorAt(0,   QColor(0, 0, 0, 0))
        grad.setColorAt(0.2, QColor(GOLD_DIM))
        grad.setColorAt(0.8, QColor(GOLD_DIM))
        grad.setColorAt(1,   QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), grad)

# ── ROK Syntax Highlighter ─────────────────────────────────────────────────
class RokHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self._rules = []

        # <color=#RRGGBB>...</color> — tag in its own color, content in that color
        self._color_pattern = QRegularExpression(r"<color=(#[0-9A-Fa-f]{6})>(.*?)</color>")

        # <size=XX> tags
        fmt_size = QTextCharFormat()
        fmt_size.setForeground(QColor("#41ff61"))
        self._rules.append((QRegularExpression(r"<size=\d+>|</size>"), fmt_size))

        # <b> tags
        fmt_b = QTextCharFormat()
        fmt_b.setForeground(QColor("#66c2ff"))
        self._rules.append((QRegularExpression(r"</?b>"), fmt_b))

        # <i> tags
        fmt_i = QTextCharFormat()
        fmt_i.setForeground(QColor("#efff5a"))
        self._rules.append((QRegularExpression(r"</?i>"), fmt_i))

        # <u> tags
        fmt_u = QTextCharFormat()
        fmt_u.setForeground(QColor("#ff7b5a"))
        self._rules.append((QRegularExpression(r"</?u>"), fmt_u))

    def highlightBlock(self, text):
        # Handle color tags specially — tag in its color, content too
        it = self._color_pattern.globalMatch(text)
        while it.hasNext():
            match = it.next()
            hex_color = match.captured(1)
            color = QColor(hex_color)

            fmt = QTextCharFormat()
            fmt.setForeground(color)

            # Color the entire match
            self.setFormat(match.capturedStart(), match.capturedLength(), fmt)

        # Apply other tag rules
        for pattern, fmt in self._rules:
            it2 = pattern.globalMatch(text)
            while it2.hasNext():
                m = it2.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)

# ── Editor Tab ─────────────────────────────────────────────────────────────
class EditorTab(BgWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(16, 16, 16, 16)

        # Left
        left = QVBoxLayout()
        left.setSpacing(6)
        top_row = QHBoxLayout()
        lbl = QLabel("CÓDIGO")
        lbl.setStyleSheet(label_style(12))
        self.counter = QLabel("0 / 2000")
        self.counter.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        top_row.addWidget(lbl)
        top_row.addStretch()
        top_row.addWidget(self.counter)
        left.addLayout(top_row)
        left.addWidget(GoldSep())

        self.code_input = QTextEdit()
        self.code_input.setStyleSheet(textedit_style())
        self._highlighter = RokHighlighter(self.code_input.document())
        self.code_input.textChanged.connect(self._on_change)
        left.addWidget(self.code_input)

        # Right
        right = QVBoxLayout()
        right.setSpacing(6)
        lbl2 = QLabel("PREVIEW")
        lbl2.setStyleSheet(label_style(12))
        right.addWidget(lbl2)
        right.addWidget(GoldSep())

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setStyleSheet(textedit_style(BORDER_GOLD))
        right.addWidget(self.preview)

        lw = QWidget(); lw.setLayout(left);  lw.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        rw = QWidget(); rw.setLayout(right); rw.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout.addWidget(lw)
        layout.addWidget(rw)

    def _on_change(self):
        text = self.code_input.toPlainText()
        n = len(text)
        self.counter.setText(f"{n} / {MAX_CHARS}")

        if n > MAX_CHARS:
            self.counter.setStyleSheet(f"color: {RED}; font-weight: bold; font-size: 12px;")
            self.code_input.setStyleSheet(textedit_style(RED))
        elif n > MAX_CHARS * 0.9:
            self.counter.setStyleSheet(f"color: {ORANGE}; font-size: 12px;")
            self.code_input.setStyleSheet(textedit_style(ORANGE))
        else:
            self.counter.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
            self.code_input.setStyleSheet(textedit_style())

        html = rok_to_html(text)
        self.preview.setHtml(f'<div style="color:{TEXT_MAIN}; font-size:{FONT_SIZE}px; background:transparent">{html}</div>')

# ── Doc Bar Entry ──────────────────────────────────────────────────────────
class DocBarEntry(QWidget):
    def __init__(self, label, parent=None, full_name=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(52)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.btn = QPushButton(label)
        self.btn.setStyleSheet(self._btn_style(False))
        self._full_label = full_name if full_name else label
        self.btn.setToolTip(self._full_label)
        self.btn.mouseDoubleClickEvent = lambda e: self._start_rename()
        row.addWidget(self.btn)
        self._edit = None

        self.del_btn = QPushButton("×")
        self.del_btn.setFixedSize(18, 18)
        self.del_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_DIM};
                font-size: 11px; border: none;
            }}
            QPushButton:hover {{ color: {RED}; }}
        """)
        row.addWidget(self.del_btn)
        row.addSpacing(4)

    def _start_rename(self):
        if self._edit:
            return
        self._edit = QLineEdit(self.btn.text().strip(), self)
        self._edit.setStyleSheet(
            f"QLineEdit {{ background: {DARK4}; color: {GOLD}; "
            f"border: 1px solid {GOLD_DIM}; font-size: 13px; padding: 2px 4px; }}"
        )
        self._edit.setGeometry(self.btn.geometry())
        self._edit.show()
        self._edit.setFocus()
        self._edit.selectAll()
        self._edit.returnPressed.connect(self._finish_rename)
        self._edit.editingFinished.connect(self._finish_rename)

    def _finish_rename(self):
        if not self._edit:
            return
        new_label = self._edit.text().strip()
        self._edit.hide()
        self._edit.deleteLater()
        self._edit = None
        if new_label:
            self._full_label = new_label
            self.btn.setToolTip(new_label)
            nums = "".join(c for c in new_label if c.isdigit())
            if nums == "".join(c for c in new_label if not c.isspace()):
                display = nums
            else:
                display = new_label[:6] if len(new_label) > 6 else new_label
            self.btn.setText(display)

    def _btn_style(self, active):
        if active:
            return f"""
                QPushButton {{
                    background: {DARK3}; color: {GOLD};
                    border: none; border-left: 3px solid {GOLD};
                    font-size: 15px; font-weight: bold;
                    padding: 0 6px; text-align: center;
                }}
            """
        return f"""
            QPushButton {{
                background: transparent; color: {TEXT_DIM};
                border: none; border-left: 3px solid transparent;
                font-size: 15px; padding: 0 6px; text-align: center;
            }}
            QPushButton:hover {{ color: {GOLD_DIM}; background: {DARK3}; }}
        """

    def set_active(self, active):
        self.btn.setStyleSheet(self._btn_style(active))

# ── Multi Editor (sidebar hotbar) ──────────────────────────────────────────
class MultiEditorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ──
        self._sidebar = QWidget()
        self._sidebar.setFixedWidth(72)
        self._sidebar.setStyleSheet(f"background: {DARK2}; border-right: 1px solid {BORDER};")
        sidebar_outer = QVBoxLayout(self._sidebar)
        sidebar_outer.setContentsMargins(0, 0, 0, 0)
        sidebar_outer.setSpacing(0)

        # Top controls
        top_w = QWidget()
        top_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        top_layout = QVBoxLayout(top_w)
        top_layout.setContentsMargins(0, 8, 0, 4)
        top_layout.setSpacing(2)

        self._add_btn = QPushButton("+")
        self._add_btn.setFixedHeight(44)
        self._add_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {GOLD_DIM};
                font-size: 18px; border: none;
                border-bottom: 1px solid {BORDER}; padding-bottom: 4px;
            }}
            QPushButton:hover {{ color: {GOLD}; background: {DARK3}; }}
        """)
        self._add_btn.clicked.connect(lambda: self.new_tab())
        top_layout.addWidget(self._add_btn)

        arrow_row = QHBoxLayout()
        arrow_row.setContentsMargins(2, 2, 2, 2)
        arrow_row.setSpacing(2)
        self._arrow_btns = []
        for symbol, direction in [("▲", -1), ("▼", 1)]:
            ab = QPushButton(symbol)
            ab.setFixedHeight(22)
            ab.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {TEXT_DIM};
                    font-size: 11px; border: none;
                }}
                QPushButton:hover {{ color: {GOLD}; background: {DARK3}; }}
            """)
            ab.clicked.connect(lambda _, d=direction: self._move_doc(d))
            arrow_row.addWidget(ab)
            self._arrow_btns.append(ab)
        arrow_w = QWidget()
        arrow_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        arrow_w.setLayout(arrow_row)
        top_layout.addWidget(arrow_w)
        sidebar_outer.addWidget(top_w)

        # Doc list area (shows PAGE_SIZE docs at a time)
        self._page_container = QWidget()
        self._page_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._sidebar_layout = QVBoxLayout(self._page_container)
        self._sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self._sidebar_layout.setSpacing(2)
        self._sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        sidebar_outer.addWidget(self._page_container, 1)

        # Page dots at bottom
        self._dots_w = QWidget()
        self._dots_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._dots_layout = QHBoxLayout(self._dots_w)
        self._dots_layout.setContentsMargins(4, 4, 4, 4)
        self._dots_layout.setSpacing(4)
        self._dots_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_outer.addWidget(self._dots_w)

        # ── Stack ──
        from PyQt6.QtWidgets import QStackedWidget
        self._stack = QStackedWidget()
        self._stack.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        main_layout.addWidget(self._sidebar)
        main_layout.addWidget(self._stack)

        self._docs = []
        self._doc_count = 0
        self._current_page = 0
        self._PAGE_SIZE = 10
        self.new_tab()

    def _rebuild_page(self):
        """Show only docs for current page."""
        start = self._current_page * self._PAGE_SIZE
        end = start + self._PAGE_SIZE
        for i, (entry, _) in enumerate(self._docs):
            self._sidebar_layout.removeWidget(entry)
            entry.hide()
        for i, (entry, _) in enumerate(self._docs):
            if start <= i < end:
                self._sidebar_layout.addWidget(entry)
                entry.show()
        self._update_dots()

    def _update_dots(self):
        # Clear existing dots
        while self._dots_layout.count():
            item = self._dots_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        total_pages = max(1, math.ceil(len(self._docs) / self._PAGE_SIZE))
        if total_pages <= 1:
            return
        for p in range(total_pages):
            dot = QPushButton()
            is_active = (p == self._current_page)
            size = 10 if is_active else 7
            dot.setFixedSize(size, size)
            dot.setStyleSheet(f"""
                QPushButton {{
                    background: {"" + GOLD if is_active else TEXT_DIM};
                    border-radius: {size // 2}px;
                    border: none;
                }}
                QPushButton:hover {{ background: {GOLD_DIM}; }}
            """)
            dot.clicked.connect(lambda _, pg=p: self._go_page(pg))
            self._dots_layout.addWidget(dot)

    def _go_page(self, page):
        self._current_page = page
        self._rebuild_page()

    def _make_label(self, name):
        # If name is purely numeric, show only numbers
        stripped = name.strip()
        nums = ''.join(c for c in stripped if c.isdigit())
        if nums and nums == ''.join(c for c in stripped if not c.isspace()):
            return nums
        return stripped[:6] if len(stripped) > 6 else stripped

    def new_tab(self, content="", name=None):
        self._doc_count += 1
        full_name = name if name else str(self._doc_count)
        label = self._make_label(name) if name else str(self._doc_count)
        tab = EditorTab()
        if content:
            tab.code_input.setPlainText(content)

        entry = DocBarEntry(label, full_name=full_name)
        self._stack.addWidget(tab)
        self._docs.append((entry, tab))

        t = tab
        entry.btn.clicked.connect(lambda _, tt=t: self._switch_to(tt))
        entry.del_btn.clicked.connect(lambda _, tt=t: self._remove_by_tab(tt))

        # Auto go to last page
        self._current_page = (len(self._docs) - 1) // self._PAGE_SIZE
        self._rebuild_page()
        self._switch_to(tab)
        return tab

    def _switch_to(self, tab):
        self._stack.setCurrentWidget(tab)
        for entry, t in self._docs:
            entry.set_active(t is tab)

    def _switch(self, index):
        if 0 <= index < len(self._docs):
            self._switch_to(self._docs[index][1])

    def _remove_by_tab(self, tab):
        if len(self._docs) <= 1:
            self._docs[0][1].code_input.clear()
            return
        # Find index by tab reference
        index = next((i for i, (_, t) in enumerate(self._docs) if t is tab), None)
        if index is None:
            return
        entry, tab = self._docs[index]
        self._sidebar_layout.removeWidget(entry)
        entry.deleteLater()
        self._stack.removeWidget(tab)
        tab.deleteLater()
        self._docs.pop(index)
        # Reconnect all with fresh lambdas
        for i, (e, _) in enumerate(self._docs):
            try: e.btn.clicked.disconnect()
            except: pass
            t = self._docs[i][1]
            e.btn.clicked.connect(lambda _, j=i, tt=t: self._switch_by_tab(tt))
            try: e.del_btn.clicked.disconnect()
            except: pass
            e.del_btn.clicked.connect(lambda _, tt=t: self._remove_by_tab(tt))
        # Adjust page if needed
        max_page = max(0, math.ceil(len(self._docs) / self._PAGE_SIZE) - 1)
        self._current_page = min(self._current_page, max_page)
        self._rebuild_page()
        if self._docs:
            self._switch_to(self._docs[min(index, len(self._docs)-1)][1])

    def _switch_by_tab(self, tab):
        self._switch_to(tab)

    def _move_doc(self, direction):
        """Move active doc up (-1) or down (+1)"""
        cur = self._stack.currentWidget()
        idx = next((i for i, (_, t) in enumerate(self._docs) if t is cur), None)
        if idx is None:
            return
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self._docs):
            return

        # Swap in list
        self._docs[idx], self._docs[new_idx] = self._docs[new_idx], self._docs[idx]

        # Rebuild sidebar (skip + button at index 0)
        for entry, _ in self._docs:
            self._sidebar_layout.removeWidget(entry)
        for entry, _ in self._docs:
            self._sidebar_layout.addWidget(entry)

        # Reconnect
        for e, t in self._docs:
            try: e.btn.clicked.disconnect()
            except: pass
            e.btn.clicked.connect(lambda _, tt=t: self._switch_by_tab(tt))
            try: e.del_btn.clicked.disconnect()
            except: pass
            e.del_btn.clicked.connect(lambda _, tt=t: self._remove_by_tab(tt))

        self._switch_to(cur)

    def current_editor(self):
        return self._stack.currentWidget()

    @property
    def code_input(self):
        w = self.current_editor()
        return w.code_input if w else None

# ── Gradient Tab ───────────────────────────────────────────────────────────
class GradientTab(BgWidget):
    def __init__(self):
        super().__init__()
        main = QVBoxLayout(self)
        main.setSpacing(18)
        main.setContentsMargins(16, 16, 16, 16)

        top = QHBoxLayout()
        top.setSpacing(30)

        # Wheel side
        wside = QVBoxLayout()
        wside.setSpacing(8)
        wside.setAlignment(Qt.AlignmentFlag.AlignTop)
        wlbl = QLabel("RODA DE CORES")
        wlbl.setStyleSheet(label_style(12))
        wside.addWidget(wlbl)
        wside.addWidget(GoldSep())

        # Wheel + brightness slider side by side
        wheel_row = QHBoxLayout()
        wheel_row.setSpacing(10)
        self.wheel = ColorWheelWidget()
        self.wheel.on_drag = self._on_wheel_drag
        wheel_row.addWidget(self.wheel)

        # Brightness slider (vertical, right of wheel)
        slider_col = QVBoxLayout()
        slider_col.setSpacing(4)
        slider_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        bright_lbl = QLabel("☀")
        bright_lbl.setStyleSheet(f"color: {GOLD}; font-size: 14px;")
        bright_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.bright_slider = QSlider(Qt.Orientation.Vertical)
        self.bright_slider.setRange(0, 100)
        self.bright_slider.setValue(100)
        self.bright_slider.setFixedHeight(260)
        self.bright_slider.setFixedWidth(24)
        self.bright_slider.setStyleSheet(f"""
            QSlider::groove:vertical {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {GOLD}, stop:1 #000000);
                width: 8px; border-radius: 4px;
                margin: 0 8px;
            }}
            QSlider::handle:vertical {{
                background: {GOLD};
                border: 2px solid {DARK};
                width: 16px; height: 16px;
                border-radius: 8px;
                margin: 0 -4px;
            }}
            QSlider::handle:vertical:hover {{
                background: #fff;
            }}
        """)
        self.bright_slider.valueChanged.connect(self._on_brightness_change)
        dark_lbl = QLabel("◾")
        dark_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 10px;")
        dark_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        slider_col.addWidget(bright_lbl)
        slider_col.addWidget(self.bright_slider)
        slider_col.addWidget(dark_lbl)
        slider_w = QWidget(); slider_w.setLayout(slider_col)
        slider_w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        wheel_row.addWidget(slider_w)

        wside.addLayout(wheel_row)
        ww = QWidget(); ww.setLayout(wside)
        ww.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        ww.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        top.addWidget(ww)

        # Controls side
        cside = QVBoxLayout()
        cside.setSpacing(14)
        cside.setAlignment(Qt.AlignmentFlag.AlignTop)

        def field(label_text, widget):
            lbl = QLabel(label_text)
            lbl.setStyleSheet(label_style(12))
            v = QVBoxLayout(); v.setSpacing(6)
            v.addWidget(lbl); v.addWidget(GoldSep()); v.addWidget(widget)
            w = QWidget(); w.setLayout(v); w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            return w

        self.num_points = QSpinBox()
        self.num_points.setRange(2, 10)
        self.num_points.setValue(2)
        self.num_points.setStyleSheet(f"""
            QSpinBox {{ background: {DARK4}; color: {TEXT_MAIN};
            border: 1px solid {BORDER}; padding: 8px; font-size: {FONT_SIZE}px; }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background: {DARK3}; border: 1px solid {BORDER}; width: 18px;
            }}
        """)
        self.num_points.valueChanged.connect(self._on_num_points_change)

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Escreve o teu texto aqui...")
        self.text_input.textChanged.connect(self._live_preview)
        self.text_input.setStyleSheet(f"""
            QLineEdit {{ background: {DARK4}; color: {TEXT_MAIN};
            border: 1px solid {BORDER}; padding: 10px; font-size: {FONT_SIZE}px; }}
            QLineEdit:focus {{ border-color: {GOLD_DIM}; }}
        """)


        cside.addWidget(field("PONTOS DE COR", self.num_points))
        cside.addWidget(field("TEXTO", self.text_input))
        cside.addStretch()

        cw = QWidget(); cw.setLayout(cside); cw.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        top.addWidget(cw)
        main.addLayout(top)

        main.addWidget(GoldSep())

        # Results
        self.results_widget = QWidget()
        self.results_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.results_widget.setVisible(False)
        res = QVBoxLayout(self.results_widget)
        res.setSpacing(12)

        prev_lbl = QLabel("PREVIEW")
        prev_lbl.setStyleSheet(label_style(12))
        res.addWidget(prev_lbl)
        res.addWidget(GoldSep())

        self.grad_preview = QTextEdit()
        self.grad_preview.setReadOnly(True)
        self.grad_preview.setFixedHeight(70)
        self.grad_preview.setStyleSheet(textedit_style(BORDER_GOLD))

        code_lbl = QLabel("CÓDIGO")
        code_lbl.setStyleSheet(label_style(12))

        self.grad_code = QTextEdit()
        self.grad_code.setReadOnly(True)
        self.grad_code.setFixedHeight(120)
        self.grad_code.setStyleSheet(textedit_style())

        self.copy_btn = QPushButton("Copiar código")
        self.copy_btn.setStyleSheet(btn_dim_style())
        self.copy_btn.clicked.connect(self._copy_code)

        res.addWidget(self.grad_preview)
        res.addWidget(code_lbl)
        res.addWidget(GoldSep())
        res.addWidget(self.grad_code)
        res.addWidget(self.copy_btn, alignment=Qt.AlignmentFlag.AlignRight)

        main.addWidget(self.results_widget)
        main.addStretch()

        self.wheel.set_num_dots(2)

    def _on_num_points_change(self):
        self.wheel.set_num_dots(self.num_points.value())
        self._live_preview()

    def _update_slider_color(self):
        idx = self.wheel.get_last_dragged()
        colors = self.wheel.get_colors()
        if idx < len(colors):
            # Get full brightness color (ignore current brightness for display)
            pt = self.wheel._dots[idx]
            c = self.wheel._color_at(pt.x(), pt.y())
            hex_color = f"#{c.red():02X}{c.green():02X}{c.blue():02X}"
        else:
            hex_color = "#FFD700"
        self.bright_slider.setStyleSheet(f"""
            QSlider::groove:vertical {{
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {hex_color}, stop:1 #000000);
                width: 8px; border-radius: 4px;
                margin: 0 8px;
            }}
            QSlider::handle:vertical {{
                background: {hex_color};
                border: 2px solid {DARK};
                width: 16px; height: 16px;
                border-radius: 8px;
                margin: 0 -4px;
            }}
            QSlider::handle:vertical:hover {{
                background: #ffffff;
            }}
        """)

    def _on_wheel_drag(self):
        # Sync slider to last dragged dot brightness and color
        idx = self.wheel.get_last_dragged()
        b = self.wheel._brightness[idx] if idx < len(self.wheel._brightness) else 1.0
        self.bright_slider.blockSignals(True)
        self.bright_slider.setValue(int(b * 100))
        self.bright_slider.blockSignals(False)
        self._update_slider_color()
        self._live_preview()

    def _on_brightness_change(self, value):
        idx = self.wheel.get_last_dragged()
        self.wheel.set_dot_brightness(idx, value / 100.0)

    def _live_preview(self):
        if self.text_input.text().strip():
            self.results_widget.setVisible(True)
            self._generate()
        else:
            self.results_widget.setVisible(False)

    @staticmethod
    def _lerp(c1, c2, t):
        return QColor(
            int(c1.red()   + (c2.red()   - c1.red())   * t),
            int(c1.green() + (c2.green() - c1.green()) * t),
            int(c1.blue()  + (c2.blue()  - c1.blue())  * t),
        )

    def _generate(self):
        text = self.text_input.text()
        if not text.strip():
            return
        colors = self.wheel.get_colors()
        if len(colors) < 2:
            return

        chars_idx = [i for i, ch in enumerate(text) if ch != " "]
        count = len(chars_idx)
        total_segs = len(colors) - 1
        code = ""

        for i, ch in enumerate(text):
            if ch == " ":
                code += " "; continue
            ci = chars_idx.index(i)
            if count <= 1:
                seg, t = 0, 0.0
            else:
                pos = ci / (count - 1) * total_segs
                seg = min(int(pos), total_segs - 1)
                t = pos - seg
            c = self._lerp(colors[seg], colors[seg+1], t)
            code += f"<color=#{c.red():02X}{c.green():02X}{c.blue():02X}>{ch}</color>"

        preview_html = re.sub(
            r"<color=(#[0-9A-Fa-f]{6})>(.*?)</color>",
            r'<span style="color:\1">\2</span>', code)

        self.grad_preview.setHtml(f'<div style="font-size:18px; color:{TEXT_MAIN}">{preview_html}</div>')
        self.grad_code.setPlainText(code)
        self.results_widget.setVisible(True)

    def _copy_code(self):
        QApplication.clipboard().setText(self.grad_code.toPlainText())
        self.copy_btn.setText("✓  Copiado!")
        QTimer.singleShot(1500, lambda: self.copy_btn.setText("Copiar código"))

# ── Translator Tab ────────────────────────────────────────────────────────
LIBRE_URL = "http://localhost:5000"
_LIBRE_PROC = None

def _load_glossary():
    global _GLOSSARY_CACHE
    if _GLOSSARY_CACHE is not None:
        return _GLOSSARY_CACHE
    glossary_path = os.path.join(_get_user_data_dir(), "glossary.json")
    try:
        with open(glossary_path, encoding="utf-8") as f:
            data = json.load(f)
        # Flatten all categories into a single list of (original, replacement)
        pt_en = []
        for cat, terms in data.get("pt_en", {}).items():
            if cat.startswith("_"):
                continue
            for orig, repl in terms.items():
                pt_en.append((orig, repl))
        en_pt = []
        for cat, terms in data.get("en_pt", {}).items():
            if cat.startswith("_"):
                continue
            for orig, repl in terms.items():
                en_pt.append((orig, repl))
        _GLOSSARY_CACHE = {"pt_en": pt_en, "en_pt": en_pt}
    except Exception as e:
        print(f"[Glossary] Erro ao carregar glossary.json: {e}")
        _GLOSSARY_CACHE = {"pt_en": [], "en_pt": []}
    return _GLOSSARY_CACHE

class GlossaryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Glossário")
        self.setMinimumSize(700, 540)
        self.setStyleSheet(f"background: {DARK2}; color: {TEXT_MAIN};")
        self._glossary_path = os.path.join(
            _get_exe_dir(), "glossary.json"
        )
        self._build()
        self._load()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Title
        title = QLabel("GLOSSÁRIO")
        title.setStyleSheet(label_style(13))
        layout.addWidget(title)
        layout.addWidget(GoldSep())

        # Direction selector
        dir_row = QHBoxLayout()
        dir_lbl = QLabel("Direção:")
        dir_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        from PyQt6.QtWidgets import QComboBox
        self._dir_combo = QComboBox()
        self._dir_combo.addItem("PT → EN", "pt_en")
        self._dir_combo.addItem("EN → PT", "en_pt")
        self._dir_combo.setStyleSheet(f"""
            QComboBox {{ background: {DARK4}; color: {TEXT_MAIN};
            border: 1px solid {BORDER}; padding: 6px 10px; font-size: 13px; }}
            QComboBox QAbstractItemView {{ background: {DARK3}; color: {TEXT_MAIN};
            border: 1px solid {BORDER_GOLD}; selection-background-color: {GOLD_DARK}; }}
        """)
        self._dir_combo.currentIndexChanged.connect(self._refresh_table)
        dir_row.addWidget(dir_lbl)
        dir_row.addWidget(self._dir_combo)
        dir_row.addStretch()
        layout.addLayout(dir_row)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filtrar termos...")
        self._search.setStyleSheet(f"""
            QLineEdit {{ background: {DARK4}; color: {TEXT_MAIN};
            border: 1px solid {BORDER}; padding: 7px; font-size: 13px; }}
            QLineEdit:focus {{ border-color: {GOLD_DIM}; }}
        """)
        self._search.textChanged.connect(self._refresh_table)
        layout.addWidget(self._search)

        # Table
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Original", "Substituição"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setStyleSheet(f"""
            QTableWidget {{ background: {DARK3}; color: {TEXT_MAIN};
            border: 1px solid {BORDER}; gridline-color: {BORDER};
            font-size: 13px; }}
            QTableWidget::item {{ padding: 6px; }}
            QTableWidget::item:selected {{ background: {GOLD_DARK}; color: {GOLD}; }}
            QHeaderView::section {{ background: {DARK4}; color: {GOLD};
            font-weight: bold; font-size: 12px; padding: 6px;
            border: 1px solid {BORDER}; }}
        """)
        self._table.setSelectionBehavior(self._table.SelectionBehavior.SelectRows)
        layout.addWidget(self._table)

        # Add / Remove row
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("+ Adicionar")
        self._add_btn.setStyleSheet(btn_gold_style())
        self._add_btn.setFixedWidth(130)
        self._add_btn.clicked.connect(self._add_row)

        self._del_btn = QPushButton("− Remover")
        self._del_btn.setStyleSheet(btn_dim_style())
        self._del_btn.setFixedWidth(130)
        self._del_btn.clicked.connect(self._del_row)

        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addWidget(GoldSep())

        # Save / Cancel
        save_row = QHBoxLayout()
        self._save_btn = QPushButton("💾  Guardar")
        self._save_btn.setStyleSheet(btn_gold_style())
        self._save_btn.clicked.connect(self._save)

        self._cancel_btn = QPushButton("Cancelar")
        self._cancel_btn.setStyleSheet(btn_dim_style())
        self._cancel_btn.clicked.connect(self.reject)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")

        save_row.addWidget(self._status_lbl)
        save_row.addStretch()
        save_row.addWidget(self._cancel_btn)
        save_row.addWidget(self._save_btn)
        layout.addLayout(save_row)

    def _load(self):
        try:
            with open(self._glossary_path, encoding='utf-8') as f:
                self._data = json.load(f)
        except Exception as e:
            self._data = {"pt_en": {}, "en_pt": {}}
            self._status_lbl.setText(f"⚠ Erro ao carregar: {e}")
        self._refresh_table()

    def _flat_terms(self, direction):
        """Flatten all categories into list of (original, replacement)."""
        terms = []
        for cat, pairs in self._data.get(direction, {}).items():
            if cat.startswith('_'):
                continue
            for orig, repl in pairs.items():
                terms.append((orig, repl))
        return sorted(terms, key=lambda x: x[0].lower())

    def _refresh_table(self):
        direction = self._dir_combo.currentData()
        terms = self._flat_terms(direction)
        query = self._search.text().lower().strip()
        if query:
            terms = [(o, r) for o, r in terms if query in o.lower() or query in r.lower()]

        self._table.setRowCount(len(terms))
        for i, (orig, repl) in enumerate(terms):
            from PyQt6.QtWidgets import QTableWidgetItem
            self._table.setItem(i, 0, QTableWidgetItem(orig))
            self._table.setItem(i, 1, QTableWidgetItem(repl))

    def _add_row(self):
        """Open a JSON glossary file and import only new terms (skip duplicates)."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar Glossário", "", "Ficheiros JSON (*.json);;Todos (*)"
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                imported = json.load(f)
        except Exception as e:
            self._status_lbl.setText(f"⚠  Erro ao ler ficheiro: {e}")
            self._status_lbl.setStyleSheet(f"color: {RED}; font-size: 11px;")
            return

        direction = self._dir_combo.currentData()

        # Flatten current glossary terms
        current_terms = {}
        for cat, pairs in self._data.get(direction, {}).items():
            if cat.startswith("_"):
                continue
            current_terms.update(pairs)

        # Flatten imported terms
        imported_flat = {}
        if direction in imported:
            # Same format as our glossary
            for cat, pairs in imported[direction].items():
                if cat.startswith("_"):
                    continue
                if isinstance(pairs, dict):
                    imported_flat.update(pairs)
        elif isinstance(imported, dict):
            # Simple flat dict: {"word": "translation", ...}
            for k, v in imported.items():
                if isinstance(v, str):
                    imported_flat[k] = v

        # Compare: only add terms not in current
        new_terms = {k: v for k, v in imported_flat.items() if k not in current_terms}
        skipped = len(imported_flat) - len(new_terms)

        if not new_terms:
            self._status_lbl.setText(f"Sem termos novos — {skipped} já existiam.")
            self._status_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
            return

        # Add new terms to "Importado" category
        if direction not in self._data:
            self._data[direction] = {}
        if "Importado" not in self._data[direction]:
            self._data[direction]["Importado"] = {}
        self._data[direction]["Importado"].update(new_terms)

        self._refresh_table()
        self._status_lbl.setText(
            f"✓  {len(new_terms)} termos importados  •  {skipped} ignorados (duplicados)"
        )
        self._status_lbl.setStyleSheet(f"color: #4caf50; font-size: 11px;")

    def _del_row(self):
        rows = self._table.selectedItems()
        if not rows:
            return
        row = self._table.currentRow()
        orig = self._table.item(row, 0).text() if self._table.item(row, 0) else ""
        if not orig:
            return
        direction = self._dir_combo.currentData()
        # Find and remove from data
        for cat, pairs in self._data.get(direction, {}).items():
            if orig in pairs:
                del pairs[orig]
                break
        self._refresh_table()

    def _save(self):
        # Collect all edits from table back to data
        direction = self._dir_combo.currentData()
        # Rebuild "Custom" category from table
        all_pairs = {}
        for row in range(self._table.rowCount()):
            orig_item = self._table.item(row, 0)
            repl_item = self._table.item(row, 1)
            if orig_item and repl_item:
                orig = orig_item.text().strip()
                repl = repl_item.text().strip()
                if orig and repl:
                    all_pairs[orig] = repl

        # Rebuild data for this direction preserving categories
        new_dir = {}
        seen = set()
        for cat, pairs in self._data.get(direction, {}).items():
            if cat.startswith('_'):
                new_dir[cat] = pairs
                continue
            new_cat = {}
            for orig, repl in pairs.items():
                if orig in all_pairs:
                    new_cat[orig] = all_pairs[orig]
                    seen.add(orig)
            if new_cat:
                new_dir[cat] = new_cat

        # New terms go to Custom
        new_custom = {o: r for o, r in all_pairs.items() if o not in seen}
        if new_custom:
            new_dir["Custom"] = new_custom

        self._data[direction] = new_dir

        try:
            with open(self._glossary_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            # Invalidate cache
            import importlib
            global _GLOSSARY_CACHE
            _GLOSSARY_CACHE = None
            self._status_lbl.setText("✓  Guardado!")
            self._status_lbl.setStyleSheet(f"color: #4caf50; font-size: 11px;")
            QTimer.singleShot(2000, lambda: self._status_lbl.setText(""))
        except Exception as e:
            self._status_lbl.setText(f"⚠  Erro: {e}")
            self._status_lbl.setStyleSheet(f"color: {RED}; font-size: 11px;")



# ── Char Map Tab ──────────────────────────────────────────────────────────────

# ── CharMap Dialog ─────────────────────────────────────────────────────────
class CharMapDialog(QDialog):
    def __init__(self, charmap_tab, parent=None):
        super().__init__(parent)
        self._tab = charmap_tab
        self.setWindowTitle("Editar CharMap")
        self.setMinimumSize(700, 540)
        self.setStyleSheet(f"background: {DARK2}; color: {TEXT_MAIN};")
        self._build()
        self._load()

    def _build(self):
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QComboBox
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("CHAR MAP")
        title.setStyleSheet(label_style(13))
        layout.addWidget(title)
        layout.addWidget(GoldSep())

        # Category selector
        cat_row = QHBoxLayout()
        cat_lbl = QLabel("Categoria:")
        cat_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        self._cat_combo = QComboBox()
        for cat in self._tab._chars:
            self._cat_combo.addItem(cat)
        self._cat_combo.setCurrentText(self._tab._current_cat)
        self._cat_combo.setStyleSheet(f"""
            QComboBox {{ background: {DARK4}; color: {TEXT_MAIN};
            border: 1px solid {BORDER}; padding: 6px 10px; font-size: 13px; }}
            QComboBox QAbstractItemView {{ background: {DARK3}; color: {TEXT_MAIN};
            border: 1px solid {BORDER_GOLD}; selection-background-color: {GOLD_DARK}; }}
        """)
        self._cat_combo.currentIndexChanged.connect(self._refresh_table)
        cat_row.addWidget(cat_lbl)
        cat_row.addWidget(self._cat_combo)
        cat_row.addStretch()
        layout.addLayout(cat_row)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filtrar caracteres...")
        self._search.setStyleSheet(f"""
            QLineEdit {{ background: {DARK4}; color: {TEXT_MAIN};
            border: 1px solid {BORDER}; padding: 7px; font-size: 13px; }}
            QLineEdit:focus {{ border-color: {GOLD_DIM}; }}
        """)
        self._search.textChanged.connect(self._refresh_table)
        layout.addWidget(self._search)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Caractere", "Nome"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setStyleSheet(f"""
            QTableWidget {{ background: {DARK3}; color: {TEXT_MAIN};
            border: 1px solid {BORDER}; gridline-color: {BORDER}; font-size: 13px; }}
            QTableWidget::item {{ padding: 6px; }}
            QTableWidget::item:selected {{ background: {GOLD_DARK}; color: {GOLD}; }}
            QHeaderView::section {{ background: {DARK4}; color: {GOLD};
            font-weight: bold; font-size: 12px; padding: 6px; border: 1px solid {BORDER}; }}
        """)
        self._table.setSelectionBehavior(self._table.SelectionBehavior.SelectRows)
        layout.addWidget(self._table)

        # Add / Remove
        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Adicionar")
        add_btn.setStyleSheet(btn_gold_style())
        add_btn.setFixedWidth(130)
        add_btn.clicked.connect(self._add_row)
        del_btn = QPushButton("− Remover")
        del_btn.setStyleSheet(btn_dim_style())
        del_btn.setFixedWidth(130)
        del_btn.clicked.connect(self._del_row)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addWidget(GoldSep())

        # Save / Cancel
        save_row = QHBoxLayout()
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setStyleSheet(btn_dim_style())
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("💾  Guardar")
        save_btn.setStyleSheet(btn_gold_style())
        save_btn.clicked.connect(self._save)
        save_row.addWidget(self._status_lbl)
        save_row.addStretch()
        save_row.addWidget(cancel_btn)
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

    def _current_cat(self):
        return self._cat_combo.currentText()

    def _load(self):
        self._refresh_table()

    def _refresh_table(self):
        from PyQt6.QtWidgets import QTableWidgetItem
        cat = self._current_cat()
        search = self._search.text().strip().lower()
        chars = self._tab._chars.get(cat, [])
        if search:
            chars = [(c, n) for c, n in chars if search in n.lower() or search in c]
        self._table.setRowCount(0)
        for i, (char, name) in enumerate(chars):
            self._table.insertRow(i)
            self._table.setItem(i, 0, QTableWidgetItem(char))
            self._table.setItem(i, 1, QTableWidgetItem(name))
            self._table.setRowHeight(i, 32)
            num = QTableWidgetItem(str(i + 1))
            num.setForeground(QColor(GOLD))
            num.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._table.setVerticalHeader(self._table.verticalHeader())
        self._table.verticalHeader().setDefaultSectionSize(32)
        self._table.verticalHeader().setStyleSheet(
            f"QHeaderView::section {{ background: {DARK4}; color: {GOLD}; "
            f"font-weight: bold; font-size: 11px; border: 1px solid {BORDER}; }}"
        )

    def _add_row(self):
        """Open a patcher JSON and import chars into their categories."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Patcher", "",
            "JSON (*.json);;Todos os ficheiros (*)"
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                patch = json.load(f)
        except Exception as e:
            self._status_lbl.setText(f"⚠ Erro ao ler ficheiro: {e}")
            return

        known_cats = set(self._tab._chars.keys())
        added = 0

        # patch can be {"Cat": [["char","name"],...], ...} or flat list [["char","name"],...]
        if isinstance(patch, dict):
            items_by_cat = {}
            for cat, entries in patch.items():
                dest = cat if cat in known_cats else "Custom"
                items_by_cat.setdefault(dest, [])
                for entry in entries:
                    if isinstance(entry, (list, tuple)) and len(entry) >= 1:
                        items_by_cat[dest].append((entry[0], entry[1] if len(entry) > 1 else ""))
        elif isinstance(patch, list):
            items_by_cat = {"Custom": []}
            for entry in patch:
                if isinstance(entry, (list, tuple)) and len(entry) >= 1:
                    items_by_cat["Custom"].append((entry[0], entry[1] if len(entry) > 1 else ""))
        else:
            self._status_lbl.setText("⚠ Formato de JSON inválido")
            return

        for dest, entries in items_by_cat.items():
            existing_chars = {c for c, _ in self._tab._chars.get(dest, [])}
            for char, name in entries:
                if char and char not in existing_chars:
                    if not name:
                        name = f"U+{ord(char[0]):04X}"
                    self._tab._chars[dest].append((char, name))
                    existing_chars.add(char)
                    added += 1

        self._status_lbl.setText(f"✔ {added} caractere(s) importado(s)")
        self._refresh_table()

    def _del_row(self):
        """Open a patcher JSON and remove matching chars from their categories."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Patcher para Remover", "",
            "JSON (*.json);;Todos os ficheiros (*)"
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                patch = json.load(f)
        except Exception as e:
            self._status_lbl.setText(f"⚠ Erro ao ler ficheiro: {e}")
            return

        known_cats = set(self._tab._chars.keys())
        removed = 0

        if isinstance(patch, dict):
            items_by_cat = {}
            for cat, entries in patch.items():
                dest = cat if cat in known_cats else "Custom"
                items_by_cat.setdefault(dest, set())
                for entry in entries:
                    if isinstance(entry, (list, tuple)) and len(entry) >= 1:
                        items_by_cat[dest].add(entry[0])
        elif isinstance(patch, list):
            items_by_cat = {"Custom": set()}
            for entry in patch:
                if isinstance(entry, (list, tuple)) and len(entry) >= 1:
                    items_by_cat["Custom"].add(entry[0])
        else:
            self._status_lbl.setText("⚠ Formato de JSON inválido")
            return

        for dest, chars_to_remove in items_by_cat.items():
            before = len(self._tab._chars.get(dest, []))
            self._tab._chars[dest] = [
                (c, n) for c, n in self._tab._chars.get(dest, [])
                if c not in chars_to_remove
            ]
            removed += before - len(self._tab._chars[dest])

        self._status_lbl.setText(f"✔ {removed} caractere(s) removido(s)")
        self._refresh_table()

    def _save(self):
        cat = self._current_cat()
        chars = []
        for r in range(self._table.rowCount()):
            c = self._table.item(r, 0)
            n = self._table.item(r, 1)
            char = c.text().strip() if c else ""
            name = n.text().strip() if n else ""
            if char:
                chars.append((char, name or f"U+{ord(char[0]):04X}"))
        self._tab._chars[cat] = chars
        path = os.path.join(_get_user_data_dir(), "charmap.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            data[cat] = [[c, n] for c, n in chars]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._status_lbl.setText("✔ Guardado")
            self._tab._populate_grid(self._tab._grids[cat]._grid, cat, "")
        except Exception as e:
            self._status_lbl.setText(f"⚠ Erro: {e}")


class CharMapTab(BgWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_text = ""
        self._toast_timer = None
        self._chars = self._load_chars()
        self._build()

    def _load_chars(self):
        path = os.path.join(_get_user_data_dir(), "charmap.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return {k: [tuple(item) for item in lst] for k, lst in data.items()}
        except Exception as e:
            print(f"[CharMap] Erro ao carregar charmap.json: {e}")
            return {"Estrelas": [], "Bullets": [], "Box Drawing": [], "Weapons": [], "Custom": []}

    def _build(self):
        from PyQt6.QtWidgets import QStackedWidget, QScrollArea, QGridLayout
        main = QVBoxLayout(self)
        main.setContentsMargins(20, 20, 20, 20)
        main.setSpacing(12)

        title = QLabel("CHAR MAP")
        title.setStyleSheet(label_style(13))
        main.addWidget(title)
        main.addWidget(GoldSep())

        # Search bar
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Pesquisar por nome...")
        self._search_input.setStyleSheet(f"""
            QLineEdit {{ background: {DARK4}; color: {TEXT_MAIN};
            border: 1px solid {BORDER}; padding: 7px; font-size: 13px; }}
            QLineEdit:focus {{ border-color: {GOLD_DIM}; }}
        """)
        self._search_input.textChanged.connect(self._on_search)
        main.addWidget(self._search_input)
        self._search_input_ref = self._search_input

        # Category buttons row (manual tabs)
        self._cats = list(self._chars.keys())
        self._current_cat = self._cats[0]
        tab_row = QHBoxLayout()
        tab_row.setSpacing(2)
        tab_row.setContentsMargins(0, 0, 0, 0)
        self._cat_btns = {}
        for cat in self._cats:
            btn = QPushButton(cat.upper())
            btn.setCheckable(True)
            btn.setChecked(cat == self._current_cat)
            btn.setStyleSheet(self._cat_btn_style(cat == self._current_cat))
            btn.clicked.connect(lambda _, c=cat: self._switch_cat(c))
            self._cat_btns[cat] = btn
            tab_row.addWidget(btn)
        tab_row.addStretch()
        main.addLayout(tab_row)
        main.addWidget(GoldSep())

        # Stacked widget — one scroll per category
        self._stack = QStackedWidget()
        self._stack.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._grids = {}
        for cat in self._cats:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet(f"QScrollArea {{ background: {DARK2}; border: 1px solid {BORDER}; }}")
            container = QWidget()
            container.setStyleSheet(f"background: transparent;")
            grid = QGridLayout(container)
            grid.setSpacing(8)
            grid.setContentsMargins(12, 12, 12, 12)
            grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            scroll.setWidget(container)
            scroll._grid = grid
            scroll._cat = cat
            self._grids[cat] = scroll
            self._stack.addWidget(scroll)
        main.addWidget(self._stack, 1)

        # Populate first category
        self._populate_grid(self._grids[self._current_cat]._grid, self._current_cat, "")

        # Edit CharMap button
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        # Unicode input
        self._unicode_input = QLineEdit()
        self._unicode_input.setPlaceholderText("U+XXXX ou caractere")
        self._unicode_input.setFixedWidth(160)
        self._unicode_input.setStyleSheet(f"""
            QLineEdit {{ background: {DARK4}; color: {TEXT_MAIN};
            border: 1px solid {BORDER}; padding: 6px; font-size: 13px; }}
            QLineEdit:focus {{ border-color: {GOLD_DIM}; }}
        """)
        self._unicode_input.returnPressed.connect(self._insert_unicode)
        ins_btn = QPushButton("+ Inserir")
        ins_btn.setStyleSheet(btn_gold_style())
        ins_btn.setFixedWidth(90)
        ins_btn.clicked.connect(self._insert_unicode)
        self._ins_btn_ref = ins_btn

        rem_btn = QPushButton("− Remover")
        rem_btn.setStyleSheet(btn_dim_style())
        rem_btn.setFixedWidth(90)
        rem_btn.clicked.connect(self._remove_unicode)

        bottom_row.addWidget(self._unicode_input)
        bottom_row.addWidget(ins_btn)
        bottom_row.addWidget(rem_btn)
        bottom_row.addStretch()
        main.addLayout(bottom_row)

        # Toast
        self._toast = QLabel("✔", self)
        self._toast.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._toast.setStyleSheet(f"""
            QLabel {{
                background: {GOLD}; color: {DARK};
                border-radius: 24px; font-size: 22px; font-weight: bold;
            }}
        """)
        self._toast.setFixedSize(48, 48)
        self._toast.hide()

    def _cat_btn_style(self, active):
        if active:
            return f"""QPushButton {{
                background: {DARK2}; color: {GOLD};
                border: 1px solid {BORDER_GOLD}; border-bottom: 2px solid {GOLD};
                padding: 6px 18px; font-size: 11px; font-weight: bold; letter-spacing: 1px;
            }}"""
        return f"""QPushButton {{
            background: {DARK3}; color: {TEXT_DIM};
            border: 1px solid {BORDER};
            padding: 6px 18px; font-size: 11px; font-weight: bold; letter-spacing: 1px;
        }}
        QPushButton:hover {{ color: {GOLD_DIM}; border-color: {BORDER_GOLD}; }}"""

    def _switch_cat(self, cat):
        self._current_cat = cat
        for c, btn in self._cat_btns.items():
            btn.setChecked(c == cat)
            btn.setStyleSheet(self._cat_btn_style(c == cat))
        idx = self._cats.index(cat)
        self._stack.setCurrentIndex(idx)
        self._populate_grid(self._grids[cat]._grid, cat, self._search_text)

    def _make_scroll(self, cat):
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        container = QWidget()
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        from PyQt6.QtWidgets import QGridLayout
        grid = QGridLayout(container)
        grid.setSpacing(8)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._populate_grid(grid, cat, "")
        scroll.setWidget(container)
        scroll._grid = grid
        scroll._cat = cat
        return scroll

    def _populate_grid(self, grid, cat, search):
        while grid.count():
            item = grid.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        chars = self._chars.get(cat, [])
        if search:
            chars = [(c, n) for c, n in chars if search.lower() in n.lower() or search in c]

        cols = 10
        for i, (char, name) in enumerate(chars):
            btn = QPushButton(char)
            btn.setFixedSize(54, 54)
            btn.setToolTip(f"{name}  •  U+{ord(char):04X}")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {DARK3};
                    color: {TEXT_MAIN};
                    border: 1px solid {BORDER};
                    border-radius: 6px;
                    font-size: 22px;
                }}
                QPushButton:hover {{
                    background: {DARK4};
                    border-color: {GOLD_DIM};
                    color: {GOLD};
                }}
                QPushButton:pressed {{
                    background: {GOLD_DARK};
                    border-color: {GOLD};
                }}
            """)
            btn.clicked.connect(lambda _, c=char: self._copy_char(c))

            grid.addWidget(btn, i // cols, i % cols)

    def _insert_unicode(self):
        raw = self._unicode_input.text().strip()
        if not raw:
            return
        if raw.upper().startswith("U+") or (len(raw) > 1 and all(c in "0123456789ABCDEFabcdef" for c in raw)):
            try:
                char = chr(int(raw.replace("U+","").replace("u+",""), 16))
            except:
                char = raw[0]
        else:
            char = raw[0]
        name = f"U+{ord(char):04X}"
        cat = self._current_cat
        existing = [c for c, _ in self._chars[cat]]
        if char not in existing:
            self._chars[cat].append((char, name))
        path = os.path.join(_get_user_data_dir(), "charmap.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            data[cat] = [[c, n] for c, n in self._chars[cat]]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CharMap] Erro ao guardar: {e}")
        self._populate_grid(self._grids[cat]._grid, cat, self._search_text)
        self._unicode_input.clear()
        self._show_toast()

    def _remove_unicode(self):
        raw = self._unicode_input.text().strip()
        if not raw:
            return
        if raw.upper().startswith("U+") or (len(raw) > 1 and all(c in "0123456789ABCDEFabcdef" for c in raw)):
            try:
                char = chr(int(raw.replace("U+","").replace("u+",""), 16))
            except:
                char = raw[0]
        else:
            char = raw[0]
        cat = self._current_cat
        before = len(self._chars[cat])
        self._chars[cat] = [(c, n) for c, n in self._chars[cat] if c != char]
        if len(self._chars[cat]) < before:
            path = os.path.join(_get_user_data_dir(), "charmap.json")
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                data[cat] = [[c, n] for c, n in self._chars[cat]]
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"[CharMap] Erro ao guardar: {e}")
            self._populate_grid(self._grids[cat]._grid, cat, self._search_text)
            self._show_toast()
        self._unicode_input.clear()

    def _copy_char(self, char):
        QApplication.clipboard().setText(char)
        self._show_toast()

    def _show_toast(self):
        if self._toast_timer:
            self._toast_timer.stop()
        x = (self.width() - self._toast.width()) // 2
        y = (self.height() - self._toast.height()) // 2
        self._toast.move(x, y)
        self._toast.raise_()
        self._toast.show()
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._toast.hide)
        self._toast_timer.start(800)

    def _on_search(self, text):
        self._search_text = text
        self._populate_grid(self._grids[self._current_cat]._grid, self._current_cat, text)





# ── Color Square Widget ────────────────────────────────────────────────────
class ColorSquare(QWidget):
    """Saturation/Value square + hue bar on the right."""
    colorChanged = pyqtSignal(QColor)
    HUE_BAR = 18

    def __init__(self, color=None, parent=None):
        super().__init__(parent)
        c = color or QColor(GOLD)
        self._hue = max(0.0, c.hsvHueF())
        self._sat = c.hsvSaturationF()
        self._val = c.valueF()
        self.setMouseTracking(True)
        self._drag = None  # "sq" or "hue"

    def set_color(self, color):
        self._hue = max(0.0, color.hsvHueF())
        self._sat = color.hsvSaturationF()
        self._val = color.valueF()
        self.update()

    def _sq_rect(self):
        return QRect(0, 0, self.width() - self.HUE_BAR - 4, self.height())

    def _hue_rect(self):
        return QRect(self.width() - self.HUE_BAR, 0, self.HUE_BAR, self.height())

    def paintEvent(self, e):
        p = QPainter(self)
        sq = self._sq_rect()
        hr = self._hue_rect()

        # SV square
        for x in range(0, sq.width(), 2):
            for y in range(0, sq.height(), 2):
                s = x / sq.width()
                v = 1.0 - (y / sq.height())
                p.fillRect(sq.x() + x, y, 2, 2, QColor.fromHsvF(self._hue, s, v))

        # Hue bar
        for y in range(hr.height()):
            hue = y / hr.height()
            p.fillRect(hr.x(), y, hr.width(), 1, QColor.fromHsvF(hue, 1.0, 1.0))

        # SV cursor
        cx = sq.x() + int(self._sat * sq.width())
        cy = int((1.0 - self._val) * sq.height())
        p.setPen(QPen(QColor("white"), 2))
        p.drawEllipse(cx - 5, cy - 5, 10, 10)
        p.setPen(QPen(QColor("black"), 1))
        p.drawEllipse(cx - 4, cy - 4, 8, 8)

        # Hue cursor
        hy = int(self._hue * hr.height())
        p.setPen(QPen(QColor("white"), 2))
        p.drawRect(hr.x() - 1, hy - 3, hr.width() + 2, 6)

    def mousePressEvent(self, e):
        if self._hue_rect().contains(e.position().toPoint()):
            self._drag = "hue"
        else:
            self._drag = "sq"
        self._pick(e.position())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton and self._drag:
            self._pick(e.position())

    def mouseReleaseEvent(self, e):
        self._drag = None

    def _pick(self, pos):
        if self._drag == "hue":
            self._hue = max(0.0, min(0.9999, pos.y() / self.height()))
        else:
            sq = self._sq_rect()
            self._sat = max(0.0, min(1.0, (pos.x() - sq.x()) / sq.width()))
            self._val = max(0.0, min(1.0, 1.0 - pos.y() / sq.height()))
        self.update()
        self.colorChanged.emit(QColor.fromHsvF(self._hue, self._sat, self._val))


# ── HUD Settings Dialog ────────────────────────────────────────────────────
class HudDialog(QDialog):
    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self._main = main_win
        self.setWindowTitle("HUD Settings")
        self.setMinimumSize(520, 480)
        self.setStyleSheet(f"background: {DARK2}; color: {TEXT_MAIN};")
        self._cfg = load_config()
        self._build()

    def _build(self):
        from PyQt6.QtWidgets import QColorDialog
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("HUD SETTINGS")
        title.setStyleSheet(label_style(13))
        layout.addWidget(title)
        layout.addWidget(GoldSep())

        # ── Wallpaper ──
        wall_lbl = QLabel("WALLPAPER")
        wall_lbl.setStyleSheet(f"color: {GOLD_DIM}; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(wall_lbl)
        wall_row = QHBoxLayout()
        wall_row.setSpacing(8)
        btn_set = QPushButton("🖼  Definir Fundo")
        btn_set.setStyleSheet(btn_gold_style())
        btn_set.clicked.connect(self._set_bg)
        btn_rm = QPushButton("✕  Remover")
        btn_rm.setStyleSheet(btn_dim_style())
        btn_rm.clicked.connect(self._rm_bg)
        wall_row.addWidget(btn_set)
        wall_row.addWidget(btn_rm)
        wall_row.addStretch()
        layout.addLayout(wall_row)
        layout.addWidget(GoldSep())

        # ── Accent Color (lines) ──
        accent_lbl = QLabel("COR DAS LINHAS")
        accent_lbl.setStyleSheet(f"color: {GOLD_DIM}; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(accent_lbl)

        accent_row = QHBoxLayout()
        accent_row.setSpacing(12)

        # Color picker square (HSV — brightness vertically, saturation horizontally)
        self._accent_color = QColor(self._cfg.get("accent_color", GOLD))
        self._color_square = ColorSquare(self._accent_color, self)
        self._color_square.setFixedSize(160, 120)
        self._color_square.colorChanged.connect(self._on_accent_change)
        accent_row.addWidget(self._color_square)

        right_col = QVBoxLayout()
        right_col.setSpacing(8)
        hex_row = QHBoxLayout()
        hex_lbl = QLabel("#")
        hex_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 13px;")
        self._hex_input = QLineEdit(self._accent_color.name()[1:].upper())
        self._hex_input.setMaxLength(6)
        self._hex_input.setFixedWidth(90)
        self._hex_input.setStyleSheet(f"""
            QLineEdit {{ background: {DARK4}; color: {TEXT_MAIN};
            border: 1px solid {BORDER}; padding: 6px; font-size: 13px; font-family: monospace; }}
            QLineEdit:focus {{ border-color: {GOLD_DIM}; }}
        """)
        self._hex_input.textChanged.connect(self._on_hex_input)
        hex_row.addWidget(hex_lbl)
        hex_row.addWidget(self._hex_input)
        hex_row.addStretch()
        right_col.addLayout(hex_row)

        self._accent_preview = QLabel()
        self._accent_preview.setFixedSize(90, 32)
        self._accent_preview.setStyleSheet(f"background: {self._accent_color.name()}; border: 1px solid {BORDER};")
        right_col.addWidget(self._accent_preview)

        btn_reset_accent = QPushButton("Reset")
        btn_reset_accent.setStyleSheet(btn_dim_style())
        btn_reset_accent.setFixedWidth(90)
        btn_reset_accent.clicked.connect(lambda: self._apply_accent(QColor(GOLD)))
        right_col.addWidget(btn_reset_accent)
        right_col.addStretch()
        accent_row.addLayout(right_col)
        layout.addLayout(accent_row)
        layout.addWidget(GoldSep())

        # ── Background Color ──
        bg_lbl = QLabel("COR DO FUNDO (sem wallpaper)")
        bg_lbl.setStyleSheet(f"color: {GOLD_DIM}; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(bg_lbl)

        bg_row = QHBoxLayout()
        bg_row.setSpacing(12)
        self._bg_color = QColor(self._cfg.get("bg_color", DARK))
        self._bg_preview = QLabel()
        self._bg_preview.setFixedSize(90, 32)
        self._bg_preview.setStyleSheet(f"background: {self._bg_color.name()}; border: 1px solid {BORDER};")
        bg_hex_lbl = QLabel("#")
        bg_hex_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 13px;")
        self._bg_hex_input = QLineEdit(self._bg_color.name()[1:].upper())
        self._bg_hex_input.setMaxLength(6)
        self._bg_hex_input.setFixedWidth(90)
        self._bg_hex_input.setStyleSheet(f"""
            QLineEdit {{ background: {DARK4}; color: {TEXT_MAIN};
            border: 1px solid {BORDER}; padding: 6px; font-size: 13px; font-family: monospace; }}
            QLineEdit:focus {{ border-color: {GOLD_DIM}; }}
        """)
        self._bg_hex_input.textChanged.connect(self._on_bg_hex)
        bg_row.addWidget(bg_hex_lbl)
        bg_row.addWidget(self._bg_hex_input)
        bg_row.addWidget(self._bg_preview)
        btn_reset_bg = QPushButton("Reset")
        btn_reset_bg.setStyleSheet(btn_dim_style())
        btn_reset_bg.setFixedWidth(70)
        btn_reset_bg.clicked.connect(lambda: self._apply_bg(QColor("#0a0a0a")))
        bg_row.addWidget(btn_reset_bg)
        bg_row.addStretch()
        layout.addLayout(bg_row)

        layout.addStretch()
        layout.addWidget(GoldSep())

        # Save / Cancel
        save_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.setStyleSheet(btn_dim_style())
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("💾  Aplicar")
        save_btn.setStyleSheet(btn_gold_style())
        save_btn.clicked.connect(self._save)
        save_row.addStretch()
        save_row.addWidget(cancel_btn)
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

    def _on_accent_change(self, color):
        self._accent_color = color
        self._accent_preview.setStyleSheet(f"background: {color.name()}; border: 1px solid {BORDER};")
        self._hex_input.blockSignals(True)
        self._hex_input.setText(color.name()[1:].upper())
        self._hex_input.blockSignals(False)

    def _apply_accent(self, color):
        self._accent_color = color
        self._accent_preview.setStyleSheet(f"background: {color.name()}; border: 1px solid {BORDER};")
        self._hex_input.blockSignals(True)
        self._hex_input.setText(color.name()[1:].upper())
        self._hex_input.blockSignals(False)
        self._color_square.set_color(color)

    def _on_hex_input(self, text):
        if len(text) == 6:
            try:
                color = QColor(f"#{text}")
                if color.isValid():
                    self._apply_accent(color)
            except: pass

    def _on_bg_hex(self, text):
        if len(text) == 6:
            try:
                color = QColor(f"#{text}")
                if color.isValid():
                    self._apply_bg(color)
            except: pass

    def _apply_bg(self, color):
        self._bg_color = color
        self._bg_preview.setStyleSheet(f"background: {color.name()}; border: 1px solid {BORDER};")
        self._bg_hex_input.blockSignals(True)
        self._bg_hex_input.setText(color.name()[1:].upper())
        self._bg_hex_input.blockSignals(False)

    def _set_bg(self):
        self.hide()
        self._main._set_background()
        self.show()

    def _rm_bg(self):
        self._main._remove_background()

    def _save(self):
        cfg = load_config()
        cfg["accent_color"] = self._accent_color.name()
        cfg["bg_color"] = self._bg_color.name()
        save_config(cfg)
        _apply_hud_globals(cfg)
        self.accept()
        # Aplica estilos a todos os widgets sem reiniciar
        _refresh_all_styles(self._main)

# ── First Boot Dialog ─────────────────────────────────────────────────────
class FirstBootDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ROK Mail Editor")
        self.setFixedSize(520, 320)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        container = QWidget()
        container.setStyleSheet(f"""
            QWidget {{
                background: {DARK2};
                border: 1px solid {BORDER_GOLD};
            }}
        """)
        inner = QVBoxLayout(container)
        inner.setContentsMargins(36, 32, 36, 28)
        inner.setSpacing(18)

        # Title
        title = QLabel("ROK MAIL EDITOR")
        title.setStyleSheet(f"color: {GOLD}; font-size: 20px; font-weight: bold; letter-spacing: 3px; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(title)

        # Gold sep
        sep = GoldSep()
        inner.addWidget(sep)

        # Message
        msg = QLabel(
            "Antes de começares, uma nota importante:\n\n"
            "Se precisares de mover este programa,\n"
            "move sempre a pasta completa.\n\n"
            "Nunca um ficheiro isolado."
        )
        msg.setStyleSheet(f"color: {TEXT_MAIN}; font-size: 14px; line-height: 1.6; border: none;")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner.addWidget(msg)

        inner.addWidget(GoldSep())

        # OK button
        btn = QPushButton("Entendido  ✓")
        btn.setStyleSheet(btn_gold_style())
        btn.clicked.connect(self.accept)
        inner.addWidget(btn)

        layout.addWidget(container)

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Shadow effect
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)

# ── Main Window ────────────────────────────────────────────────────────────

def _refresh_all_styles(win):
    """Reaplica todos os estilos da janela principal com as cores atuais."""
    from PyQt6.QtWidgets import QPushButton, QLabel, QSlider, QLineEdit, QSpinBox, QTextEdit, QScrollArea

    # Janela principal
    win.setStyleSheet(f"""
        QMainWindow {{ background: {DARK}; }}
        QWidget {{ color: {TEXT_MAIN}; }}
        QToolTip {{ background: {DARK3}; color: {GOLD}; border: 1px solid {BORDER_GOLD}; }}
    """)

    # Tab bar
    win.tabs_widget.setStyleSheet(f"""
        QTabWidget::pane {{
            border: 1px solid {BORDER_GOLD};
            background: transparent;
            top: -1px;
        }}
        QTabBar::tab {{
            background: {DARK3};
            color: {TEXT_DIM};
            padding: 9px 28px;
            border: 1px solid {BORDER};
            font-weight: bold; font-size: 12px;
            letter-spacing: 2px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background: {DARK2};
            color: {GOLD};
            border-color: {BORDER_GOLD};
            border-top: 2px solid {GOLD};
        }}
        QTabBar::tab:hover:!selected {{
            color: {GOLD_DIM};
            border-color: {BORDER_GOLD};
        }}
    """)

    # Título e separador
    win.title_lbl.setStyleSheet(f"color: {GOLD}; font-size: 22px; font-weight: bold; letter-spacing: 3px;")
    win.gold_sep.update()

    # Percorre todos os widgets e reaplica estilos pelo tipo/texto
    for w in win.findChildren(QLabel):
        txt = w.text().strip().upper()
        # Labels de secção (CÓDIGO, PREVIEW, RODA DE CORES, etc.)
        if txt in ("CÓDIGO", "PREVIEW", "RODA DE CORES", "PONTOS DE COR", "TEXTO",
                   "CHAR MAP", "EDITOR", "GRADIENTE", "HUD SETTINGS", "WALLPAPER",
                   "COR DAS LINHAS", "COR DO FUNDO (SEM WALLPAPER)"):
            w.setStyleSheet(label_style(12))
        elif txt in ("☀", "◾"):
            w.setStyleSheet(f"color: {GOLD}; font-size: 14px;" if txt == "☀" else f"color: {TEXT_DIM}; font-size: 10px;")

    # Botões de categoria do CharMap
    charmap_tab = win._charmap_tab
    for cat, btn in charmap_tab._cat_btns.items():
        btn.setStyleSheet(charmap_tab._cat_btn_style(cat == charmap_tab._current_cat))

    # Barra de pesquisa e botão Inserir do CharMap
    charmap_tab._search_input_ref.setStyleSheet(f"""
        QLineEdit {{ background: {DARK4}; color: {TEXT_MAIN};
        border: 1px solid {BORDER}; padding: 7px; font-size: 13px; }}
        QLineEdit:focus {{ border-color: {GOLD_DIM}; }}
    """)
    charmap_tab._ins_btn_ref.setStyleSheet(btn_gold_style())

    # Botão "+" da sidebar do editor
    win._editor_widget._add_btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent; color: {GOLD_DIM};
            font-size: 18px; border: none;
            border-bottom: 1px solid {BORDER}; padding-bottom: 4px;
        }}
        QPushButton:hover {{ color: {GOLD}; background: {DARK3}; }}
    """)

    # Setas da sidebar
    for ab in win._editor_widget._arrow_btns:
        ab.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_DIM};
                font-size: 11px; border: none;
            }}
            QPushButton:hover {{ color: {GOLD}; background: {DARK3}; }}
        """)

    # DocBarEntry — reaplica estilo em todos os docs
    for entry, tab in win._editor_widget._docs:
        is_active = (win._editor_widget._stack.currentWidget() is tab)
        entry.set_active(is_active)

    # Engrenagem
    win.gear_btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent; color: {GOLD_DIM};
            font-size: 18px; border: 1px solid {BORDER}; border-radius: 17px;
        }}
        QPushButton:hover {{ color: {GOLD}; border-color: {GOLD_DIM}; background: {DARK3}; }}
    """)

    # Slider do gradiente — percorre tabs
    for i in range(win.tabs_widget.count()):
        tab = win.tabs_widget.widget(i)
        for slider in tab.findChildren(QSlider):
            # Tenta detetar se é o brightness slider pelo pai
            slider.setStyleSheet(f"""
                QSlider::groove:vertical {{
                    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 {GOLD}, stop:1 #000000);
                    width: 8px; border-radius: 4px; margin: 0 8px;
                }}
                QSlider::handle:vertical {{
                    background: {GOLD}; border: 2px solid {DARK};
                    width: 16px; height: 16px; border-radius: 8px; margin: 0 -4px;
                }}
                QSlider::handle:vertical:hover {{ background: #fff; }}
            """)

    # Botão Inseri e outros botões com estilos gold/dim
    from PyQt6.QtWidgets import QPushButton
    for btn in win.findChildren(QPushButton):
        txt = btn.text().strip()
        # Botões gold (Inseri, +, etc.)
        if txt in ("+ Inserir", "Inseri", "+ Adicionar"):
            btn.setStyleSheet(btn_gold_style())
        # Botão sidebar activo (número do doc)
        cur_style = btn.styleSheet()
        if f"border-left: 3px solid" in cur_style and GOLD in cur_style:
            btn.setStyleSheet(btn.styleSheet().replace(
                btn.styleSheet(), btn.styleSheet()))

    # TextEdit borders — preview tem borda BORDER_GOLD, código tem BORDER
    from PyQt6.QtWidgets import QTextEdit
    for te in win.findChildren(QTextEdit):
        if te.isReadOnly():
            te.setStyleSheet(textedit_style(BORDER_GOLD))
        else:
            te.setStyleSheet(textedit_style())

    # Força repaint de todos os widgets filhos
    for w in win.findChildren(QWidget):
        w.update()
    win.update()
    win.repaint()


def _apply_hud_globals(cfg):
    global GOLD, GOLD_DIM, GOLD_DARK, BORDER_GOLD, DARK, DARK2, DARK3, DARK4, FONT_SIZE
    FONT_SIZE = cfg.get("font_size", 13)
    if "accent_color" in cfg:
        c = QColor(cfg["accent_color"])
        if c.isValid():
            GOLD = c.name()
            h, s, v, _ = c.getHsvF()
            GOLD_DIM    = QColor.fromHsvF(h, min(1.0, s*0.85), max(0.0, v*0.75)).name()
            GOLD_DARK   = QColor.fromHsvF(h, min(1.0, s*0.9),  max(0.0, v*0.4)).name()
            BORDER_GOLD = QColor.fromHsvF(h, min(1.0, s*0.8),  max(0.0, v*0.55)).name()
    if "bg_color" in cfg:
        c = QColor(cfg["bg_color"])
        if c.isValid():
            DARK  = c.name()
            DARK2 = QColor(min(255,c.red()+8),  min(255,c.green()+8),  min(255,c.blue()+8)).name()
            DARK3 = QColor(min(255,c.red()+16), min(255,c.green()+16), min(255,c.blue()+16)).name()
            DARK4 = QColor(min(255,c.red()+24), min(255,c.green()+24), min(255,c.blue()+24)).name()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ROK Mail Editor")
        self.resize(1280, 860)
        self.setStyleSheet(f"""
            QMainWindow {{ background: {DARK}; }}
            QWidget {{ color: {TEXT_MAIN}; }}
            QToolTip {{ background: {DARK3}; color: {GOLD}; border: 1px solid {BORDER_GOLD}; }}
        """)

        # Apply HUD settings
        _hud_cfg = load_config()
        _apply_hud_globals(_hud_cfg)

        central = BgWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Title bar
        title_row = QHBoxLayout()
        self.title_lbl = QLabel("⚔  ROK MAIL EDITOR")
        self.title_lbl.setStyleSheet(f"""
            color: {GOLD};
            font-size: 22px;
            font-weight: bold;
            letter-spacing: 3px;
        """)
        self.title_lbl.setGraphicsEffect(None)
        title_row.addWidget(self.title_lbl)
        title_row.addStretch()

        self.gear_btn = QPushButton("⚙")
        self.gear_btn.setFixedSize(34, 34)
        self.gear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {GOLD_DIM};
                font-size: 18px;
                border: 1px solid {BORDER};
                border-radius: 17px;
            }}
            QPushButton:hover {{
                color: {GOLD};
                border-color: {GOLD_DIM};
                background: {DARK3};
            }}
        """)
        self.gear_btn.clicked.connect(self._open_settings)
        title_row.addWidget(self.gear_btn)
        layout.addLayout(title_row)
        self.gold_sep = GoldSep()
        layout.addWidget(self.gold_sep)

        tabs = QTabWidget()
        self.tabs_widget = tabs
        tabs.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {BORDER_GOLD};
                background: transparent;
                top: -1px;
            }}
            QTabBar::tab {{
                background: {DARK3};
                color: {TEXT_DIM};
                padding: 9px 28px;
                border: 1px solid {BORDER};
                font-weight: bold; font-size: 12px;
                letter-spacing: 2px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {DARK2};
                color: {GOLD};
                border-color: {BORDER_GOLD};
                border-top: 2px solid {GOLD};
            }}
            QTabBar::tab:hover:!selected {{
                color: {GOLD_DIM};
                border-color: {BORDER_GOLD};
            }}
        """)

        self._tabs = tabs
        self._config = load_config()
        self._last_dir = self._config.get("last_dir", os.path.expanduser("~"))
        self._editor_widget = MultiEditorWidget()
        tabs.addTab(self._editor_widget, "EDITOR")
        tabs.addTab(GradientTab(), "GRADIENTE")
        self._charmap_tab = CharMapTab()
        tabs.addTab(self._charmap_tab, "CHAR MAP")
        layout.addWidget(tabs)

        # Start cascade animation after show
        QTimer.singleShot(50, self._animate_cascade)

    def _animate_cascade(self):
        from PyQt6.QtWidgets import QGraphicsOpacityEffect

        widgets = [self.title_lbl, self.gear_btn, self.gold_sep, self.tabs_widget]
        self._anims = []

        for i, w in enumerate(widgets):
            effect = QGraphicsOpacityEffect(w)
            effect.setOpacity(0.0)
            w.setGraphicsEffect(effect)

            anim = QPropertyAnimation(effect, b"opacity")
            anim.setDuration(450)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(0.0)

            QTimer.singleShot(i * 200, anim.start)
            self._anims.append((effect, anim))

    def closeEvent(self, e):
        e.accept()
        QApplication.quit()

    def _open_settings(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {DARK3};
                color: {TEXT_MAIN};
                border: 1px solid {BORDER_GOLD};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 8px 20px;
                font-size: 13px;
            }}
            QMenu::item:selected {{
                background: {GOLD_DARK};
                color: {GOLD};
            }}
        """)
        action_new  = menu.addAction("📝  Novo")
        action_save = menu.addAction("💾  Guardar")
        action_open = menu.addAction("📂  Abrir")
        action_charmap = menu.addAction("➕  Adicionar ao CharMap")

        # Recents submenu
        recents = load_config().get("recents", [])
        recent_actions = []
        if recents:
            menu.addSeparator()
            rec_label = menu.addAction("🕘  RECENTES")
            rec_label.setEnabled(False)
            for r in recents:
                name = os.path.basename(r)
                a = menu.addAction(f"  📄  {name}")
                recent_actions.append((a, r))

        menu.addSeparator()
        action_hud = menu.addAction("🎨  HUD Settings")
        action_bg = menu.addAction("🖼  Definir Fundo")
        action_rm = menu.addAction("✕  Remover Fundo")
        action = menu.exec(self.gear_btn.mapToGlobal(self.gear_btn.rect().bottomLeft()))
        if action == action_hud:
            HudDialog(self, self).exec()
        elif action == action_charmap:
            self._tabs.setCurrentWidget(self._charmap_tab)
            CharMapDialog(self._charmap_tab, self).exec()
        elif action == action_new:
            self._new_file()
        elif action == action_save:
            self._save_file()
        elif action == action_open:
            self._open_file()
        elif action == action_bg:
            self._set_background()
        elif action == action_rm:
            self._remove_background()
        else:
            for a, path in recent_actions:
                if action == a:
                    self._open_recent(path)
                    break

    def _new_file(self):
        editor = self._editor_widget
        text = editor.code_input.toPlainText()
        if text.strip():
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Novo ficheiro")
            dlg.setText("Tens conteúdo não guardado.\nQueres guardar antes de continuar?")
            dlg.setStandardButtons(
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )
            dlg.setDefaultButton(QMessageBox.StandardButton.Save)
            dlg.setStyleSheet(f"""
                QMessageBox {{ background: {DARK2}; color: {TEXT_MAIN}; }}
                QLabel {{ color: {TEXT_MAIN}; font-size: 13px; }}
                QPushButton {{ background: {DARK4}; color: {TEXT_MAIN}; border: 1px solid {BORDER}; padding: 6px 16px; }}
                QPushButton:hover {{ border-color: {GOLD_DIM}; color: {GOLD}; }}
            """)
            res = dlg.exec()
            if res == QMessageBox.StandardButton.Cancel:
                return
            if res == QMessageBox.StandardButton.Save:
                self._save_file()
        editor.new_tab()
        self._tabs.setCurrentIndex(0)

    def _save_file(self):
        dlg = QFileDialog(self, "Guardar ficheiro", self._last_dir, "Todos os ficheiros (*);;Ficheiros ROK (*.rok);;Ficheiros de texto (*.txt)")
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dlg.setFilter(dlg.filter() | QDir.Filter.Hidden)
        if not dlg.exec():
            return
        path = dlg.selectedFiles()[0]
        # Get code from editor tab
        editor = self._editor_widget
        text = editor.code_input.toPlainText()
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        self._last_dir = os.path.dirname(path)
        add_recent(path)
        cfg = load_config()
        cfg["last_dir"] = self._last_dir
        save_config(cfg)

    def _open_file(self):
        dlg = QFileDialog(self, "Abrir ficheiro", self._last_dir, "Ficheiros ROK (*.rok);;Ficheiros de texto (*.txt);;Todos os ficheiros (*)")
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dlg.setFilter(dlg.filter() | QDir.Filter.Hidden)
        if not dlg.exec():
            return
        path = dlg.selectedFiles()[0]
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        self._editor_widget.new_tab(content=text)
        self._tabs.setCurrentIndex(0)
        self._last_dir = os.path.dirname(path)
        add_recent(path)
        cfg = load_config()
        cfg["last_dir"] = self._last_dir
        save_config(cfg)

    def _open_recent(self, path):
        if not os.path.exists(path):
            add_recent_remove(path)
            return
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        self._editor_widget.new_tab(content=text)
        self._tabs.setCurrentIndex(0)
        self._last_dir = os.path.dirname(path)
        add_recent(path)
        cfg = load_config()
        cfg["last_dir"] = self._last_dir
        save_config(cfg)

    def _set_background(self):
        start = os.path.expanduser("~")
        dlg = QFileDialog(self, "Escolher imagem de fundo", start, "Imagens (*.png *.jpg *.jpeg *.bmp *.webp)")
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dlg.setFilter(dlg.filter() | QDir.Filter.Hidden)
        if not dlg.exec():
            return
        path = dlg.selectedFiles()[0]
        dest = os.path.join(_APPDATA_DIR, "back.png")
        shutil.copy2(path, dest)
        global BG_IMAGE
        BG_IMAGE = QPixmap(dest)
        self.update()
        self.centralWidget().update()

    def _remove_background(self):
        global BG_IMAGE
        BG_IMAGE = None
        dest = os.path.join(_APPDATA_DIR, "back.png")
        if os.path.exists(dest):
            try:
                os.remove(dest)
            except Exception as e:
                print(f"[BG] Erro ao remover: {e}")
        self.update()
        self.centralWidget().update()
        self.repaint()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Set taskbar/window icon
    # Procura o ícone — no PyInstaller o _MEIPASS tem os dados empacotados
    _icon_path = None
    for _candidate in [
        os.path.join(getattr(sys, '_MEIPASS', ''), 'icon.ico'),
        os.path.join(getattr(sys, '_MEIPASS', ''), 'icon.png'),
        os.path.join(_get_exe_dir(), 'icon.ico'),
        os.path.join(_get_exe_dir(), 'icon.png'),
    ]:
        if os.path.exists(_candidate):
            _icon_path = _candidate
            break
    if _icon_path:
        from PyQt6.QtGui import QIcon
        app.setWindowIcon(QIcon(_icon_path))

    load_bg()
    app.setStyle("Fusion")

    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(DARK))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_MAIN))
    palette.setColor(QPalette.ColorRole.Base, QColor(DARK3))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(DARK2))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_MAIN))
    palette.setColor(QPalette.ColorRole.Button, QColor(DARK4))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_MAIN))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(GOLD_DARK))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(GOLD))
    app.setPalette(palette)

    # First boot check
    cfg = load_config()
    if not cfg.get("first_boot_done"):
        dlg = FirstBootDialog()
        dlg.exec()
        cfg = load_config()
        cfg["first_boot_done"] = True
        save_config(cfg)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())