from pathlib import Path
import shutil
import subprocess
from typing import Callable
import os


VIDEO_EXTENSIONS = [".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".wmv", ".m4v", ".vob"]
OUTPUT_FORMATS = ["mp4", "mkv", "avi", "mov", "webm", "flv", "wmv", "m4v", "vob"]
QUALITY_PRESETS = {
    "Alta (CRF 18)": "18",
    "Media (CRF 23)": "23",
    "Baixa (CRF 28)": "28",
}
RESOLUTION_PRESETS = {
    "Original": None,
    "1080p (1920x1080)": (1920, 1080),
    "720p (1280x720)": (1280, 720),
    "480p (854x480)": (854, 480),
    "380p (640x380)": (640, 380),
}
CODEC_PRESETS = {
    "H.264 (AVC)": ["-c:v", "libx264"],
    "H.265 (HEVC)": ["-c:v", "libx265"],
    "VP9": ["-c:v", "libvpx-vp9"],
    "AV1": ["-c:v", "libaom-av1"],
    "MPEG-2": ["-c:v", "mpeg2video"],
    "MPEG-4 Part 2": ["-c:v", "mpeg4"],
    "VP8": ["-c:v", "libvpx"],
    "Theora": ["-c:v", "libtheora"],
    "ProRes": ["-c:v", "prores_ks"],
    "DNxHD": ["-c:v", "dnxhd"],
    "Huffyuv (lossless)": ["-c:v", "huffyuv"],
}
DVD_TARGET_PRESETS = {
    "Desativado": None,
    "DVD PAL (720x576, 25fps)": "pal-dvd",
    "DVD NTSC (720x480, 29.97fps)": "ntsc-dvd",
}

ProgressCallback = Callable[[str, float | None, int | None, int | None], None]
CancelCheck = Callable[[], bool]


def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def check_tool(name: str) -> bool:
    return shutil.which(name) is not None


def check_dvdauthor() -> bool:
    if check_tool("dvdauthor"):
        return True
    if not check_tool("wsl"):
        return False
    probe = subprocess.run(
        ["wsl", "sh", "-lc", "command -v dvdauthor >/dev/null 2>&1"],
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0


def _windows_to_wsl_path(path: Path) -> str:
    path_str = str(path.resolve())
    drive, tail = os.path.splitdrive(path_str)
    if not drive:
        return path_str.replace("\\", "/")
    drive_letter = drive[0].lower()
    return f"/mnt/{drive_letter}{tail.replace('\\', '/')}"


def _build_dvdauthor_cmd(base_cmd: list[str], use_wsl: bool) -> list[str]:
    if use_wsl:
        quoted = " ".join(f'"{arg}"' for arg in base_cmd)
        return ["wsl", "sh", "-lc", quoted]
    return base_cmd


def build_output_path(source_file: Path, output_dir: Path | None, output_format: str) -> Path:
    target_dir = output_dir if output_dir else source_file.parent
    return target_dir / f"{source_file.stem}_convertido.{output_format}"


def build_scale_filter(preset: tuple[int, int] | None) -> str | None:
    if preset is None:
        return None
    width, height = preset
    return (
        f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )


def run_ffmpeg(
    source_file: Path,
    target_file: Path,
    crf: str,
    codec_args: list[str],
    scale_filter: str | None,
    dvd_target: str | None,
    cancel_check: CancelCheck | None = None,
) -> tuple[bool, str, bool]:
    cmd = ["ffmpeg", "-y", "-i", str(source_file)]
    if dvd_target:
        if dvd_target == "pal-dvd":
            dvd_w, dvd_h, dvd_fps = 720, 576, "25"
        else:
            dvd_w, dvd_h, dvd_fps = 720, 480, "29.97"
        dvd_vf = (
            f"scale=w={dvd_w}:h={dvd_h}:force_original_aspect_ratio=decrease,"
            f"pad={dvd_w}:{dvd_h}:(ow-iw)/2:(oh-ih)/2"
        )
        cmd.extend(
            [
                "-target",
                dvd_target,
                "-r",
                dvd_fps,
                "-vf",
                dvd_vf,
                "-c:v",
                "mpeg2video",
                "-b:v",
                "6000k",
                "-maxrate",
                "9000k",
                "-bufsize",
                "1835k",
                "-c:a",
                "ac3",
                "-b:a",
                "192k",
            ]
        )
    else:
        cmd.extend([*codec_args, "-crf", crf, "-preset", "medium"])
        if scale_filter:
            cmd.extend(["-vf", scale_filter])
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])
    cmd.append(str(target_file))

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    while True:
        if cancel_check and cancel_check():
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
            return False, f"CANCELADO: {source_file.name}", True

        try:
            stdout, stderr = process.communicate(timeout=0.4)
            exit_code = process.returncode
            if exit_code == 0:
                return True, f"OK: {target_file}", False
            error_msg = (stderr or stdout or "").strip() or "Erro desconhecido no FFmpeg."
            return False, f"FALHA: {source_file.name}\n{error_msg}", False
        except subprocess.TimeoutExpired:
            continue


