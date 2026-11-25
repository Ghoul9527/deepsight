"""Burn the DeepSight film HUD into a copy of a local MP4."""

from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont

WHITE, MUTED, MINT, AMBER = "#F0F8FB", "#B4D1DD", "#9EF0D7", "#F4C381"
GRID = (172, 216, 230, 85)
LANG = {
    "zh": ("潜镜", "相机深度", "用时", "垂直速度", "水温", "深度曲线", "最深", "目标",
           "水面", "下潜", "转身", "上升", "完成", "演示数据"),
    "en": ("DEEPSIGHT", "CAMERA DEPTH", "ELAPSED", "VERTICAL SPEED", "WATER TEMP",
           "DEPTH PROFILE", "MAX", "TARGET", "SURFACE", "DESCENT", "TURN", "ASCENT",
           "COMPLETE", "SIMULATED DATA"),
}
GAP_SECONDS = 2.0


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将潜镜 HUD 烧录到 MP4 副本 / Burn the DeepSight HUD into an MP4 copy")
    parser.add_argument("video", type=Path, help="GoPro 原片 / source MP4")
    parser.add_argument("--data", "--数据", type=Path, help="深度 JSONL，默认与 MP4 同名 / depth JSONL")
    parser.add_argument("--lang", "--语言", choices=("zh", "en"), default="zh")
    parser.add_argument("--name", "--姓名", help="潜水员姓名 / diver name")
    parser.add_argument("--discipline", "--项目", help="项目代号 / e.g. FIM, CWT, CNF")
    parser.add_argument("--target-depth", "--目标深度", type=float, help="目标深度（米） / target depth in metres")
    parser.add_argument("--offset", "--偏移", type=float, default=0,
                        help="JSONL 零点在视频中的秒数 / video time for JSONL t=0")
    parser.add_argument("--output", "--输出", type=Path, help="新 MP4 的路径 / output MP4")
    parser.add_argument("--hud-fps", type=int, choices=range(5, 61), metavar="5–60", default=20)
    parser.add_argument("--ffmpeg", help="ffmpeg.exe 的路径 / path to the FFmpeg executable")
    parser.add_argument("--font", type=Path, help="支持所选语言的字库 / font file")
    parser.add_argument("--demo", action="store_true", help="显式使用带标记的模拟数据 / use labelled synthetic data")
    return parser.parse_args()


def find_ffmpeg(preferred: str | None) -> str:
    if preferred:
        return preferred
    portable = Path(__file__).resolve().parent.parent / ".venv/Scripts/ffmpeg.exe"
    if result := shutil.which("ffmpeg"):
        return result
    if portable.is_file():
        return str(portable)
    raise ValueError("找不到 FFmpeg。请使用 --ffmpeg 指定路径。 / FFmpeg was not found.")


def probe_video(ffmpeg: str, source: Path) -> tuple[float, int, int]:
    result = subprocess.run([ffmpeg, "-hide_banner", "-i", str(source)],
                            capture_output=True, text=True, errors="replace")
    duration = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    video_line = next((line for line in result.stderr.splitlines() if "Video:" in line), "")
    size = re.search(r"(?<!\w)(\d{2,5})x(\d{2,5})(?!\w)", video_line)
    if not duration or not size:
        raise ValueError("无法读取 MP4 时长或尺寸。 / Could not probe MP4 duration or size.")
    hours, minutes, seconds = map(float, duration.groups())
    width, height = map(int, size.groups())
    rotation = re.search(r"rotation of\s+(-?\d+(?:\.\d+)?)\s+degrees", result.stderr)
    if rotation and abs(round(float(rotation[1]))) % 180 == 90:
        width, height = height, width
    return hours * 3600 + minutes * 60 + seconds, width, height


