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
4. Choose `image_size (分辨率)` and `aspect_ratio (宽高比)`. The node writes the matching size/aspect phrase at the beginning of the prompt.
5. Use `response_format (响应格式)`:
   - `url`: returns and downloads the R2 CDN image URL.
   - `b64_json`: decodes the API base64 data URL directly.

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

## Example Workflow

Open `example_workflow.json` in this folder. It contains Note nodes with usage comments and a basic text-to-image example wired to `PreviewImage`.
