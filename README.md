# Comfyui-Luck gpt-2.0

ComfyUI custom node for APIYi `gpt-image-2-all`.

`Comfyui-Luck gpt-2.0` supports text-to-image, single image editing, multi-image fusion, and natural-language image editing. The model does not accept `size`, `n`, `quality`, or `aspect_ratio` API fields, so this node converts size and aspect controls into a prompt prefix.

## Install

1. Put this folder into ComfyUI `custom_nodes`.
2. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

3. Restart ComfyUI and search for `Comfyui-Luck gpt-2.0`.

## Usage

1. Fill `api_key (API密钥)` with your APIYi key.
2. Write the generation or editing instruction in `prompt (提示词)`.
3. Keep `mode (模式)` as `AUTO` for normal use:
   - No image input: text-to-image.
   - Any `image_01` to `image_14` input: image editing or multi-image fusion.
4. Choose `image_size (分辨率)` and `aspect_ratio (宽高比)`. The node writes a strong size/aspect control block at the beginning of the prompt.
5. Use `response_format (响应格式)`:
   - `url`: returns and downloads the R2 CDN image URL.
   - `b64_json`: decodes the API base64 data URL directly.

## API Calls

This node uses APIYi OpenAI-compatible image endpoints:

- Text-to-image: `POST https://api.apiyi.com/v1/images/generations`
- Image edit / multi-image fusion: `POST https://api.apiyi.com/v1/images/edits`
- Backup gateways: `https://vip.apiyi.com/v1` and `https://b.apiyi.com/v1`

Authentication:

```text
Authorization: Bearer YOUR_API_KEY
```

Text-to-image JSON body:

```json
{
  "model": "gpt-image-2-all",
  "prompt": "横版 16:9 电影画幅，黄昏时的海边老灯塔",
  "response_format": "url"
}
```

Image edit / fusion form body:

```text
model=gpt-image-2-all
prompt=把图1的人物放进图2的场景，参考图3的画风
response_format=url
image[]=ref1.png
image[]=ref2.png
image[]=ref3.png
```

Allowed request fields for `gpt-image-2-all` are only:

- `model`
- `prompt`
- `response_format`
- repeated `image[]` in edit mode

Do not send `size`, `n`, `quality`, or `aspect_ratio`; the API may reject those fields. This node keeps size and aspect controls in the UI, then writes them into the prompt prefix.

The actual prompt sent to the API starts like this when `image_size=2K` and `aspect_ratio=16:9`:

```text
【画幅与尺寸要求】1920x1080 横版，宽屏 16:9 电影画幅。请严格按这个尺寸倾向和画幅比例构图，不要生成其他比例；这只是生成控制指令，不要把这些文字写进画面。

你的原始提示词...
```

Because the API does not expose a real `size` field for `gpt-image-2-all`, this is prompt-based control. It improves compliance, but the remote model can still occasionally return a nearby adaptive size.

## Size And Aspect Prompt Mapping

| Aspect | AUTO size prompt | 1K | 2K | 4K |
|---|---|---|---|---|
| 1:1 | 1024x1024 square / 1:1 | 1024x1024 | 2048x2048 | 4096x4096 |
| 16:9 | widescreen 16:9 cinematic | 1024x576 | 1920x1080 | 3840x2160 |
| 9:16 | vertical 9:16 phone poster | 576x1024 | 1080x1920 | 2160x3840 |
| 21:9 | ultra-wide 21:9 banner | 1344x576 | 2560x1080 | 5120x2160 |
| 4:3 | 4:3 standard frame | 1024x768 | 2048x1536 | 4096x3072 |
| 3:2 | 3:2 classic frame | 1152x768 | 2160x1440 | 4320x2880 |

## Notes

- The node sends only allowed API fields: `model`, `prompt`, `response_format`, and repeated `image[]` for edit mode.
- `seed (种子)` is a ComfyUI UI control only and is not sent to the API.
- `timeout_seconds (超时秒数)` defaults to 120 seconds, matching the API recommendation.
- Share workflows only after clearing your API key.

## Troubleshooting

If ComfyUI reports:

```text
Value 3 smaller than min of 30
timeout_seconds (超时秒数)
```

you are loading an older workflow where the seed control value is missing. The widget values after `seed` shift left, so `retry_times=3` is incorrectly read as `timeout_seconds=3`.

Fix: use the updated `example_workflow.json`, or open the node and set `timeout_seconds (超时秒数)` back to `120` and `retry_times (重试次数)` to `3`.

## Example Workflow

Open `example_workflow.json` in this folder. It contains Note nodes with usage comments and a basic text-to-image example wired to `PreviewImage`.
