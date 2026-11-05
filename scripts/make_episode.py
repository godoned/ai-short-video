"""一条命令跑完整条流水线：出图 → 配音 → 成片 → 封面。

用法:
    python make_episode.py --project <项目目录> --check     # 只体检，不生成
    python make_episode.py --project <项目目录>             # 缺什么补什么，再出片
    python make_episode.py --project <项目目录> --force     # 图、音全部重来
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

HERE = Path(__file__).resolve().parent


def check(cfg: dict, project: Path, external_audio: bool = False) -> int:
    """体检：不生成任何东西，只回答'这台机器现在能不能出片'。

    external_audio=True 表示配音由外部提供（云 TTS / 真人录音），
    此时本地 TTS 缺失只提示、不判失败。
    """
    common.log(f"== 体检：{project} ==")
    common.log(f"   技能目录：{HERE.parent}")
    ok = True

    for b in ("ffmpeg", "ffprobe"):
        found = common.which(b)
        common.log(f"  [{'OK' if found else '--'}] {b}: {found or '未安装'}")
        ok &= bool(found)

    env_file = Path(cfg["ark_api_key_file"]) if cfg.get("ark_api_key_file") else None
    if env_file is None:
        common.log("  [..] 配置文件: 未设置 ark_api_key_file（只读环境变量 ARK_API_KEY）")
    else:
        common.log(f"  [{'OK' if env_file.exists() else '..'}] 配置文件: {env_file}"
                   + ("" if env_file.exists() else "（不存在，将只读环境变量 ARK_API_KEY）"))
    try:
        key = common.api_key(cfg)
        common.log(f"  [OK] ARK_API_KEY: {key[:4]}…{key[-4:]}")
    except SystemExit as e:
        common.log(f"  [--] ARK_API_KEY 缺失: {e}")
        ok = False

    tts_root = Path(cfg["tts_root"]) if cfg.get("tts_root") else None
    tts_py = Path(cfg["tts_python"]) if cfg.get("tts_python") else None
    voice = (tts_root / "voices" / cfg["tts_voice"]) if (tts_root and cfg.get("tts_voice")) else None
    if external_audio:
        common.log("  [..] 本地 TTS: 已声明用外部音频，跳过")
    elif tts_root is None or tts_py is None or voice is None:
        common.log("  [--] 本地 TTS: config.json 未配置 tts_root / tts_python / tts_voice")
        common.log("       ↳ 没有本地 TTS 也能出片：自己准备 audio\\lineNN.wav，"
                   "然后加 --external-audio 再体检")
        ok = False
    else:
        common.log(f"  [{'OK' if tts_root.exists() else '--'}] tts_root: {tts_root}")
        common.log(f"  [{'OK' if tts_py.exists() else '--'}] TTS python: {tts_py}")
        common.log(f"  [{'OK' if voice.exists() else '--'}] 参考音色: {voice.name}")
        ok &= tts_root.exists() and tts_py.exists() and voice.exists()
        if not tts_root.exists():
            common.log("       ↳ 没有本地 TTS 也能出片：自己准备 audio\\lineNN.wav，"
                       "然后加 --external-audio 再体检")

    try:
        data = common.load_shots(project)
        common.log(f"  [OK] shots.json: 《{data['title']}》{len(data['shots'])} 镜")
    except SystemExit as e:
        common.log(f"  [--] shots.json: {e}")
        return 1

    miss_img = [s["id"] for s in data["shots"] if not (project / "images" / f"img{s['id']:02d}.png").exists()]
    miss_aud = [s["id"] for s in data["shots"] if not (project / "audio" / f"line{s['id']:02d}.wav").exists()]
    common.log(f"  [{'OK' if not miss_img else '..'}] 图 {len(data['shots']) - len(miss_img)}/{len(data['shots'])}"
               + (f"（缺 {miss_img}）" if miss_img else ""))
    common.log(f"  [{'OK' if not miss_aud else '..'}] 音 {len(data['shots']) - len(miss_aud)}/{len(data['shots'])}"
               + (f"（缺 {miss_aud}）" if miss_aud else ""))
    if external_audio and miss_aud:
        ok = False
        common.log("       ↳ 外部音频模式：先把 lineNN.wav 放进 audio\\（48k 单声道）")

    est = (len(miss_img) * 22 + (0 if external_audio else len(miss_aud) * 12)
           + (0 if miss_aud or external_audio else 40)) / 60 + 4
    common.log(f"  预计耗时 ≈ {est:.0f} 分钟")
    common.log(f"  结论：{'可以出片' if ok else '先修上面标 [--] 的项'}")
    return 0 if ok else 1


def step(name: str, cmd: list[str]) -> None:
    t0 = time.time()
    common.log(f"\n---- {name} ----")
    p = subprocess.run(cmd, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise SystemExit(f"{name} 失败（exit {p.returncode}）")
    common.log(f"---- {name} 用时 {time.time() - t0:.1f}s ----")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--skip-images", action="store_true")
    ap.add_argument("--skip-tts", action="store_true")
    ap.add_argument("--skip-cover", action="store_true")
    ap.add_argument("--external-audio", action="store_true",
                    help="配音由外部提供（云 TTS / 真人），跳过本地 TTS")
    args = ap.parse_args()

    cfg = common.load_config()
    project = common.resolve_project(args.project)

    if args.check:
        return check(cfg, project, external_audio=args.external_audio)

    t_all = time.time()
    py = sys.executable

    if not args.skip_images:
        step("出图", [py, str(HERE / "make_images.py"), "--project", str(project)]
             + (["--force"] if args.force else []))
    if not args.skip_tts and not args.external_audio:
        step("配音", [cfg["tts_python"], str(HERE / "tts_batch.py"), "--project", str(project)]
             + (["--force"] if args.force else []))
    if args.external_audio:
        common.log("外部音频模式：跳过本地 TTS，直接用 audio\\lineNN.wav")

    build_cmd = [py, str(HERE / "build_video.py"), "--project", str(project)]
    if args.out:
        build_cmd += ["--out", args.out]
    step("合成", build_cmd)

    if not args.skip_cover:
        step("封面", [py, str(HERE / "make_cover.py"), "--project", str(project)])

    common.log(f"\n全部完成，总用时 {(time.time() - t_all) / 60:.1f} 分钟")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
