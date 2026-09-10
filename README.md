# Comfyui-Luck gpt-2.0

API易 GPT 图像模型的 ComfyUI 自定义节点包，当前包含出图节点和提示词控制节点：

> **重要说明**
>
> API易图像模型能力会随上游状态变化，尤其是 `gpt-image-2-vip` 的 `size` 参数、输出分辨率和可用端点。本文档按当前 API易公开文档校准；如遇到接口行为变化、节点报错或文档不一致，请优先到 [GitHub Issues](https://github.com/luckdvr/Comfyui-Luck-gpt2.0/issues) 反馈，并附上节点名称、模型、端点、报错信息和 ComfyUI 控制台日志。

| 节点 | 模型 | 适合场景 | 尺寸控制 |
|---|---|---|---|
| `Comfyui-Luck gpt-2.0 all` | `gpt-image-2-all` | 便宜、快、中文友好、文生图/改图/多图融合 | 只能把比例写进 prompt |
| `Comfyui-Luck gpt-image-2-vip` | `gpt-image-2-vip` | 固定 `$0.03/张`、Codex 官逆线 | 当前 `size` 失效，仅用 prompt 控比例 |
| `Comfyui-Luck gpt-image-2` | `gpt-image-2` / `gpt-image-2.5-flare` / `gpt-image-2.5-sunburst` | 需要真实 size、2K/4K、自定义尺寸、quality、mask | 真正传 `size` API 参数 |

| 提示词节点 | 默认模型 | 适合场景 |
|---|---|---|
| `GPT-Image-2 文生图提示词控制器` | `gemini-3.5-flash` | 将文字需求整理为更适合 GPT-Image-2 的结构化生图提示词 |
| `图生图提示词控制器` | `gemini-3.5-flash` | 读取最多 5 张参考图和可选主体图，生成带风格、构图、版式约束的出图提示词 |
| `文本停留编辑器` | - | 工作流执行中暂停，手动编辑文本后继续 |

提示词控制器使用 API易 OpenAI 兼容 `POST /v1/chat/completions`，和 Luck 出图节点一样使用 `Authorization: Bearer YOUR_API_KEY`。模型下拉包含 `gemini-3.5-flash`、`gpt-5.5`、`gpt-4o`、`gpt-4.1-mini`、`gemini-2.5-flash`、`gemini-2.5-pro`。

`图生图提示词控制器` 的 `reference_image_01` 必填，`reference_image_02` 到 `reference_image_05` 可选；多张参考图会一起发送给多模态模型综合分析。`subject_image` 仍然是可选主体图，用来锁定最终画面的核心产品或人物。

多图参考的推荐接法：

- 只把图片接到 `图生图提示词控制器`：只做图像理解和提示词增强，后面可以按文生图使用优化后的 prompt。
- 同一批图片同时接到后面的出图节点：才是真正的多图参考 / 多图编辑 / 多图融合。
- 5 张图以内，优先接 `图生图提示词控制器` 一起分析，再把同一批图接到后面的出图节点。
- `Comfyui-Luck gpt-image-2` 支持最多 16 张参考图，并支持真实 size、quality 和 mask；`gpt-2.0 all` / `gpt-image-2-vip` 目前最多支持 `image_01` 到 `image_14`。

完整链路示例：

```text
5张参考图
  ├─ 接到 图生图提示词控制器 reference_image_01~reference_image_05
  └─ 同时接到 Comfyui-Luck gpt-image-2 image_01~image_05

图生图提示词控制器 optimized_prompt
  └─ 接到 Comfyui-Luck gpt-image-2 prompt
```

如果其中一张图是必须锁定的主体图，可以额外接到 `subject_image`，并放在后面出图节点的 `image_01`。

暂停编辑后再出图的推荐接法：

```text
提示词控制器 optimized_prompt
  └─ 接到 文本停留编辑器 text_list

文本停留编辑器 edited_text
  └─ 接到 出图节点 prompt
```

`edited_text` 是单条字符串，适合接普通出图节点的 prompt。`edited_texts` 是列表输出，保留给批量文本工作流使用。

运行时请对最终 `PreviewImage` 或 `SaveImage` 发起队列执行。流程停在 `文本停留编辑器` 后，点击节点上的 `Continue` 即可让当前执行继续到后面的出图节点；不要再次点击主运行按钮，否则 ComfyUI 会重新排队并重新执行上游提示词增强。

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
- 默认走 API易当前更推荐的 Images API：`/v1/images/generations` 或 `/v1/images/edits`。
- 可切到 `chat_completions (对话/URL参考图)`，用于对话式调用或在线 URL 参考图场景。
- 不支持真实 `size`、`quality`、`n`、`aspect_ratio` API 字段，节点不会发送这些字段。

比例控制只做很短的 prompt 前置，不加额外噪音。`gpt-image-2-all` 不传真实 `size`，稳定度以 API易文档的实测前缀为准；其它比例只作为构图风格提示。

| 需求 | 前置写法 | 文档实测输出 |
|---|---|---:|
| 横版 | `横版 16:9` | 约 `1672x941` |
| 竖版 | `竖屏 9:16` | 约 `941x1672` |
| 标准横版 | `4:3` | 约 `1448x1086` |
| 标准竖版 | `3:4` | 约 `1086x1448` |
| 经典横版 | `3:2 尺寸` | 约 `1536x1024` |
| 经典竖版 | `2:3 尺寸` | 约 `1024x1536` |
| 长竖屏 | `2:5 竖屏` | 约 `793x1983` |
| 长横屏 | `5:2 横屏` | 约 `1983x793` |

说明：

- 这是提示词控制，不是硬尺寸控制。
- `response_format` 只在 Images API 端点里发送。
- `chat_completions` 端点会兼容解析 `choices[0].message.content` 里的图片 URL / data URL，也兼容 `data[].url` / `data[].b64_json`。
- URL 输出通常是临时 CDN 链接，约 1 天有效；需要长期保存时请尽快转存。
- 推荐超时：`300` 秒。
- `408`、`429`、`5xx` 会按 `retry_times` 自动重试。

## 节点 2：Comfyui-Luck gpt-image-2-vip

使用 `gpt-image-2-vip`。

特点：

- 统一按次计费，约 `$0.03/张`。
- Codex 官逆线，约 90-150 秒。
- 支持文生图、单图改图、多图融合、自然语言改图。
- 默认走 Images API；可切到 `chat_completions (对话/URL参考图)`。
- API易文档 2026-06-23 起提示：`size` 参数再次失效，目前仅自适应 1K，2K / 4K / 锁尺寸暂不生效。
- 本节点保留 `image_size` / `aspect_ratio` 控件兼容旧工作流，但当前默认不发送 `size`，只把比例写进 prompt 兜底。
- 不支持 `quality` 和 `n`，节点不会发送这些字段。
- `b64_json` 已带 `data:image/png;base64,` 前缀，节点会自动兼容解码。

说明：

- `image_size` 当前只保留为界面提示和旧工作流兼容值，不代表真实输出分辨率。
- 需要真实 `size`、`quality` 或 mask 局部重绘时，请使用 `Comfyui-Luck gpt-image-2`。
- 推荐超时：`300` 秒。
- `408`、`429`、`5xx` 会按 `retry_times` 自动重试。

## 节点 3：Comfyui-Luck gpt-image-2

支持 API易官转的 `gpt-image-2`、`gpt-image-2.5-flare` 和 `gpt-image-2.5-sunburst`。更新后重启 ComfyUI，在原节点的 `model (模型)` 下拉框切换即可。节点名称、ID、控件顺序和默认模型 `gpt-image-2` 保持不变，已有工作流不会自动切换模型或画质。

### GPT-Image 2.5（2026-09-10 更新）

按 [API易模型概览](https://docs.apiyi.com/api-capabilities/gpt-image-2/overview)，Flare 速度优先，Sunburst 更侧重画质和编辑精度。两款都支持文生图、图片编辑、16 张参考图和 mask；节点根据 `mode` 和参考图使用 [文生图接口](https://docs.apiyi.com/api-capabilities/gpt-image-2/text-to-image) 或 [图片编辑接口](https://docs.apiyi.com/api-capabilities/gpt-image-2/image-edit)。

模型下拉框同时提供 `gpt-image-2.5-flare-2026-09-08` 和 `gpt-image-2.5-sunburst-2026-09-08`，用于固定日期快照。

| 模型 | quality 可选值 |
|---|---|
| `gpt-image-2` | `auto` / `low` / `medium` / `high` |
| 两款 2.5（含日期版本） | `auto` / `low` / `medium` / `high` / `xhigh` / `max` |

注意：按 API易 2026-09-09 的同尺寸实测输出 token 量，2.5 的 `high` 对应旧版 `medium`，2.5 的 `max` 对应旧版 `high`；这不是逐像素画质相同的保证。迁移时请主动选择画质。`auto` 的费用与耗时可能变化，建议明确选档。旧模型选择 `xhigh/max`，或传入无效模型/画质时，节点会在发送请求前报错，不会静默降档。

特点：

- 真正传 `size` 参数，面板按 Nano 风格拆成 `image_size (分辨率)` + `aspect_ratio (宽高比)`。
- `quality` 按上表选择；`xhigh`、`max` 仅限 2.5。
- `output_format`：`png`、`jpeg`、`webp`。
- `output_compression`：`jpeg` / `webp` 时可用，范围 0-100。
- 支持最多 16 张参考图。
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
| `1:2` | `720x1440` | `1024x2048` | `1920x3840` |
| `2:1` | `1440x720` | `2048x1024` | `3840x1920` |
| `1:3` | `480x1440` | `672x2016` | `1280x3840` |
| `3:1` | `1440x480` | `2016x672` | `3840x1280` |
| `2:3` | `768x1152` | `1440x2160` | `2304x3456` |
| `3:2` | `1152x768` | `2160x1440` | `3456x2304` |
| `3:4` | `768x1024` | `1536x2048` | `2448x3264` |
| `4:3` | `1024x768` | `2048x1536` | `3264x2448` |
| `4:5` | `768x960` | `1536x1920` | `2304x2880` |
| `5:4` | `960x768` | `1920x1536` | `2880x2304` |
| `9:16` | `720x1280` | `1152x2048` | `2160x3840` |
| `16:9` | `1280x720` | `2048x1152` | `3840x2160` |
| `9:21` | `640x1488` | `960x2240` | `1648x3840` |
| `21:9` | `1344x576` | `2464x1056` | `3808x1632` |

说明：

- `aspect_ratio` 列表和提示词控制器保持一致：`AUTO`、`1:4`、`4:1`、`1:8`、`8:1`、`1:1`、`1:2`、`2:1`、`1:3`、`3:1`、`2:3`、`3:2`、`3:4`、`4:3`、`4:5`、`5:4`、`9:16`、`16:9`、`9:21`、`21:9`。
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

- 三款模型返回 `b64_json`，节点会自动解码成 ComfyUI 图片，也兼容带 data URL 前缀的结果。
- 节点不会发送 `response_format` 或 `input_fidelity`，避免接口拒绝请求。
- 节点主面板不再显示 `background` / `moderation`，默认不传，使用 API 默认值。
- 节点默认超时 `600` 秒；2.5 的 `xhigh/max`、2K/4K 或复杂编辑建议保留该值，必要时调高。同步请求在客户端超时后仍可能计费，自动重试可能产生额外费用；不希望自动重试时将 `retry_times` 设为 `1`。
- `408`、`429`、`5xx` 会按 `retry_times` 自动重试。`408 Timeout` 通常是 APIYi 上游生成任务超时，不是节点参数填错。

`background` / `moderation` 原本的作用：

- `background`: Images API 的背景控制字段，本节点默认不传。API易当前参数速查表与详细字段对 `transparent` 的说明不一致，本次未新增透明背景开关。
- `moderation`: 文生图审核强度，通常是 `auto` 或 `low`。它不属于图片编辑接口的核心字段，日常使用默认即可，所以节点主面板不再暴露。

## API 域名

可选域名：

- 主域名：`https://api.apiyi.com/v1`
- 国内备用 / 企业专用：`https://b.apiyi.com/v1`
- 全球直连 / 海外推荐：`https://vip.apiyi.com/v1`
- 兼容旧域名：`https://api.apiyi.com`、`https://b.apiyi.com`、`https://vip.apiyi.com`
- 兼容旧工作流：`http://api.apiyi.com:16888`、`http://b.apiyi.com:16888`

节点底层会兼容带 `/v1` 和不带 `/v1` 的 base url，并把超时拆成连接超时 `30` 秒 + 节点面板里的读取超时秒数，减少长耗时生成时的中断。

鉴权格式：

```text
Authorization: Bearer YOUR_API_KEY
```

## 示例工作流

打开 `example_workflow.json`。

里面包含：

- 一个 `gpt-image-2-all` 示例，默认使用推荐的 Images API 端点。
- 一个 `gpt-image-2-vip` 示例，保留 `image_size` / `aspect_ratio` 控件但不发送当前失效的 `size`。
- 一个 `gpt-image-2` 示例，使用真实 `size=2048x1152`、`quality=high`、`output_format=jpeg`。
- 中文 Note 节点，说明三个模型怎么选、All/VIP 的 prompt 比例兜底、真实尺寸控制和图片编辑/mask 用法。

分享工作流前请清空 API Key。

`example_workflow_gpt_image_2_5.json` 是独立的 2.5 示例：Flare 文生图 → Sunburst 编辑 → 预览。两处 API Key 均为空；运行整条链路会依次请求两款模型，各生成一张图片。默认 `1K + 1:1`、`quality=high`、超时 `600` 秒，并将 `retry_times=1` 以免演示时自动重复请求。需要最高档时手动改为 `max`。

## 开发验证

安装 `requirements.txt` 后运行：

```bash
python3 -m unittest discover -s tests -v
```

测试使用模拟接口，不调用收费服务，覆盖新模型与日期版本的请求字段、画质校验、多图/蒙版、图片解码和旧工作流兼容。实际 API 出图和完整 ComfyUI 界面仍需在对应环境验证。

## 常见问题

### gpt-image-2-all 能不能硬控 2K / 4K？

不能。`gpt-image-2-all` 没有 `size` 参数，2K / 4K 只能作为 prompt 描述，无法保证输出像素。当前节点只前置官方推荐比例写法，不额外加入噪音尺寸描述。

### gpt-image-2-vip 怎么用？

添加 `Comfyui-Luck gpt-image-2-vip` 节点后，`image_size` 和 `aspect_ratio` 仍可保留旧工作流习惯；但按 API易 2026-06-23 文档，`size` 当前失效，本节点不会发送 `size`，只把比例作为 prompt 前缀兜底。

### 哪个节点能真实控制分辨率？

如果需要真实 `size`、`quality` 或 mask 局部重绘，用 `Comfyui-Luck gpt-image-2`。`gpt-image-2-all` 和当前状态下的 `gpt-image-2-vip` 都只能用 prompt 控制比例，不能承诺像素级锁尺寸。

### 加载旧工作流报 `Value 3 smaller than min of 30`？

这是旧工作流 widget 顺序不匹配导致的：`retry_times=3` 被错读成了 `timeout_seconds=3`。请使用当前 `example_workflow.json`，或重新添加节点。

### 接入 `文本停留编辑器` 后，`gpt-image-2` 报 `Value not in list`？

这是把 `prompt` 转成输入口后，旧 workflow 少了一个 prompt 占位，导致后面的控件整体前移：例如 `mode` 被读成 `gpt-image-2`、`api_base` 被读成 `2K`、`image_size` 被读成 `16:9`。当前节点会在校验阶段放行，并在运行时自动把这些错位参数恢复；新 `example_workflow.json` 也已经补好占位。若界面上仍显示错位，重载当前工作流或重新添加 `Comfyui-Luck gpt-image-2` 节点即可。
