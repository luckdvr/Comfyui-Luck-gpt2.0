#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comfyui-Luck gpt-2.0 nodes for APIYi.

The gpt-image-2-all API does not accept size, n, quality, or aspect_ratio.
Composition controls are converted into a prompt prefix. The official
gpt-image-2 node exposes real size/quality/mask controls.
"""

import base64
import json
import re
import time
from io import BytesIO

import numpy as np
from PIL import Image
import requests
import torch


API_BASE_URLS = [
    "https://api.apiyi.com",
    "https://b.apiyi.com",
    "https://vip.apiyi.com",
]


AUTO_RATIO_PROMPTS = {
    "1:1": "1024×1024 方图 / 1:1 方形构图",
    "16:9": "横版 16:9 / 宽屏 16:9 电影画幅",
    "9:16": "竖版 9:16 / 手机海报 9:16",
    "21:9": "横幅 21:9 超宽银幕",
    "4:3": "4:3 标准画幅",
    "3:2": "3:2 经典画幅",
}


def tensor_to_png_bytes(tensor):
    """ComfyUI IMAGE tensor -> PNG bytes."""
    if tensor is None:
        raise ValueError("输入图像为空")

    single = tensor[0:1] if len(tensor.shape) == 4 else tensor.unsqueeze(0)
    arr = (single[0].cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def tensor_to_data_url(tensor):
    """ComfyUI IMAGE tensor -> PNG data URL."""
    return "data:image/png;base64," + base64.b64encode(tensor_to_png_bytes(tensor)).decode("utf-8")


def mask_to_png_bytes(mask):
    """ComfyUI MASK -> RGBA PNG mask for OpenAI Images edit.

    ComfyUI mask value 1 means edit area. OpenAI-style image masks use
    transparent pixels as edit area, so alpha is inverted.
    """
    if mask is None:
        return None

    if len(mask.shape) == 3:
        mask_np = mask[0].cpu().numpy()
    else:
        mask_np = mask.cpu().numpy()

    alpha = ((1.0 - mask_np) * 255).clip(0, 255).astype(np.uint8)
    height, width = alpha.shape
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[:, :, :3] = 255
    rgba[:, :, 3] = alpha

    buf = BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buf, format="PNG")
    return buf.getvalue()


def image_bytes_to_tensor(image_bytes):
    """Image bytes -> ComfyUI tensor (1,H,W,3)."""
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    arr = np.array(img).astype(np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0).float()


def b64_json_to_tensor(b64_json):
    """Decode API b64_json. APIYi may include a data URL prefix."""
    value = (b64_json or "").strip()
    if not value:
        raise ValueError("b64_json 为空")

    if "," in value and value.lower().startswith("data:"):
        value = value.split(",", 1)[1]

    return image_bytes_to_tensor(base64.b64decode(value))


def extract_image_references(text):
    """Extract image URLs and data URLs from chat completion text."""
    if not text:
        return []

    refs = []
    data_pattern = r"data:image/[A-Za-z0-9.+-]+;base64,[A-Za-z0-9+/=]+"
    url_pattern = r"https?://[^\s)\]\"']+\.(?:png|jpg|jpeg|webp)(?:\?[^\s)\]\"']*)?"

    refs.extend(re.findall(data_pattern, text))
    refs.extend(match[0] if isinstance(match, tuple) else match for match in re.findall(url_pattern, text, re.I))

    seen = set()
    unique_refs = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            unique_refs.append(ref)
    return unique_refs


def _validate_gpt_image2_size(size_value):
    if size_value == "auto":
        return size_value

    if not re.fullmatch(r"\d{3,4}x\d{3,4}", size_value):
        raise ValueError("size 必须类似 1600x1200，且宽高都是数字")

    width, height = [int(v) for v in size_value.split("x")]
    max_side = max(width, height)
    min_side = min(width, height)
    total_pixels = width * height

    if width % 16 != 0 or height % 16 != 0:
        raise ValueError("size 的宽和高都必须是 16 的倍数")
    if max_side > 3840:
        raise ValueError("size 最大边不能超过 3840px")
    if max_side / min_side > 3:
        raise ValueError("size 长边/短边不能超过 3:1，因此 3:1 和 1:3 可以，超过不行")
    if total_pixels < 655360 or total_pixels > 8294400:
        raise ValueError("size 总像素需在 655,360 到 8,294,400 之间")

    return f"{width}x{height}"


def normalize_size(size, custom_size=""):
    option = (size or "auto").strip().lower().replace("×", "x")

    if option.startswith("auto"):
        return "auto"

    if option.startswith("custom"):
        custom = (custom_size or "").strip().lower().replace("×", "x")
        if not custom:
            raise ValueError("选择 custom 时，custom_size 必须填写，例如 3072x1024 或 1024x3072")
        return _validate_gpt_image2_size(custom)

    match = re.match(r"(\d{3,4}x\d{3,4})", option)
    if match:
        return _validate_gpt_image2_size(match.group(1))

    raise ValueError(f"无法识别 size 选项: {size}")


def emit_runtime_status(
    node_id,
    status,
    message="",
    elapsed_seconds=0.0,
    attempt=0,
    retry_times=0,
    timeout_seconds=0,
):
    """Send runtime status to the ComfyUI frontend extension."""
    if node_id in (None, ""):
        return
    try:
        from server import PromptServer

        if PromptServer.instance is None:
            return

        PromptServer.instance.send_sync(
            "comfyui_luck_gpt20_status",
            {
                "node_id": str(node_id),
                "status": status,
                "message": message,
                "elapsed_seconds": float(elapsed_seconds),
                "attempt": int(attempt),
                "retry_times": int(retry_times),
                "timeout_seconds": int(timeout_seconds),
                "timestamp": time.time(),
            },
        )
    except Exception:
        pass


class ComfyuiLuckGPT20Node:
    """Comfyui-Luck gpt-2.0 text-to-image and image editing node."""

    MODELS = ["gpt-image-2-all"]
    ASPECT_RATIOS = ["AUTO", "1:1", "16:9", "9:16", "21:9", "4:3", "3:2"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key (API密钥)": ("STRING", {"default": "", "multiline": False}),
                "prompt (提示词)": ("STRING", {"default": "", "multiline": True}),
                "mode (模式)": (["AUTO", "text2img", "img2img"], {"default": "AUTO"}),
                "model (模型)": (cls.MODELS, {"default": "gpt-image-2-all"}),
                "api_base (接口域名)": (API_BASE_URLS, {"default": "https://api.apiyi.com"}),
                "endpoint (端点)": (["chat_completions (推荐)", "images_api (兼容)"], {"default": "chat_completions (推荐)"}),
                "aspect_ratio (宽高比)": (cls.ASPECT_RATIOS, {"default": "AUTO"}),
                "response_format (响应格式)": (["url", "b64_json"], {"default": "url"}),
                "seed (种子)": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 2147483647,
                        "control_after_generate": True,
                    },
                ),
                "timeout_seconds (超时秒数)": ("INT", {"default": 300, "min": 30, "max": 1200}),
                "retry_times (重试次数)": ("INT", {"default": 3, "min": 1, "max": 10}),
            },
            "optional": {
                **{f"image_{i:02d}": ("IMAGE",) for i in range(1, 15)}
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "response", "image_urls")
    FUNCTION = "generate"
    CATEGORY = "Comfyui-Luck/gpt-2.0"

    def _prompt_prefix(self, aspect_ratio):
        if aspect_ratio != "AUTO":
            return AUTO_RATIO_PROMPTS.get(aspect_ratio, "")
        return ""

    def _compose_prompt(self, prompt, aspect_ratio):
        clean_prompt = (prompt or "").strip()
        prefix = self._prompt_prefix(aspect_ratio)

        if not clean_prompt and not prefix:
            raise ValueError("prompt 不能为空")

        if prefix and clean_prompt:
            return f"{prefix}，{clean_prompt}", prefix
        if prefix:
            return prefix, prefix
        return clean_prompt, ""

    def _collect_images(self, kwargs):
        image_payloads = []
        for i in range(1, 15):
            tensor = kwargs.get(f"image_{i:02d}")
            if tensor is None:
                continue
            image_payloads.append((f"image_{i:02d}.png", tensor_to_png_bytes(tensor)))
        return image_payloads

    def _download_image_url(self, url, timeout_seconds):
        headers = {
            "User-Agent": "Comfyui-Luck gpt-2.0/1.0",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        }
        response = requests.get(url, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()
        return image_bytes_to_tensor(response.content)

    def _parse_response_images(self, data, timeout_seconds):
        items = data.get("data")
        if not items:
            raise RuntimeError(f"API 未返回图片数据: {data}")
        if not isinstance(items, list):
            items = [items]

        tensors = []
        urls = []
        for item in items:
            if not isinstance(item, dict):
                continue

            if item.get("b64_json"):
                tensors.append(b64_json_to_tensor(item["b64_json"]))
                continue

            if item.get("url"):
                url = item["url"]
                urls.append(url)
                tensors.append(self._download_image_url(url, timeout_seconds))

        if not tensors:
            raise RuntimeError(f"未能解析响应中的图片: {data}")

        return torch.cat(tensors, dim=0), urls

    def _parse_chat_response_images(self, data, timeout_seconds):
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"对话式 API 未返回 choices: {data}")

        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        image_refs = extract_image_references(content)
        if not image_refs:
            raise RuntimeError(f"对话式 API 未返回图片链接或 data URL: {content}")

        tensors = []
        urls = []
        for ref in image_refs:
            if ref.lower().startswith("data:image/"):
                tensors.append(b64_json_to_tensor(ref))
            else:
                urls.append(ref)
                tensors.append(self._download_image_url(ref, timeout_seconds))

        return torch.cat(tensors, dim=0), urls, content

    def _request_text2img(self, api_base, headers, model, prompt, response_format, timeout_seconds):
        payload = {
            "model": model,
            "prompt": prompt,
            "response_format": response_format,
        }
        return requests.post(
            f"{api_base}/v1/images/generations",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=timeout_seconds,
        )

    def _request_img2img(self, api_base, headers, model, prompt, response_format, image_payloads, timeout_seconds):
        data = {
            "model": model,
            "prompt": prompt,
            "response_format": response_format,
        }
        files = [
            ("image[]", (filename, BytesIO(image_bytes), "image/png"))
            for filename, image_bytes in image_payloads
        ]
        return requests.post(
            f"{api_base}/v1/images/edits",
            headers=headers,
            data=data,
            files=files,
            timeout=timeout_seconds,
        )

    def _request_chat(self, api_base, headers, model, prompt, image_payloads, timeout_seconds):
        if image_payloads:
            content = [{"type": "text", "text": prompt}]
            for _, image_bytes in image_payloads:
                data_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("utf-8")
                content.append({"type": "image_url", "image_url": {"url": data_url}})
        else:
            content = prompt

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "stream": False,
        }
        return requests.post(
            f"{api_base}/v1/chat/completions",
            headers={**headers, "Content-Type": "application/json"},
            json=payload,
            timeout=timeout_seconds,
        )

    def generate(self, **kwargs):
        api_key = kwargs.get("api_key (API密钥)", "")
        prompt = kwargs.get("prompt (提示词)", "")
        mode = kwargs.get("mode (模式)", "AUTO")
        model = kwargs.get("model (模型)", "gpt-image-2-all")
        api_base = kwargs.get("api_base (接口域名)", "https://api.apiyi.com").rstrip("/")
        endpoint = kwargs.get("endpoint (端点)", "chat_completions (推荐)")
        aspect_ratio = kwargs.get("aspect_ratio (宽高比)", "AUTO")
        response_format = kwargs.get("response_format (响应格式)", "url")
        seed = kwargs.get("seed (种子)", 0)
        timeout_seconds = kwargs.get("timeout_seconds (超时秒数)", 300)
        retry_times = kwargs.get("retry_times (重试次数)", 3)
        unique_id = kwargs.get("unique_id")
        start_ts = time.time()

        if not api_key.strip():
            emit_runtime_status(unique_id, "error", "API Key 为空", 0.0, 0, retry_times, timeout_seconds)
            raise ValueError("API Key 不能为空")

        effective_prompt, prompt_prefix = self._compose_prompt(prompt, aspect_ratio)
        image_payloads = self._collect_images(kwargs)
        print(f"[Comfyui-Luck gpt-2.0] effective prompt: {effective_prompt[:500]}")

        if mode == "AUTO":
            actual_mode = "img2img" if image_payloads else "text2img"
        else:
            actual_mode = mode

        if actual_mode == "img2img" and not image_payloads:
            emit_runtime_status(unique_id, "error", "img2img 模式需要至少一张参考图", 0.0, 0, retry_times, timeout_seconds)
            raise ValueError("img2img 模式需要至少一张参考图")

        headers = {"Authorization": f"Bearer {api_key.strip()}"}
        last_error = None

        print(f"[Comfyui-Luck gpt-2.0] endpoint={endpoint}, mode={actual_mode}, model={model}, seed={seed} (not sent to API)")
        emit_runtime_status(unique_id, "running", "开始生成", 0.0, 0, retry_times, timeout_seconds)

        for attempt in range(1, retry_times + 1):
            try:
                emit_runtime_status(
                    unique_id,
                    "running",
                    f"{'图片编辑' if actual_mode == 'img2img' else '文生图'}请求中 ({attempt}/{retry_times})",
                    time.time() - start_ts,
                    attempt,
                    retry_times,
                    timeout_seconds,
                )

                if endpoint.startswith("chat_completions"):
                    response = self._request_chat(
                        api_base,
                        headers,
                        model,
                        effective_prompt,
                        image_payloads,
                        timeout_seconds,
                    )
                elif actual_mode == "img2img":
                    response = self._request_img2img(
                        api_base,
                        headers,
                        model,
                        effective_prompt,
                        response_format,
                        image_payloads,
                        timeout_seconds,
                    )
                else:
                    response = self._request_text2img(
                        api_base,
                        headers,
                        model,
                        effective_prompt,
                        response_format,
                        timeout_seconds,
                    )

                if response.status_code != 200:
                    last_error = f"API 错误 {response.status_code}: {response.text}"
                    if response.status_code == 429 or response.status_code >= 500:
                        time.sleep(min(2 ** (attempt - 1), 8))
                        continue
                    raise RuntimeError(last_error)

                data = response.json()
                emit_runtime_status(
                    unique_id,
                    "running",
                    "解析图片",
                    time.time() - start_ts,
                    attempt,
                    retry_times,
                    timeout_seconds,
                )
                chat_content = ""
                if endpoint.startswith("chat_completions"):
                    image_tensor, image_urls, chat_content = self._parse_chat_response_images(data, timeout_seconds)
                else:
                    image_tensor, image_urls = self._parse_response_images(data, timeout_seconds)

                elapsed = time.time() - start_ts
                response_info = {
                    "status": "success",
                    "model": model,
                    "endpoint": endpoint,
                    "mode": actual_mode,
                    "api_base": api_base,
                    "aspect_ratio": aspect_ratio,
                    "prompt_prefix": prompt_prefix,
                    "prompt": effective_prompt,
                    "response_format": response_format,
                    "chat_content": chat_content,
                    "seed": seed,
                    "seed_note": "seed is a ComfyUI control only and is not sent to gpt-image-2-all",
                    "input_images": len(image_payloads),
                    "output_images": int(image_tensor.shape[0]),
                    "image_urls": image_urls,
                    "elapsed_seconds": round(elapsed, 2),
                }

                emit_runtime_status(
                    unique_id,
                    "success",
                    f"生成成功 (耗时 {elapsed:.1f}s)",
                    elapsed,
                    attempt,
                    retry_times,
                    timeout_seconds,
                )
                return (
                    image_tensor,
                    json.dumps(response_info, ensure_ascii=False, indent=2),
                    "\n".join(image_urls),
                )

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_error = str(exc)
                if attempt < retry_times:
                    emit_runtime_status(
                        unique_id,
                        "running",
                        f"网络或超时，重试中 ({attempt}/{retry_times})",
                        time.time() - start_ts,
                        attempt,
                        retry_times,
                        timeout_seconds,
                    )
                    time.sleep(min(2 ** (attempt - 1), 8))
                    continue
                break
            except Exception as exc:
                last_error = str(exc)
                if attempt < retry_times and ("429" in last_error or "5" in last_error[:3]):
                    time.sleep(min(2 ** (attempt - 1), 8))
                    continue
                emit_runtime_status(
                    unique_id,
                    "error",
                    last_error,
                    time.time() - start_ts,
                    attempt,
                    retry_times,
                    timeout_seconds,
                )
                raise

        elapsed = time.time() - start_ts
        emit_runtime_status(
            unique_id,
            "error",
            f"连续 {retry_times} 次失败",
            elapsed,
            retry_times,
            retry_times,
            timeout_seconds,
        )
        raise RuntimeError(f"Comfyui-Luck gpt-2.0 连续 {retry_times} 次失败，最后错误: {last_error}")


class ComfyuiLuckGPTImage2Node:
    """Official gpt-image-2 node with real size, quality, format, and mask controls."""

    MODELS = ["gpt-image-2"]
    SIZES = [
        "auto (自动)",
        "1024x1024 (1:1 方形)",
        "1536x1024 (3:2 横版)",
        "1024x1536 (2:3 竖版)",
        "2048x2048 (1:1 2K 方形)",
        "2048x1152 (16:9 2K 横版)",
        "3840x2160 (16:9 4K 横版, 实验)",
        "2160x3840 (9:16 4K 竖版, 实验)",
        "3072x1024 (3:1 超宽, 合法边界)",
        "1024x3072 (1:3 长竖, 合法边界)",
        "custom (自定义宽x高)",
    ]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key (API密钥)": ("STRING", {"default": "", "multiline": False}),
                "prompt (提示词)": ("STRING", {"default": "", "multiline": True}),
                "mode (模式)": (["AUTO", "text2img", "img2img"], {"default": "AUTO"}),
                "model (模型)": (cls.MODELS, {"default": "gpt-image-2"}),
                "api_base (接口域名)": (API_BASE_URLS, {"default": "https://api.apiyi.com"}),
                "size_ratio (尺寸/比例)": (cls.SIZES, {"default": "2048x1152 (16:9 2K 横版)"}),
                "custom_size (custom时: 宽x高, 例3072x1024)": ("STRING", {"default": "", "multiline": False}),
                "quality (画质)": (["auto", "low", "medium", "high"], {"default": "auto"}),
                "output_format (输出格式)": (["png", "jpeg", "webp"], {"default": "png"}),
                "output_compression (压缩率)": ("INT", {"default": 85, "min": 0, "max": 100}),
                "background (背景)": (["auto", "opaque"], {"default": "auto"}),
                "moderation (审核)": (["auto", "low"], {"default": "auto"}),
                "seed (种子)": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 2147483647,
                        "control_after_generate": True,
                    },
                ),
                "timeout_seconds (超时秒数)": ("INT", {"default": 360, "min": 60, "max": 1800}),
                "retry_times (重试次数)": ("INT", {"default": 2, "min": 1, "max": 5}),
            },
            "optional": {
                **{f"image_{i:02d}": ("IMAGE",) for i in range(1, 6)},
                "mask": ("MASK",),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "response")
    FUNCTION = "generate"
    CATEGORY = "Comfyui-Luck/gpt-image-2"

    def _collect_images(self, kwargs):
        image_payloads = []
        for i in range(1, 6):
            tensor = kwargs.get(f"image_{i:02d}")
            if tensor is None:
                continue
            image_payloads.append((f"image_{i:02d}.png", tensor_to_png_bytes(tensor)))
        return image_payloads

    def _payload_fields(self, model, prompt, size, quality, output_format, output_compression, background, moderation):
        fields = {
            "model": model,
            "prompt": prompt,
        }
        if size != "auto":
            fields["size"] = size
        if quality != "auto":
            fields["quality"] = quality
        if output_format != "png":
            fields["output_format"] = output_format
            fields["output_compression"] = output_compression
        if background != "auto":
            fields["background"] = background
        if moderation != "auto":
            fields["moderation"] = moderation
        return fields

    def _request_text2img(self, api_base, headers, fields, timeout_seconds):
        return requests.post(
            f"{api_base}/v1/images/generations",
            headers={**headers, "Content-Type": "application/json"},
            json=fields,
            timeout=timeout_seconds,
        )

    def _request_img2img(self, api_base, headers, fields, image_payloads, mask_bytes, timeout_seconds):
        files = [
            ("image[]", (filename, BytesIO(image_bytes), "image/png"))
            for filename, image_bytes in image_payloads
        ]
        if mask_bytes is not None:
            files.append(("mask", ("mask.png", BytesIO(mask_bytes), "image/png")))

        data = {key: str(value) for key, value in fields.items()}
        return requests.post(
            f"{api_base}/v1/images/edits",
            headers=headers,
            data=data,
            files=files,
            timeout=timeout_seconds,
        )

    def _parse_response_images(self, data):
        items = data.get("data")
        if not items:
            raise RuntimeError(f"API 未返回图片数据: {data}")
        if not isinstance(items, list):
            items = [items]

        tensors = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("b64_json"):
                tensors.append(b64_json_to_tensor(item["b64_json"]))

        if not tensors:
            raise RuntimeError(f"未能解析 gpt-image-2 响应图片: {data}")

        return torch.cat(tensors, dim=0)

    def generate(self, **kwargs):
        api_key = kwargs.get("api_key (API密钥)", "")
        prompt = kwargs.get("prompt (提示词)", "")
        mode = kwargs.get("mode (模式)", "AUTO")
        model = kwargs.get("model (模型)", "gpt-image-2")
        api_base = kwargs.get("api_base (接口域名)", "https://api.apiyi.com").rstrip("/")
        size = kwargs.get("size_ratio (尺寸/比例)", kwargs.get("size (尺寸)", "2048x1152 (16:9 2K 横版)"))
        custom_size = kwargs.get(
            "custom_size (custom时: 宽x高, 例3072x1024)",
            kwargs.get("custom_size (自定义尺寸)", ""),
        )
        quality = kwargs.get("quality (画质)", "auto")
        output_format = kwargs.get("output_format (输出格式)", "png")
        output_compression = kwargs.get("output_compression (压缩率)", 85)
        background = kwargs.get("background (背景)", "auto")
        moderation = kwargs.get("moderation (审核)", "auto")
        seed = kwargs.get("seed (种子)", 0)
        timeout_seconds = kwargs.get("timeout_seconds (超时秒数)", 360)
        retry_times = kwargs.get("retry_times (重试次数)", 2)
        unique_id = kwargs.get("unique_id")
        start_ts = time.time()

        if not api_key.strip():
            emit_runtime_status(unique_id, "error", "API Key 为空", 0.0, 0, retry_times, timeout_seconds)
            raise ValueError("API Key 不能为空")

        clean_prompt = (prompt or "").strip()
        if not clean_prompt:
            raise ValueError("prompt 不能为空")

        effective_size = normalize_size(size, custom_size)
        image_payloads = self._collect_images(kwargs)
        mask_bytes = mask_to_png_bytes(kwargs.get("mask"))

        if mode == "AUTO":
            actual_mode = "img2img" if image_payloads else "text2img"
        else:
            actual_mode = mode

        if actual_mode == "img2img" and not image_payloads:
            emit_runtime_status(unique_id, "error", "img2img 模式需要至少一张参考图", 0.0, 0, retry_times, timeout_seconds)
            raise ValueError("img2img 模式需要至少一张参考图")
        if mask_bytes is not None and not image_payloads:
            raise ValueError("mask 只能和 image_01 一起用于图片编辑")

        headers = {"Authorization": f"Bearer {api_key.strip()}"}
        fields = self._payload_fields(
            model,
            clean_prompt,
            effective_size,
            quality,
            output_format,
            output_compression,
            background,
            moderation,
        )
        if actual_mode == "img2img":
            fields.pop("moderation", None)

        print(f"[Comfyui-Luck gpt-image-2] mode={actual_mode}, fields={fields}, seed={seed} (not sent to API)")
        emit_runtime_status(unique_id, "running", "开始生成", 0.0, 0, retry_times, timeout_seconds)

        last_error = None
        for attempt in range(1, retry_times + 1):
            try:
                emit_runtime_status(
                    unique_id,
                    "running",
                    f"{'图片编辑' if actual_mode == 'img2img' else '文生图'}请求中 ({attempt}/{retry_times})",
                    time.time() - start_ts,
                    attempt,
                    retry_times,
                    timeout_seconds,
                )

                if actual_mode == "img2img":
                    response = self._request_img2img(
                        api_base,
                        headers,
                        fields,
                        image_payloads,
                        mask_bytes,
                        timeout_seconds,
                    )
                else:
                    response = self._request_text2img(api_base, headers, fields, timeout_seconds)

                if response.status_code != 200:
                    last_error = f"API 错误 {response.status_code}: {response.text}"
                    if response.status_code == 429 or response.status_code >= 500:
                        time.sleep(min(2 ** (attempt - 1), 8))
                        continue
                    raise RuntimeError(last_error)

                data = response.json()
                image_tensor = self._parse_response_images(data)
                elapsed = time.time() - start_ts
                response_info = {
                    "status": "success",
                    "model": model,
                    "mode": actual_mode,
                    "api_base": api_base,
                    "size_option": size,
                    "request_fields": fields,
                    "input_images": len(image_payloads),
                    "mask": mask_bytes is not None,
                    "output_images": int(image_tensor.shape[0]),
                    "usage": data.get("usage"),
                    "seed": seed,
                    "seed_note": "seed is a ComfyUI control only and is not sent to gpt-image-2",
                    "elapsed_seconds": round(elapsed, 2),
                }
                emit_runtime_status(
                    unique_id,
                    "success",
                    f"生成成功 (耗时 {elapsed:.1f}s)",
                    elapsed,
                    attempt,
                    retry_times,
                    timeout_seconds,
                )
                return (image_tensor, json.dumps(response_info, ensure_ascii=False, indent=2))

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                last_error = str(exc)
                if attempt < retry_times:
                    emit_runtime_status(
                        unique_id,
                        "running",
                        f"网络或超时，重试中 ({attempt}/{retry_times})",
                        time.time() - start_ts,
                        attempt,
                        retry_times,
                        timeout_seconds,
                    )
                    time.sleep(min(2 ** (attempt - 1), 8))
                    continue
                break
            except Exception as exc:
                last_error = str(exc)
                emit_runtime_status(
                    unique_id,
                    "error",
                    last_error,
                    time.time() - start_ts,
                    attempt,
                    retry_times,
                    timeout_seconds,
                )
                raise

        elapsed = time.time() - start_ts
        emit_runtime_status(
            unique_id,
            "error",
            f"连续 {retry_times} 次失败",
            elapsed,
            retry_times,
            retry_times,
            timeout_seconds,
        )
        raise RuntimeError(f"Comfyui-Luck gpt-image-2 连续 {retry_times} 次失败，最后错误: {last_error}")


NODE_CLASS_MAPPINGS = {
    "ComfyuiLuckGPT20Node": ComfyuiLuckGPT20Node,
    "ComfyuiLuckGPTImage2Node": ComfyuiLuckGPTImage2Node,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ComfyuiLuckGPT20Node": "Comfyui-Luck gpt-2.0 all",
    "ComfyuiLuckGPTImage2Node": "Comfyui-Luck gpt-image-2",
}
