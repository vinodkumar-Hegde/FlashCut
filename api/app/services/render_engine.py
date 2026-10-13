import json
import math
import subprocess
from pathlib import Path


FONT_FILE = (
    "/usr/share/fonts/truetype/"
    "dejavu/DejaVuSans-Bold.ttf"
)


def has_audio(
    source_path: Path,
) -> bool:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=index",
            "-of",
            "json",
            str(source_path),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )

    payload = json.loads(
        result.stdout
    )

    return bool(
        payload.get(
            "streams"
        )
    )


def escape_drawtext(
    value: str,
) -> str:
    return (
        value
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
    )


def render_video(
    *,
    source_path: Path,
    output_path: Path,
    clips: list[dict],
    watermark: str,
    timeout_seconds: int,
):
    if not clips:
        raise ValueError(
            "No clips supplied."
        )

    audio = has_audio(
        source_path
    )

    filters = []
    concat_inputs = []

    for index, clip in enumerate(
        clips
    ):
        start = float(
            clip["start"]
        )

        end = float(
            clip["end"]
        )

        if (
            not math.isfinite(start)
            or not math.isfinite(end)
            or start < 0
            or end <= start
        ):
            raise ValueError(
                "Invalid clip timestamps."
            )

        filters.append(
            (
                f"[0:v]"
                f"trim=start={start:.3f}:"
                f"end={end:.3f},"
                f"setpts=PTS-STARTPTS"
                f"[v{index}]"
            )
        )

        concat_inputs.append(
            f"[v{index}]"
        )

        if audio:
            filters.append(
                (
                    f"[0:a]"
                    f"atrim=start={start:.3f}:"
                    f"end={end:.3f},"
                    f"asetpts=PTS-STARTPTS"
                    f"[a{index}]"
                )
            )

            concat_inputs.append(
                f"[a{index}]"
            )

    if audio:
        filters.append(
            (
                "".join(
                    concat_inputs
                )
                + f"concat=n={len(clips)}:"
                + "v=1:a=1"
                + "[vcat][acat]"
            )
        )

    else:
        filters.append(
            (
                "".join(
                    concat_inputs
                )
                + f"concat=n={len(clips)}:"
                + "v=1:a=0"
                + "[vcat]"
            )
        )

    text = escape_drawtext(
        watermark
    )

    filters.append(
        (
            "[vcat]"
            "drawtext="
            f"fontfile={FONT_FILE}:"
            f"text='{text}':"
            "x=w-tw-24:"
            "y=h-th-24:"
            "fontsize=28:"
            "fontcolor=white:"
            "box=1:"
            "boxcolor=black@0.55"
            "[vout]"
        )
    )

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source_path),
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[vout]",
    ]

    if audio:
        command.extend([
            "-map",
            "[acat]",
        ])

    suffix = (
        output_path
        .suffix
        .lower()
    )

    if suffix == ".mp4":
        command.extend([
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
        ])

        if audio:
            command.extend([
                "-c:a",
                "aac",
                "-b:a",
                "160k",
            ])

        command.extend([
            "-movflags",
            "+faststart",
        ])

    elif suffix == ".webm":
        command.extend([
            "-c:v",
            "libvpx-vp9",
            "-crf",
            "31",
            "-b:v",
            "0",
            "-row-mt",
            "1",
            "-deadline",
            "good",
            "-cpu-used",
            "2",
        ])

        if audio:
            command.extend([
                "-c:a",
                "libopus",
                "-b:a",
                "128k",
            ])

    else:
        raise ValueError(
            "Unsupported output container."
        )

    command.append(
        str(output_path)
    )

    subprocess.run(
        command,
        check=True,
        timeout=timeout_seconds,
    )
