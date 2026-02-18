import asyncio
from collections.abc import Callable

import flet as ft


def build_splash_container(step_text: ft.Text) -> ft.Container:
    splash_content = ft.Container(
        expand=True,
        bgcolor=ft.Colors.with_opacity(0.98, ft.Colors.WHITE),
        padding=20,
        content=ft.Column(
            [
                ft.ProgressRing(width=42, height=42),
                ft.Text("Conversor de Video", size=26, weight=ft.FontWeight.BOLD),
                step_text,
                ft.Divider(),
                ft.Text("Desenvolvedor:  Francisco Armando Chico", weight=ft.FontWeight.BOLD),
                ft.Text("Empresa: SoftSafe"),
                ft.Text("Ano de lancamento: 2026"),
                ft.Text("Ferramentas utilizadas: Python, Flet, FFmpeg, dvdauthor, WSL"),
                ft.Text("Converter seus vídeos nunca foi tão fácil. Com uma interface limpa e intuitiva, nosso app cuida da parte pesada para você. Basta adicionar seus arquivos na fila, escolher o formato e deixar o resto conosco. Boas-vindas! Obrigado por usar o conversor."),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            spacing=10,
        ),
    )
    return ft.Container(content=splash_content, visible=True)


async def run_startup_splash(
    step_text: ft.Text,
    splash_container: ft.Container,
    main_container: ft.Container,
    ffmpeg_status: ft.Text,
    dvdauthor_status: ft.Text,
    convert_button: ft.Button,
    create_video_ts_button: ft.Button,
    check_ffmpeg_fn: Callable[[], bool],
    check_dvdauthor_fn: Callable[[], bool],
    update_ui: Callable[[], None],
    on_result: Callable[[bool, bool], None],
) -> None:
    step_text.value = "Inicializando interface..."
    update_ui()
    await asyncio.sleep(0.35)

    step_text.value = "Verificando FFmpeg..."
    update_ui()
    ffmpeg_ok = await asyncio.to_thread(check_ffmpeg_fn)
    ffmpeg_status.value = "FFmpeg detectado no sistema." if ffmpeg_ok else "FFmpeg nao encontrado no PATH."
    ffmpeg_status.color = ft.Colors.GREEN if ffmpeg_ok else ft.Colors.RED
    update_ui()
    await asyncio.sleep(0.25)

    step_text.value = "Verificando dvdauthor..."
    update_ui()
    dvdauthor_ok = await asyncio.to_thread(check_dvdauthor_fn)
    dvdauthor_status.value = "dvdauthor detectado." if dvdauthor_ok else "dvdauthor nao encontrado no PATH."
    dvdauthor_status.color = ft.Colors.GREEN if dvdauthor_ok else ft.Colors.RED
    convert_button.disabled = not ffmpeg_ok
    create_video_ts_button.disabled = not dvdauthor_ok
    on_result(ffmpeg_ok, dvdauthor_ok)
    update_ui()
    await asyncio.sleep(0.35)

    step_text.value = "Recursos carregados. Bem-vindo!"
    update_ui()
    await asyncio.sleep(0.45)

    splash_container.visible = False
    main_container.visible = True
    update_ui()
