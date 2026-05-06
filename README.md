# Comfyui-Luck gpt-2.0

API易 GPT 图像模型的 ComfyUI 自定义节点包，当前包含三个独立节点：

| 节点 | 模型 | 适合场景 | 尺寸控制 |
|---|---|---|---|
| `Comfyui-Luck gpt-2.0 all` | `gpt-image-2-all` | 便宜、快、中文友好、文生图/改图/多图融合 | 只能把比例写进 prompt |
| `Comfyui-Luck gpt-image-2-vip` | `gpt-image-2-vip` | 固定 `$0.03/张`、需要 30 档尺寸或 4K | 真正传 30 档 `size` API 参数 |
| `Comfyui-Luck gpt-image-2` | `gpt-image-2` | 需要真实 size、2K/4K、自定义尺寸、quality、mask | 真正传 `size` API 参数 |

## 安装

1. 把整个目录复制到 ComfyUI 的 `custom_nodes` 目录。
2. 安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

3. 重启 ComfyUI，搜索 `Comfyui-Luck`。

## 节点 1：Comfyui-Luck gpt-2.0 all

使用 `gpt-image-2-all`。

特点：

- 统一按次计费，约 `$0.03/张`。
- ChatGPT 网页线，约 30-60 秒，出图较快。
- 支持文生图、单图改图、多图融合、自然语言改图。
- 默认走 API易主推的 `POST /v1/chat/completions`，提示词遵循更好。
- 可切到 `images_api (兼容)`，走 `/v1/images/generations` 或 `/v1/images/edits`。
- 不支持真实 `size`、`quality`、`n`、`aspect_ratio` API 字段，节点不会发送这些字段。

比例控制只做很短的 prompt 前置，不加额外噪音：

| 需求 | 前置写法 |
|---|---|
| 方形 | `1024×1024 方图 / 1:1 方形构图` |
| 横版 | `横版 16:9 / 宽屏 16:9 电影画幅` |
| 竖版 | `竖版 9:16 / 手机海报 9:16` |
| 超宽横幅 | `横幅 21:9 超宽银幕` |
| 经典印刷 | `4:3 标准画幅` 或 `3:2 经典画幅` |

说明：

- 这是提示词控制，不是硬尺寸控制。
- `response_format` 只在 `images_api (兼容)` 端点里发送。
- 默认 `chat_completions (推荐)` 端点会从 `choices[0].message.content` 里提取图片 URL 或 data URL。
- URL 输出通常是临时 CDN 链接，约 1 天有效；需要长期保存时请尽快转存。
- 推荐超时：`300` 秒。
- `408`、`429`、`5xx` 会按 `retry_times` 自动重试。

## 节点 2：Comfyui-Luck gpt-image-2-vip

使用 `gpt-image-2-vip`。

特点：

- 统一按次计费，约 `$0.03/张`，所有 size 同价。
- Codex 官逆线，约 90-150 秒，适合必须锁定尺寸或需要 4K 的场景。
- 支持文生图、单图改图、多图融合、自然语言改图。
- 支持 `chat_completions (推荐)` 与 `images_api (兼容)` 两种端点。
- 真正发送 `size` 字段；不支持 `quality` 和 `n`，节点不会发送这些字段。
- `b64_json` 已带 `data:image/png;base64,` 前缀，节点会自动兼容解码。

尺寸换算：

| vip_aspect_ratio | 1K Fast | 2K Recommended | 4K Detail |
|---|---:|---:|---:|
| `1:1` | `1280x1280` | `2048x2048` | `2880x2880` |
| `2:3` | `848x1280` | `1360x2048` | `2336x3520` |
| `3:2` | `1280x848` | `2048x1360` | `3520x2336` |
| `3:4` | `960x1280` | `1536x2048` | `2480x3312` |
| `4:3` | `1280x960` | `2048x1536` | `3312x2480` |
| `4:5` | `1024x1280` | `1632x2048` | `2560x3216` |
| `5:4` | `1280x1024` | `2048x1632` | `3216x2560` |
| `9:16` | `720x1280` | `1152x2048` | `2160x3840` |
| `16:9` | `1280x720` | `2048x1152` | `3840x2160` |
| `21:9` | `1280x544` | `2048x864` | `3840x1632` |

说明：

- 节点会把上表解析成真实 `size` 字段发送给 API。
- `gpt-image-2-vip` 不接受表外尺寸；需要任意合法自定义尺寸时，请使用 `Comfyui-Luck gpt-image-2`。
- 推荐超时：`300` 秒。
- `408`、`429`、`5xx` 会按 `retry_times` 自动重试。

## 节点 3：Comfyui-Luck gpt-image-2

使用官方契约的 `gpt-image-2`。

特点：

- 真正传 `size` 参数，面板按 Nano 风格拆成 `image_size (分辨率)` + `aspect_ratio (宽高比)`。
- `quality`：`auto`、`low`、`medium`、`high`。
- `output_format`：`png`、`jpeg`、`webp`。
- `output_compression`：`jpeg` / `webp` 时可用，范围 0-100。
- 支持最多 5 张参考图。
- 支持可选 `mask` 局部重绘，透明区域 = 要重绘，不透明区域 = 保留。

尺寸换算：

