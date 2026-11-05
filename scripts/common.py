"""共享工具：配置、路径解析、ffmpeg 调用、时长探测。

所有脚本都从这里拿配置。仓库里不放任何机器相关路径，
真实路径写在 config.json（已被 .gitignore 忽略），模板见 config.example.json。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = SKILL_ROOT / "config.json"
EXAMPLE_PATH = SKILL_ROOT / "config.example.json"

# 只有与机器无关的默认值；路径类一律留空，由 config.json 提供
DEFAULT_CONFIG = {
    "ark_api_key_file": "",
    "image_model": "doubao-seedream-5-0-flash-260915",
    "image_size": "1584x2816",

    "tts_root": "",
    "tts_python": "",
    "tts_voice": "",
    "tts_ascii_link": "",
    "tts_ascii_root": "",

    "width": 1080,
    "height": 1920,
    "fps": 30,
    "overlap": 0.35,
    "subtitle_font": "Microsoft YaHei",
    "subtitle_size": 54,

    "video_crf": 19,
    "video_preset": "medium",
    "audio_bitrate": "192k",
    "loudness_lufs": -17,
    "loudness_tp": -2.0,
}


def load_config() -> dict:
    """读 config.json；环境变量可覆盖（ARK_API_KEY / DSH_SKILL_TTS_PYTHON）。"""
    if not CONFIG_PATH.exists():
        raise SystemExit(
            f"缺少 {CONFIG_PATH}\n"
            f"  复制模板后按自己机器改路径：\n"
            f"    copy \"{EXAMPLE_PATH}\" \"{CONFIG_PATH}\""
        )
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except json.JSONDecodeError as e:
        raise SystemExit(f"config.json 不是合法 JSON：{e}")
    if os.environ.get("DSH_SKILL_TTS_PYTHON"):
        cfg["tts_python"] = os.environ["DSH_SKILL_TTS_PYTHON"]
    return cfg


def resolve_project(arg: str | None) -> Path:
    """--project 指向含 shots.json 的目录；缺省用当前目录。"""
    p = Path(arg).expanduser().resolve() if arg else Path.cwd().resolve()
    if not (p / "shots.json").exists():
        raise SystemExit(f"找不到 {p / 'shots.json'}：--project 要指向含 shots.json 的项目目录")
    return p


def load_shots(project: Path) -> dict:
    data = json.loads((project / "shots.json").read_text(encoding="utf-8"))
    for key in ("title", "shots"):
        if key not in data:
            raise SystemExit(f"shots.json 缺少字段: {key}")
    if not data["shots"]:
        raise SystemExit("shots.json 的 shots 为空")
    for s in data["shots"]:
        for key in ("id", "line", "prompt"):
            if key not in s:
                raise SystemExit(f"第 {s.get('id', '?')} 镜缺字段: {key}")
        s.setdefault("gap_after", 0.7)
        s.setdefault("motion", "zoom_in")
    data.setdefault("style", "")
    data.setdefault("lead_in", 1.5)
    data.setdefault("tail", 4.0)
    data.setdefault("output", f"{data['title']}_竖屏成片.mp4")
    return data


def read_env_file(path: Path) -> dict:
    env = {}
    if not path or not path.exists():
        return env
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def api_key(cfg: dict) -> str:
    key = os.environ.get("ARK_API_KEY", "").strip()
    if not key and cfg.get("ark_api_key_file"):
        key = read_env_file(Path(cfg["ark_api_key_file"])).get("ARK_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "缺少 ARK_API_KEY：二选一\n"
            "  1) config.json 的 ark_api_key_file 指向一个含 ARK_API_KEY=xxx 的 .env\n"
            "  2) 设环境变量 ARK_API_KEY"
        )
    return key


def run(cmd: list[str], cwd: Path | None = None, quiet: bool = True) -> None:
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=quiet,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if p.returncode != 0:
        if quiet:
            sys.stderr.write((p.stdout or "")[-2500:] + "\n")
            sys.stderr.write((p.stderr or "")[-2500:] + "\n")
        raise SystemExit(f"命令失败(exit {p.returncode}): {' '.join(cmd[:6])} ...")


def adur(path: Path) -> float:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(p.stdout.strip())
    except ValueError:
        raise SystemExit(f"读不出时长（文件损坏？）: {path}")


def vsize(path: Path) -> tuple[int, int]:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    m = re.match(r"(\d+),(\d+)", p.stdout.strip())
    if not m:
        raise SystemExit(f"读不出尺寸: {path}")
    return int(m.group(1)), int(m.group(2))


def need_ffmpeg() -> None:
    for b in ("ffmpeg", "ffprobe"):
        if shutil.which(b) is None:
            raise SystemExit(f"PATH 里找不到 {b}，先装 ffmpeg 并加进环境变量")


def which(b: str) -> str | None:
    return shutil.which(b)


def log(msg: str) -> None:
    print(msg, flush=True)