def read_samples(path: Path) -> tuple[list[tuple[float, float, float | None]], dict]:
    rows, metadata = {}, {}
    with path.open(encoding="utf-8-sig") as source:
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
                if item.get("type") == "start":
                    metadata.update(item)
                if item.get("type") != "depth":
                    continue
                t, depth = float(item["elapsed_s"]), float(item["depth_m"])
                if not (math.isfinite(t) and t >= 0 and math.isfinite(depth)):
                    raise ValueError("invalid time or depth")
                temperature = item.get("temperature_c")
                temperature = float(temperature) if temperature is not None else None
                if temperature is not None and not math.isfinite(temperature):
                    temperature = None
                rows[t] = (t, depth, temperature)
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                raise ValueError(f"{path.name}:{number}: {exc}") from exc
    if not rows:
        raise ValueError(f"{path.name} 没有深度样本 / no depth samples")
    return sorted(rows.values()), metadata


def demo_samples(duration: float) -> list[tuple[float, float, float]]:
    count = max(2, math.ceil(duration * 5))
    rows = []
    for ratio in sorted({i / count for i in range(count + 1)} | {.47}):
        depth = 42.5 * (ratio / .47 if ratio < .47 else (1 - ratio) / .53)
        rows.append((duration * ratio, depth, 26.4 - depth * .14))
    return rows


