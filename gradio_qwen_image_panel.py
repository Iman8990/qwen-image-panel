"""Qwen-Image — Gradio panel on Modal (teaching build).

Standalone app 'qwen-image-panel', separate from the Ideogram apps.
Reuses the 'ideogram4-model-auth' secret (HF_TOKEN) and the
'ideogram4-panel-auth' secret (panel login) read-only; weights live on
their own volume 'qwen-image-weights'. Nothing Ideogram is modified.

Two models, one class each (a GPU boots only for the tab in use):
  TextServer - Qwen/Qwen-Image-2512       (QwenImagePipeline)
  EditServer - Qwen/Qwen-Image-Edit-2511  (QwenImageEditPlusPipeline)

Deploy:  modal deploy gradio_qwen_image_panel.py
"""

import base64
import io
import os
import random
import time

import modal

T2I_REPO = "Qwen/Qwen-Image-2512"
EDIT_REPO = "Qwen/Qwen-Image-Edit-2511"
MODEL_DIR = "/models"
MAX_SEED = 2**31 - 1

# Official negative prompt from the Qwen-Image-2512 model card.
DEFAULT_NEGATIVE = "低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲。"

app = modal.App("qwen-image-panel")

vol = modal.Volume.from_name("qwen-image-weights", create_if_missing=True)
secrets = [modal.Secret.from_name("ideogram4-model-auth")]
panel_secrets = secrets + [modal.Secret.from_name("ideogram4-panel-auth")]

image = (
    modal.Image.from_registry("nvidia/cuda:12.1.1-devel-ubuntu22.04", add_python="3.11")
    .apt_install("libgomp1", "git")
    .pip_install(
        "huggingface_hub",
        "fastapi",
        "httpx",
        "torch",
        "torchvision",
        "pillow",
        "transformers",
        "accelerate",
        "safetensors",
        "sentencepiece",
        "protobuf",
        "gradio",
    )
    .pip_install("git+https://github.com/huggingface/diffusers.git")
)


def _download(repo):
    """Snapshot-download a repo into the shared HF cache on the volume."""
    from huggingface_hub import snapshot_download

    token = os.environ.get("HF_TOKEN") or None
    print(f"Downloading {repo} (cached on volume after first run)...", flush=True)
    path = snapshot_download(repo, cache_dir=MODEL_DIR, token=token)
    print(f"Download ready: {repo}", flush=True)
    return path


def _to_b64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


@app.cls(
    gpu="A100-80GB",
    image=image,
    volumes={MODEL_DIR: vol},
    secrets=secrets,
    max_containers=1,
    timeout=3600,
)
class TextServer:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import QwenImagePipeline

        path = _download(T2I_REPO)
        print("Loading Qwen-Image-2512 pipeline...", flush=True)
        self.pipe = QwenImagePipeline.from_pretrained(
            path, torch_dtype=torch.bfloat16
        ).to("cuda")
        gen = torch.Generator(device="cuda").manual_seed(42)
        _ = self.pipe(
            "a red apple on a wooden table",
            negative_prompt=DEFAULT_NEGATIVE,
            width=832,
            height=832,
            num_inference_steps=4,
            true_cfg_scale=4.0,
            generator=gen,
        ).images[0]
        print("Qwen-Image-2512 warmup done", flush=True)

    @modal.method()
    def generate(
        self,
        prompt,
        negative_prompt="",
        width=1328,
        height=1328,
        num_inference_steps=50,
        true_cfg_scale=4.0,
        seed=None,
        num_images=1,
    ):
        import torch

        gen = torch.Generator(device="cuda")
        if seed is not None:
            gen.manual_seed(int(seed))
        else:
            seed = gen.seed()

        out = self.pipe(
            prompt=prompt,
            negative_prompt=(negative_prompt or ""),
            width=int(width),
            height=int(height),
            num_inference_steps=int(num_inference_steps),
            true_cfg_scale=float(true_cfg_scale),
            generator=gen,
            num_images_per_prompt=int(num_images),
        ).images
        return {"images_b64": [_to_b64(im) for im in out], "seed": seed}


