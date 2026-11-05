# ai-short-video

一条命令，把一份 `shots.json` 变成带配音、字幕、混音的竖屏短视频。

**A local-first short-video pipeline: image model + local TTS + ffmpeg.**
Feed it a JSON shot list, get a 1080×1920 MP4 with narration, burned-in subtitles and a mixed soundtrack.

![封面](examples/1024/preview/cover.jpg)

| | |
|---|---|
| ![街景](examples/1024/preview/01-street.jpg) | ![老楼](examples/1024/preview/02-building.jpg) |

> 案例《第 1024 单》：14 个镜头 / 112.7 秒 / 1080×1920 / −16.5 LUFS。
> 全部画面由 Seedream 文生图，配音由本地 VoxCPM2 克隆音色，合成由 ffmpeg 完成。

## 这是什么

一套**图片模型 + TTS + ffmpeg** 的生产管线，解决"没有视频生成模型时，怎么稳定产出带声音的短片"：

- 分镜图：任意文生图模型（默认接火山 Seedream 5.0 flash，可换）
- 配音：任意 TTS（默认接本地 VoxCPM2，也可用云 TTS / 真人录音）
- 合成：`zoompan` 做推拉摇、`xfade` 做叠化、ASS 做字幕、`sidechaincompress` 做混音

它把"创意"和"机械劳动"切开：你只写 `shots.json`（台词 + 每镜画面），剩下的自动跑。

## 它不是什么

说实话，免得你踩坑：

- **不是视频生成模型**。画面是静态图 + 运镜，没有人物走动、没有口型、没有真实物理运动。
- **配音是音色克隆，不是真人**。情绪靠标点和停顿，高潮句建议真人补录。
- **雨声是程序化噪声**（pink noise + 滤波），不是实录音效。
- 要"真运动"只能接可灵 / 万相 / Seedance 这类视频模型，成本是这套的 10 倍起。

## 快速开始

### 1. 需要什么

| 必需 | 说明 |
|---|---|
| Python 3.8+ | 脚本只用标准库，**不需要 pip install** |
| ffmpeg + ffprobe | 必须在 PATH 中，且带 libass（压字幕） |
| 图片模型的 key | 默认是火山方舟 `ARK_API_KEY` |
| TTS（可选） | 没有也能跑，见下方"外部音频" |

```powershell
winget install Gyan.FFmpeg     # Windows
```

### 2. 配置

```powershell
git clone <this-repo>
cd ai-short-video
copy config.example.json config.json   # 然后改成你自己机器的路径
```

`config.json` 已被 `.gitignore` 忽略，不会误传。只有一处路径必填：`ark_api_key_file`
（指向含 `ARK_API_KEY=xxx` 的 `.env`），或者直接设环境变量。

### 3. 跑一条

```powershell
python scripts\make_episode.py --project examples\1024 --check   # 先体检
python scripts\make_episode.py --project examples\1024           # 出片
```

`examples/1024` 里只有 `shots.json`，没有图片和音频——第一次跑会真的去生成 14 张图和 14 段配音。

### 外部音频（不用本地 TTS）

管线对配音的全部要求是：`audio\lineNN.wav`、48kHz 单声道、时长可读。

```powershell
ffmpeg -i 任意音频.mp3 -ac 1 -ar 48000 -c:a pcm_s16le examples\1024\audio\line01.wav
python scripts\make_episode.py --project examples\1024 --external-audio
```

## 工作原理

```text
shots.json
   │
   ├─ make_images.py ──▶ images/imgNN.png ─┐
   │   （文生图，风格词统一）                │
   │                                        ├─ build_video.py ──▶ 成片.mp4
   ├─ tts_batch.py ───▶ audio/lineNN.wav ──┘   （运镜→叠化→字幕→混音→压制）
   │   （逐句合成，时长即时间线）
   │
   └─ make_cover.py ──▶ 封面.jpg
```

关键设计：**时间线由音频时长驱动**，不是拍脑袋配的。

```python
t = lead
for s in shots:
    d = adur(wav)                       # 这句配音到底多长（ffprobe 读，不估）
    shot_dur = d + s["gap_after"]       # 这个镜头就占这么久
    t += shot_dur
```