def convert_video_queue(
    selected_videos: list[Path],
    selected_output_dir: Path | None,
    output_format: str,
    codec_name: str,
    quality_name: str,
    resolution_name: str,
    dvd_profile_name: str,
    progress_callback: ProgressCallback | None = None,
    cancel_check: CancelCheck | None = None,
) -> str:
    codec_args = CODEC_PRESETS[codec_name]
    crf = QUALITY_PRESETS[quality_name]
    scale_filter = build_scale_filter(RESOLUTION_PRESETS[resolution_name])
    dvd_target = DVD_TARGET_PRESETS[dvd_profile_name]

    total = len(selected_videos)
    done = 0
    failures = 0
    messages: list[str] = []

    for source_file in list(selected_videos):
        if cancel_check and cancel_check():
            messages.append("Conversao cancelada pelo usuario.")
            break

        if progress_callback:
            progress_callback(
                f"Convertendo {done + 1}/{total}: {source_file.name}",
                None,
                done,
                total,
            )

        if not source_file.exists():
            failures += 1
            done += 1
            messages.append(f"FALHA: arquivo nao encontrado - {source_file}")
            if progress_callback:
                progress_callback(
                    f"Convertendo... {done}/{total}",
                    done / total if total else 0,
                    done,
                    total,
                )
            continue

        target_format = "mpg" if dvd_target else output_format
        target_file = build_output_path(source_file, selected_output_dir, target_format)
        ok, msg, canceled = run_ffmpeg(
            source_file=source_file,
            target_file=target_file,
            crf=crf,
            codec_args=codec_args,
            scale_filter=scale_filter,
            dvd_target=dvd_target,
            cancel_check=cancel_check,
        )
        if canceled:
            messages.append(msg)
            break
        if not ok:
            failures += 1
        messages.append(msg)
        done += 1
        if progress_callback:
            progress_callback(
                f"Convertendo... {done}/{total}",
                done / total if total else 0,
                done,
                total,
            )

    was_canceled = any(m.startswith("CANCELADO:") or "cancelada" in m.lower() for m in messages)
    prefix = "Cancelado." if was_canceled else "Finalizado."
    summary = f"{prefix} Sucesso: {done - failures} | Falhas: {failures}\n\n" + "\n\n".join(messages)
    if dvd_target:
        summary += (
            "\n\nModo DVD: arquivo MPEG-2 gerado (.mpg). "
            "Para criar VIDEO_TS com .VOB/.IFO/.BUP, use a autoria de DVD."
        )
    return summary


def build_dvd_output_dir(base_dir: Path) -> Path:
    index = 1
    while True:
        candidate = base_dir / f"DVD_OUTPUT_{index}"
        if not candidate.exists():
            return candidate
        index += 1


def collect_mpg_sources(selected_videos: list[Path], selected_output_dir: Path | None) -> list[Path]:
    files: list[Path] = []
    for source in selected_videos:
        converted = build_output_path(source, selected_output_dir, "mpg")
        if converted.exists():
            files.append(converted)
    if files:
        return files

    base_dir = selected_output_dir if selected_output_dir else Path.cwd()
    return sorted(base_dir.glob("*.mpg"))


def run_dvdauthor(
    mpg_files: list[Path],
    dvd_output_dir: Path,
    dvd_profile_name: str = "DVD NTSC (720x480, 29.97fps)",
) -> tuple[bool, str]:
    dvd_output_dir.mkdir(parents=True, exist_ok=True)

    use_wsl = not check_tool("dvdauthor")
    if use_wsl and not check_tool("wsl"):
        return False, "dvdauthor nao encontrado no Windows e WSL nao disponivel."

    if use_wsl:
        output_arg = _windows_to_wsl_path(dvd_output_dir)
        mpg_args = [_windows_to_wsl_path(f) for f in mpg_files]
    else:
        output_arg = str(dvd_output_dir)
        mpg_args = [str(f) for f in mpg_files]

    video_format = "pal" if "PAL" in dvd_profile_name.upper() else "ntsc"
    create_titles = _build_dvdauthor_cmd(
        ["dvdauthor", "-o", output_arg, "-f", video_format, "-t", *mpg_args],
        use_wsl,
    )
    create_table = _build_dvdauthor_cmd(
        ["dvdauthor", "-o", output_arg, "-f", video_format, "-T"],
        use_wsl,
    )

    run_cwd = os.environ.get("USERPROFILE", "C:\\") if use_wsl else None
    first = subprocess.run(create_titles, capture_output=True, text=True, cwd=run_cwd)
    if first.returncode != 0:
        return False, first.stderr.strip() or "Falha ao criar titulos DVD."

    second = subprocess.run(create_table, capture_output=True, text=True, cwd=run_cwd)
    if second.returncode != 0:
        return False, second.stderr.strip() or "Falha ao criar tabela DVD."

    video_ts = dvd_output_dir / "VIDEO_TS"
    if not video_ts.exists():
        return False, f"Processo concluido sem VIDEO_TS em {dvd_output_dir}."

    return True, f"VIDEO_TS criado em: {video_ts}"


def create_video_ts_from_selection(
    selected_videos: list[Path],
    selected_output_dir: Path | None,
    dvd_profile_name: str = "DVD NTSC (720x480, 29.97fps)",
) -> tuple[bool, str]:
    if not check_dvdauthor():
        return False, "Instale dvdauthor no PATH do Windows ou no WSL."

    mpg_files = collect_mpg_sources(selected_videos, selected_output_dir)
    if not mpg_files:
        return False, "Nenhum .mpg encontrado. Converta em modo DVD antes de criar VIDEO_TS."

    base_dir = selected_output_dir if selected_output_dir else mpg_files[0].parent
    dvd_output_dir = build_dvd_output_dir(base_dir)
    return run_dvdauthor(mpg_files, dvd_output_dir, dvd_profile_name)
