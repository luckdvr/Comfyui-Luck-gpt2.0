"""Offline API contract and workflow regression tests; no paid API calls."""

import base64
from contextlib import ExitStack, redirect_stdout
import importlib.util
from io import BytesIO, StringIO
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
import torch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("luck_image_nodes", ROOT / "gpt_2_0_node.py")
nodes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(nodes)

NEW_MODELS = (
    "gpt-image-2.5-flare",
    "gpt-image-2.5-sunburst",
    "gpt-image-2.5-flare-2026-09-08",
    "gpt-image-2.5-sunburst-2026-09-08",
)


def workflow_kwargs(node):
    """Decode ComfyUI's serialized widgets, including seed's extra control."""
    values = iter(node["widgets_values"])
    kwargs = {}
    for name, (_, options) in nodes.ComfyuiLuckGPTImage2Node.INPUT_TYPES()["required"].items():
        kwargs[name] = next(values)
        if options.get("control_after_generate"):
            next(values)
    if next(values, None) is not None:
        raise AssertionError("Unexpected extra widget value")
    return kwargs


class Image25Tests(unittest.TestCase):
    def setUp(self):
        self.contexts = ExitStack()
        self.addCleanup(self.contexts.close)
        self.node = nodes.ComfyuiLuckGPTImage2Node()
        self.kwargs = {
            "api_key (API密钥)": "offline-test-key",
            "prompt (提示词)": "保留主体，把背景换成海边",
            "model (模型)": NEW_MODELS[0],
            "quality (画质)": "high",
            "image_size (分辨率)": "2K",
            "aspect_ratio (宽高比)": "16:9",
            "retry_times (重试次数)": 1,
        }
        self.expected = torch.zeros((1, 8, 12, 3))
        self.expected[..., 0] = 1
        buf = BytesIO()
        Image.new("RGB", (12, 8), (255, 0, 0)).save(buf, format="PNG")
        self.b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        self.usage = {"input_tokens": 10, "output_tokens": 196, "total_tokens": 206}
        self.response = Mock(status_code=200)
        self.response.json.return_value = {
            "data": [{"b64_json": self.b64}], "usage": self.usage,
        }
        self.post = self.contexts.enter_context(patch.object(nodes.APIYI_HTTP_SESSION, "post", return_value=self.response))
        self.contexts.enter_context(patch.object(nodes.APIYI_HTTP_SESSION, "get", side_effect=AssertionError("Unexpected network GET")))
        self.contexts.enter_context(redirect_stdout(StringIO()))

    def test_new_models_and_quality_reach_generation_api_unchanged(self):
        for model in NEW_MODELS:
            for quality in ("auto", "low", "medium", "high", "xhigh", "max"):
                with self.subTest(model=model, quality=quality):
                    self.post.reset_mock()
                    image, info = self.node.generate(**{
                        **self.kwargs, "model (模型)": model, "quality (画质)": quality,
                        "image_size (分辨率)": "4K", "output_format (输出格式)": "webp",
                        "output_compression (压缩率)": 73,
                    })
                    self.post.assert_called_once()
                    args, kwargs = self.post.call_args
                    self.assertEqual(args[0], "https://api.apiyi.com/v1/images/generations")
                    expected_fields = {
                        "model": model, "prompt": self.kwargs["prompt (提示词)"],
                        "size": "3840x2160", "output_format": "webp", "output_compression": 73,
                    }
                    if quality != "auto":
                        expected_fields["quality"] = quality
                    self.assertEqual(kwargs["json"], expected_fields)
                    self.assertEqual(kwargs["timeout"], (30, 600))
                    self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")
                    self.assertEqual(kwargs["headers"]["Authorization"], "Bearer offline-test-key")
                    torch.testing.assert_close(image, self.expected)
                    info = json.loads(info)
                    self.assertEqual(info["model"], model)
                    self.assertEqual(info["request_fields"], expected_fields)
                    self.assertEqual(info["usage"], self.usage)

    def test_16_images_mask_order_and_new_quality_reach_edits_api(self):
        for model in NEW_MODELS:
            with self.subTest(model=model):
                self.post.reset_mock()
                mask = torch.zeros((1, 8, 12))
                mask[:, :, :6] = 1
                images = {f"image_{i:02d}": torch.full((1, 8, 12, 3), i / 16) for i in range(1, 17)}
                _, info = self.node.generate(**{
                    **self.kwargs, **images, "model (模型)": model, "mask": mask,
                    "quality (画质)": "max", "api_base (接口域名)": "https://api.apiyi.com",
                    "image_size (分辨率)": "custom (自定义)",
                    "custom_size (仅custom填写: 宽x高)": "1600x1200",
                    "output_format (输出格式)": "jpeg", "output_compression (压缩率)": 85,
                })
                self.post.assert_called_once()
                args, kwargs = self.post.call_args
                self.assertEqual(args[0], "https://api.apiyi.com/v1/images/edits")
                self.assertNotIn("Content-Type", kwargs["headers"])
                self.assertEqual(kwargs["data"], {
                    "model": model, "prompt": self.kwargs["prompt (提示词)"],
                    "size": "1600x1200", "quality": "max", "output_format": "jpeg",
                    "output_compression": "85",
                })
                files = kwargs["files"]
                self.assertEqual(len(files), 17)
                for i, (field, (filename, content, mime)) in enumerate(files[:16], 1):
                    self.assertEqual((field, filename, mime), ("image[]", f"image_{i:02d}.png", "image/png"))
                    pixel = Image.open(content).getpixel((0, 0))
                    self.assertEqual(pixel, (int(i / 16 * 255),) * 3)
                self.assertEqual(files[-1][0], "mask")
                mask_image = Image.open(files[-1][1][1])
                self.assertEqual(mask_image.mode, "RGBA")
                alpha = np.array(mask_image)[..., 3]
                self.assertTrue(np.all(alpha[:, :6] == 0))
                self.assertTrue(np.all(alpha[:, 6:] == 255))
                info = json.loads(info)
                self.assertEqual((info["mode"], info["input_images"], info["mask"]), ("img2img", 16, True))

    def test_invalid_model_or_quality_is_rejected_before_encoding_or_request(self):
        cases = [("gpt-image-2", "xhigh"), ("gpt-image-2", "max"),
                 (NEW_MODELS[0], "hd"), (NEW_MODELS[1], "standard"),
                 ("unknown-model", "high")]
        with patch.object(self.node, "_collect_images") as collect:
            for model, quality in cases:
                with self.subTest(model=model, quality=quality), self.assertRaisesRegex(ValueError, "不支持"):
                    self.node.generate(**{**self.kwargs, "model (模型)": model, "quality (画质)": quality})
            collect.assert_not_called()
        self.post.assert_not_called()

    def test_original_workflows_keep_model_quality_size_and_widget_alignment(self):
        workflow = json.loads((ROOT / "example_workflow.json").read_text())
        for node in workflow["nodes"]:
            if node["type"] != "ComfyuiLuckGPTImage2Node":
                continue
            with self.subTest(node=node["id"]):
                kwargs = workflow_kwargs(node)
                kwargs["api_key (API密钥)"] = "offline-test-key"
                kwargs["prompt (提示词)"] = "工作流兼容检查"
                self.node.generate(**kwargs)
                self.assertEqual(self.post.call_args.kwargs["json"], {
                    "model": "gpt-image-2", "prompt": "工作流兼容检查",
                    "size": "2048x1152", "quality": "high",
                    "output_format": "jpeg", "output_compression": 85,
                })

    def test_shifted_workflow_preserves_selected_model_and_quality(self):
        for model in ("gpt-image-2", *NEW_MODELS):
            with self.subTest(model=model):
                quality = "high" if model == "gpt-image-2" else "max"
                self.node.generate(**{
                    **self.kwargs, "mode (模式)": model,
                    "model (模型)": "https://api.apiyi.com/v1",
                    "api_base (接口域名)": "2K", "image_size (分辨率)": "16:9",
                    "aspect_ratio (宽高比)": "1600x1200",
                    "custom_size (仅custom填写: 宽x高)": quality,
                    "quality (画质)": "jpeg", "output_format (输出格式)": 85,
                })
                fields = self.post.call_args.kwargs["json"]
                self.assertEqual((fields["model"], fields["quality"], fields["size"]), (model, quality, "2048x1152"))

    def test_default_png_auto_and_data_url_response_remain_compatible(self):
        self.response.json.return_value["data"][0]["b64_json"] = "data:image/png;base64," + self.b64
        image, _ = self.node.generate(**{
            **self.kwargs, "image_size (分辨率)": "auto (不传size)", "quality (画质)": "auto",
        })
        self.assertEqual(self.post.call_args.kwargs["json"], {
            "model": NEW_MODELS[0], "prompt": self.kwargs["prompt (提示词)"],
        })
        torch.testing.assert_close(image, self.expected)

    def test_model_options_defaults_and_node_id(self):
        schema = self.node.INPUT_TYPES()["required"]
        self.assertTrue(set(NEW_MODELS).issubset(schema["model (模型)"][0]))
        self.assertEqual(schema["model (模型)"][1]["default"], "gpt-image-2")
        self.assertEqual(schema["quality (画质)"][1]["default"], "auto")
        self.assertIs(nodes.NODE_CLASS_MAPPINGS["ComfyuiLuckGPTImage2Node"], type(self.node))

    def test_new_example_chain_uses_both_models_without_saved_keys(self):
        workflow = json.loads((ROOT / "example_workflow_gpt_image_2_5.json").read_text())
        by_id = {n["id"]: n for n in workflow["nodes"]}
        self.assertEqual(len(by_id), len(workflow["nodes"]))
        self.assertEqual(workflow["last_node_id"], max(by_id))
        self.assertEqual(workflow["last_link_id"], max(link[0] for link in workflow["links"]))
        for link_id, src, src_slot, dst, dst_slot, kind in workflow["links"]:
            self.assertIn(link_id, by_id[src]["outputs"][src_slot]["links"])
            self.assertEqual(by_id[dst]["inputs"][dst_slot]["link"], link_id)
            self.assertEqual(by_id[dst]["inputs"][dst_slot]["type"], kind)
        result = None
        models = []
        for node in workflow["nodes"]:
            if node["type"] != "ComfyuiLuckGPTImage2Node":
                continue
            kwargs = workflow_kwargs(node)
            self.assertEqual(kwargs["api_key (API密钥)"], "")
            self.assertEqual(kwargs["retry_times (重试次数)"], 1)
            kwargs["api_key (API密钥)"] = "offline-test-key"
            if result is not None:
                kwargs["image_01"] = result
            result, info = self.node.generate(**kwargs)
            models.append(json.loads(info)["model"])
        self.assertEqual(models, list(NEW_MODELS[:2]))
        self.assertEqual(json.loads(info)["mode"], "img2img")


if __name__ == "__main__":
    unittest.main()