class Hud:
    def __init__(self, size, samples, args, metadata, duration):
        self.width, self.height = size
        self.vertical = self.height > self.width
        self.scale = self.width / (540 if self.vertical else 960)
        self.samples = samples
        self.times = [row[0] for row in samples]
        self.maximum = max(samples, key=lambda row: row[1])
        self.ceiling = max(10, math.ceil(self.maximum[1] / 10) * 10)
        self.args = args
        self.end = duration - args.offset
        self.start = -args.offset
        self.words = LANG[args.lang]
        fonts = Path("C:/Windows/Fonts")
        text_font = args.font or fonts / ("msyh.ttc" if args.lang == "zh" else "bahnschrift.ttf")
        digits_font = fonts / "consola.ttf"
        self.label = ImageFont.truetype(str(text_font), self.px(15))
        self.small = ImageFont.truetype(str(text_font), self.px(13))
        self.brand = ImageFont.truetype(str(text_font), self.px(22))
        self.number = ImageFont.truetype(str(digits_font), self.px(64))
        self.measure = ImageFont.truetype(str(digits_font), self.px(17))
        self.base = Image.new("RGBA", size)
        draw = ImageDraw.Draw(self.base)
        name = args.name or metadata.get("athlete_name") or ("陈林" if args.demo and args.lang == "zh" else "LIN CHEN" if args.demo else "")
        discipline = args.discipline or metadata.get("discipline") or ("FIM" if args.demo else "")
        target = args.target_depth if args.target_depth is not None else metadata.get("target_depth_m")
        if target is None and args.demo:
            target = 45.0
        details = "  /  ".join(part for part in (discipline,
                     f"{self.words[7]} {float(target):.1f} m" if target is not None else "") if part)
        ext = self.width / self.scale
        self.title(draw, (ext-52, 41), self.words[0], self.brand, anchor="ra")
        if name:
            self.title(draw, (53, 41), name, self.brand)
        if details:
            self.title(draw, (54, 73 if name else 48), details, self.small)
        if args.demo:
            self.title(draw, (ext-52, 72), self.words[13], self.small, MUTED, anchor="ra")

        self.lower = (self.height / self.scale) - 165 - (144 if self.vertical else 0)
        self.graph_x = 53 if self.vertical else ext - 326
        self.graph_y = self.lower + (180 if self.vertical else 48)
        self.graph_width = ext - 160 if self.vertical else 228
        self.graph_height = 55
        self.trace_index = bisect_left(self.times, self.start)
        self.trace_tail = None
        self.title(draw, (53, self.lower), self.words[1], self.label, MUTED)
        self.title(draw, (119, self.lower+123), self.words[2], self.small, MUTED)
        self.title(draw, (216, self.lower+103), self.words[3], self.small, MUTED)
        self.title(draw, (356, self.lower+103), self.words[4], self.small, MUTED)
        self.title(draw, (self.graph_x, self.graph_y-28), self.words[5], self.label)
        for fraction in (0, .5, 1):
            y = self.graph_y + self.graph_height * fraction
            draw.line([self.xy(self.graph_x, y), self.xy(self.graph_x+self.graph_width, y)], fill=GRID)
            if fraction != .5:
                self.title(draw, (self.graph_x+self.graph_width+9, y),
                           f"{self.ceiling * fraction:.0f} m", self.small, MUTED, anchor="lm")

    def px(self, pixels):
        return max(1, round(pixels * self.scale))

    def xy(self, x, y):
        return tuple(round(value * self.scale) for value in (x, y))

    def title(self, draw, point, text, font, color=WHITE, anchor="la"):
        draw.text(self.xy(*point), str(text), fill=color, font=font, anchor=anchor,
                  stroke_width=self.px(1), stroke_fill=(5, 21, 33, 210))

    def point(self, t, depth):
        return self.xy(self.graph_x + self.graph_width * (t - self.start) / (self.end-self.start),
                       self.graph_y + self.graph_height * max(0, depth) / self.ceiling)

    def values(self, t):
        i = bisect_right(self.times, t)
        depth, temperature, speed = None, None, None
        if 0 < i < len(self.times):
            a, b = self.samples[i-1], self.samples[i]
            span = b[0] - a[0]
            if span <= GAP_SECONDS:
                ratio = (t-a[0])/span
                depth = a[1]+(b[1]-a[1])*ratio
                speed = (b[1]-a[1])/span
                if a[2] is not None and b[2] is not None:
                    temperature = a[2]+(b[2]-a[2])*ratio
            elif t == a[0]:
                depth, temperature = a[1:]
        elif i and t == self.times[-1]:
            depth, temperature = self.samples[-1][1:]
        return i, depth, temperature, speed

    def frame(self, video_time):
        t = video_time - self.args.offset
        i, depth, temperature, speed = self.values(t)
        # Commit newly visible samples to the chart once per render.
        trace_draw = ImageDraw.Draw(self.base)
        for at, level, _ in self.samples[self.trace_index:i]:
            if self.trace_tail is not None:
                prev_t, prev_depth = self.trace_tail
                if at - prev_t <= GAP_SECONDS:
                    trace_draw.line([self.point(prev_t, prev_depth), self.point(at, level)],
                                    fill=MINT, width=self.px(2))
            self.trace_tail = (at, level)
        self.trace_index = max(self.trace_index, i)
        im = self.base.copy()
        draw = ImageDraw.Draw(im)
        value = f"{depth:04.1f}" if depth is not None else "—"
        self.title(draw, (51, self.lower+10), value, self.number)
        unit_x = 54 + self.number.getlength(value) / self.scale + 10
        self.title(draw, (unit_x, self.lower+60), "m", self.label)
        elapsed = int(video_time)
        self.title(draw, (54, self.lower+123), f"{elapsed//60:02}:{elapsed%60:02}", self.measure)
        direction = " ↓" if speed is not None and speed > .05 else " ↑" if speed is not None and speed < -.05 else ""
        self.title(draw, (216, self.lower+123), f"{abs(speed):.2f} m/s{direction}" if speed is not None else "—", self.measure)
        self.title(draw, (356, self.lower+123), f"{temperature:.1f} °C" if temperature is not None else "—", self.measure)
        if depth is not None:
            cursor = self.point(t, depth)
            if self.trace_tail is not None and t - self.trace_tail[0] <= GAP_SECONDS:
                draw.line([self.point(*self.trace_tail), cursor], fill=MINT, width=self.px(2))
            r = self.px(4)
            draw.ellipse((cursor[0]-r,cursor[1]-r,cursor[0]+r,cursor[1]+r), fill=MINT)
        peak_time, peak_depth, _ = self.maximum
        if self.start <= peak_time <= t and peak_depth >= 1:
            x, y = self.point(peak_time, peak_depth)
            r = self.px(4)
            draw.ellipse((x-r,y-r,x+r,y+r), fill=AMBER)
            self.title(draw, (self.graph_x+self.graph_width, self.graph_y-28),
                       f"{self.words[6]} {peak_depth:.1f} m", self.small, AMBER, anchor="ra")
        if depth is not None:
            phase = 12 if depth < .5 and t > peak_time else 8 if depth < .5 else 10 if abs(t-peak_time) < 1.5 else 9 if t < peak_time else 11
            self.title(draw, (self.graph_x, self.graph_y+self.graph_height+10), self.words[phase],
                       self.small, AMBER if phase == 10 else MINT)
        return im


