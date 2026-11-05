"""按 shots.json 批量出图（Seedream，9:16 竖构图）。

用法:
    python make_images.py --project <项目目录>              # 跳过已生成的
    python make_images.py --project <项目目录> --force      # 全部重出
    python make_images.py --project <项目目录> --only 3,7   # 只出指定镜号
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/images/generations"


def post(payload: dict, key: str, timeout: int = 300) -> dict:
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:400]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    common.need_ffmpeg()
    cfg = common.load_config()
    project = common.resolve_project(args.project)
    data = common.load_shots(project)

    key = common.api_key(cfg)
    images = project / "images"
    images.mkdir(parents=True, exist_ok=True)

    only = {int(x) for x in args.only.split(",") if x.strip()} if args.only else None
    todo = [s for s in data["shots"] if only is None or s["id"] in only]
    common.log(f"项目 {project.name}｜{len(todo)} 镜待处理｜模型 {cfg['image_model']}")

    failed = []
    for shot in todo:
        out = images / f"img{shot['id']:02d}.png"
        if out.exists() and not args.force:
            common.log(f"  skip {out.name}")
            continue
        prompt = shot["prompt"] + ("，" + data["style"] if data["style"] else "")
        payload = {
            "model": cfg["image_model"],
            "prompt": prompt,
            "size": cfg["image_size"],
            "output_format": "png",
            "response_format": "url",
            "watermark": False,
        }
        for attempt in range(3):
            try:
                t0 = time.time()
                common.log(f"  [{shot['id']:02d}] generating ...")
                resp = post(payload, key)
                items = resp.get("data") or []
                if not items or not items[0].get("url"):
                    raise RuntimeError(f"无图片返回: {json.dumps(resp, ensure_ascii=False)[:200]}")
                with urllib.request.urlopen(items[0]["url"], timeout=180) as r:
                    out.write_bytes(r.read())
                common.log(f"  [{shot['id']:02d}] ok {items[0].get('size')} "
                           f"{out.stat().st_size // 1024}KB {time.time() - t0:.1f}s")
                break
            except Exception as exc:  # noqa: BLE001
                common.log(f"  [{shot['id']:02d}] retry {attempt + 1}/3: {exc}")
                time.sleep(3 * (attempt + 1))
        else:
            failed.append(shot["id"])

    if failed:
        common.log(f"失败镜号: {failed}（其余已保存，重跑只补这些）")
        return 1
    common.log("图片全部就绪")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
