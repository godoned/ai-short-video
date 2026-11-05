# FFmpeg 速查（这条管线实际用到的部分）

## 命令骨架

```text
ffmpeg [全局] [输入] [滤镜] [映射+编码] [输出]
```

```powershell
ffmpeg -y -hide_banner -loglevel error `
  -i a.mp4 -i b.mp4 `
  -filter_complex "[0:v][1:v]xfade=transition=fade:duration=0.35:offset=7.8[x1]" `
  -map "[x1]" -map 2:a `
  -c:v libx264 -crf 19 -pix_fmt yuv420p -movflags +faststart out.mp4
```

| 参数 | 作用 | 本管线取值 |
|---|---|---|
| `-vf` / `-filter_complex` | 单路 / 多路滤镜（`[标签]` 连线） | 运镜用 `-vf`，叠化和混音用 `-filter_complex` |
| `-map` | 选流 | `-map "[vout]" -map N:a` |
| `-crf` | 质量，越小越清晰 | 中间 16，成片 19 |
| `-preset` | 速度档 | 中间 veryfast，成片 medium |
| `-pix_fmt yuv420p` | 兼容性 | 必写 |
| `-movflags +faststart` | 网页秒开 | 成片必写 |

## 静图 → 视频流

```powershell
ffmpeg -framerate 30 -loop 1 -t 8 -i img.png -r 30 out.mp4
```

## 运镜 zoompan

原理：每帧按 `z` 放大 → 从 `(x,y)` 裁一块 `iw/z × ih/z` 的窗口 → 缩放成 `s`。

```powershell
# 推
zoompan=z='1+0.10*(on/N)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30
# 拉
zoompan=z='1.12-0.10*(on/N)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30
# 横移（z 固定）
zoompan=z='1.08':x='(iw-iw/zoom)*(on/N)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30
# 竖摇
zoompan=z='1.08':x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(on/N)':d=1:s=1080x1920:fps=30
```

- `on` 当前帧、`N` 总帧数，`on/N` 就是 0→1 进度
- `x/y` 是**裁切框左上角**，居中要写 `iw/2-(iw/zoom/2)`
- 裁之前把图放大会更锐：`scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840`
- 缓动（起停软）：把 `on/N` 换成 `p*p*(3-2*p)`

## 转场 xfade

```powershell
[0:v][1:v]xfade=transition=fade:duration=0.35:offset=7.8[x1]
```

`fade` 叠化 / `fadeblack` 黑场 / `wipeleft` 划像 / `dissolve` 溶解。

**时长补偿**：叠化会吃掉 overlap 那么长。必须给每段补回，最后一段不补：

```text
clip 时长 = 分镜时长 + overlap
offset_i  = 前 i 段累计 − overlap
```

不补就会画面越跑越快，十几段后差好几秒，字幕全错位。

## 字幕 ASS

```powershell
ffmpeg -i in.mp4 -vf "ass=subs.ass" -c:v libx264 -crf 19 out.mp4
```

```ini
[Script Info]
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Microsoft YaHei,54,&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,1,0,0,0,100,100,1.5,0,1,3.2,1.6,2,90,90,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:08.38,0:00:15.90,Sub,,0,0,0,,{\fad(120,120)}收件人，林小满。
```

- 颜色 `&HAABBGGRR&`（**和 #RRGGBB 反着**）；局部改色用 `\1c&H...&`，`\color` 是非法的
- `Alignment` 小键盘：2 底部居中 / 5 正中；`MarginV` 底部对齐时是离底边距离
- 标签：`\fad(in,out)` `\pos(x,y)` `\fs80` `\1c&H..&` `\N`
- 时间格式 `h:mm:ss.cc`

## 音频

```powershell
# 摆位置
[0:a]adelay=1500:all=1[v0]
# 混（normalize=0 必须写，否则除以路数，声音消失）
[v0][v1]amix=inputs=2:duration=longest:normalize=0
# 人声一开口雨声退（第1路被压，第2路当开关）
[rain][voice]sidechaincompress=threshold=0.035:ratio=5:attack=150:release=700[rduck]
# 统一响度
[vout][rduck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-17:TP=-2.0:LRA=11,aresample=48000,volume=2.2dB,alimiter=limit=0.95
```

- 合成噪声：`anoisesrc=color=pink:amplitude=0.30` + `highpass=420` + `lowpass=6800` + `volume=0.055` ≈ 雨声
- `I` 目标 −16~−14 LUFS，`TP` ≤ −1 dBTP，`LRA` 10–12
- 两遍 loudnorm 更准：先 `print_format=json` 测，再 `measured_I=...:linear=true`

## 质感

```powershell
eq=saturation=0.98:contrast=1.03:brightness=0.012,
noise=alls=6:allf=t+u,
vignette=angle=PI/5.2,
fade=t=in:st=0:d=1.2,
fade=t=out:st=T-1.6:d=1.5
```

这些要放在叠化**之后**，否则每段各加一层，接缝处颗粒和暗角会跳。

## 排错

```powershell
ffprobe -v error -show_entries format=duration -of csv=p=0 x.mp4       # 时长
ffmpeg -hide_banner -i x.mp4 -af loudnorm=print_format=summary -f null NUL  # 响度
ffmpeg -y -ss 8 -i x.mp4 -frames:v 1 check.jpg                          # 抽帧
ffmpeg -v error -i x.mp4 -f null NUL                                    # 坏帧自检
```
