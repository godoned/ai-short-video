"""出竖屏封面（标题 + 钩子句），复用 ASS 排版。

用法: python make_cover.py --project <项目目录> [--out xx.jpg] [--image img01.png]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from build_video import split_phrases  # noqa: E402

CFG = common.load_config()
W, H = int(CFG["width"]), int(CFG["height"])
FONT = CFG["subtitle_font"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--image", default="img01.png")
    args = ap.parse_args()

    common.need_ffmpeg()
    project = common.resolve_project(args.project)
    data = common.load_shots(project)
    build = project / "build"
    build.mkdir(parents=True, exist_ok=True)

    cover = data.get("cover") or {}
    hook = cover.get("hook") or split_phrases(data["shots"][0]["line"], limit=16)[:2]
    hook = list(hook) if isinstance(hook, list) else [str(hook)]
    # "系统提示：" 这种短标签不要单独成行，并到下一行去
    if len(hook) > 1 and hook[0].rstrip().endswith(("：", ":")):
        hook[0] = hook[0].rstrip() + hook.pop(1)
    foot = cover.get("foot", "AI 生成短片")

    lines = [f'Dialogue: 0,0:00:00.00,0:00:10.00,Big,,0,0,0,,{{\\pos({W // 2},540)}}{data["title"]}']
    for i, h in enumerate(hook[:2]):
        lines.append(f'Dialogue: 0,0:00:00.00,0:00:10.00,Sub,,0,0,0,,'
                     f'{{\\pos({W // 2},{680 + i * 70})}}{h}')
    lines.append(f'Dialogue: 0,0:00:00.00,0:00:10.00,Foot,,0,0,0,,{{\\pos({W // 2},{H - 160})}}{foot}')

    ass = build / "cover.ass"
    ass.write_text(f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Big,{FONT},132,&H00FFFFFF,&H00FFFFFF,&H00101010,&H60000000,1,0,0,0,100,100,8,0,1,4,3,5,0,0,0,1
Style: Sub,{FONT},50,&H00E6E6E6,&H00FFFFFF,&H00101010,&H60000000,1,0,0,0,100,100,2,0,1,3,2,5,0,0,0,1
Style: Foot,{FONT},34,&H00B4B4B4,&H00FFFFFF,&H00101010,&H60000000,0,0,0,0,100,100,2,0,1,2.6,1.4,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(lines) + "\n", encoding="utf-8-sig")

    out = Path(args.out) if args.out else project.parent / f"封面_{data['title']}.jpg"
    common.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-i", str(project / "images" / args.image),
        "-vf", f"scale={W}:{H},eq=brightness=-0.04:contrast=1.05,vignette=angle=PI/5,"
               "ass=cover.ass,format=yuvj420p",
        "-frames:v", "1", "-q:v", "2", str(out),
    ], cwd=build)
    common.log(f"cover -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