def burn(ffmpeg, source, output, hud, duration, dimensions, fps):
    width, height = dimensions
    with TemporaryDirectory(prefix=".deepsight-hud-", dir=output.parent) as workspace:
        temp = Path(workspace) / "render.mp4"
        stderr = Path(workspace) / "ffmpeg.log"
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(source),
            "-f", "rawvideo", "-pixel_format", "rgba", "-video_size", f"{hud.width}x{hud.height}",
            "-framerate", str(fps), "-i", "pipe:0",
            "-filter_complex", f"[1:v]scale={width}:{height},format=rgba[h];"
            "[0:v:0][h]overlay=eof_action=pass:repeatlast=0,pad=ceil(iw/2)*2:ceil(ih/2)*2[v]",
            "-map", "[v]", "-map", "0:a?", "-map_metadata", "0", "-fps_mode", "passthrough",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "copy", "-movflags", "+faststart", str(temp),
        ]
        with stderr.open("wb") as errors, subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors,
        ) as process:
            try:
                with process.stdin:
                    for index in range(math.ceil(duration * fps) + 1):
                        process.stdin.write(hud.frame(index / fps).tobytes())
            except BrokenPipeError:
                pass
            except BaseException:
                process.kill()
                raise
            status = process.wait()
        if status or not temp.is_file():
            raise RuntimeError(stderr.read_text(encoding="utf-8", errors="replace") or "FFmpeg failed")
        # Exclusive creation protects any file that appeared during rendering.
        with temp.open("rb") as source_file, output.open("xb") as destination:
            try:
                shutil.copyfileobj(source_file, destination)
            except OSError:
                destination.close()
                output.unlink(missing_ok=True)
                raise


def main():
    args = arguments()
    video = args.video.resolve(strict=True)
    output = (args.output or video.with_name(f"{video.stem}_HUD_{args.lang}.mp4")).resolve()
    if video.suffix.lower() != ".mp4" or output.suffix.lower() != ".mp4":
        raise ValueError("输入和输出必须是 MP4。 / Input and output must be MP4.")
    if output.exists():
        raise ValueError(f"输出已存在 / Output exists: {output}")
    if not math.isfinite(args.offset):
        raise ValueError("偏移必须是有限秒数。 / Offset must be finite.")
    if args.target_depth is not None and not (math.isfinite(args.target_depth) and args.target_depth >= 0):
        raise ValueError("目标深度必须是非负有限数。 / Invalid target depth.")
    if args.demo and args.data:
        raise ValueError("--demo 与 --data 不能同时使用。 / Choose either --demo or --data.")
    ffmpeg = find_ffmpeg(args.ffmpeg)
    duration, width, height = probe_video(ffmpeg, video)
    if duration <= 0:
        raise ValueError("MP4 时长必须大于零。 / MP4 duration must be positive.")
    if args.demo:
        samples, metadata = demo_samples(duration), {}
    else:
        samples, metadata = read_samples(args.data or video.with_suffix(".jsonl"))
        if samples[-1][0]+args.offset < 0 or samples[0][0]+args.offset > duration:
            raise ValueError("数据与视频时间不重叠，请检查 --offset。 / No temporal overlap.")
    scale = min(1., 1280 / max(width, height))
    hud_size = (round(width * scale), round(height * scale))
    hud = Hud(hud_size, samples, args, metadata, duration)
    output.parent.mkdir(parents=True, exist_ok=True)
    print(f"Rendering {args.lang} HUD · {width}×{height} · {duration:.1f} s", flush=True)
    burn(ffmpeg, video, output, hud, duration, (width, height), args.hud_fps)
    print(output)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