所以改一句台词，整片自动重排，字幕和画面不会错位。

## 目录结构

```text
├── SKILL.md                  # 给 AI 助手看的操作说明（本仓库也是一个 DSH 技能）
├── config.example.json       # 配置模板
├── scripts/
│   ├── common.py             # 配置/路径/ffmpeg 封装
│   ├── make_images.py        # 批量出图（幂等、重试）
│   ├── tts_batch.py          # 逐句配音
│   ├── build_video.py        # 运镜 + 转场 + 字幕 + 混音 + 压制
│   ├── make_cover.py         # 封面
│   ├── qa_asr.py             # 用本地 ASR 回听成片（可选）
│   └── make_episode.py       # 一键串流程 + --check 体检
├── templates/shots.example.json
├── reference/
│   ├── ffmpeg-cheatsheet.md  # 运镜/转场/字幕/音频的命令与参数
│   └── troubleshooting.md    # 按症状查故障
└── examples/1024/            # 一个完整案例（剧本 + 分镜 + 文案 + 预览图）
```

## `shots.json` 速查

```json
{
  "title": "第1024单",
  "style": "写实电影感，35mm胶片质感，冷蓝与暖黄对比，画面中不出现可辨认文字，竖构图9:16",
  "lead_in": 1.5,
  "tail": 4.0,
  "shots": [
    { "id": 1, "line": "系统提示：这是您第一千零二十四次，配送同一份订单。",
      "prompt": "远景、俯拍：暴雨夜空街，黄色雨衣骑手独自穿过十字路口……",
      "motion": "zoom_in", "gap_after": 1.6 }
  ]
}
```

| 字段 | 作用 |
|---|---|
| `line` | 口播台词。**字幕逐句来自这里**，改一处配音和字幕同步改 |
| `prompt` | 画面描述，会自动拼上 `style` |
| `motion` | `zoom_in` `zoom_out` `pan_left` `pan_right` `tilt_up` `tilt_down` |
| `gap_after` | 这句说完停几秒（情绪留白 1–2s / 常规 0.6–0.8s） |
| `ease` | 运镜加缓动，起停更软 |
| `fx` | `vhs` = 老电视扫描线 + 色散 + 噪点 |

## 几个实现要点

1. **叠化会吃掉时长**：`clip 时长 = 分镜时长 + overlap`，最后一段不加。漏了就会画面越跑越快，十几段后差好几秒。
2. **ASS 颜色是 `&HAABBGGRR&`**，和 `#RRGGBB` 反着；改局部色用 `\1c`，`\color` 是非法标签，会静默变黑。
3. **字幕断句**先按标点切、再合并，不要按字数硬切——否则"一千零二十四"会被切成"一千零二十 / 四次"。
4. **`amix` 必须写 `normalize=0`**，否则十几路会被除以路数，人声直接消失。
5. **人声一开口雨声要退**：`sidechaincompress` 用配音当侧链压雨声，比手动调音量自然。
6. **响度统一到 −16 LUFS**：`loudnorm` 后 `+2.2dB` 再用 `alimiter` 兜底。

细节命令见 [`reference/ffmpeg-cheatsheet.md`](reference/ffmpeg-cheatsheet.md)，报错见 [`reference/troubleshooting.md`](reference/troubleshooting.md)。

## 案例：为什么是"思念"而不是"搞笑"

`examples/1024/publish.md` 里记了选题依据：抓 B 站排行榜 100 条，
播放榜是电竞/游戏/搞笑，但**互动率榜（播放≥10万）前八里有 5 条是怀旧/思念类**
（未闻花名 516‰、江歌妈妈 408‰）。

在"只有图片和配音"的条件下，情绪片比搞笑片更容易成立——这条判断比任何滤镜参数都更影响结果。

## 兼容性

主力平台是 **Windows**（路径 junction、系统字体）。macOS / Linux 需要改两处：

- `config.json` 的 `subtitle_font`：`PingFang SC` / `Noto Sans CJK SC`
- 本地 TTS 的路径（或者直接用 `--external-audio`）

## License

代码 MIT。`examples/` 里的文字与图片是原创示例，采用 CC BY-NC 4.0（可转载，不可商用）。
