<div align="right">
  <a href="README.md"><img src="https://img.shields.io/badge/Language-English-blue?style=for-the-badge&logo=readme&logoColor=white" alt="English"></a>
  <a href="README.pt-BR.md"><img src="https://img.shields.io/badge/Língua-Português-green?style=for-the-badge&logo=readme&logoColor=white" alt="Português"></a>
</div>

# LetrasBR - Real-time Synced Lyrics & Translation

[![Version](https://img.shields.io/badge/version-2.1.0-blue.svg?style=flat-square)](https://github.com/erickovisck/letras_br)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-3776AB.svg?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Android Version](https://img.shields.io/badge/android-API%2026%2B-3DDC84.svg?style=flat-square&logo=android&logoColor=white)](https://developer.android.com)
[![Extension Manifest](https://img.shields.io/badge/extension-Manifest%20V3-orange.svg?style=flat-square&logo=googlechrome&logoColor=white)](https://developer.chrome.com/docs/extensions/mv3/intro/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Download APK](https://img.shields.io/badge/Download%20APK-v2.1.0-brightgreen.svg?style=flat-square&logo=android)](https://github.com/erickovisck/letras_br/releases/latest)

> **A modern, lightweight ecosystem for real-time synchronized music lyrics and translation across YouTube Music and Spotify Web. Includes a customizable desktop floating overlay (always-on-top), a Chromium browser extension, a web Picture-in-Picture mode, and a native Android application.**

---

## Table of Contents

- [Switch Language](#-switch-language)
- [Key Features](#-key-features)
- [Supported Platforms & Ecosystem](#-supported-platforms--ecosystem)
- [Architecture & Workflow](#-architecture--workflow)
- [Browser Extension Installation](#-browser-extension-installation)
  - [1. Chrome, Brave & Edge Setup](#1-chrome-brave--microsoft-edge-setup)
  - [2. Verifying and Using the Extension](#2-verifying-and-using-the-extension)
- [Desktop Server & Overlay Setup](#-desktop-server--overlay-setup)
  - [1. Prerequisites](#1-prerequisites)
  - [2. Quickstart (Windows)](#2-quickstart-windows)
  - [3. Manual Setup & CLI Options](#3-manual-setup--cli-options)
- [Android App & APK Download](#-android-app--apk-download)
  - [1. APK Installation](#1-apk-installation-ready-to-use)
  - [2. Granting Permissions](#2-granting-permissions)
  - [3. Building from Source](#3-building-from-source)
- [Mobile Web & Picture-in-Picture (PiP)](#-mobile-web--picture-in-picture-pip)
- [Configuration & Settings](#-configuration--settings)
- [Troubleshooting & FAQ](#-troubleshooting--faq)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License & Author](#-license--author)

---

## 🌐 Switch Language

- 🇺🇸 **English:** Current version
- 🇧🇷 **Português:** [Clique aqui para ler a versão em Português](README.pt-BR.md)

---

## ✨ Key Features

- **Real-time Sub-second Synchronization:** Intelligently aligns time-stamped lyrics directly with the audio stream of YouTube Music and Spotify Web.
- **Multilingual Real-time Translations:** Instant line-by-line translations for Portuguese (PT-BR), English (EN), Spanish (ES), and French (FR).
- **Desktop Floating Overlay (Always-On-Top):** Minimalist, draggable, transparent Tkinter-based HUD window with customizable opacity, font size, and color themes.
- **Chromium Browser Extension (Manifest V3):** Automatically extracts metadata and timestamps from active tabs without requiring web account credentials.
- **Native Android App (Kotlin):** Background service using `MediaSessionManager` and `NotificationListenerService` with a floating draggable overlay over any Android app.
- **Mobile Picture-in-Picture (PiP) Player:** Native browser PiP canvas video generator for floating lyrics on devices where native overlays aren't possible.
- **Integrated Media Player Controls:** Pause, play, and skip songs directly from the desktop or mobile floating overlay.
- **1-Click Launch Protocol:** Windows custom protocol (`letrasbr://`) to start the desktop server and overlay straight from browser buttons.

---

## 📱 Supported Platforms & Ecosystem

| Component | Platform / Tech | Description | Status |
| :--- | :--- | :--- | :---: |
| **Browser Extension** | Chromium (Chrome, Brave, Edge, Opera) | MV3 content script detecting playback on YouTube Music & Spotify | ✅ Available |
| **Desktop Server & Overlay** | Python 3.10+ / FastAPI / Tkinter | Local API on `localhost:8000` + Floating HUD overlay | ✅ Available |
| **Native Android App** | Android 8.0+ (Kotlin) | Background media listener + System Alert floating window | ✅ APK Available |
| **Mobile Web Overlay** | HTML5 Canvas / PiP Video | Responsive web player with Picture-in-Picture subtitles | ✅ Available |

---

## 🏗 Architecture & Workflow

```text
  +-------------------------------------------------------------+
  |                   Music Source in Browser                   |
  |             (music.youtube.com / open.spotify.com)          |
  +-------------------------------------------------------------+
                                 |
                                 | (DOM playback time & track metadata)
                                 v
  +-------------------------------------------------------------+
  |              LetrasBR Browser Extension (MV3)               |
  |     - content.js / spotify_content.js                       |
  |     - background.js (proxy & heartbeat)                     |
  +-------------------------------------------------------------+
                                 |
                                 | HTTP POST /sync (title, artist, position, is_paused)
                                 v
  +-------------------------------------------------------------+
  |              LetrasBR Python Core API (FastAPI)             |
  |                     (http://localhost:8000)                 |
  +-------------------------------------------------------------+
            |                                       |
            | (Scrapes & Aligns Lyrics)             | (Broadcasting state)
            v                                       v
  +--------------------+         +--------------------------------------+
  | Providers / Scraper|         | Desktop Floating Overlay (Tkinter)   |
  | - Letras.mus.br    |         | - Draggable HUD, Click-through       |
  | - YtMusicApi Sync  |         | - Media Controls (Play/Pause, Skip)  |
  +--------------------+         +--------------------------------------+
                                                    ^
                                                    | (HTTP polling / sync)
                                 +--------------------------------------+
                                 | Native Android App / Mobile Web PiP  |
                                 | - Floating Window (SYSTEM_ALERT)     |
                                 +--------------------------------------+
```

---

## 📦 Browser Extension Installation

The extension allows YouTube Music and Spotify Web to communicate current playback time and song info with the local sync engine.

### 1. Chrome, Brave & Microsoft Edge Setup

1. **Download or Clone this Repository:**
   ```bash
   git clone https://github.com/erickovisck/letras_br.git
   ```
   *(Or download the ZIP file from GitHub and extract it to your machine).*

2. **Open the Extensions Page in your browser:**
   - **Google Chrome:** Navigate to `chrome://extensions`
   - **Brave Browser:** Navigate to `brave://extensions`
   - **Microsoft Edge:** Navigate to `edge://extensions`
   - **Opera / Opera GX:** Navigate to `opera://extensions`

3. **Enable Developer Mode:**
   - Look for the **Developer mode** (*Modo do desenvolvedor*) toggle switch, usually located in the top-right corner, and turn it **ON**.

4. **Load Unpacked Extension:**
   - Click on the **"Load unpacked"** (*Carregar sem compactação*) button in the top-left toolbar.
   - In the file picker dialog, navigate to the cloned folder and select the **`extension`** directory:
     ```text
     letras_br/
     ├── android/
     ├── extension/   <--- SELECT THIS FOLDER
     │   ├── manifest.json
     │   ├── background.js
     │   ├── content.js
     │   └── spotify_content.js
     ├── letrasbr_api/
     ...
     ```

5. **Confirmation:**
   - The extension **LetrasBR Tradutor - YouTube Music & Spotify** will now appear in your list of installed extensions with version `2.0.0+`.

---

### 2. Verifying and Using the Extension

1. Ensure the desktop server is running (see [Desktop Server Setup](#-desktop-server--overlay-setup)).
2. Open [YouTube Music](https://music.youtube.com) or [Spotify Web](https://open.spotify.com).
3. In the bottom-right corner of the player, a floating status badge `⚙️` will appear.
4. Play any track: the extension will detect song changes and sync lyrics automatically!

---

## 🖥️ Desktop Server & Overlay Setup

The desktop server powers the lyrics alignment engine, fetches translations, and displays the transparent floating overlay.

### 1. Prerequisites & Dependencies

- Python 3.10 or higher installed with Tkinter support:
  ```bash
  python --version
  ```
- **[ytmusicapi](https://github.com/sigma67/ytmusicapi)** ([PyPI](https://pypi.org/project/ytmusicapi/)): The official Python client used by the backend to query YouTube Music's internal endpoints for time-stamped lyrics.

### 2. Quickstart (Windows)

You have two ready-to-use scripts in the root directory:

- **`configurar_ambiente.bat`**: Runs the complete initial configuration (validates Python, creates `.venv`, installs `requirements.txt`, and registers Windows protocol).
- **`iniciar_servidor.bat`**: Starts the server and overlay. **Self-healing:** If the virtual environment or dependencies are not loaded, it automatically configures them before launching!

```cmd
# Simply double-click:
iniciar_servidor.bat
```

### 3. Manual Setup & CLI Options

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate       # On Windows
# source .venv/bin/activate  # On Linux/macOS

# 2. Install dependencies (including ytmusicapi)
pip install -r letrasbr_api/requirements.txt

# Alternatively, install ytmusicapi directly:
# pip install ytmusicapi

# 3. Register 1-click browser protocol (Windows only, optional)
python letrasbr_api/protocol.py

# 4. Start the server and overlay
python run_api.py
```

#### Headless Mode (Server Only)
If you only want the API without the desktop Tkinter overlay (e.g., when serving to an Android device on your local network):

```bash
python run_api.py --no-overlay
```

---

## 📱 Android App & APK Download

A native Kotlin Android application is provided to display synchronized lyrics directly over the official YouTube Music mobile app.

### 1. APK Installation (Ready to Use)

You can download the pre-compiled standalone APK directly from GitHub Releases:

[![Download APK](https://img.shields.io/badge/Download-Android%20APK%20(v2.1.0)-3DDC84?style=for-the-badge&logo=android&logoColor=white)](https://github.com/erickovisck/letras_br/releases/latest)

> 💡 *Note: If you are downloading the APK directly to your phone, enable "Install unknown apps" in your browser/file manager settings.*

### 2. Granting Permissions

To allow real-time background detection and the floating HUD:
1. Open **LetrasBR Tradutor** on your phone.
2. Grant **Notification / Media Listener Access** (to detect what is playing in YouTube Music).
3. Grant **Display Over Other Apps** permission (to draw the floating subtitle box).
4. Enter your computer's local IP address running the API (e.g. `http://192.168.1.15:8000`).
5. Tap **Test Connection**, switch on **Enable Floating Overlay**, and enjoy!

### 3. Building from Source

To compile the Android app manually:

```bash
cd android
./gradlew assembleDebug
```
The compiled APK will be generated at:
`android/app/build/outputs/apk/debug/app-debug.apk`.

---

## 📱 Mobile Web & Picture-in-Picture (PiP)

If you are on iOS or prefer not to install the native Android app:

1. Connect your phone to the same Wi-Fi network as your PC.
2. Open your mobile browser and access:
   ```text
   http://<YOUR-PC-IP>:8000/mobile
   ```
3. Tap the **📺 PiP** button to launch a native Picture-in-Picture floating subtitle window over any app!

---

## ⚙️ Configuration & Settings

Settings can be toggled in real-time through the desktop overlay gear icon `⚙️` or via the web extension:

- **Languages:** Portuguese (`pt`), English (`en`), Spanish (`es`), French (`fr`).
- **Display Modes:** 
  - `both`: Original line + Translated line.
  - `translation`: Translated line only.
  - `original`: Original lyric only.
- **Visuals:** Window opacity slider, font size adjustment, dark theme presets.

---

## ❓ Troubleshooting & FAQ

<details>
<summary><strong>1. The extension says "Offline" or fails to connect</strong></summary>
Make sure the desktop server is running by executing <code>python run_api.py</code> or double-clicking <code>iniciar_servidor.bat</code>. Verify that <a href="http://localhost:8000/">http://localhost:8000/</a> responds in your browser.
</details>

<details>
<summary><strong>2. Floating overlay is not displaying on top of games/fullscreen video</strong></summary>
Ensure the target game/player is in <em>Borderless Windowed</em> mode rather than Exclusive Fullscreen, which restricts Windows topmost overlay windows.
</details>

<details>
<summary><strong>3. Android app cannot connect to the server</strong></summary>
Ensure both your Android phone and PC are connected to the exact same Wi-Fi network. Check your Windows Firewall to verify port <code>8000</code> is not blocked for incoming local connections.
</details>

---

## 🗺 Roadmap

- [ ] Chrome Web Store official release.
- [ ] Apple Music Web integration.
- [ ] Offline lyrics caching with SQLite.
- [ ] Synchronized word-by-word karaoke highlighting.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes in Portuguese (`git commit -m 'feat: adiciona suporte ao Apple Music'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

---

## 📄 License & Author

Distributed under the **MIT License**. See `LICENSE` for more information.

**Author:** [Erick Fernando Martins Santos](https://github.com/erickovisck)  
**GitHub:** [@erickovisck](https://github.com/erickovisck)  
**Email:** `erickmartinslima3@gmail.com`
