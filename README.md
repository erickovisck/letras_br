<div align="right">
  <a href="README.md"><img src="https://img.shields.io/badge/Language-English-blue?style=for-the-badge&logo=readme&logoColor=white" alt="English"></a>
  <a href="README.pt-BR.md"><img src="https://img.shields.io/badge/Língua-Português-green?style=for-the-badge&logo=readme&logoColor=white" alt="Português"></a>
</div>

# LetrasBR - Real-time Synced Lyrics & Translation

[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg?style=flat-square)](https://github.com/erickovisck/letras_br)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-PySide6%20(Qt6)-41CD52.svg?style=flat-square&logo=qt&logoColor=white)](https://www.qt.io/)
[![Windows Media](https://img.shields.io/badge/Windows-GSMTC%20Native-0078D6.svg?style=flat-square&logo=windows&logoColor=white)](https://learn.microsoft.com)
[![Android Version](https://img.shields.io/badge/android-API%2026%2B-3DDC84.svg?style=flat-square&logo=android&logoColor=white)](https://developer.android.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Download APK](https://img.shields.io/badge/Download%20APK-v2.1.0-brightgreen.svg?style=flat-square&logo=android)](https://github.com/erickovisck/letras_br/releases/latest)

> **A modern, complete ecosystem for real-time synchronized music lyrics and translations. Now 100% native desktop on Windows with PySide6 (Qt 6) and direct Windows Media Controls (GSMTC) integration — seamlessly detects YouTube Music, Spotify, and browser media players without needing browser extensions!**

---

## Table of Contents

- [Switch Language](#-switch-language)
- [Key Features](#-key-features)
- [Supported Platforms](#-supported-platforms)
- [Project Directory Structure](#-project-directory-structure)
- [Desktop Quickstart (Windows)](#-desktop-quickstart-windows)
  - [1. LetrasBR.exe Executable & Windows Search](#1-letrasbrexe-executable--windows-search)
  - [2. Starting via Batch Script (.bat)](#2-starting-via-batch-script-bat)
  - [3. How the Native Executable (.exe) Works](#3-how-the-native-executable-exe-works)
- [Visual Interface & Customization](#-visual-interface--customization)
- [Android Application & APK Download](#-android-application--apk-download)
- [Mobile Web & Picture-in-Picture (PiP)](#-mobile-web--picture-in-picture-pip)
- [Web Extension (Legacy / Optional)](#-web-extension-legacy--optional)
- [Troubleshooting & FAQ](#-troubleshooting--faq)
- [License & Author](#-license--author)

---

## 🌐 Switch Language

- 🇺🇸 **English:** Current version
- 🇧🇷 **Português:** [Clique aqui para ler a versão em Português](README.pt-BR.md)

---

## ✨ Key Features

- **100% Native Desktop (Windows GSMTC):** Monitors YouTube Music (in any browser such as Chrome, Edge, Brave, etc.), Spotify desktop app, and system players directly via the Windows OS API, eliminating extension reliance.
- **Native Integrated Executable (`LetrasBR.exe`):** Silent Win32 launcher (no black CMD terminal window) with embedded icon and indexed in the Windows Start Menu — just press `Win` and type `LetrasBR`.
- **3D Perspective Verse Animation (Instagram Stories Style):** The previous verse shrinks and moves back/up in 3D perspective while the new verse smoothly transitions from the background to the foreground at 60 FPS using pure `QPainter` with no opaque artifacts.
- **Miniplayer with Timeline Seek Slider:** ⏮, ⏯, ⏭ buttons and an interactive timeline seek slider to scrub forward or backward directly from the overlay, with real-time timestamp display (`01:23 / 03:45`).
- **Freeform Resize Grip (`⇲`):** Located at the bottom-right corner with a diagonal resize cursor to adjust width and height simultaneously.
- **Comprehensive Settings Menu (`⚙️`):**
  - Background color picker with alpha/opacity slider.
  - Independent color pickers for original lyrics and translations.
  - Complete typography selection with `QFontComboBox` (all installed system fonts).
  - Divided ergonomic font size adjustment: dedicated `[−]` and `[+]` buttons and precision slider (10pt to 36pt).
  - Bold and Italic toggles.
  - Display modes: Both, Translation Only, or Original Only.
  - Server URL configuration to connect to remote servers on local network or cloud.
- **Smart Autoplay & Fast Track-Switching Handling:** Instant visual status feedback (*"Carregando tradução..."*), atomic request cancellation to prevent stale lyric overlap, and advanced YouTube title cleaning (`(Official Video)`, `(Clip Oficial)`, `[Visualizer]`, etc.).
- **System Tray Integration:** Taskbar notification area icon with context menu to toggle overlay visibility, control playback, or exit.
- **Multilingual Translations:** Instant line-by-line translations for Portuguese (PT-BR), English (EN), Spanish (ES), and French (FR).

---

## 📱 Supported Platforms

| Component | Platform / Tech | Description | Status |
| :--- | :--- | :--- | :---: |
| **Main Desktop App** | Windows 10/11 (PySide6 / WinRT GSMTC) | Executable `LetrasBR.exe`, translucent overlay, native capture | ✅ Available (v3.0) |
| **Decoupled API Server** | Python 3.10+ / FastAPI | Local or remote backend for lyric scraping and alignment | ✅ Available |
| **Native Android App** | Android 8.0+ (Kotlin) | Native media listener + Floating HUD overlay (`SYSTEM_ALERT`) | ✅ APK Available |
| **Web Extension (Optional)** | Chromium (Chrome, Brave, Edge, Opera) | MV3 content script for browsers (kept in `extension/`) | ✅ Legacy/Optional |

---

## 📁 Project Directory Structure

The project is cleanly and modularly organized:

```text
TRADUTOR YT MUSIC/
├── LetrasBR.exe              # Main launcher executable (root folder)
├── run_api.py                # Python entry point (PySide6 GUI + FastAPI server)
├── configurar_ambiente.bat   # Environment setup and .venv creator (Python >= 3.10)
├── iniciar_servidor.bat      # Batch script for quick terminal launch
│
├── assets/                   # Application icons and branding
│   ├── app_icon.ico          # Native Windows icon (used for .exe and system tray)
│   └── app_icon.png          # High-resolution PNG icon
│
├── config/                   # User configuration files
│   └── overlay_config.json   # Colors, fonts, opacity, coordinates, and window dimensions
│
├── scripts/                  # Build and Windows registration utilities
│   ├── Launcher.cs           # C# source code for silent Win32 launcher
│   ├── build_exe.bat         # Compiles LetrasBR.exe using native .NET csc.exe
│   ├── registrar_menu_iniciar.bat # Registers Start Menu shortcut for Windows Search
│   └── registrar_protocolo.bat    # Registers letrasbr:// URL protocol in Windows Registry
│
├── letrasbr_api/             # Core backend and graphical interface modules
│   ├── overlay_qt.py         # PySide6 GUI (HUD overlay, 3D verse animation, controls)
│   ├── media_monitor.py      # Native Windows Media Monitor (WinRT GSMTC)
│   ├── lyrics_client.py      # Async lyrics worker with request cancellation
│   ├── scraper.py            # letras.mus.br lyrics and translation scraper
│   ├── aligner.py            # Verse-by-verse temporal alignment engine
│   ├── config.py             # Configuration file manager
│   ├── main.py               # REST API endpoints (FastAPI)
│   └── requirements.txt      # Python dependencies (PySide6, winrt, fastapi, etc.)
│
├── android/                  # Native Kotlin Android application
└── extension/                # Chromium Manifest V3 Web Extension (legacy/optional)
```

---

## 🚀 Desktop Quickstart (Windows)

### Prerequisites
- **Windows 10 or 11** (64-bit)
- **Python 3.10 or higher** installed and on PATH ([Download Python](https://www.python.org/downloads/)).

### 1. `LetrasBR.exe` Executable & Windows Search

`LetrasBR.exe` is located at the root of the project directory.

1. **Initial Environment Setup:**
   - Run `configurar_ambiente.bat`. It checks Python version compatibility, sets up `.venv`, installs requirements, and registers the Windows Start Menu shortcut.
2. **Open via Windows Start Menu:**
   - Press the `Win` key on your keyboard, type **`LetrasBR`**, and hit **Enter**.
3. **Direct Launch:**
   - Double-click `LetrasBR.exe`. The app starts completely silently without opening command prompt windows.

### 2. Starting via Batch Script (.bat)

If you wish to view real-time log outputs or debug messages:
- Double-click `iniciar_servidor.bat`.

---

### 3. How the Native Executable (.exe) Works

`LetrasBR.exe` was designed to eliminate the typical black console window (`cmd.exe`) when launching Python applications on Windows.

#### The Process:
1. **C# Source Code (`scripts/Launcher.cs`):**
   - A Win32 application compiled as `WinExe` (GUI application with no console attached).
   - Locates `.venv\Scripts\pythonw.exe` in the application directory.
   - If `.venv` does not exist yet, it triggers `iniciar_servidor.bat` for automatic setup.
   - Spawns the Python process with `CreateNoWindow = true` and `UseShellExecute = false`.
2. **Native Windows Compiler (`csc.exe`):**
   - Requires no bulky external toolchains like Visual Studio or PyInstaller.
   - Uses the built-in Microsoft .NET Framework compiler present on every Windows 10/11 system at `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe`.
   - Embeds the project icon (`assets/app_icon.ico`) directly into the `.exe`.
3. **Recompiling:**
   - To recompile the executable at any time after modifications, simply run:
     ```cmd
     scripts\build_exe.bat
     ```

---

## 🎨 Visual Interface & Customization

The floating overlay can be fully personalized to match your desktop aesthetic:

- **Drag & Reposition:** Click and drag the dark top bar to place the overlay anywhere on your screens.
- **Freeform Resize:** Click and drag the `⇲` handle at the bottom right corner.
- **Scrub / Seek Audio:** Use the interactive progress slider in the top bar beside the media buttons.
- **Settings Menu (`⚙️`):**
  - Adjust background color and opacity/transparency in real time.
  - Choose independent colors for original and translated lyrics.
  - Select any installed font family and adjust font size using ergonomic `[−]` and `[+]` buttons or slider.
  - Toggle Bold and Italic styles.
- **System Tray:** Right-click the LetrasBR tray icon next to the Windows clock for quick media actions or to exit.

---

## 📱 Android Application & APK Download

A native Kotlin Android companion app displays floating lyrics over YouTube Music on mobile devices.

### 1. Download the APK

Grab the latest prebuilt APK from [Releases](https://github.com/erickovisck/letras_br/releases/latest):

[![Download APK](https://img.shields.io/badge/Download-APK%20Android%20(v2.1.0)-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://github.com/erickovisck/letras_br/releases/latest)

### 2. Required Permissions:
1. Grant **Notification Access / Media Session** permission.
2. Grant **Display over other apps** (Draw overlay) permission.
3. Enter your computer's local IP address (e.g. `http://192.168.1.15:8000`) and tap **Test Connection**.

---

## 📱 Mobile Web & Picture-in-Picture (PiP)

If you use iOS or prefer not to install the Android APK:

1. Connect your smartphone to the same Wi-Fi network as your PC.
2. In your mobile browser, navigate to:
   ```text
   http://<YOUR-PC-IP>:8000/mobile
   ```
3. Tap **📺 PiP** to launch floating synchronized subtitles in a native Picture-in-Picture window.

---

## 🧩 Web Extension (Legacy / Optional)

The Chromium extension (in `extension/`) remains available for direct in-browser injection:
1. Navigate to `chrome://extensions` (or `edge://extensions`, `brave://extensions`).
2. Enable **Developer mode**.
3. Click **Load unpacked** and select the `extension/` directory.

---

## ❓ Troubleshooting & FAQ

<details>
<summary><strong>1. LetrasBR is not detecting what is playing</strong></summary>
Ensure YouTube Music or Spotify is playing audio on Windows. Check if the Windows Media flyout appears when pressing volume keys on your keyboard with track information.
</details>

<details>
<summary><strong>2. LetrasBR.exe does not start</strong></summary>
Run <code>configurar_ambiente.bat</code> once to ensure the <code>.venv</code> virtual environment with Python >= 3.10 and all packages in <code>requirements.txt</code> have been installed.
</details>

<details>
<summary><strong>3. The overlay doesn't stay above full-screen games</strong></summary>
Set your game to <em>Borderless Windowed</em> mode, as Windows Exclusive Fullscreen blocks third-party overlay windows.
</details>

---

## 📄 License & Author

Distributed under the **MIT License**. See `LICENSE` for details.

**Author:** [Erick Fernando Martins Santos](https://github.com/erickovisck)  
**GitHub:** [@erickovisck](https://github.com/erickovisck)  
**Email:** `erickmartinslima3@gmail.com`
