# Theem-r

> **Visual theme builder for [EmuLnk](https://github.com/EmuLnk)-compatible emulators.**  
> Design HUD overlays, find live memory addresses, and export ready-to-install theme packages — all from a single HTML file, no install required.

<div align="center">

**[▶ Launch Theem-r in your browser](https://elbardacus.github.io/theem-r/)**

*No install · No login · Works offline after first load*

</div>

---

> 🤖 **AI-assisted project** — Theem-r was designed and built with the help of Claude (Anthropic).  
> The code, documentation, and tooling were developed collaboratively between a human developer and an AI pair-programmer.  
> Contributions, forks, and improvements from the community are very welcome.

---

## What is Theem-r?

EmuLnk lets you run a second-screen HUD on your phone while gaming — showing live stats like health, money, position, and anything else pulled from emulator memory in real time.

**Theem-r is the tool you use to build those HUDs.**

You drag widgets onto a phone-shaped canvas, wire them to live memory values discovered with the built-in scanner, and export a ZIP that drops straight into EmuLnk. No coding required for the basics. If you want to get into the weeds, everything is open and hackable.

---

## 🔍 Memory Scanner

The Memory Scanner is the core tool for finding the memory addresses that power your HUD. It connects directly to your running emulator and lets you search live RAM — the same technique cheat engines use.

**You don't need to know any addresses in advance.** Theem-r ships with a pre-loaded database of verified addresses for popular games. If your game is in the list, just click a row and the address is ready to pin.

For everything else, the interactive scan narrows down thousands of candidates to a single confirmed address in a few rounds.

### Setting up ADB (desktop connection)

ADB (Android Debug Bridge) is a free tool from Google that lets Theem-r talk to your emulator device over USB.

**Install ADB:**
- [Download Android Platform Tools](https://developer.android.com/tools/releases/platform-tools) (Windows / Mac / Linux — pick your platform)
- Extract the ZIP anywhere — no installer needed

**Connect your device:**
1. Enable **Developer Options** on your Android device (tap Build Number 7 times in Settings → About)
2. Enable **USB Debugging** inside Developer Options
3. Plug in via USB and run:
   ```bash
   adb devices
   ```
   Your device should appear in the list.

**Forward the scanner port:**
```bash
adb forward tcp:55356 tcp:55356
```

Then in Theem-r's Scanner tab, set IP to `127.0.0.1`, port `55356`, and hit **Test**. The green dot means you're live.

> **On-device shortcut:** If you open Theem-r directly in the browser on your Android device (not on a desktop), it auto-connects to `127.0.0.1:55356` on load — no ADB forwarding needed.

### Scanning workflow

1. Launch your game and get to a point where you know a specific value (e.g. you have exactly **85 HP**)
2. In the **Scanner tab**, enter `85` and hit **Scan** — Theem-r finds every RAM address currently holding that value
3. Take a hit in-game to change your HP, then enter the new value and **Re-scan** — this filters down the candidates
4. Repeat until you're down to one address (usually takes 2–4 rounds)
5. Hit **Pin** on the address — give it an ID (`health`) and a type (`u8`, `float`, etc.)
6. The pinned address is now a named **data point** that any widget on your canvas can bind to

### Known addresses

Popular games already have verified addresses in the built-in database. When your game ID resolves, a list of known addresses appears as one-click rows — click any row to read the live value immediately, no scanning needed. These cover things like health, money, position, wanted level, and more.

### Useful references for finding addresses

| Resource | What it's for |
|---|---|
| [RetroAchievements](https://retroachievements.org) | Community-sourced memory notes for thousands of games — enable in Advanced panel with a free API key |
| [GameTDB](https://www.gametdb.com/) | Game ID lookup for Wii, GameCube, DS, 3DS, Switch — Theem-r uses this automatically for Wii/GCN IDs |
| [PCSX2 GameIndex](https://github.com/PCSX2/pcsx2) | Verified PS1/PS2/PSP disc serials — used automatically, no setup |
| [GB Hardware DB (gekkio)](https://gbhwdb.gekkio.fi/cartridges/gb.html) | Physical ROM IDs for Game Boy / GBC cartridges (helpful when your ROM file name doesn't match expectations) |

---

## Quick Start

### Option A — Run it online (easiest)
**[Open Theem-r →](https://elbardacus.github.io/theem-r/)** — runs entirely in your browser, nothing to install.

### Option B — Run it locally
1. Download [`index.html`](index.html) from this repo
2. Open it in any modern browser (Chrome / Firefox / Edge)

### Then
3. Pick a console and type a Game ID in the right-side panel
4. Add widgets from the **Design** tab on the left
5. Use the **Scanner** tab to find and pin memory addresses
6. Click **Export ZIP** in the header when you're happy with the layout
7. Extract the ZIP into your EmuLnk themes folder on your Android device

---

## Features

### 🎨 Visual canvas editor
- 360 × 640 canvas matches EmuLnk's phone viewport exactly
- Drag, resize, and nudge widgets with your mouse or arrow key inputs
- Live preview updates as you edit properties

### 📦 Widget types
| Widget | What it shows |
|--------|--------------|
| **Bar** | Progress bar — great for HP, stamina, fuel |
| **Number** | Live numeric value with prefix / suffix |
| **Stars** | Star/pip display for things like wanted level |
| **Text** | Static label or flavour text |
| **Minimap** | 2D position dot on a world-space grid |
| **Image** | Boxart, banner, or any image URL |
| **Scanner** | Inline memory scanner widget inside the HUD |
| **Editor** | In-HUD value editor |

### 🕹️ Supported consoles
NES · SNES · N64 · Game Boy · Game Boy Color · Game Boy Advance · Nintendo DS · Nintendo 3DS · GameCube · Wii · PlayStation 1 · PlayStation 2 · PlayStation Portable · Sega Genesis / Mega Drive

### 🔎 Automatic game lookup
Type a Game ID and Theem-r tries to resolve it automatically across multiple databases — no setup required for most:

| ID format | Source | Requires |
|---|---|---|
| `SLUS-20946` (PS1/PS2/PSP disc serial) | [PCSX2 GameIndex](https://github.com/PCSX2/pcsx2) | Nothing |
| `RMCE01` / `GMSE01` (Wii / GameCube) | [GameTDB](https://www.gametdb.com/) | Nothing |
| Any title string | [RetroAchievements](https://retroachievements.org) | Free RA API key |

Once a game resolves you get its title, genre, and suggested scan fields filled in automatically.

### 🖼️ Zero-config game art
Box art, title screens, and gameplay screenshots are pulled from the public [libretro-thumbnails](https://github.com/libretro-thumbnails) repos — no account, no API key, no setup. Click any thumbnail to add it as an Image widget.

### 💾 Export in official format
The exported ZIP follows the [EmuLnk/emulnk-repo](https://github.com/EmuLnk/emulnk-repo) folder layout exactly:
```
themes/<CONSOLE>/<PROFILE>/<THEME_ID>/
  theme.json
  index.html
profiles/
  <PROFILE>.json      (if memory addresses were pinned)
README.txt
```
You can commit this directly into a fork of emulnk-repo and open a PR to share your theme with the community.

### 🧠 Optional power features
These require free API keys but add significant capability:

| Feature | Where to get a key |
|---|---|
| **RetroAchievements** — auto-scrapes memory addresses from community achievement data | [retroachievements.org](https://retroachievements.org) (free account) |
| **SteamGridDB** — hero images, banners, and logos | [steamgriddb.com](https://www.steamgriddb.com) (free account) |

Keys are saved locally in your browser (`localStorage`) and never transmitted anywhere except to those APIs directly.

---

## Installing a theme on your device

### Option A — ADB push (fastest for testing)
```bash
# Extract the ZIP first, then:
adb push themes/  /sdcard/emulink/themes/
adb push profiles/<PROFILE>.json  /sdcard/emulink/profiles/
```

### Option B — File manager
Copy the extracted folders to your device manually via USB or a file manager app, placing them at the paths above.

### Option C — Fork emulnk-repo
1. Fork [EmuLnk/emulnk-repo](https://github.com/EmuLnk/emulnk-repo)
2. Extract the ZIP into the root of your fork (folder layout matches perfectly)
3. Open a pull request to share your theme with all EmuLnk users

---

## Contributing

Theem-r is open source and forks / PRs are welcome.

**Good things to contribute:**
- Known memory addresses for more games (add to `KNOWN_ADDRS` in `index.html`)
- New genre hints in `GENRE_FIELD_HINTS`
- Additional game entries in `GAME_DB` with verified serials
- Bug fixes, UI polish, new widget types

If you build a theme for a specific game, consider submitting it to [EmuLnk/emulnk-repo](https://github.com/EmuLnk/emulnk-repo) directly.

---

## Technical details

<details>
<summary>Architecture</summary>

Theem-r is intentionally a **single self-contained HTML file** — no build step, no npm, no server. Open it in a browser and everything works, including offline. All logic, styles, and templates live in `index.html`.

**Key data structures:**

| Name | Purpose |
|---|---|
| `CONSOLE_MAP` | All supported consoles — RA system ID, libretro repo name, game ID format hint, serial regex, GameTDB flag |
| `GAME_DB` | Seed game library with verified serials / ROM IDs, genre, RA ID, libretro filename |
| `GAME_CACHE` | Runtime store for games resolved via online lookup (cleared on page reload) |
| `KNOWN_ADDRS` | Pre-confirmed memory addresses keyed by game ID |
| `GENRE_FIELD_HINTS` | Genre → suggested scan data points mapping |
| `PRESETS` | Built-in profiles matching the official emulnk-repo profiles |
| `WTYPES` | Widget type registry — label, icon, default size, default config |
| `state` | Single mutable object holding canvas widgets, active profile, and theme metadata |

</details>

<details>
<summary>Game lookup flow</summary>

When a Game ID is typed, `onGameId()` resolves it in four tiers:

1. **Local (`GAME_DB` / `GAME_CACHE`)** — instant, no network
2. **PCSX2 GameIndex** (`lookupDiscSerial`) — for `XXXX-NNNNN` disc serials (PS1/PS2/PSP).  
   Fetches `raw.githubusercontent.com/PCSX2/pcsx2/master/bin/resources/GameIndex.yaml` once per session, caches in `sessionStorage`, searches with `String.indexOf` + regex. Zero-config, no API key.
3. **GameTDB** (`lookupViaGameTDB`) — for 6-char Wii / GameCube IDs (e.g. `RMCE01`).  
   Fetches `gametdb.com/wiitdb.txt?GAMECUBE=1` once per session (~330 KB plain text), caches in `sessionStorage`, searches with `indexOf`. Zero-config, no API key.
4. **RetroAchievements** (`lookupViaRA`) — for any console when an RA key is saved.  
   Calls `API_SearchGamesList.php?search=QUERY&c=RA_SYSTEM_ID`, picks the result with the most achievements as the canonical match.

Results land in `GAME_CACHE` and trigger art fetch + genre hints + known address display.

</details>

<details>
<summary>Zero-config art (libretro-thumbnails)</summary>

Box art, title screens (`Titles`), and gameplay snaps (`Snaps`) come from the public [libretro-thumbnails](https://github.com/libretro-thumbnails) GitHub organisation.

URL pattern:
```
https://raw.githubusercontent.com/libretro-thumbnails/<CONSOLE_REPO>/master/Named_<KIND>/<FILENAME>.png
```

- `CONSOLE_REPO` comes from `CONSOLE_MAP[console].libretroRepo`
- `FILENAME` is the No-Intro/Redump canonical game name (stored as `libretroName` in `GAME_DB`, or inferred for online-resolved games)
- Broken images self-hide via `onerror` — no pre-flight requests needed

</details>

<details>
<summary>ZIP export format</summary>

The ZIP is built entirely in JavaScript using an inline STORE-method builder (no external library). It produces spec-compliant `.zip` files using `Uint8Array` + CRC32, working offline and from `file://` URLs.

Output structure mirrors [EmuLnk/emulnk-repo](https://github.com/EmuLnk/emulnk-repo):
```
themes/<console>/<profileId>/<themeId>/theme.json   ← EmuLnk theme manifest
themes/<console>/<profileId>/<themeId>/index.html   ← HUD WebView page
profiles/<profileId>.json                           ← memory profile (if pins exist)
README.txt
```

The generated `index.html` exposes a global `updateData(b64)` function that EmuLnk calls on every memory poll tick with a base64-encoded JSON payload:
```js
{
  isConnected: true,
  values: { "money": 75000, "health": 85.0, … },
  settings: { … }
}
```

</details>

<details>
<summary>Memory profile schema</summary>

Profile JSON follows the official [EmuLnk Profile Format](https://github.com/EmuLnk/emulnk-repo/wiki/Profile-Format):

```jsonc
{
  "id": "GTASA",
  "name": "GTA San Andreas",
  "platform": "PS2",
  "gameIds": ["SLUS-20946"],
  "bundles": {
    "money": { "base": { "SLUS-20946": "0xA2DA04" }, "pollRate": "high" }
  },
  "dataPoints": [
    { "id": "money", "description": "Cash on hand", "type": "u32_le",
      "size": 4, "bundle": "money", "offset": "0x0" }
  ]
}
```

Each pinned address in the Scanner tab becomes a bundle with `base = { gameId: address }` and a dataPoint at `offset: "0x0"`. This matches the multi-region addressing pattern supported by EmuLnk.

</details>

<details>
<summary>Theme manifest schema</summary>

`theme.json` follows the [EmuLnk Theme Format](https://github.com/EmuLnk/emulnk-repo/wiki/Theme-Format):

```jsonc
{
  "id": "MyHUD",
  "type": "theme",
  "targetProfileId": "GTASA",
  "targetConsole": "PS2",
  "meta": {
    "name": "My HUD",
    "author": "you",
    "version": "1.0.0",
    "description": "Custom HUD for GTA San Andreas",
    "minAppVersion": 1
  },
  "hideOverlay": false,
  "settings": [
    { "id": "show_minimap", "label": "Show Minimap", "type": "toggle", "default": "true" }
  ]
}
```

</details>

---

## License

MIT — see [LICENSE](LICENSE).  
Free to use, fork, modify, and distribute.  Credit appreciated but not required.

---

*Built with ❤️ and a lot of AI pair-programming.*  
*Theme format and profile schema © [EmuLnk](https://github.com/EmuLnk) — used with respect for their open specification.*