@app.cls(
    gpu="A100-80GB",
    image=image,
    volumes={MODEL_DIR: vol},
    secrets=secrets,
    max_containers=1,
    timeout=3600,
)
class EditServer:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import QwenImageEditPlusPipeline
        from PIL import Image

        path = _download(EDIT_REPO)
        print("Loading Qwen-Image-Edit-2511 pipeline...", flush=True)
        self.pipe = QwenImageEditPlusPipeline.from_pretrained(
            path, torch_dtype=torch.bfloat16
        ).to("cuda")
        warm = Image.new("RGB", (512, 512), (200, 180, 160))
        gen = torch.Generator(device="cuda").manual_seed(42)
        with torch.inference_mode():
            _ = self.pipe(
                image=[warm],
                prompt="change the background to a solid blue color",
                negative_prompt=" ",
                num_inference_steps=4,
                true_cfg_scale=4.0,
                guidance_scale=1.0,
                generator=gen,
                num_images_per_prompt=1,
            ).images[0]
        print("Qwen-Image-Edit-2511 warmup done", flush=True)

    @modal.method()
    def edit(
        self,
        images_b64,
        prompt,
        negative_prompt=" ",
        width=None,
        height=None,
        num_inference_steps=40,
        true_cfg_scale=4.0,
        guidance_scale=1.0,
        seed=None,
        num_images=1,
    ):
        import torch
        from PIL import Image

        imgs = []
        for b64 in images_b64:
            im = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
            imgs.append(im)

        gen = torch.Generator(device="cuda")
        if seed is not None:
            gen.manual_seed(int(seed))
        else:
            seed = gen.seed()

        inputs = {
            "image": imgs,
            "prompt": prompt,
            "negative_prompt": (negative_prompt if negative_prompt is not None else " "),
            "num_inference_steps": int(num_inference_steps),
            "true_cfg_scale": float(true_cfg_scale),
            "guidance_scale": float(guidance_scale),
            "generator": gen,
            "num_images_per_prompt": int(num_images),
        }
        if width and height:
            inputs["width"] = int(width)
            inputs["height"] = int(height)
        with torch.inference_mode():
            out = self.pipe(**inputs).images
        return {"images_b64": [_to_b64(im) for im in out], "seed": seed}


# ---------------- Gradio panel ----------------

# Aspect ratios from the Qwen-Image-2512 model card.
SIZE_PRESETS = {
    "1:1 — 1328×1328": (1328, 1328),
    "16:9 — 1664×928": (1664, 928),
    "9:16 — 928×1664": (928, 1664),
    "4:3 — 1472×1104": (1472, 1104),
    "3:4 — 1104×1472": (1104, 1472),
    "3:2 — 1584×1056": (1584, 1056),
    "2:3 — 1056×1584": (1056, 1584),
}
EDIT_SIZE_PRESETS = {"Auto (from input image)": (None, None), **SIZE_PRESETS}


