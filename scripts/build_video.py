"""分镜图 + 逐句配音 → 竖屏成片（Ken Burns 运镜 / 叠化 / 字幕 / 混音）。

用法:
    python build_video.py --project <项目目录>            # 全流程
    python build_video.py --project <项目目录> --dry      # 只打印时间线
    python build_video.py --project <项目目录> --skip-clips  # 复用已有片段，只重混音+重出成片
    python build_video.py --project <项目目录> --out xxx.mp4
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

CFG = common.load_config()
W, H, FPS = int(CFG["width"]), int(CFG["height"]), int(CFG["fps"])
OVERLAP = float(CFG["overlap"])
FONT = CFG["subtitle_font"]
SUB_SIZE = int(CFG["subtitle_size"])


# ---------------------------------------------------------------- 运镜

def prog(n: int, ease: bool) -> str:
    """0→1 的时间进度；ease=True 用 smoothstep（起停更软）。"""
    p = f"(on/{n})"
    return f"({p}*{p}*(3-2*{p}))" if ease else p


def motion_expr(kind: str, frames: int, ease: bool = False) -> str:
    n = max(frames, 2)
    p = prog(n, ease)
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    s = f":d=1:s={W}x{H}:fps={FPS}"
    table = {
        "zoom_in":      f"zoompan=z='1+0.10*{p}':x='{cx}':y='{cy}'{s}",
        "zoom_in_slow": f"zoompan=z='1+0.06*{p}':x='{cx}':y='{cy}'{s}",
        "zoom_in_fast": f"zoompan=z='1+0.22*{p}':x='{cx}':y='{cy}'{s}",
        "zoom_out":     f"zoompan=z='1.12-0.10*{p}':x='{cx}':y='{cy}'{s}",
        "pan_right":    f"zoompan=z='1.08':x='(iw-iw/zoom)*{p}':y='{cy}'{s}",
        "pan_left":     f"zoompan=z='1.08':x='(iw-iw/zoom)*(1-{p})':y='{cy}'{s}",
        "tilt_up":      f"zoompan=z='1.08':x='{cx}':y='(ih-ih/zoom)*(1-{p})'{s}",
        "tilt_down":    f"zoompan=z='1.08':x='{cx}':y='(ih-ih/zoom)*{p}'{s}",
    }
    if kind not in table:
        raise SystemExit(f"未知 motion: {kind}（可选 {'/'.join(table)}）")
    return table[kind]


def make_clip(img: Path, dur: float, kind: str, out: Path, fx: str | None, ease: bool) -> None:
    frames = int(round(dur * FPS))
    vf = (
        f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,"
        f"crop={W * 2}:{H * 2},setsar=1,"
        + motion_expr(kind, frames, ease)
    )
    if fx == "vhs":
        vf += (",gblur=sigma=1.1,drawgrid=w=iw:h=4:t=1:c=black@0.14,"
               "rgbashift=rh=3:bh=-3,noise=alls=16:allf=t+u,eq=saturation=0.9:contrast=1.06")
    vf += ",format=yuv420p"
    common.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-framerate", str(FPS), "-loop", "1", "-t", f"{dur:.3f}", "-i", str(img),
        "-vf", vf, "-r", str(FPS), "-t", f"{dur:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
        "-pix_fmt", "yuv420p", str(out),
    ])


# ---------------------------------------------------------------- 字幕

def ts(sec: float) -> str:
    sec = max(sec, 0.0)
    return f"{int(sec // 3600)}:{int(sec % 3600 // 60):02d}:{sec % 60:05.2f}"


def split_phrases(line: str, limit: int = 16, hard: int = 20) -> list[str]:
    """按标点断句 → 合并到 ≤limit 字 → 超长才硬切（且尽量切在标点）。"""
    parts = [p for p in re.split(r"(?<=[，。！？；：—])", line.strip()) if p]
    out: list[str] = []
    for p in parts:
        while len(p) > hard:
            cut = max(p.rfind("，", 0, limit), p.rfind("、", 0, limit), p.rfind("：", 0, limit))
            cut = cut + 1 if cut > 4 else limit
            out.append(p[:cut])
            p = p[cut:]
        if p:
            out.append(p)
    merged: list[str] = []
    for p in out:
        if merged and len(merged[-1]) + len(p) <= limit:
            merged[-1] += p
        else:
            merged.append(p)
    return merged


def build_ass(segs: list[dict], total: float, title: str, path: Path) -> None:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{FONT},{SUB_SIZE},&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,1,0,0,0,100,100,1.5,0,1,3.2,1.6,2,90,90,250,1
Style: Title,{FONT},92,&H00F2F2F2,&H00FFFFFF,&H00101010,&H96000000,1,0,0,0,100,100,6,0,1,3.6,2.4,5,0,0,0,1
Style: End,{FONT},64,&H00F2F2F2,&H00FFFFFF,&H00101010,&H96000000,1,0,0,0,100,100,4,0,1,3.0,2.0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = [
        f'Dialogue: 0,{ts(0.35)},{ts(3.1)},Title,,0,0,0,,{{\\fad(700,700)\\pos({W // 2},760)}}{title}',
    ]
    for seg in segs:
        phrases = split_phrases(seg["line"])
        total_chars = sum(len(p) for p in phrases) or 1
        t0 = seg["start"]
        span = seg["audio_dur"] - 0.06
        for ph in phrases:
            d = max(span * len(ph) / total_chars, 0.55)
            ev.append(f'Dialogue: 0,{ts(t0)},{ts(t0 + d)},Sub,,0,0,0,,{{\\fad(120,120)}}{ph}')
            t0 += d
    end_t = total - 3.4
    ev.append(f'Dialogue: 0,{ts(end_t)},{ts(total - 0.25)},Title,,0,0,0,,'
              f'{{\\fad(600,600)\\pos({W // 2},540)}}{{\\fs80}}{title}')
    path.write_text(header + "\n".join(ev) + "\n", encoding="utf-8-sig")


# ---------------------------------------------------------------- 主流程

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--skip-clips", action="store_true")
    ap.add_argument("--no-subs", action="store_true")
    args = ap.parse_args()

    common.need_ffmpeg()
    project = common.resolve_project(args.project)
    data = common.load_shots(project)
    shots, lead, tail = data["shots"], float(data["lead_in"]), float(data["tail"])

    build = project / "build"
    clips = build / "clips"
    out_path = Path(args.out) if args.out else project.parent / data["output"]

    t = lead
    segs = []
    for s in shots:
        wav = project / "audio" / f"line{s['id']:02d}.wav"
        img = project / "images" / f"img{s['id']:02d}.png"
        if not wav.exists():
            raise SystemExit(f"缺配音: {wav}")
        if not img.exists():
            raise SystemExit(f"缺画面: {img}")
        d = common.adur(wav)
        segs.append({
            "id": s["id"], "line": s["line"], "start": t, "audio_dur": d,
            "shot_dur": d + float(s["gap_after"]), "motion": s["motion"],
            "img": img, "fx": s.get("fx"), "ease": bool(s.get("ease")),
        })
        t += d + float(s["gap_after"])
    total = t + tail
    segs[0]["shot_dur"] += lead
    segs[-1]["shot_dur"] += tail

    common.log(f"{data['title']}｜{len(segs)} 镜｜总长 {total:.2f}s")
    for s in segs:
        common.log(f"  {s['id']:02d} 起{s['start']:7.2f} 音{s['audio_dur']:5.2f} 镜{s['shot_dur']:5.2f} "
                   f"{s['motion']:<12}{' ' + s['fx'] if s['fx'] else ''}")
    if args.dry:
        return 0
    if total > 120:
        common.log(f"⚠ 总长 {total:.1f}s 超过 120s，竖屏平台会被截断或降权")

    build.mkdir(parents=True, exist_ok=True)
    clips.mkdir(parents=True, exist_ok=True)

    # 1) 逐镜运镜片段
    for i, s in enumerate(segs):
        dur = s["shot_dur"] + (OVERLAP if i < len(segs) - 1 else 0.0)
        f = clips / f"clip{i + 1:02d}.mp4"
        if args.skip_clips and f.exists():
            continue
        common.log(f"clip {i + 1:02d} {dur:.2f}s ...")
        make_clip(s["img"], dur, s["motion"], f, s["fx"], s["ease"])

    # 2) 混音
    common.log("audio mix ...")
    inputs, filters = [], []
    for i, s in enumerate(segs):
        inputs += ["-i", f"../audio/line{s['id']:02d}.wav"]
        filters.append(f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=mono,"
                       f"adelay={int(round(s['start'] * 1000))}:all=1[v{i}]")
    mix_in = "".join(f"[v{i}]" for i in range(len(segs)))
    filters.append(f"{mix_in}amix=inputs={len(segs)}:duration=longest:normalize=0[voice]")
    filters.append(f"[voice]apad=whole_dur={total:.3f},atrim=0:{total:.3f},asplit=2[vout][vsc]")
    filters.append(f"anoisesrc=color=pink:amplitude=0.30:duration={total:.3f}:seed=7,"
                   "highpass=f=420,lowpass=f=6800,volume=0.055[rain]")
    filters.append("[rain][vsc]sidechaincompress=threshold=0.035:ratio=5:attack=150:release=700[rduck]")
    filters.append("[vout][rduck]amix=inputs=2:duration=first:normalize=0,"
                   f"loudnorm=I={CFG['loudness_lufs']}:TP={CFG['loudness_tp']}:LRA=11,"
                   "aresample=48000,volume=2.2dB,alimiter=limit=0.95[aout]")
    common.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
                "-filter_complex", ";".join(filters), "-map", "[aout]",
                "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", "mix.wav"], cwd=build)

    # 3) 字幕
    ass = build / "subs.ass"
    build_ass(segs, total, data["title"], ass)

    # 4) 合成
    common.log("final render ...")
    n = len(segs)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for i in range(n):
        cmd += ["-i", f"clips/clip{i + 1:02d}.mp4"]
    cmd += ["-i", "mix.wav"]

    fc, acc, last = [], segs[0]["shot_dur"] + OVERLAP, "[0:v]"
    for i in range(1, n):
        nxt = f"[x{i}]"
        fc.append(f"{last}[{i}:v]xfade=transition=fade:duration={OVERLAP}:offset={acc - OVERLAP:.3f}{nxt}")
        last = nxt
        acc = acc + segs[i]["shot_dur"] + (OVERLAP if i < n - 1 else 0.0) - OVERLAP
    tail_filters = (f"{last}eq=saturation=0.98:contrast=1.03:brightness=0.012,"
                    "noise=alls=6:allf=t+u,vignette=angle=PI/5.2,"
                    f"fade=t=in:st=0:d=1.2,fade=t=out:st={total - 1.6:.3f}:d=1.5")
    if not args.no_subs:
        tail_filters += ",ass=subs.ass"
    fc.append(tail_filters + ",format=yuv420p[vout]")

    cmd += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", f"{n}:a",
            "-c:v", "libx264", "-preset", CFG["video_preset"], "-crf", str(CFG["video_crf"]),
            "-r", str(FPS), "-c:a", "aac", "-b:a", CFG["audio_bitrate"], "-ar", "48000",
            "-movflags", "+faststart", "-t", f"{total:.3f}", str(out_path)]
    common.run(cmd, cwd=build)
    common.log(f"done -> {out_path}  {common.adur(out_path):.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
