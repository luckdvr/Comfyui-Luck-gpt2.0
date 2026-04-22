#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comfyui-Luck gpt-2.0 node for APIYi.

The gpt-image-2-all API does not accept size, n, quality, or aspect_ratio.
Resolution and composition controls are converted into a prompt prefix.
"""

import base64
import json
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


SIZE_RATIO_PROMPTS = {
    "1K": {
        "1:1": "1024×1024 方图 / 1:1 方形构图",
        "16:9": "1024×576 横版 / 宽屏 16:9 电影画幅",
        "9:16": "576×1024 竖版 / 手机海报 9:16",
        "21:9": "1344×576 横幅 / 21:9 超宽银幕",
        "4:3": "1024×768 标准画幅 / 4:3 构图",
        "3:2": "1152×768 经典画幅 / 3:2 构图",
    },
    "2K": {
        "1:1": "2048×2048 方图 / 1:1 方形构图",
        "16:9": "1920×1080 横版 / 宽屏 16:9 电影画幅",
        "9:16": "1080×1920 竖版 / 手机海报 9:16",
        "21:9": "2560×1080 横幅 / 21:9 超宽银幕",
        "4:3": "2048×1536 标准画幅 / 4:3 构图",
        "3:2": "2160×1440 经典画幅 / 3:2 构图",
    },
    "4K": {
        "1:1": "4096×4096 方图 / 1:1 方形构图",
        "16:9": "3840×2160 横版 / 4K 16:9 电影画幅",
        "9:16": "2160×3840 竖版 / 4K 手机海报 9:16",
        "21:9": "5120×2160 横幅 / 21:9 超宽银幕",
        "4:3": "4096×3072 标准画幅 / 4:3 构图",
        "3:2": "4320×2880 经典画幅 / 3:2 构图",
    },
}


SIZE_ONLY_PROMPTS = {
    "1K": "1K 清晰图片",
    "2K": "2K 高清图片",
    "4K": "4K 超高清图片",
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
                "image_size (分辨率)": (["AUTO", "1K", "2K", "4K"], {"default": "AUTO"}),
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
                "timeout_seconds (超时秒数)": ("INT", {"default": 120, "min": 30, "max": 1200}),
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

    def _prompt_prefix(self, image_size, aspect_ratio):
        if image_size != "AUTO" and aspect_ratio != "AUTO":
            return SIZE_RATIO_PROMPTS.get(image_size, {}).get(aspect_ratio, "")

        if aspect_ratio != "AUTO":
            return AUTO_RATIO_PROMPTS.get(aspect_ratio, "")

        if image_size != "AUTO":
            return SIZE_ONLY_PROMPTS.get(image_size, "")

        return ""

    def _compose_prompt(self, prompt, image_size, aspect_ratio):
        clean_prompt = (prompt or "").strip()
        prefix = self._prompt_prefix(image_size, aspect_ratio)

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

    def generate(self, **kwargs):
        api_key = kwargs.get("api_key (API密钥)", "")
        prompt = kwargs.get("prompt (提示词)", "")
        mode = kwargs.get("mode (模式)", "AUTO")
        model = kwargs.get("model (模型)", "gpt-image-2-all")
        api_base = kwargs.get("api_base (接口域名)", "https://api.apiyi.com").rstrip("/")
        image_size = kwargs.get("image_size (分辨率)", "AUTO")
        aspect_ratio = kwargs.get("aspect_ratio (宽高比)", "AUTO")
        response_format = kwargs.get("response_format (响应格式)", "url")
        seed = kwargs.get("seed (种子)", 0)
        timeout_seconds = kwargs.get("timeout_seconds (超时秒数)", 120)
        retry_times = kwargs.get("retry_times (重试次数)", 3)
        unique_id = kwargs.get("unique_id")
        start_ts = time.time()

        if not api_key.strip():
            emit_runtime_status(unique_id, "error", "API Key 为空", 0.0, 0, retry_times, timeout_seconds)
            raise ValueError("API Key 不能为空")

        effective_prompt, prompt_prefix = self._compose_prompt(prompt, image_size, aspect_ratio)
        image_payloads = self._collect_images(kwargs)

        if mode == "AUTO":
            actual_mode = "img2img" if image_payloads else "text2img"
        else:
            actual_mode = mode

        if actual_mode == "img2img" and not image_payloads:
            emit_runtime_status(unique_id, "error", "img2img 模式需要至少一张参考图", 0.0, 0, retry_times, timeout_seconds)
            raise ValueError("img2img 模式需要至少一张参考图")

        headers = {"Authorization": f"Bearer {api_key.strip()}"}
        last_error = None

        print(f"[Comfyui-Luck gpt-2.0] mode={actual_mode}, model={model}, seed={seed} (not sent to API)")
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

                if actual_mode == "img2img":
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
                image_tensor, image_urls = self._parse_response_images(data, timeout_seconds)

                elapsed = time.time() - start_ts
                response_info = {
                    "status": "success",
                    "model": model,
                    "mode": actual_mode,
                    "api_base": api_base,
                    "image_size": image_size,
                    "aspect_ratio": aspect_ratio,
                    "prompt_prefix": prompt_prefix,
                    "prompt": effective_prompt,
                    "response_format": response_format,
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


NODE_CLASS_MAPPINGS = {
    "ComfyuiLuckGPT20Node": ComfyuiLuckGPT20Node,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ComfyuiLuckGPT20Node": "Comfyui-Luck gpt-2.0",
}
