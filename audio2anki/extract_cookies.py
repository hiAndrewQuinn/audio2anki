"""Extract YouTube auth cookies from a local Firefox profile to Netscape cookies.txt.

Firefox-only by design: its `cookies.sqlite` is a plain SQLite database, so we
can read it with the stdlib `sqlite3` module and zero extra dependencies. That
keeps the supply-chain surface minimal.

Chrome-family browsers encrypt their cookie values with a key kept in the OS
keychain (libsecret / Keychain / DPAPI), which would force us to pull in
`secretstorage` + `cryptography` and reimplement what yt-dlp's
`--cookies-from-browser` already does. Not worth the duplication or the extra
deps, so this command refuses anything but Firefox.
"""

import configparser
import os
import platform
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import click


# Hosts that count as "YouTube-related" for filtering and diagnostics.
YOUTUBE_HOSTS = (".youtube.com", ".google.com", ".googlevideo.com")

# Cookies YouTube actually checks when deciding whether you're a signed-in
# human. If none of these are present in the export, the cookies.txt file is
# useless for the bot-check workaround — we surface that to the user instead
# of letting them rerun audio2anki and fail again.
YOUTUBE_AUTH_COOKIE_NAMES = (
    "SID",
    "SSID",
    "HSID",
    "APISID",
    "SAPISID",
    "__Secure-1PSID",
    "__Secure-3PSID",
    "__Secure-1PAPISID",
    "__Secure-3PAPISID",
    "LOGIN_INFO",
)


def _firefox_profile_candidates():
    """Return likely Firefox profiles-dir locations, in priority order.

    We probe several because Linux distros ship Firefox via apt, snap, and
    flatpak, and each puts the profile somewhere different.
    """
    system = platform.system().lower()
    home = Path.home()
    if system == "darwin":
        return [home / "Library" / "Application Support" / "Firefox"]
    if system == "windows":
        appdata = os.getenv("APPDATA")
        return [Path(appdata) / "Mozilla" / "Firefox"] if appdata else []
    return [
        home / ".mozilla" / "firefox",
        home / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
        home / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",
    ]


def _select_profiles_dir():
    for candidate in _firefox_profile_candidates():
        if candidate.exists() and (candidate / "profiles.ini").exists():
            return candidate
    return None


def _select_profile(profiles_dir, requested_name=None):
    """Resolve a profile dir from profiles.ini, honoring --profile if given.

    Returns (profile_dir, available_names). `available_names` lets the caller
    print a helpful list when the requested name doesn't match.

    Modern Firefox tracks the per-install default profile in [Install...]
    sections (one per installation, e.g. firefox vs firefox-esr) — those win
    over the legacy [Profile*].Default=1 flag, which can point at a stale
    profile that was never actually opened. Order of preference:

      1. --profile NAME (exact match on the [Profile*].Name= field)
      2. The [Install*] section's Default= path (preferring the one whose
         path actually contains a cookies.sqlite — that's the live one)
      3. [Profile*].Default=1
      4. The only profile, if there's exactly one
    """
    cfg = configparser.ConfigParser()
    cfg.read(profiles_dir / "profiles.ini")

    profiles = []
    for section in cfg.sections():
        if not section.startswith("Profile"):
            continue
        name = cfg.get(section, "Name", fallback="")
        path = cfg.get(section, "Path", fallback="")
        is_relative = cfg.getboolean(section, "IsRelative", fallback=True)
        is_default = cfg.getboolean(section, "Default", fallback=False)
        if not path:
            continue
        full = (profiles_dir / path) if is_relative else Path(path)
        profiles.append({"name": name, "path": full, "default": is_default})

    available = [p["name"] for p in profiles if p["name"]]

    if requested_name:
        for p in profiles:
            if p["name"] == requested_name:
                return p["path"], available
        return None, available

    # Prefer [Install*] sections, picking one with a populated profile if
    # there's more than one Firefox install on the box (firefox + firefox-esr
    # is a common Debian setup).
    install_paths = []
    for section in cfg.sections():
        if not section.startswith("Install"):
            continue
        path = cfg.get(section, "Default", fallback="")
        if path:
            install_paths.append(profiles_dir / path)
    for p in install_paths:
        if (p / "cookies.sqlite").exists():
            return p, available
    if install_paths:
        return install_paths[0], available

    for p in profiles:
        if p["default"]:
            return p["path"], available

    if len(profiles) == 1:
        return profiles[0]["path"], available

    return None, available


def _read_cookies(cookies_db):
    """Return all rows from moz_cookies, working around Firefox's WAL lock.

    Firefox keeps the SQLite DB locked while running; copying the file to a
    temp dir and opening that copy read-only sidesteps the lock entirely.
    """
    with tempfile.TemporaryDirectory() as td:
        copy = Path(td) / "cookies.sqlite"
        shutil.copy2(cookies_db, copy)
        # Firefox uses WAL mode — copy the sidecar files too if present so
        # we don't miss recent writes.
        for suffix in ("-wal", "-shm"):
            sidecar = cookies_db.with_name(cookies_db.name + suffix)
            if sidecar.exists():
                shutil.copy2(sidecar, copy.with_name(copy.name + suffix))
        conn = sqlite3.connect(f"file:{copy}?mode=ro", uri=True)
        try:
            cursor = conn.execute(
                "SELECT host, path, isSecure, expiry, name, value, isHttpOnly "
                "FROM moz_cookies"
            )
            return list(cursor)
        finally:
            conn.close()


