# audio2anki — audio flashcards, no SRT, no API, no nothing.

![image](https://github.com/user-attachments/assets/e7667553-a3d5-4734-83fa-875410bd7f91)

**audio2anki** turns any audio file or YouTube URL into an Anki flashcard deck (`.apkg`) where each card pairs a short audio clip with its transcript text. Nothing is sent to any cloud API — Whisper transcription and audio processing both run **entirely locally**. The only network call is the YouTube download itself.

Useful for language learners, podcast students, or anyone who wants to study audio alongside text.

## Install

You only need [`uv`](https://docs.astral.sh/uv/). Then:

```bash
uv tool install --with openai-whisper "audio2anki @ git+https://github.com/hiAndrewQuinn/audio2anki"
```

That's it. `audio2anki` is now on your `$PATH` from any directory and bundles **everything** it needs: `yt-dlp`, `openai-whisper`, plus auto-downloads of `ffmpeg`/`ffprobe` and a JavaScript runtime (`deno`) on first use. No system-level prereqs beyond `uv` itself.

Bundled binaries are preferred over any system installs of the same tools, so behavior stays consistent across machines.

### Windows

The same install command works. A few first-time gotchas:

- If `audio2anki` isn't recognized after install, run `uv tool update-shell` (or restart your shell) so `uv`'s tool directory ends up on `PATH`.
- First YouTube run downloads ~85 MB total (ffmpeg ~50 MB + deno ~35 MB) into `%LOCALAPPDATA%`. Windows Defender / SmartScreen occasionally flag fresh GitHub-release binaries — if a subprocess fails with a missing-file error right after install, allow the binary in your AV settings.
- Behind a corporate proxy, set `HTTPS_PROXY` before the first YouTube run so the Deno download can reach GitHub.

## Use

```bash
# YouTube URL — downloads audio, transcribes, builds deck
audio2anki "https://www.youtube.com/watch?v=fJ6ASXsx-nA"

# Local audio file — transcribes (if no .tsv exists), builds deck
audio2anki path/to/audio.mp3

# Local audio + existing Whisper TSV — just builds the deck
audio2anki path/to/audio.mp3 path/to/transcript.tsv
```

The `.apkg` lands in your current directory. Language is auto-detected, so you'll get Spanish subtitles for a Spanish clip, Finnish for a Finnish clip, etc.

![image](https://github.com/user-attachments/assets/6c5c7d77-dd03-4a76-ad55-36d5fb198861)

First-run downloads (cached afterward, all done automatically):

- Whisper model (~1.5 GB for the default `turbo` model)
- `ffmpeg` + `ffprobe` v8 (~50 MB, via `static-ffmpeg`)
- `deno` (~35 MB, only if you use a YouTube URL)

## GUI

There's also a small cross-platform desktop GUI installed alongside the CLI:

```bash
audio2anki-gui
```

The same `uv tool install` line gives you both `audio2anki` and `audio2anki-gui` — no separate install. The GUI is a thin wrapper that runs the CLI as a subprocess and streams its output into a log pane, so anything the CLI does, the GUI does.

Built with [Flet](https://flet.dev/), which bundles its own desktop runtime (`flet-desktop`) — no system Qt/GTK/etc. needed.

On Linux, the **Browse…** / **Choose…** buttons shell out to [Zenity](https://help.gnome.org/users/zenity/stable/) for the native file/folder picker. Install it once if you want those buttons to work (you can always paste paths into the text fields instead):

```bash
sudo apt install zenity   # Debian/Ubuntu
```

## Options

| Flag | What it does |
|---|---|
| `--whisper` | Force re-transcribing with Whisper, even if a `.tsv` already exists |
| `--whisper-model NAME` | Pick a Whisper model (default: `turbo`; options: `tiny`, `base`, `small`, `medium`, `large`, `turbo`) |
| `--deck-name NAME` | Override the auto-derived deck name |
| `--slow` / `--slower` / `--slowest` | Render audio at 0.75× / 0.5× / 0.25× (pitch preserved). The slower it gets, the more echo-ey it sounds — that's how time-stretching math works. |
| `--audio-dir PATH` | Where to save clip MP3s (default: `clips`) |
| `--transcripts-dir PATH` | Where to look for / save transcripts (default: `transcripts`) |
| `--output-apkg PATH` | Output filename (default: auto-derived from the audio filename) |
| `--youtube URL` | Explicit YouTube URL flag (positional URL works too) |
| `--cookies-from-browser BROWSER` | Pass cookies from a local browser to `yt-dlp` (e.g. `firefox`, `chrome`, `chromium`, `brave`, `edge`, `safari`). Use this when YouTube responds with "sign in to confirm you're not a bot". |
| `--cookies PATH` | Path to a Netscape-format `cookies.txt` file. Useful if your browser cookies aren't directly readable. |

## YouTube notes

YouTube uses a JavaScript "n-challenge" signature scheme that `yt-dlp` needs a JS runtime to solve. audio2anki **auto-downloads [Deno](https://deno.land/) on first YouTube use** (~35MB, cached at `~/.cache/audio2anki/deno`) so this just works — no manual install. If you already have `deno` on `$PATH`, that one is used instead.

Beyond that, audio2anki tries the default player client first and then falls back through `tv → ios → web_safari → android_vr → mweb` if YouTube has broken the default extraction path for that client.

For age-gated, subscription, or bot-checked videos, pass cookies to `yt-dlp` with one of:

```bash
audio2anki --cookies-from-browser firefox 'https://www.youtube.com/watch?v=...'
audio2anki --cookies ./cookies.txt        'https://www.youtube.com/watch?v=...'
```

The Flet GUI (`audio2anki-gui`) exposes the same control as a "Cookies (for YouTube auth)" dropdown with browser shortcuts and a `cookies.txt` file picker. Setting `BROWSER=firefox` in a `.env` file still works as a fallback if you prefer env-var config.

### When `--cookies-from-browser` doesn't work

`--cookies-from-browser` reads the browser's cookie database directly, which has surprisingly many failure modes — especially on Linux, where Chrome's auth cookies are encrypted with a key in the OS keyring. If you see `Sign in to confirm you're not a bot` even after passing cookies, check the log for warnings like `cannot decrypt v11 cookies: no key found` or `Extracted 204 cookies (2110 could not be decrypted)`. That means yt-dlp got the cookie file but couldn't read the auth cookies — it's a keyring/lock issue, not a missing-cookies one.

Things to try, in order:

1. **Quit the browser fully** and rerun. yt-dlp can't always read the cookie database while the browser holds it open.
2. **Make sure your keyring is unlocked.** On Linux, `gnome-keyring` or `kwallet` needs to be unlocked in your current login session. Logging out and back in often fixes it.
3. **Confirm you're actually signed in.** Open YouTube in the browser and confirm you see your avatar in the top right.
4. **Try the other major browser.** If `chrome` fails, try `firefox` (or vice-versa).
5. **Bypass the keyring entirely with the bundled extractor** — covered next.

### `audio2anki-extract-cookies firefox`

Bundled alongside the CLI is a small stdlib-only cookie extractor for **Firefox specifically**:

```bash
audio2anki-extract-cookies firefox -o cookies.txt
audio2anki --cookies cookies.txt 'https://www.youtube.com/watch?v=...'
```

By default it pulls only `youtube.com`/`google.com`/`googlevideo.com` cookies (pass `--all-domains` to export everything). Crucially, it **reports whether it actually found YouTube auth cookies** (`SID`, `SAPISID`, `HSID`, `LOGIN_INFO`, etc.) — if it didn't, you aren't signed in to YouTube in Firefox and it tells you so directly.

Why Firefox-only: Firefox stores cookies in a plain SQLite database, so this command needs nothing beyond the Python stdlib and has no extra supply-chain surface. Chrome-family browsers encrypt cookie values with a key in the OS keychain; replicating that path would just duplicate (and shift the trust burden of) what `yt-dlp --cookies-from-browser chrome` already does.

If you don't have or use Firefox, export `cookies.txt` from your browser of choice with an extension like [cookies.txt LOCALLY](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt-one-click/) and pass the resulting file via `--cookies`.

## Develop

```bash
git clone https://github.com/hiAndrewQuinn/audio2anki
cd audio2anki
uv sync --extra whisper
uv run audio2anki "https://www.youtube.com/watch?v=fJ6ASXsx-nA"
```

## License

[Unlicense](LICENSE). Do whatever you want with it.
