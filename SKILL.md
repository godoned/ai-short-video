---
name: ai-short-video
description: 用本地图片模型（Seedream 5.0 flash）+ 本地 TTS（VoxCPM2）+ ffmpeg，生产 60–120 秒竖屏短视频：选题 → 口播稿 → 分镜 → 出图 → 配音 → 运镜合成 → 字幕 → 混音 → 质检。用户说"再做一条短视频""换个题材重做""沿用上次那套管线"时加载本技能。
---

# AI 竖屏短视频生产管线

一套跑通过的本地管线：**图片模型出分镜图 + 本地 TTS 逐句配音 + ffmpeg 做运镜/叠化/字幕/混音**。
成片规格默认 1080×1920 / 30fps / ≤120s / −16 LUFS。

## 何时用

- 用户要一条竖屏短视频，且手上只有"图片模型 + TTS"，没有视频生成模型；
- 用户说"用上次那套 / 再来一条 / 换个题材"，需要复用同一套脚本与口径；
- 需要把一段文字故事稳定地产成带配音字幕的成片。

**不适用**：需要真人表演、口型对白、连续运动镜头（那要视频生成模型，见文末"能力边界"）。

## 装到一台新电脑（5 分钟）

技能包本身零业务依赖（不含台词、图片、音频），但运行需要这些东西：

| 必需 | 说明 | 缺了怎么办 |
|---|---|---|
| Python 3.8+ | 脚本只用标准库 | 装一个 |
| ffmpeg + ffprobe 在 PATH | **必须带 libass**（压字幕） | `winget install Gyan.FFmpeg` |
| ARK_API_KEY | Seedream 的云 key | 写进 `.env` 或环境变量 |
| 本地 TTS（可选） | 16 GB / 模型 6.9 GB | **可以不要**，见下方"外部音频模式" |

```powershell
# 1) 拷技能目录，挂进 DSH 的技能根（真实目录 → 联接）
Copy-Item -Recurse D:\dsh-skills\ai-short-video <新位置>\ai-short-video
New-Item -ItemType Junction -Path "<DSH技能目录>\ai-short-video" -Target "<新位置>\ai-short-video"

# 2) 改 config.json 的路径（.env 位置、tts_python、tts_root、字体）
# 3) 体检，按提示修到全绿
python <技能目录>\scripts\make_episode.py --project <项目> --check
```

**外部音频模式**（没有本地 TTS 也能出片）：管线对配音的全部要求是
`audio\lineNN.wav`、48kHz 单声道、时长可读。云 TTS / 真人录音 / 剪映导出都行：

```powershell
ffmpeg -i 任意音频.mp3 -ac 1 -ar 48000 -c:a pcm_s16le audio\line01.wav
python scripts\make_episode.py --project <项目> --external-audio
```

跨系统注意：`config.json` 的 `subtitle_font` 在 macOS 上要改成 `PingFang SC`，
Linux 用 `Noto Sans CJK SC`。

## 开工前必须先做三件事

```powershell
# ① 体检：key / 模型 / 音色 / 缺哪些图音
python "<技能目录>\scripts\make_episode.py" --project "<项目目录>" --check

# ② 读 config.json：所有外部路径都在这里，换机器只改这一份
# ③ 读 <项目目录>\shots.json：这是全片的唯一事实来源
```

体检不过就别开始生成，先修 `config.json`（路径）或 `.env`（key）。

## 项目结构（约定，脚本按此查找）

```text
<项目目录>\
  shots.json         # 全片唯一真相：标题、风格、每一镜的台词与画面
  images\img01.png   # 出图产物（1584×2816）
  audio\line01.wav   # 逐句配音（48k 单声道）
  build\             # 中间产物：clips\、mix.wav、subs.ass、cover.ass
<项目目录>\..\       # 成片与封面默认落在这里（项目目录的上一级）
```

新建项目 = 建目录 + 从 `templates\shots.example.json` 复制一份 `shots.json` 改内容。

```powershell
$S = "<技能目录>"; $P = "D:\work out\新的一集"
New-Item -ItemType Directory -Force -Path $P | Out-Null
Copy-Item "$S\templates\shots.example.json" "$P\shots.json"
# 改 shots.json（title / style / 每镜 line 与 prompt）后：
python "$S\scripts\make_episode.py" --project $P --check
```

## 五步流程

```powershell
$S = "<技能目录>"
$P = "<项目目录>"

# 一步到底（缺什么补什么）
python "$S\scripts\make_episode.py" --project $P

# 或者分步
python "$S\scripts\make_images.py" --project $P              # 出图（约 22s/张）
& "<tts_python>" "$S\scripts\tts_batch.py" --project $P       # 配音（必须用 TTS 的 python）
python "$S\scripts\build_video.py"  --project $P --dry        # 先看时间线，别急着渲
python "$S\scripts\build_video.py"  --project $P              # 合成（约 4 分钟）
python "$S\scripts\make_cover.py"   --project $P              # 封面
```

**幂等**：出图和配音都会跳过已存在的文件。改台词只重跑 `tts_batch`（加 `--force`），
改画面只重跑 `make_images`，改运镜/字幕只重跑 `build_video --skip-clips`（省 5 分钟）。