def _matches_filter(host, hosts_filter):
    if not hosts_filter:
        return True
    return any(host == h or host.endswith(h) for h in hosts_filter)


def _format_netscape(rows, hosts_filter):
    yield "# Netscape HTTP Cookie File\n"
    yield "# Generated by audio2anki-extract-cookies\n"
    yield "\n"
    for host, path, is_secure, expiry, name, value, is_http_only in rows:
        if not _matches_filter(host, hosts_filter):
            continue
        # The leading dot on host signals "this cookie applies to subdomains".
        # Firefox's host column already encodes that correctly; just mirror it.
        domain_specified = "TRUE" if host.startswith(".") else "FALSE"
        secure = "TRUE" if is_secure else "FALSE"
        expiry_int = int(expiry) if expiry else 0
        line_host = f"#HttpOnly_{host}" if is_http_only else host
        yield (
            f"{line_host}\t{domain_specified}\t{path}\t{secure}\t"
            f"{expiry_int}\t{name}\t{value}\n"
        )


@click.command()
@click.argument("browser", type=click.Choice(["firefox"], case_sensitive=False))
@click.option(
    "--profile",
    default=None,
    help="Firefox profile name (matches the Name= entry in profiles.ini). "
    "Defaults to the profile marked Default=1.",
)
@click.option(
    "-o",
    "--output",
    "output_path",
    default="cookies.txt",
    show_default=True,
    type=click.Path(dir_okay=False),
    help="Where to write the Netscape-format cookies file.",
)
@click.option(
    "--all-domains",
    is_flag=True,
    default=False,
    help="Export every cookie, not just YouTube/Google ones. Default is to "
    "export only youtube.com / google.com / googlevideo.com cookies.",
)
def main(browser, profile, output_path, all_domains):
    """Extract cookies from BROWSER (only `firefox` is supported) into a
    Netscape-format cookies.txt that you can pass to audio2anki via --cookies.

    Why Firefox-only: Firefox stores cookies in a plain SQLite database we can
    read with the stdlib. Chrome-family browsers encrypt their cookie values
    with a key in the OS keychain — yt-dlp already handles that path via
    --cookies-from-browser chrome, so this command does not duplicate it.
    """
    profiles_dir = _select_profiles_dir()
    if profiles_dir is None:
        candidates = _firefox_profile_candidates()
        click.echo("Error: Firefox profile directory not found.", err=True)
        click.echo("Looked in:", err=True)
        for c in candidates:
            click.echo(f"  {c}", err=True)
        click.echo(
            "Is Firefox installed and has it been opened at least once?", err=True
        )
        sys.exit(1)

    profile_dir, available = _select_profile(profiles_dir, profile)
    if profile_dir is None:
        if profile:
            click.echo(
                f"Error: no Firefox profile named {profile!r} found in "
                f"{profiles_dir / 'profiles.ini'}.",
                err=True,
            )
        else:
            click.echo(
                "Error: could not determine which Firefox profile to use "
                "(no profile is marked Default=1 and there is more than one).",
                err=True,
            )
        if available:
            click.echo("Available profiles:", err=True)
            for name in available:
                click.echo(f"  {name}", err=True)
            click.echo(
                "Pass --profile <name> to pick one explicitly.", err=True
            )
        sys.exit(1)

    cookies_db = profile_dir / "cookies.sqlite"
    if not cookies_db.exists():
        click.echo(
            f"Error: cookies.sqlite not found in profile {profile_dir}. "
            "Has Firefox ever been opened with this profile?",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Reading cookies from {cookies_db}")

    try:
        rows = _read_cookies(cookies_db)
    except (sqlite3.Error, OSError) as e:
        click.echo(f"Error reading cookies database: {e}", err=True)
        sys.exit(1)

    hosts_filter = None if all_domains else YOUTUBE_HOSTS
    output = "".join(_format_netscape(rows, hosts_filter))
    cookie_count = sum(
        1 for row in rows if _matches_filter(row[0], hosts_filter)
    )

    Path(output_path).write_text(output, encoding="utf-8")

    youtube_auth_found = sorted(
        {
            name
            for host, _path, _sec, _exp, name, _val, _http in rows
            if _matches_filter(host, YOUTUBE_HOSTS)
            and name in YOUTUBE_AUTH_COOKIE_NAMES
        }
    )

    click.echo(f"Wrote {cookie_count} cookies to {output_path}")

    if youtube_auth_found:
        click.echo(
            f"Found YouTube auth cookies: {', '.join(youtube_auth_found)}"
        )
        click.echo("")
        click.echo(
            f"Use with: audio2anki --cookies {output_path} <youtube-url>"
        )
        return

    click.echo("", err=True)
    click.echo(
        "Warning: no YouTube auth cookies (SID, SAPISID, HSID, LOGIN_INFO, "
        "etc.) were found in this Firefox profile.",
        err=True,
    )
    click.echo(
        "This usually means you aren't signed in to YouTube in Firefox.",
        err=True,
    )
    click.echo("", err=True)
    click.echo("To fix:", err=True)
    click.echo("  1. Open Firefox.", err=True)
    click.echo("  2. Go to https://www.youtube.com/ and sign in.", err=True)
    click.echo(
        "  3. Make sure you actually see your avatar in the top right "
        "(some accounts get redirected to a sign-in confirmation page "
        "that doesn't actually finish the login).",
        err=True,
    )
    click.echo(f"  4. Rerun: audio2anki-extract-cookies firefox -o {output_path}", err=True)
    sys.exit(2)


if __name__ == "__main__":
    main()
