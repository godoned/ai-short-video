# 故障排查（按症状查）

## 出图相关

**`HTTP 401` / `AuthenticationError`**
Key 没读到。检查 `config.json` 的 `ark_api_key_file` 指向的 `.env` 里有没有 `ARK_API_KEY=`，
或直接设环境变量 `ARK_API_KEY`。注意 `.env` 必须是 UTF-8。

**`InvalidParameter: size`**
`image_size` 只能是 `1K` / `1.5K` / `2K`，或 `宽x高` 且总像素在 921600–4624220 之间、宽高比 1/16–16。
9:16 竖屏用 `1584x2816`（2K 档）。

**图上出现乱码文字**
模型画中文必糊。两个办法：提示词里写死"画面中不出现任何可辨认的文字"；或者让它写英文/数字。
已经生成了就重出，不要试图用后期抹。

**人物前后不一致**
`style` 只管质感，不管长相。让角色每次出场的描述**逐字相同**（发型、疤、衣服颜色），
必要时用 `--only` 单张重出，而不是整批重来。

## 配音相关

**`ModuleNotFoundError: torch` / `No module named voxcpm`**
用错了解释器。必须用 TTS 自带的 python：
`"D:\tts语音ai本地部署\win-unpacked\python\build_venv\python\python.exe" tts_batch.py ...`

**`RuntimeError: ... kaldi-io ... traditional_to_simple.fst`**
这是文本正则化组件（wetext）读不了含中文的路径。脚本已经默认 `do_normalize=False`，
如果你的项目改过这个参数，改回来即可。

**`OSError: Not found: "...\chn_jpn_yue_eng_ko_spectok.bpe.model"`**
sentencepiece 同样读不了中文路径。建一个 ASCII 目录联接：
```powershell
New-Item -ItemType Junction -Path "D:\tts_ascii" -Target "D:\tts语音ai本地部署"
```
然后确保 `config.json` 的 `tts_ascii_root` 指向 `D:\tts_ascii\win-unpacked\python`。

**语速忽快忽慢**
`cfg_value` 默认 2.0。想更稳就降到 1.6–1.8；想更有起伏就升到 2.2。别超过 2.5，会飘。
长句尽量用逗号断开，模型对长句的节奏控制最差。

## 合成相关

**`Filtergraph ... not connected`**
`-filter_complex` 里某个 `[标签]` 没被消费。常见于 asplit 之后只用了一路。
要么删掉多余的 asplit，要么把另一路接到 `-map` 或用 `anullsink`。

**画面比声音快/慢，越到后面差得越多**
叠化补偿漏了。规则：`clip 时长 = 分镜时长 + overlap`（**最后一段不加**）。
漏一段就差 0.35 秒，13 段就是 4.5 秒。

**字幕是黑色 / 看不见**
颜色写错了。ASS 是 `&HAABBGGRR&`（不是 `#RRGGBB`），改局部颜色用 `\1c&H...&`，
**`\color` 不是合法标签**，写了会被静默忽略并回落到黑色。

**字幕把数字/词语切成两半**
断句算法问题。`split_phrases()` 先按标点切、再合并到 ≤limit 字，只有超过 `hard` 才硬切。
把 `hard` 调大（比如 22）可以少切，代价是偶尔出现两行字幕。

**中文字幕变成方框**
`subtitle_font` 写的字体系统里没有。Windows 上 `Microsoft YaHei` / `SimHei` 都安全。

**视频在手机/网页上不能播**
漏了 `-pix_fmt yuv420p` 或 `-movflags +faststart`。两者脚本都默认加了。

## 交付前自检

```powershell
# 时长/分辨率/编码
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,width,height -of default=nw=1 成片.mp4
# 响度（目标 -16 ~ -14 LUFS，TP ≤ -1）
ffmpeg -hide_banner -i 成片.mp4 -af loudnorm=print_format=summary -f null NUL
# 抽帧看字幕
ffmpeg -y -ss 8 -i 成片.mp4 -frames:v 1 check.jpg
# 整片解码，无输出 = 无坏帧
ffmpeg -v error -i 成片.mp4 -f null NUL
```
