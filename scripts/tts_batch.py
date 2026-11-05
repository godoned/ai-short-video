"""按 shots.json 逐句合成配音（本地 VoxCPM2）。

**必须用 TTS 自带的 python 运行**（它装了 torch）：
    "<tts_python>" tts_batch.py --project <项目目录>

用法:
    --force        全部重出
    --only 1,2     只出指定镜号
    --voice xxx.mp3  换参考音色（相对 <tts_root>/voices）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def write_wav(path: Path, sr: int, wav) -> None:
    import numpy as np

    wav = np.clip(np.asarray(wav, dtype=np.float32).reshape(-1), -1.0, 1.0)
    pcm = (wav * 32767.0).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(int(sr))
        f.writeframes(pcm.tobytes())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--voice", default="")
    args = ap.parse_args()

    cfg = common.load_config()
    project = common.resolve_project(args.project)
    data = common.load_shots(project)
    audio = project / "audio"
    audio.mkdir(parents=True, exist_ok=True)

    only = {int(x) for x in args.only.split(",") if x.strip()} if args.only else None
    todo = [s for s in data["shots"] if only is None or s["id"] in only]
    need = [s for s in todo if args.force or not (audio / f"line{s['id']:02d}.wav").exists()]
    if not need:
        common.log("配音已齐，无需生成")
        return 0

    tts_root = Path(cfg["tts_root"]) if cfg.get("tts_root") else None
    if tts_root is None or not tts_root.exists():
        raise SystemExit(
            "config.json 没配好本地 TTS（tts_root）。两条路：\n"
            "  1) 配好 tts_root / tts_python / tts_voice\n"
            "  2) 不用本地 TTS：自己准备 audio\\lineNN.wav，改用 "
            "make_episode.py --project <项目> --external-audio"
        )
    os.chdir(tts_root)
    sys.path.insert(0, str(tts_root / "src"))
    sys.path.insert(0, str(tts_root))

    import webui  # noqa: E402  延迟导入：只有这里需要 torch

    voice_name = args.voice or cfg["tts_voice"]
    voice = str(tts_root / "voices" / voice_name)
    if not Path(voice).exists():
        raise SystemExit(f"参考音色不存在: {voice}")

    common.log(f"加载模型（首次约 40s）… 音色 {voice_name}")
    demo = webui.VoxCPMDemo(model_id="./models/VoxCPM2", device="auto")
    common.log("模型就绪")

    for shot in need:
        text = shot["line"].strip()
        sr, wav = demo.generate_tts_audio(
            text,
            control_instruction="",
            reference_wav_path_input=voice,
            prompt_text="",
            cfg_value_input=2.0,
            do_normalize=False,      # wetext 读不了中文路径，且中文数字本来就该手写
            denoise=True,
            inference_timesteps=10,
            segment=True,
        )
        out = audio / f"line{shot['id']:02d}.wav"
        write_wav(out, sr, wav)
        dur = len(wav) / float(sr)
        common.log(f"  [{shot['id']:02d}] {dur:5.2f}s  {dur / max(len(text), 1):.2f}s/字  {text[:16]}")
    common.log("配音完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
