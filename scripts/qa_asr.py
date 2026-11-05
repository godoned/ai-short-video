"""成片质检：本地 SenseVoice 把音轨转文字，核对配音有没有串行/吞字。

必须用 TTS 的 python 运行（它装了 funasr）：
    "<tts_python>" qa_asr.py --project <项目目录>

注意：sentencepiece 读不了中文路径，脚本会优先用 config 里的 tts_ascii_link
（需要先用 New-Item -ItemType Junction 建一个 ASCII 别名）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="")
    ap.add_argument("--audio", default="", help="默认用 build/mix.wav，没有就从成片抽")
    args = ap.parse_args()

    cfg = common.load_config()
    project = common.resolve_project(args.project)
    data = common.load_shots(project)

    wav = Path(args.audio) if args.audio else project / "build" / "mix.wav"
    if not wav.exists():
        final = project.parent / data["output"]
        if not final.exists():
            raise SystemExit("既没有 build/mix.wav，也找不到成片")
        wav = project / "build" / "qa.wav"
        wav.parent.mkdir(parents=True, exist_ok=True)
        common.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(final),
                    "-vn", "-ac", "1", "-ar", "16000", str(wav)])

    link = Path(cfg["tts_ascii_link"])
    tts_root = Path(cfg["tts_root"])
    # sentencepiece 打不开含中文的路径：优先走 ASCII 联接
    ascii_root = Path(cfg["tts_ascii_root"])
    model = (ascii_root if ascii_root.exists() else tts_root) / "models" / "SenseVoiceSmall"
    if not model.exists():
        raise SystemExit(f"找不到 SenseVoice 模型: {model}\n"
                         f"提示：先建 ASCII 联接：New-Item -ItemType Junction -Path {link} "
                         f"-Target {tts_root.parent.parent}")

    import os
    sys.path.insert(0, str(tts_root / "src"))
    sys.path.insert(0, str(tts_root))
    os.chdir(tts_root)

    from funasr import AutoModel  # noqa: E402

    m = AutoModel(model=str(model), device="cpu", disable_update=True, log_level="ERROR")
    res = m.generate(input=str(wav), language="zh", use_itn=True, batch_size_s=60)
    txt = "\n".join(r["text"].split("|>")[-1].strip() for r in res)
    out = wav.parent / "asr.txt"
    out.write_text(txt, encoding="utf-8")
    common.log(txt)
    common.log(f"\n转写已存: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
