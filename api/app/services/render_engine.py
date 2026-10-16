import json
import math
import subprocess
import tempfile
import time
from pathlib import Path


def probe_media(
    source_path: Path,
) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
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

    streams = payload.get(
        "streams",
        []
    )

    video = next(
        (
            item
            for item
            in streams
            if item.get(
                "codec_type"
            )
            == "video"
        ),
        None,
    )

    if video is None:
        raise ValueError(
            "Video stream is missing."
        )

    width = int(
        video.get(
            "width",
            0,
        )
    )

    height = int(
        video.get(
            "height",
            0,
        )
    )

    if (
        width <= 0
        or height <= 0
    ):
        raise ValueError(
            "Invalid video dimensions."
        )

    duration_raw = (
        payload
        .get(
            "format",
            {},
        )
        .get(
            "duration"
        )
    )

    try:
        duration = float(
            duration_raw
        )

    except (
        TypeError,
        ValueError,
    ):
        duration = 0.0

    if (
        not math.isfinite(
            duration
        )
        or duration <= 0
    ):
        raise ValueError(
            "Invalid video duration."
        )

    audio = any(
        item.get(
            "codec_type"
        )
        == "audio"
        for item
        in streams
    )

    return {
        "width":
            width,

        "height":
            height,

        "duration":
            duration,

        "audio":
            audio,
    }


def _video_filter(
    *,
    input_index: int,
    output_label: str,
    width: int,
    height: int,
    start: float | None,
    duration: float,
) -> str:
    parts = [
        f"[{input_index}:v:0]",
    ]

    if start is None:
        parts.append(
            "trim="
            f"duration={duration:.3f}"
        )

    else:
        parts.append(
            "trim="
            f"start={start:.3f}:"
            f"duration={duration:.3f}"
        )

    parts.extend([
        "setpts=PTS-STARTPTS",
        (
            "scale="
            f"w={width}:"
            f"h={height}:"
            "force_original_aspect_ratio="
            "decrease"
        ),
        (
            f"pad={width}:{height}:"
            "(ow-iw)/2:"
            "(oh-ih)/2"
        ),
        "fps=30",
        "setsar=1",
        "format=yuv420p",
    ])

    return (
        parts[0]
        + ",".join(
            parts[1:]
        )
        + f"[{output_label}]"
    )


def _audio_filter(
    *,
    input_index: int,
    output_label: str,
    has_audio: bool,
    start: float | None,
    duration: float,
) -> str:
    if not has_audio:
        return (
            "anullsrc="
            "r=48000:"
            "cl=stereo,"
            f"atrim=duration={duration:.3f},"
            "asetpts=PTS-STARTPTS"
            f"[{output_label}]"
        )

    parts = [
        f"[{input_index}:a:0]",
    ]

    if start is None:
        parts.append(
            "atrim="
            f"duration={duration:.3f}"
        )

    else:
        parts.append(
            "atrim="
            f"start={start:.3f}:"
            f"duration={duration:.3f}"
        )

    parts.extend([
        "asetpts=PTS-STARTPTS",
        "aresample=48000",
        (
            "aformat="
            "sample_fmts=fltp:"
            "channel_layouts=stereo"
        ),
        (
            "apad="
            f"whole_dur={duration:.3f}"
        ),
        (
            "atrim="
            f"duration={duration:.3f}"
        ),
    ])

    return (
        parts[0]
        + ",".join(
            parts[1:]
        )
        + f"[{output_label}]"
    )


def _remaining_timeout(
    deadline: float,
) -> int:
    remaining = int(
        math.ceil(
            deadline
            - time.monotonic()
        )
    )

    if remaining <= 0:
        raise TimeoutError(
            "Video rendering timed out."
        )

    return remaining


def _run_ffmpeg(
    command: list[str],
    *,
    deadline: float,
):
    subprocess.run(
        command,
        check=True,
        timeout=_remaining_timeout(
            deadline
        ),
    )


def _codec_arguments(
    suffix: str,
) -> list[str]:
    if suffix == ".mp4":
        return [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-movflags",
            "+faststart",
        ]

    if suffix == ".webm":
        return [
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
            "4",
            "-c:a",
            "libopus",
            "-b:a",
            "128k",
            "-ar",
            "48000",
            "-ac",
            "2",
        ]

    raise ValueError(
        "Unsupported output container."
    )


