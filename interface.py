from pathlib import Path
import threading
import time
import tkinter as tk
import os

import flet as ft

from main import (
    CODEC_PRESETS,
    DVD_TARGET_PRESETS,
    OUTPUT_FORMATS,
    QUALITY_PRESETS,
    RESOLUTION_PRESETS,
    VIDEO_EXTENSIONS,
    check_ffmpeg,
    check_dvdauthor,
    convert_video_queue,
    create_video_ts_from_selection,
)
from splash_screen import build_splash_container, run_startup_splash


def app_main(page: ft.Page):
    def rgba(hex_color: str, alpha: float) -> str:
        h = hex_color.lstrip("#")
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    try:
        root = tk.Tk()
        root.withdraw()
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        root.destroy()
    except Exception:
        screen_w, screen_h = 1280, 720

    target_w = int(screen_w * 0.35)
    target_h = int(screen_h * 0.70)
    target_left = max(0, (screen_w - target_w) // 2)
    target_top = max(0, (screen_h - target_h) // 2)

    page.title = "Conversor de Video"
    window_pos = {"left": target_left, "top": target_top}
    try:
        win = page.window
        win.width = target_w
        win.height = target_h
        if hasattr(win, "title_bar_hidden"):
            win.title_bar_hidden = True
        if hasattr(win, "frameless"):
            win.frameless = True
        if hasattr(win, "left"):
            win.left = target_left
        if hasattr(win, "top"):
            win.top = target_top
        win.min_width = target_w
        win.max_width = target_w
        win.min_height = target_h
        win.max_height = target_h
        win.resizable = False
        if hasattr(win, "maximizable"):
            win.maximizable = False
        if hasattr(win, "minimizable"):
            win.minimizable = False
            
    except Exception:
        page.window_width = target_w
        page.window_height = target_h
        if hasattr(page, "window_title_bar_hidden"):
            page.window_title_bar_hidden = True
        if hasattr(page, "window_frameless"):
            page.window_frameless = True
        if hasattr(page, "window_left"):
            page.window_left = target_left
        if hasattr(page, "window_top"):
            page.window_top = target_top
        page.window_min_width = target_w
        page.window_max_width = target_w
        page.window_min_height = target_h
        page.window_max_height = target_h
        page.window_resizable = False
        if hasattr(page, "window_maximizable"):
            page.window_maximizable = False
        if hasattr(page, "window_minimizable"):
            page.window_minimizable = False
    page.padding = 12
    page.scroll = ft.ScrollMode.AUTO
    page.theme_mode = ft.ThemeMode.LIGHT

    ffmpeg_ok = False
    dvdauthor_ok = False
    selected_output_dir: Path | None = None
    selected_videos: list[Path] = []

    title = ft.Text("CONVERSOR DE VIDEO", size=30, weight=ft.FontWeight.BOLD)
    subtitle = ft.Text(
        "Uma interface intuitiva e poderosa construída sobre o motor do FFmpeg, projetada para lidar com os codecs mais modernos da indústria (H.265, VP9 e AV1). Este conversor foca na preservação da fidelidade visual enquanto otimiza o armazenamento através de compressão inteligente.",
        size=12,
    )
    ffmpeg_status = ft.Text(
        "FFmpeg: verificando...",
        color=ft.Colors.AMBER,
        weight=ft.FontWeight.W_600,
    )
    dvdauthor_status = ft.Text(
        "dvdauthor: verificando...",
        color=ft.Colors.AMBER,
        weight=ft.FontWeight.W_600,
    )

    output_dir_text = ft.Text("Pasta de saida: mesma pasta de cada video.")
    queue_count_text = ft.Text("Fila: 0 video(s)")
    queue_view = ft.ListView(height=40, spacing=4, visible=False)
    remove_item_dropdown = ft.Dropdown(label="Item da fila", width=300, options=[])
    queue_action_btn_style = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=4))
    remove_item_button = ft.OutlinedButton("Remover item", style=queue_action_btn_style)
    clear_queue_button = ft.OutlinedButton("Limpar fila", style=queue_action_btn_style)
    clear_all_button = ft.OutlinedButton("Limpar tudo", style=queue_action_btn_style)

    format_dropdown = ft.Dropdown(
        label="Formato de saida",
        value="mp4",
        options=[ft.dropdown.Option(fmt) for fmt in OUTPUT_FORMATS],
        width=150,
    )
    codec_dropdown = ft.Dropdown(
        label="Codec de video",
        value="H.265 (HEVC)",
        options=[ft.dropdown.Option(name) for name in CODEC_PRESETS.keys()],
        width=150,
    )
    quality_dropdown = ft.Dropdown(
        label="Qualidade",
        value="Media (CRF 23)",
        options=[ft.dropdown.Option(name) for name in QUALITY_PRESETS.keys()],
        width=150,
    )
    resolution_dropdown = ft.Dropdown(
        label="Resolução",
        value="Original",
        options=[ft.dropdown.Option(name) for name in RESOLUTION_PRESETS.keys()],
        width=150,
    )
    dvd_profile_dropdown = ft.Dropdown(
        label="Perfil para disco DVD",
        value="Desativado",
        options=[ft.dropdown.Option(name) for name in DVD_TARGET_PRESETS.keys()],
        width=220,
    )

    progress = ft.ProgressBar(width=440, value=0)
    status_text = ft.Text("Aguardando ação.", selectable=True)
    cancel_event = threading.Event()
    add_videos_button = ft.IconButton(
        icon=ft.Icons.ADD,
        icon_size=22,
        tooltip="Adicionar videos",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=7)),
    )
    pick_output_button = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN,
        icon_size=22,
        tooltip="Escolher pasta de saida",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=7)),
    )
    clear_output_button = ft.IconButton(
        icon=ft.Icons.HOME,
        icon_size=22,
        tooltip="Usar pasta de cada video",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=7)),
    )
    convert_button = ft.IconButton(
        icon=ft.Icons.PLAY_ARROW,
        icon_size=22,
        tooltip="Converter fila",
        disabled=not ffmpeg_ok,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=7)),
    )
    cancel_button = ft.IconButton(
        icon=ft.Icons.CANCEL,
        icon_size=22,
        tooltip="Cancelar conversão",
        disabled=True,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=7)),
    )
    create_video_ts_button = ft.IconButton(
        icon=ft.Icons.SAVE,
        icon_size=22,
        tooltip="Criar VIDEO_TS",
        disabled=True,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=7)),
    )
    theme_button = ft.IconButton(
        icon=ft.Icons.DARK_MODE,
        icon_size=22,
        tooltip="Alternar tema Dark/Light",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=7)),
    )
    minimize_button = ft.IconButton(
        icon=ft.Icons.MINIMIZE,
        icon_size=22,
        tooltip="Minimizar janela",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=7)),
    )
    move_button = ft.IconButton(
        icon=ft.Icons.OPEN_WITH,
        icon_size=22,
        tooltip="Mover janela",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=7)),
    )
    close_button = ft.IconButton(
        icon=ft.Icons.CLOSE,
        icon_size=22,
        tooltip="Fechar programa",
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=7)),
    )
    splash_step_text = ft.Text("Recursos carregando...", size=14, weight=ft.FontWeight.W_600)

    def update_ui():
        page.update()

    def refresh_queue():
        queue_view.controls.clear()
        remove_item_dropdown.options = []
        for idx, video in enumerate(selected_videos, start=1):
            queue_view.controls.append(ft.Text(f"{idx}. {video}"))
            remove_item_dropdown.options.append(ft.dropdown.Option(str(idx), f"{idx}. {video.name}"))
        queue_view.visible = len(selected_videos) > 0
        if queue_view.visible:
            queue_view.height = min(130, max(40, len(selected_videos) * 24))
        if selected_videos:
            selected_value = remove_item_dropdown.value
            valid_values = {str(i) for i in range(1, len(selected_videos) + 1)}
            remove_item_dropdown.value = selected_value if selected_value in valid_values else "1"
        else:
            remove_item_dropdown.value = None
        queue_count_text.value = f"Fila: {len(selected_videos)} video(s)"
        update_ui()

    def set_status(message: str, progress_value: float | None = None, running: bool = False):
        status_text.value = message
        if progress_value is None and running:
            progress.value = None
        elif progress_value is not None:
            progress.value = progress_value
        convert_button.disabled = running or (not ffmpeg_ok)
        create_video_ts_button.disabled = running or (not dvdauthor_ok)
        cancel_button.disabled = not running
        update_ui()

    def set_window_position(left: int, top: int):
        window_pos["left"] = left
        window_pos["top"] = top
        try:
            if hasattr(page.window, "left"):
                page.window.left = left
            if hasattr(page.window, "top"):
                page.window.top = top
        except Exception:
            if hasattr(page, "window_left"):
                page.window_left = left
            if hasattr(page, "window_top"):
                page.window_top = top

    def apply_theme_styles():
        is_dark = page.theme_mode == ft.ThemeMode.DARK
        body_fg = "#FFFFFF" if is_dark else "#000000"
        header_bg = "#000000" if is_dark else "#FFFFFF"
        header_fg = "#FFFFFF" if is_dark else "#000000"
        hover = rgba(header_fg, 0.16)

        navbar.bgcolor = header_bg
        title.color = header_fg
        subtitle.color = header_fg
        output_dir_text.color = body_fg
        queue_count_text.color = body_fg
        status_text.color = body_fg

        for dd in [remove_item_dropdown, format_dropdown, codec_dropdown, quality_dropdown, resolution_dropdown, dvd_profile_dropdown]:
            dd.label_style = ft.TextStyle(color=body_fg)
            dd.text_style = ft.TextStyle(color=body_fg)
            dd.border_color = body_fg

        for btn in [
            add_videos_button,
            pick_output_button,
            clear_output_button,
            convert_button,
            cancel_button,
            create_video_ts_button,
            theme_button,
            minimize_button,
            move_button,
            close_button,
        ]:
            btn.icon_color = header_fg
            btn.style = ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=7),
                side=ft.BorderSide(1, header_fg),
                bgcolor={ft.ControlState.HOVERED: hover},
            )

    file_picker = ft.FilePicker()
    dir_picker = ft.FilePicker()
    page.services.extend([file_picker, dir_picker])

    async def pick_videos(_):
        files = await file_picker.pick_files(
            allow_multiple=True,
            allowed_extensions=[ext.replace(".", "") for ext in VIDEO_EXTENSIONS],
            dialog_title="Selecione um ou mais videos",
        )
        if not files:
            return
        for f in files:
            if not f.path:
                continue
            path = Path(f.path)
            if path.suffix.lower() in VIDEO_EXTENSIONS and path not in selected_videos:
                selected_videos.append(path)
        refresh_queue()

    def clear_queue(_):
        selected_videos.clear()
        refresh_queue()

    def clear_all(_):
        nonlocal selected_output_dir
        selected_videos.clear()
        selected_output_dir = None
        output_dir_text.value = "Pasta de saida: mesma pasta de cada video."
        format_dropdown.value = "mp4"
        codec_dropdown.value = "H.265 (HEVC)"
        quality_dropdown.value = "Media (CRF 23)"
        resolution_dropdown.value = "Original"
        dvd_profile_dropdown.value = "Desativado"
        progress.value = 0
        set_status("Tudo limpo.", progress_value=0, running=False)
        refresh_queue()

    def remove_selected_item(_):
        if not selected_videos:
            set_status("A fila esta vazia.", progress_value=0)
            return
        if not remove_item_dropdown.value:
            set_status("Selecione um item da fila para remover.", progress_value=0)
            return
        idx = int(remove_item_dropdown.value) - 1
        if idx < 0 or idx >= len(selected_videos):
            set_status("Item selecionado invalido.", progress_value=0)
            return
        removed = selected_videos.pop(idx)
        refresh_queue()
        set_status(f"Removido da fila: {removed.name}", progress_value=0)

    async def pick_output_dir(_):
        nonlocal selected_output_dir
        chosen_dir = await dir_picker.get_directory_path(dialog_title="Selecione a pasta de saida")
        if chosen_dir:
            selected_output_dir = Path(chosen_dir)
            output_dir_text.value = f"Pasta de saida: {selected_output_dir}"
        else:
            selected_output_dir = None
            output_dir_text.value = "Pasta de saida: mesma pasta de cada video."
        update_ui()

    def clear_output_dir(_):
        nonlocal selected_output_dir
        selected_output_dir = None
        output_dir_text.value = "Pasta de saida: mesma pasta de cada video."
        update_ui()

    def convert_worker():
        start_ts = time.monotonic()

        def format_seconds(seconds: float) -> str:
            sec = max(0, int(seconds))
            h = sec // 3600
            m = (sec % 3600) // 60
            s = sec % 60
            if h > 0:
                return f"{h:02d}:{m:02d}:{s:02d}"
            return f"{m:02d}:{s:02d}"

        def on_progress(
            message: str,
            progress_value: float | None,
            done: int | None,
            total: int | None,
        ):
            elapsed = time.monotonic() - start_ts
            status_with_time = f"{message}\nTempo decorrido: {format_seconds(elapsed)}"
            if done is not None and total and done > 0:
                avg_per_item = elapsed / done
                remaining_items = max(total - done, 0)
                eta_seconds = avg_per_item * remaining_items
                status_with_time += f" | Tempo restante: {format_seconds(eta_seconds)}"
            set_status(status_with_time, progress_value=progress_value, running=True)

        summary = convert_video_queue(
            selected_videos=selected_videos,
            selected_output_dir=selected_output_dir,
            output_format=format_dropdown.value or "mp4",
            codec_name=codec_dropdown.value or "H.265 (HEVC)",
            quality_name=quality_dropdown.value or "Media (CRF 23)",
            resolution_name=resolution_dropdown.value or "Original",
            dvd_profile_name=dvd_profile_dropdown.value or "Desativado",
            progress_callback=on_progress,
            cancel_check=cancel_event.is_set,
        )
        set_status(summary, progress_value=1 if selected_videos else 0, running=False)

    def start_conversion(_):
        if not ffmpeg_ok:
            set_status("Instale o FFmpeg e adicione ao PATH para converter.", progress_value=0)
            return
        if not selected_videos:
            set_status("Adicione videos na fila antes de converter.", progress_value=0)
            return
        cancel_event.clear()
        worker = threading.Thread(target=convert_worker, daemon=True)
        worker.start()

    def cancel_conversion(_):
        cancel_event.set()
        set_status("Cancelando conversao...", progress_value=None, running=True)

    def create_video_ts_worker():
        set_status("Gerando VIDEO_TS com dvdauthor...", running=True)
        ok, msg = create_video_ts_from_selection(
            selected_videos=selected_videos,
            selected_output_dir=selected_output_dir,
            dvd_profile_name=dvd_profile_dropdown.value or "DVD NTSC (720x480, 29.97fps)",
        )
        if ok:
            set_status(msg, progress_value=1, running=False)
        else:
            set_status(f"Falha no dvdauthor:\n{msg}", progress_value=0, running=False)

    def start_create_video_ts(_):
        if not dvdauthor_ok:
            set_status("Instale o dvdauthor e adicione ao PATH.", progress_value=0)
            return
        worker = threading.Thread(target=create_video_ts_worker, daemon=True)
        worker.start()

    def toggle_theme(_):
        if page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
            theme_button.icon = ft.Icons.DARK_MODE
        else:
            page.theme_mode = ft.ThemeMode.DARK
            theme_button.icon = ft.Icons.LIGHT_MODE
        apply_theme_styles()
        update_ui()

    def minimize_app(_):
        try:
            page.window.minimized = True
        except Exception:
            if hasattr(page, "window_minimized"):
                page.window_minimized = True
        update_ui()

    async def move_app(_):
        quick_position = ft.Dropdown(
            label="Mover para",
            value="Centro",
            width=260,
            options=[
                ft.dropdown.Option("Centro"),
                ft.dropdown.Option("Canto superior esquerdo"),
                ft.dropdown.Option("Canto superior direito"),
                ft.dropdown.Option("Canto inferior esquerdo"),
                ft.dropdown.Option("Canto inferior direito"),
            ],
        )

        def close_dialog(dialog):
            if hasattr(page, "close"):
                page.close(dialog)
            else:
                dialog.open = False
                if hasattr(page, "dialog"):
                    page.dialog = None
            update_ui()

        def open_dialog(dialog):
            if hasattr(page, "open"):
                page.open(dialog)
            else:
                if hasattr(page, "dialog"):
                    page.dialog = dialog
                dialog.open = True
                update_ui()

        async def confirm_move(__):
            option = quick_position.value or "Centro"
            positions = {
                "Centro": (
                    max(0, (screen_w - target_w) // 2),
                    max(0, (screen_h - target_h) // 2),
                ),
                "Canto superior esquerdo": (0, 0),
                "Canto superior direito": (max(0, screen_w - target_w), 0),
                "Canto inferior esquerdo": (0, max(0, screen_h - target_h)),
                "Canto inferior direito": (
                    max(0, screen_w - target_w),
                    max(0, screen_h - target_h),
                ),
            }
            x, y = positions.get(option, positions["Centro"])
            set_window_position(x, y)
            set_status(f"Janela movida para: {option}.", progress_value=0, running=False)
            close_dialog(move_dialog)

        def cancel_move(__):
            close_dialog(move_dialog)

        move_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Mover janela"),
            content=ft.Column([quick_position], tight=True, spacing=8),
            actions=[
                ft.TextButton("Cancelar", on_click=cancel_move),
                ft.TextButton("Mover", on_click=confirm_move),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        open_dialog(move_dialog)

    async def close_app(_):
        closed = False
        try:
            await page.window.close()
            closed = True
        except Exception:
            pass
        if not closed:
            try:
                page.window.destroy()
                closed = True
            except Exception:
                pass
        if not closed and hasattr(page, "window_destroy") and callable(getattr(page, "window_destroy")):
            try:
                page.window_destroy()
                closed = True
            except Exception:
                pass
        if not closed:
            os._exit(0)

    convert_button.on_click = start_conversion
    cancel_button.on_click = cancel_conversion
    create_video_ts_button.on_click = start_create_video_ts
    theme_button.on_click = toggle_theme
    minimize_button.on_click = minimize_app
    move_button.on_click = move_app
    close_button.on_click = close_app
    add_videos_button.on_click = pick_videos
    pick_output_button.on_click = pick_output_dir
    clear_output_button.on_click = clear_output_dir
    remove_item_button.on_click = remove_selected_item
    clear_queue_button.on_click = clear_queue
    clear_all_button.on_click = clear_all

    navbar_row = ft.Row(
        [
            ft.Container(content=add_videos_button, expand=1, alignment=ft.Alignment(0, 0)),
            ft.Container(content=pick_output_button, expand=1, alignment=ft.Alignment(0, 0)),
            ft.Container(content=clear_output_button, expand=1, alignment=ft.Alignment(0, 0)),
            ft.Container(content=convert_button, expand=1, alignment=ft.Alignment(0, 0)),
            ft.Container(content=cancel_button, expand=1, alignment=ft.Alignment(0, 0)),
            ft.Container(content=create_video_ts_button, expand=1, alignment=ft.Alignment(0, 0)),
            ft.Container(content=theme_button, expand=1, alignment=ft.Alignment(0, 0)),
            ft.Container(content=minimize_button, expand=1, alignment=ft.Alignment(0, 0)),
            ft.Container(content=move_button, expand=1, alignment=ft.Alignment(0, 0)),
            ft.Container(content=close_button, expand=1, alignment=ft.Alignment(0, 0)),
        ],
        wrap=False,
        spacing=0,
    )

    navbar = ft.Container(
        expand=True,
        height=80,
        border_radius=7,
        bgcolor="#000000",
        padding=6,
        content=navbar_row,
    )

    header = ft.Column(
        controls=[
            navbar,
            title,
            subtitle,
            ft.Row([ffmpeg_status, dvdauthor_status], wrap=True),
        ],
        spacing=8,
    )

    main_content = ft.Column(
            controls=[
                header,
                ft.Divider(),
                ft.Row(
                    [
                        remove_item_dropdown,
                        queue_count_text,
                    ],
                    wrap=True,
                ),
                ft.Row(
                    [
                        remove_item_button,
                        clear_queue_button,
                        clear_all_button,
                    ],
                    wrap=True,
                ),
                queue_view,
                output_dir_text,
                ft.Row(
                    [
                        format_dropdown,
                        codec_dropdown,
                        quality_dropdown,
                        resolution_dropdown,
                        dvd_profile_dropdown,
                    ],
                    wrap=True,
                ),
                progress,
                status_text,
            ],
            spacing=8,
            tight=True,
        )

    main_container = ft.Container(content=main_content, visible=False)
    splash_container = build_splash_container(splash_step_text)

    page.add(ft.Stack([main_container, splash_container], expand=True))

    def set_startup_flags(ffmpeg_value: bool, dvdauthor_value: bool):
        nonlocal ffmpeg_ok, dvdauthor_ok
        ffmpeg_ok = ffmpeg_value
        dvdauthor_ok = dvdauthor_value
        apply_theme_styles()

    page.run_task(
        run_startup_splash,
        splash_step_text,
        splash_container,
        main_container,
        ffmpeg_status,
        dvdauthor_status,
        convert_button,
        create_video_ts_button,
        check_ffmpeg,
        check_dvdauthor,
        update_ui,
        set_startup_flags,
    )


if __name__ == "__main__":
    ft.run(app_main)
