"""Flet desktop GUI for audio2anki.

Shells out to the `audio2anki` CLI as a subprocess and streams its output
into a log widget. Keeps cli.py untouched — no shared in-process state.
"""

import os
import platform
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import flet as ft


WHISPER_MODELS = ["tiny", "base", "small", "medium", "large", "turbo"]
SPEEDS = [
    ("Normal (1x)", None),
    ("Slow (0.75x)", "--slow"),
    ("Slower (0.5x)", "--slower"),
    ("Slowest (0.25x)", "--slowest"),
]
DEFAULT_OUTPUT_DIR = Path.home() / "audio2anki-output"


def _resolve_audio2anki():
    """Find the `audio2anki` CLI executable installed alongside this GUI."""
    venv_bin = os.path.dirname(sys.executable)
    suffix = ".exe" if platform.system().lower() == "windows" else ""
    candidate = os.path.join(venv_bin, "audio2anki" + suffix)
    if os.path.exists(candidate):
        return candidate
    return shutil.which("audio2anki")


def _open_in_file_manager(path):
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    elif sys.platform == "win32":
        os.startfile(str(path))  # noqa: SIM115
    else:
        subprocess.Popen(["xdg-open", str(path)])


def main(page=None):
    if page is None:
        ft.app(main)
        return

    page.title = "audio2anki"
    page.window.width = 720
    page.window.height = 720
    page.padding = 20

    state = {"proc": None, "thread": None, "output_dir": DEFAULT_OUTPUT_DIR}

    source_input = ft.TextField(
        label="Audio file path or YouTube URL",
        hint_text="https://www.youtube.com/watch?v=... or /path/to/audio.mp3",
        expand=True,
    )

    file_picker = ft.FilePicker()
    folder_picker = ft.FilePicker()
    page.overlay.extend([file_picker, folder_picker])

    def on_browse_file(e):
        files = file_picker.pick_files(allow_multiple=False)
        if files:
            source_input.value = files[0].path
            page.update()

    browse_btn = ft.ElevatedButton("Browse…", on_click=on_browse_file)

    model_dd = ft.Dropdown(
        label="Whisper model",
        value="turbo",
        options=[ft.dropdown.Option(m) for m in WHISPER_MODELS],
        width=200,
    )
    speed_dd = ft.Dropdown(
        label="Speed",
        value="Normal (1x)",
        options=[ft.dropdown.Option(label) for label, _ in SPEEDS],
        width=200,
    )

    deck_name_input = ft.TextField(label="Deck name (optional)", expand=True)

    output_dir_input = ft.TextField(
        label="Output folder",
        value=str(DEFAULT_OUTPUT_DIR),
        expand=True,
    )
    def on_browse_folder(e):
        path = folder_picker.get_directory_path()
        if path:
            output_dir_input.value = path
            state["output_dir"] = Path(path)
            page.update()

    choose_folder_btn = ft.ElevatedButton("Choose…", on_click=on_browse_folder)

    run_btn = ft.FilledButton("Run", icon=ft.Icons.PLAY_ARROW)
    cancel_btn = ft.OutlinedButton("Cancel", icon=ft.Icons.STOP, disabled=True)
    spinner = ft.ProgressRing(width=20, height=20, visible=False)
    status_text = ft.Text("Idle", color=ft.Colors.GREY)

    log_view = ft.ListView(expand=True, spacing=2, auto_scroll=True, padding=10)
    log_container = ft.Container(
        content=log_view,
        bgcolor=ft.Colors.BLACK12,
        border_radius=6,
        expand=True,
    )

    open_folder_btn = ft.TextButton(
        "Open output folder",
        icon=ft.Icons.FOLDER_OPEN,
        visible=False,
        on_click=lambda e: _open_in_file_manager(state["output_dir"]),
    )

    def append_log(line):
        log_view.controls.append(ft.Text(line, font_family="monospace", size=12, selectable=True))
        if len(log_view.controls) > 2000:
            del log_view.controls[:1000]
        page.update()

    def set_running(running):
        run_btn.disabled = running
        cancel_btn.disabled = not running
        spinner.visible = running
        if running:
            status_text.value = "Running…"
            status_text.color = ft.Colors.BLUE
            open_folder_btn.visible = False
        page.update()

    def on_run(e):
        cli = _resolve_audio2anki()
        if not cli:
            append_log("ERROR: could not locate the `audio2anki` executable. Is it installed on PATH?")
            return

        source = source_input.value.strip() if source_input.value else ""
        if not source:
            append_log("ERROR: enter an audio file path or YouTube URL first.")
            return

        out_dir = Path(output_dir_input.value).expanduser()
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as err:
            append_log(f"ERROR: could not create output folder {out_dir}: {err}")
            return
        state["output_dir"] = out_dir

        args = [cli, source]
        if model_dd.value and model_dd.value != "turbo":
            args += ["--whisper-model", model_dd.value]
        for label, flag in SPEEDS:
            if speed_dd.value == label and flag:
                args.append(flag)
        if deck_name_input.value and deck_name_input.value.strip():
            args += ["--deck-name", deck_name_input.value.strip()]

        log_view.controls.clear()
        append_log(f"$ {' '.join(args)}")
        append_log(f"  (cwd: {out_dir})")
        set_running(True)

        def worker():
            try:
                proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    text=True,
                    cwd=str(out_dir),
                )
                state["proc"] = proc
                for line in proc.stdout:
                    append_log(line.rstrip())
                rc = proc.wait()
                state["proc"] = None
                if rc == 0:
                    status_text.value = "Done"
                    status_text.color = ft.Colors.GREEN
                    open_folder_btn.visible = True
                else:
                    status_text.value = f"Failed (exit {rc})"
                    status_text.color = ft.Colors.RED
            except Exception as exc:
                append_log(f"ERROR: {exc}")
                status_text.value = "Failed"
                status_text.color = ft.Colors.RED
            finally:
                set_running(False)

        t = threading.Thread(target=worker, daemon=True)
        state["thread"] = t
        t.start()

    def on_cancel(e):
        proc = state.get("proc")
        if proc and proc.poll() is None:
            append_log("Cancelling…")
            proc.terminate()

    run_btn.on_click = on_run
    cancel_btn.on_click = on_cancel

    page.add(
        ft.Text("audio2anki", size=24, weight=ft.FontWeight.BOLD),
        ft.Row([source_input, browse_btn]),
        ft.Row([model_dd, speed_dd]),
        deck_name_input,
        ft.Row([output_dir_input, choose_folder_btn]),
        ft.Row([run_btn, cancel_btn, spinner, status_text]),
        ft.Container(content=log_container, expand=True, height=300),
        open_folder_btn,
    )


if __name__ == "__main__":
    main()