def _encode_segment(
    *,
    input_path: Path,
    output_path: Path,
    width: int,
    height: int,
    duration: float,
    has_audio: bool,
    deadline: float,
    start: float | None = None,
):
    if (
        not math.isfinite(duration)
        or duration <= 0
    ):
        raise ValueError(
            "Invalid segment duration."
        )

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
    ]

    # Input-side seek avoids decoding the
    # complete source for every selected clip.
    if start is not None:
        command.extend([
            "-ss",
            f"{start:.3f}",
        ])

    command.extend([
        "-i",
        str(input_path),
        "-t",
        f"{duration:.3f}",
    ])

    video_filter = (
        "[0:v:0]"
        f"trim=duration={duration:.3f},"
        "setpts=PTS-STARTPTS,"
        f"scale=w={width}:h={height}:"
        "force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:"
        "(ow-iw)/2:(oh-ih)/2,"
        "fps=30,"
        "setsar=1,"
        "format=yuv420p"
        "[v]"
    )

    if has_audio:
        audio_filter = (
            "[0:a:0]"
            f"atrim=duration={duration:.3f},"
            "asetpts=PTS-STARTPTS,"
            "aresample=48000,"
            "aformat="
            "sample_fmts=fltp:"
            "channel_layouts=stereo,"
            f"apad=whole_dur={duration:.3f},"
            f"atrim=duration={duration:.3f}"
            "[a]"
        )

    else:
        audio_filter = (
            "anullsrc="
            "r=48000:"
            "cl=stereo,"
            f"atrim=duration={duration:.3f},"
            "asetpts=PTS-STARTPTS"
            "[a]"
        )

    command.extend([
        "-filter_complex",
        (
            video_filter
            + ";"
            + audio_filter
        ),
        "-map",
        "[v]",
        "-map",
        "[a]",
    ])

    command.extend(
        _codec_arguments(
            output_path
            .suffix
            .lower()
        )
    )

    command.append(
        str(output_path)
    )

    _run_ffmpeg(
        command,
        deadline=deadline,
    )


def render_video(
    *,
    source_path: Path,
    output_path: Path,
    clips: list[dict],
    timeout_seconds: int,
    intro_path: Path | None = None,
    outro_path: Path | None = None,
    max_asset_duration_seconds: int = 60,
):
    if not clips:
        raise ValueError(
            "No clips supplied."
        )

    source_info = probe_media(
        source_path
    )

    target_width = int(
        source_info["width"]
    )

    target_height = int(
        source_info["height"]
    )

    # H.264/yuv420p requires even dimensions.
    if target_width % 2:
        target_width -= 1

    if target_height % 2:
        target_height -= 1

    if (
        target_width < 2
        or target_height < 2
    ):
        raise ValueError(
            "Invalid target dimensions."
        )

    suffix = (
        output_path
        .suffix
        .lower()
    )

    # Validate container before doing work.
    _codec_arguments(
        suffix
    )

    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    with tempfile.TemporaryDirectory(
        prefix="flashcut-engine-"
    ) as workdir_raw:
        workdir = Path(
            workdir_raw
        )

        fragments: list[Path] = []
        fragment_number = 0

        def next_fragment() -> Path:
            nonlocal fragment_number

            path = (
                workdir
                / (
                    "segment-"
                    f"{fragment_number:04d}"
                    + suffix
                )
            )

            fragment_number += 1

            return path

        # -------------------------------------------------
        # Intro
        # -------------------------------------------------

        if intro_path is not None:
            intro_info = probe_media(
                intro_path
            )

            intro_duration = float(
                intro_info[
                    "duration"
                ]
            )

            if (
                intro_duration
                > max_asset_duration_seconds
            ):
                raise ValueError(
                    "Intro exceeds "
                    "duration limit."
                )

            fragment = (
                next_fragment()
            )

            _encode_segment(
                input_path=intro_path,
                output_path=fragment,
                width=target_width,
                height=target_height,
                duration=(
                    intro_duration
                ),
                has_audio=bool(
                    intro_info[
                        "audio"
                    ]
                ),
                deadline=deadline,
            )

            fragments.append(
                fragment
            )

        # -------------------------------------------------
        # Selected content
        # -------------------------------------------------

        for clip in clips:
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

            duration = (
                end
                - start
            )

            fragment = (
                next_fragment()
            )

            _encode_segment(
                input_path=source_path,
                output_path=fragment,
                width=target_width,
                height=target_height,
                duration=duration,
                has_audio=bool(
                    source_info[
                        "audio"
                    ]
                ),
                deadline=deadline,
                start=start,
            )

            fragments.append(
                fragment
            )

        # -------------------------------------------------
        # Outro
        # -------------------------------------------------

        if outro_path is not None:
            outro_info = probe_media(
                outro_path
            )

            outro_duration = float(
                outro_info[
                    "duration"
                ]
            )

            if (
                outro_duration
                > max_asset_duration_seconds
            ):
                raise ValueError(
                    "Outro exceeds "
                    "duration limit."
                )

            fragment = (
                next_fragment()
            )

            _encode_segment(
                input_path=outro_path,
                output_path=fragment,
                width=target_width,
                height=target_height,
                duration=(
                    outro_duration
                ),
                has_audio=bool(
                    outro_info[
                        "audio"
                    ]
                ),
                deadline=deadline,
            )

            fragments.append(
                fragment
            )

        if not fragments:
            raise ValueError(
                "No render fragments created."
            )

        # All fragments were encoded with the exact
        # same video/audio profile. Concatenation can
        # therefore be stream-copy only: no second
        # expensive encode and no giant filter graph.
        concat_file = (
            workdir
            / "concat.txt"
        )

        concat_file.write_text(
            "".join(
                (
                    "file '"
                    + fragment
                    .resolve()
                    .as_posix()
                    + "'\n"
                )
                for fragment
                in fragments
            ),
            encoding="utf-8",
        )

        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
        ]

        if suffix == ".mp4":
            command.extend([
                "-movflags",
                "+faststart",
            ])

        command.append(
            str(output_path)
        )

        _run_ffmpeg(
            command,
            deadline=deadline,
        )