def build_panel():
    import gradio as gr
    from PIL import Image

    def resolve_seed(seed):
        if seed is None or int(seed) < 0:
            return random.randint(0, MAX_SEED)
        return int(seed)

    def decode(images_b64):
        return [Image.open(io.BytesIO(base64.b64decode(b))) for b in images_b64]

    # ---- Text to Image (2512) ----
    def gen_t2i(prompt, negative_prompt=DEFAULT_NEGATIVE, size="1:1 — 1328×1328",
                width=1328, height=1328, steps=50, true_cfg=4.0, seed=-1, num_images=1):
        seed = resolve_seed(seed)
        call = TextServer().generate.spawn(
            (prompt or ""),
            negative_prompt=(negative_prompt or ""),
            width=int(width),
            height=int(height),
            num_inference_steps=int(steps),
            true_cfg_scale=float(true_cfg),
            seed=seed,
            num_images=int(num_images),
        )
        started = time.time()
        yield None, None, "Model is loading / generating… (first run downloads ~58 GB and takes several minutes)"
        while True:
            try:
                result = call.get(timeout=10)
                break
            except TimeoutError:
                yield None, None, f"Generating… {int(time.time() - started)}s"
        yield decode(result["images_b64"]), result["seed"], f"Done in {int(time.time() - started)}s"

    # ---- Image Edit (2511) ----
    def gen_edit(img1, img2=None, img3=None, prompt="", negative_prompt=" ",
                 size="Auto (from input image)", steps=40, true_cfg=4.0,
                 guidance=1.0, seed=-1, num_images=1):
        imgs = [im for im in (img1, img2, img3) if im is not None]
        if not imgs:
            yield None, None, "Upload at least one image first"
            return
        seed = resolve_seed(seed)
        width, height = EDIT_SIZE_PRESETS.get(size, (None, None))
        call = EditServer().edit.spawn(
            [_to_b64(im.convert("RGB")) for im in imgs],
            (prompt or ""),
            negative_prompt=(negative_prompt if negative_prompt is not None else " "),
            width=width,
            height=height,
            num_inference_steps=int(steps),
            true_cfg_scale=float(true_cfg),
            guidance_scale=float(guidance),
            seed=seed,
            num_images=int(num_images),
        )
        started = time.time()
        yield None, None, "Model is loading / editing… (first run downloads ~58 GB and takes several minutes)"
        while True:
            try:
                result = call.get(timeout=10)
                break
            except TimeoutError:
                yield None, None, f"Editing… {int(time.time() - started)}s"
        yield decode(result["images_b64"]), result["seed"], f"Done in {int(time.time() - started)}s"

    def apply_preset(name):
        if name in SIZE_PRESETS:
            w, h = SIZE_PRESETS[name]
            return w, h
        return gr.update(), gr.update()

    with gr.Blocks(title="Qwen-Image") as demo:
        gr.Markdown("# Qwen-Image")

        with gr.Tab("Text to Image — 2512"):
            t_prompt = gr.Textbox(label="Prompt", lines=3)
            t_negative = gr.Textbox(label="Negative prompt", lines=2, value=DEFAULT_NEGATIVE)
            with gr.Row():
                t_size = gr.Dropdown(label="Size", choices=list(SIZE_PRESETS) + ["Custom"],
                                     value="1:1 — 1328×1328")
                t_width = gr.Slider(label="Width", minimum=256, maximum=2048, step=16, value=1328)
                t_height = gr.Slider(label="Height", minimum=256, maximum=2048, step=16, value=1328)
            with gr.Row():
                t_steps = gr.Slider(label="Steps", minimum=1, maximum=100, step=1, value=50)
                t_cfg = gr.Slider(label="True CFG scale", minimum=0.0, maximum=10.0, step=0.1, value=4.0)
            with gr.Row():
                t_seed = gr.Number(label="Seed (−1 = random)", value=-1, precision=0)
                t_num = gr.Slider(label="Images", minimum=1, maximum=4, step=1, value=1)
            t_run = gr.Button("Generate", variant="primary")
            t_out = gr.Gallery(label="Result", columns=2)
            t_seed_out = gr.Number(label="Seed used", precision=0)
            t_status = gr.Textbox(label="Status", interactive=False)

            t_size.change(apply_preset, inputs=t_size, outputs=[t_width, t_height])
            t_run.click(
                gen_t2i,
                inputs=[t_prompt, t_negative, t_size, t_width, t_height,
                        t_steps, t_cfg, t_seed, t_num],
                outputs=[t_out, t_seed_out, t_status],
            )
            gr.Examples(
                examples=[
                    ["An ultra-realistic close-up of a golden retriever outdoors under soft daylight. Hair is exquisitely detailed: strands distinct, color transitioning naturally from warm gold to light cream. Eyes are moist and expressive; background softly blurred."],
                    ["A modern tech presentation slide, dark blue gradient background, large white bold title at the top reading \"Qwen-Image Roadmap\", a glowing horizontal timeline below with three blue rounded labels reading \"May 2025 — Project Launch\", \"August 2025 — Open Source Release\", \"December 2025 — Qwen-Image-2512 Release\", clean layout, crisp small text"],
                    ["At dawn, a thin mist veils the sea. An ancient stone lighthouse stands at the cliff's edge, its beacon faintly visible through the fog. Black rocks are pounded by waves, sending up bursts of white spray. The sky glows in soft blue-purple hues."],
                    ["A 20-year-old East Asian girl with delicate features and large bright brown eyes, naturally wavy long hair in twin ponytails, wearing a modern cute dress in bright soft colors, standing indoors at an anime convention surrounded by banners and posters, casual smartphone snapshot look, natural indoor light"],
                ],
                inputs=[t_prompt],
                outputs=[t_out, t_seed_out, t_status],
                fn=gen_t2i,
                cache_examples=False,
            )

        with gr.Tab("Image Edit — 2511"):
            gr.Markdown("Character consistency · multi-person fusion (Image 1 + Image 2) · "
                        "edit text inside images · replace materials · new viewpoints · relighting")
            with gr.Row():
                e_img1 = gr.Image(label="Image 1 (required)", type="pil")
                e_img2 = gr.Image(label="Image 2 (optional)", type="pil")
                e_img3 = gr.Image(label="Image 3 (optional)", type="pil")
            e_prompt = gr.Textbox(label="Edit instruction", lines=3)
            e_negative = gr.Textbox(label="Negative prompt", lines=1, value=" ")
            with gr.Row():
                e_size = gr.Dropdown(label="Output size", choices=list(EDIT_SIZE_PRESETS),
                                     value="Auto (from input image)")
                e_steps = gr.Slider(label="Steps", minimum=1, maximum=100, step=1, value=40)
            with gr.Row():
                e_cfg = gr.Slider(label="True CFG scale", minimum=0.0, maximum=10.0, step=0.1, value=4.0)
                e_guidance = gr.Slider(label="Guidance scale", minimum=0.0, maximum=5.0, step=0.05, value=1.0)
            with gr.Row():
                e_seed = gr.Number(label="Seed (−1 = random)", value=-1, precision=0)
                e_num = gr.Slider(label="Images", minimum=1, maximum=4, step=1, value=1)
            e_run = gr.Button("Edit", variant="primary")
            e_out = gr.Gallery(label="Result", columns=2)
            e_seed_out = gr.Number(label="Seed used", precision=0)
            e_status = gr.Textbox(label="Status", interactive=False)

            e_run.click(
                gen_edit,
                inputs=[e_img1, e_img2, e_img3, e_prompt, e_negative, e_size,
                        e_steps, e_cfg, e_guidance, e_seed, e_num],
                outputs=[e_out, e_seed_out, e_status],
            )
    return demo


# max_containers=1: Gradio's queue keeps state in memory — join and stream
# must hit the same container, or the stream 404s mid-generation.
@app.function(image=image, secrets=panel_secrets, timeout=1800, max_containers=1, scaledown_window=300)
@modal.asgi_app()
def gradio_app():
    import gradio as gr
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    web_app = FastAPI()

    @web_app.middleware("http")
    async def basic_auth(request: Request, call_next):
        user = os.environ.get("PANEL_USER", "")
        password = os.environ.get("PANEL_PASSWORD", "")
        if user and password:
            auth = request.headers.get("authorization", "")
            ok = False
            if auth.startswith("Basic "):
                try:
                    decoded = base64.b64decode(auth[6:]).decode("utf-8")
                    u, _, p = decoded.partition(":")
                    ok = u == user and p == password
                except Exception:
                    ok = False
            if not ok:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Login required"},
                    headers={"WWW-Authenticate": "Basic"},
                )
        return await call_next(request)

    return gr.mount_gradio_app(web_app, build_panel(), path="/")