| aspect_ratio | 1K | 2K | 4K |
|---|---:|---:|---:|
| `AUTO` | 不传 size | 不传 size | 不传 size |
| `1:4` | `480x1440` | `672x2016` | `1280x3840` |
| `4:1` | `1440x480` | `2016x672` | `3840x1280` |
| `1:8` | `480x1440` | `672x2016` | `1280x3840` |
| `8:1` | `1440x480` | `2016x672` | `3840x1280` |
| `1:1` | `1024x1024` | `2048x2048` | `2880x2880` |
| `2:3` | `768x1152` | `1440x2160` | `2304x3456` |
| `3:2` | `1152x768` | `2160x1440` | `3456x2304` |
| `3:4` | `768x1024` | `1536x2048` | `2448x3264` |
| `4:3` | `1024x768` | `2048x1536` | `3264x2448` |
| `4:5` | `768x960` | `1536x1920` | `2304x2880` |
| `5:4` | `960x768` | `1920x1536` | `2880x2304` |
| `9:16` | `720x1280` | `1152x2048` | `2160x3840` |
| `16:9` | `1280x720` | `2048x1152` | `3840x2160` |
| `21:9` | `1344x576` | `2464x1056` | `3808x1632` |

说明：

- `aspect_ratio` 列表参考 Nano 节点：`AUTO`、`1:4`、`4:1`、`1:8`、`8:1`、`1:1`、`2:3`、`3:2`、`3:4`、`4:3`、`4:5`、`5:4`、`9:16`、`16:9`、`21:9`。
- `auto (不传size)` 或 `aspect_ratio=AUTO` 会让 API 自适应。
- `gpt-image-2` 官方限制长边/短边 <= 3:1，所以 `1:4`、`4:1`、`1:8`、`8:1` 会自动收敛到最接近的合法边界尺寸，不会硬传非法比例。
- `4K` 档位尽量取合法大尺寸；`4K + 1:1` 不是 `3840x3840`，因为总像素会超官方上限，所以使用 `2880x2880`。
- 超过 `2560x1440` 总像素量的输出，官方提示属于实验性，可能更慢或更容易超时。

`custom_size` 只在 `image_size` 选择 `custom (自定义)` 时填写，格式如 `1600x1200`、`3072x1024`、`1024x3072`。选择 1K/2K/4K 时会忽略这个输入框。

`custom_size` 约束：

- 最大边 <= 3840px。
- 宽和高都是 16 的倍数。
- 长边/短边 <= 3:1，也就是说 3:1 和 1:3 都可以，超过不行。
- 总像素在 655,360 到 8,294,400 之间。

说明：

- `gpt-image-2` 返回的 `b64_json` 是纯 base64，不带 `data:image/...;base64,` 前缀；节点会自动解码成 ComfyUI 图片。
- 节点不会发送 `input_fidelity`。
- 节点主面板不再显示 `background` / `moderation`，默认不传，使用 API 默认值。
- 推荐超时：`360` 秒。
- `408`、`429`、`5xx` 会按 `retry_times` 自动重试。`408 Timeout` 通常是 APIYi 上游生成任务超时，不是节点参数填错。

`background` / `moderation` 原本的作用：

- `background`: OpenAI Images API 的背景控制字段。`gpt-image-2` 不支持 `transparent`，而 `auto` / `opaque` 对大多数普通出图区别不明显，所以节点默认不传。
- `moderation`: 文生图审核强度，通常是 `auto` 或 `low`。它不属于图片编辑接口的核心字段，日常使用默认即可，所以节点主面板不再暴露。

## API 域名

可选域名：

- 主域名：`https://api.apiyi.com`
- 备用：`https://vip.apiyi.com`
- 备用：`https://b.apiyi.com`

鉴权格式：

```text
Authorization: Bearer YOUR_API_KEY
```

## 示例工作流

打开 `example_workflow.json`。

里面包含：

- 一个 `gpt-image-2-all` 示例，默认使用推荐的 chat/completions 端点。
- 一个 `gpt-image-2-vip` 示例，使用 `image_size=2K Recommended` + `aspect_ratio=16:9`，发送 `size=2048x1152`。
- 一个 `gpt-image-2` 示例，使用真实 `size=2048x1152`、`quality=high`、`output_format=jpeg`。
- 中文 Note 节点，说明三个模型怎么选、比例前置写法、VIP 30 档 size、真实尺寸控制和图片编辑/mask 用法。

分享工作流前请清空 API Key。

## 常见问题

### gpt-image-2-all 能不能硬控 2K / 4K？

不能。`gpt-image-2-all` 没有 `size` 参数，2K / 4K 只能作为 prompt 描述，无法保证输出像素。当前节点按你的要求只前置官方推荐比例写法，不再额外加入噪音尺寸描述。

### gpt-image-2-vip 怎么用？

添加 `Comfyui-Luck gpt-image-2-vip` 节点，再选 `image_size` 和 `aspect_ratio`。例如 `2K Recommended + 16:9` 会发送 `size=2048x1152`；`4K Detail + 16:9` 会发送 `size=3840x2160`。

### 哪个节点能真实控制分辨率？

如果只需要 30 档常见尺寸并想固定 `$0.03/张`，用 `Comfyui-Luck gpt-image-2-vip`。如果需要任意合法自定义尺寸、`quality` 或 mask 局部重绘，用 `Comfyui-Luck gpt-image-2`。例如 `image_size=2K` + `aspect_ratio=4:3` 会真正向 API 传 `size=2048x1536`。

### 加载旧工作流报 `Value 3 smaller than min of 30`？

这是旧工作流 widget 顺序不匹配导致的：`retry_times=3` 被错读成了 `timeout_seconds=3`。请使用当前 `example_workflow.json`，或重新添加节点。
