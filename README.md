# ⚔ ROK Mail Editor

```
  ██████╗ 
 ██╔════╝ 
 ╚█████╗  
  ╚═══██╗ 
 ██████╔╝ 
 ╚═════╝  
  by Sifrado
```

A powerful Rise of Kingdoms mail editor with live preview, gradient generator, and character map.

---

## Features

- **Live ROK Code Editor** — Write ROK-formatted text with real-time colored preview
- **Syntax Highlighting** — Color tags, size tags, bold, italic and underline highlighted in the editor
- **Multi-document Sidebar** — Work on multiple mails simultaneously with a sleek sidebar
- **Gradient Generator** — Interactive color wheel to generate multi-color gradients character by character
- **Character Map** — Browse and copy special characters (Stars, Bullets, Box Drawing, Weapons, Custom)
- **HUD Settings** — Fully customizable accent color, background color, and wallpaper
- **Glossary** — Built-in PT↔EN translation glossary, editable and importable
- **Recent Files** — Quick access to the last 3 opened files
- **Persistent Config** — Settings and preferences saved automatically

---

## Supported Tags

| Tag | Effect |
|-----|--------|
| `<color=#RRGGBB>text</color>` | Colored text |
| `<size=N>text</size>` | Text size |
| `<b>text</b>` | Bold |
| `<i>text</i>` | Italic |
| `<u>text</u>` | Underline |

---

## Installation

### Windows
1. Download `ROKEditor.exe`
2. Right-click → Properties → Check **Unblock** if prompted
3. Double-click to run — no installation required

### Linux
1. Download `ROKEditor` binary
2. Make executable: `chmod +x ROKEditor`
3. Run: `./ROKEditor`
   Or install globally: `sudo cp ROKEditor /usr/local/bin/RE`

### Android
1. Download `ROKEditor.apk`
2. Enable **Install from unknown sources** in Settings
3. Open the APK and install

---

## File Storage

| Platform | Config & Data |
|----------|--------------|
| Windows | `%APPDATA%\ROKEditor\` |
| Linux | `~/.config/ROKEditor/` |
| Android | App internal storage |

`charmap.json` and `glossary.json` are stored next to the executable and can be edited manually.

---

## Building from Source

### Requirements
- Python 3.11+
- PyQt6
- Nuitka (for `.exe`)
- PyInstaller (for Linux binary)
- Node.js + Capacitor (for APK)

### Windows / Linux
```bash
pip install pyqt6 nuitka
python -m nuitka --onefile --enable-plugin=pyqt6 RE49.py
```

### Android
```bash
npm install
npx cap sync
cd android && ./gradlew assembleDebug
```

---

## License

GPL v3 — Free to use, share, and modify. See [LICENSE](LICENSE) for details.

---

## Credits

Built by **Sifrado** for the Rise of Kingdoms community. 🏰
