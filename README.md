# Comfyui-Luck gpt-2.0

API易 GPT 图像模型的 ComfyUI 自定义节点包，当前包含两个独立节点：

| 节点 | 模型 | 适合场景 | 尺寸控制 |
|---|---|---|---|
| `Comfyui-Luck gpt-2.0 all` | `gpt-image-2-all` | 便宜、快、中文友好、文生图/改图/多图融合 | 只能把比例写进 prompt |
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

## 节点 2：Comfyui-Luck gpt-image-2

使用官方契约的 `gpt-image-2`。

特点：

- 真正传 `size` 参数，`size_ratio (尺寸/比例)` 一栏同时展示像素尺寸和比例。
- `quality`：`auto`、`low`、`medium`、`high`。
- `output_format`：`png`、`jpeg`、`webp`。
- `output_compression`：`jpeg` / `webp` 时可用，范围 0-100。
- `background`：`auto` 或 `opaque`，不提供 `transparent`，避免 API 报错。
- 支持最多 5 张参考图。
- 支持可选 `mask` 局部重绘，透明区域 = 要重绘，不透明区域 = 保留。

预设/便捷尺寸：

| size | 含义 |
|---|---|
| `auto (自动)` | 模型自适应 |
| `1024x1024 (1:1 方形)` | 1K 方形 |
| `1536x1024 (3:2 横版)` | 1K 横版 |
| `1024x1536 (2:3 竖版)` | 1K 竖版 |
| `2048x2048 (1:1 2K 方形)` | 2K 方形 |
| `2048x1152 (16:9 2K 横版)` | 2K 横版 |
| `3840x2160 (16:9 4K 横版, 实验)` | 4K 横版，超过 2560x1440 总像素量，官方提示为实验性 |
| `2160x3840 (9:16 4K 竖版, 实验)` | 4K 竖版，超过 2560x1440 总像素量，官方提示为实验性 |
| `3072x1024 (3:1 超宽, 合法边界)` | 合法的 3:1 边界便捷项 |
| `1024x3072 (1:3 长竖, 合法边界)` | 合法的 1:3 边界便捷项 |
| `custom (自定义宽x高)` | 使用 `custom_size` |

`custom_size` 必须同时满足：

- 最大边 <= 3840px。
- 宽和高都是 16 的倍数。
- 长边/短边 <= 3:1，也就是说 3:1 和 1:3 都可以，超过不行。
- 总像素在 655,360 到 8,294,400 之间。

`custom_size` 只在 `size_ratio` 选择 `custom (自定义宽x高)` 时填写，格式如 `1600x1200`、`3072x1024`、`1024x3072`。选择其他预设时会忽略这个输入框。

说明：

- `gpt-image-2` 返回的 `b64_json` 是纯 base64，不带 `data:image/...;base64,` 前缀；节点会自动解码成 ComfyUI 图片。
- 节点不会发送 `input_fidelity`。
- 节点不提供 `background=transparent`。
- `moderation` 只在文生图请求里发送，编辑请求不发送，减少参数校验风险。
- 推荐超时：`360` 秒。

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
- 一个 `gpt-image-2` 示例，使用真实 `size=2048x1152`、`quality=high`、`output_format=jpeg`。
- 中文 Note 节点，说明两个渠道怎么选、比例前置写法、真实尺寸控制和图片编辑/mask 用法。

分享工作流前请清空 API Key。

## 常见问题

### gpt-image-2-all 能不能硬控 2K / 4K？

不能。`gpt-image-2-all` 没有 `size` 参数，2K / 4K 只能作为 prompt 描述，无法保证输出像素。当前节点按你的要求只前置官方推荐比例写法，不再额外加入噪音尺寸描述。

### 哪个节点能真实控制分辨率？

用 `Comfyui-Luck gpt-image-2`。它会真正向 API 传 `size`，例如 `2048x1152`、`3840x2160`、`3072x1024`，或合法的 `custom_size`。

### 加载旧工作流报 `Value 3 smaller than min of 30`？

这是旧工作流 widget 顺序不匹配导致的：`retry_times=3` 被错读成了 `timeout_seconds=3`。请使用当前 `example_workflow.json`，或重新添加节点。