## shots.json 字段

```json
{
  "title": "第1024单",
  "output": "第1024单_竖屏成片.mp4",
  "style": "全片共用的风格词（质感/色调/禁止出现文字）",
  "lead_in": 1.5,
  "tail": 4.0,
  "cover": { "hook": ["钩子第一行", "钩子第二行"], "foot": "AI 生成短片" },
  "shots": [
    {
      "id": 1,
      "line": "这句要念的台词（字幕也从这里来）",
      "prompt": "这镜的画面：景别、机位、主体、前景背景、光线、道具",
      "motion": "zoom_in",
      "gap_after": 1.2,
      "ease": true,
      "fx": "vhs"
    }
  ]
}
```

| 字段 | 说明 |
|---|---|
| `id` | 从 1 连续递增；决定文件命名 `img01` / `line01` |
| `line` | 口播台词，**字幕逐句来自这里**，一处改，配音和字幕同时改 |
| `prompt` | 画面描述，会自动拼上 `style` |
| `motion` | `zoom_in` `zoom_in_slow` `zoom_in_fast` `zoom_out` `pan_left` `pan_right` `tilt_up` `tilt_down` |
| `gap_after` | 这句说完后停几秒（情绪留白 1–2s，正常 0.6–0.8s） |
| `ease` | 可选，运镜加缓动（起停变软） |
| `fx` | 可选，`vhs` = 老电视扫描线 + 色散 + 噪点 |

**不要**在 `line` 里写阿拉伯数字（"1024"），写成"一千零二十四"，避免 TTS 读法不可控。

## 创作口径（决定好不好看，不是技术问题）

1. **10 秒内抛钩子**：一个异常数字、一句禁忌、一个反常画面。不要铺垫世界观。
2. **一句台词 = 一个镜头**：句子超过 20 字就拆开，观众跟不上也配不好音。
3. **每句结尾是"能拍出来的东西"**（灯亮、门开、饭凉、备注多一行），不要写"他很难过"。
4. **结尾回收开头**：开头埋的物件/台词，最后要给一个反向或呼应。
5. **运镜要有区别**：连续三镜不要同一种运动，快慢靠 `gap_after` 和镜头时长对比。
6. **画面禁文字**：`style` 里写死"不出现可辨认文字"，模型画中文必乱码。
7. **角色一致性靠逐字复述**：同一角色每次出场，发型/疤痕/衣服的描述一字不改。

## 时长怎么控

时间线是**算出来的**，不是配出来的：

```text
分镜时长 = 该句配音真实时长 + gap_after
总长     = lead_in + Σ分镜时长 + tail
```

配音时长由 `ffprobe` 读，所以改一句词，整片自动重排。
超过 120s 脚本会告警；要压时长优先砍 `gap_after` 和镜头数，不要压语速。

## 合成阶段的四个硬点（错了返工很贵）

1. **叠化补偿**：`clip 时长 = 分镜时长 + overlap`，最后一段不加。不做的话画面会越跑越快。
2. **字幕颜色** `&HAABBGGRR&`；改局部色用 `\1c&H..&`（`\color` 是非法标签，会静默变黑）。
3. **字幕断句**：先按标点切、再合并，`hard` 阈值内不要硬切数字。
4. **响度**：`loudnorm` 到 −17 再 `+2.2dB`，实测落在 −16.5 LUFS，TP −2.0。

细节命令与原理见 `reference\ffmpeg-cheatsheet.md`；报错按 `reference\troubleshooting.md` 查。

## 质检（交付前逐条过）

```powershell
# 时长/规格
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height -of default=nw=1 成片.mp4
# 响度（目标 −16~−14 LUFS，TP ≤ −1）
ffmpeg -hide_banner -i 成片.mp4 -af loudnorm=print_format=summary -f null NUL
# 抽帧看字幕与转场（至少 5 个时间点）
ffmpeg -y -ss 8 -i 成片.mp4 -frames:v 1 check.jpg
# 坏帧自检（无输出=通过）
ffmpeg -v error -i 成片.mp4 -f null NUL
# 配音回听（必须用 TTS 的 python；核对有没有串行/吞字）
& "<tts_python>" "$S\scripts\qa_asr.py" --project $P
```

- [ ] 总时长 ≤ 120s（或用户指定）
- [ ] −16±1 LUFS，TP ≤ −1
- [ ] 首帧标题、中段字幕、末帧落版都正常
- [ ] 字幕没有把数字/词语切两半
- [ ] 解码零报错、ASR 转写与台词一致

## 交付物

成片 mp4、封面 jpg、`shots.json`、`build\subs.ass`（可作软字幕）、发布文案
（标题 3 选 1 + 简介 + 话题 + 数据依据 + 复现命令）。

## 能力边界（必须如实告知）

- 画面是**静态图 + 运镜**，不是视频生成：没有人物走动、没有口型、没有真实物理交互。
- 配音是**音色克隆**，不是真人；情绪靠标点与停顿，高潮句建议真人补录。
- 雨声是程序化噪声（pink noise + 滤波），不是实录音效。
- 要"真运动"只能接视频模型（可灵 / 万相 / Seedance），成本按秒计费，是这套的 10 倍起。
