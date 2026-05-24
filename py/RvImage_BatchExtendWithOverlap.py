#
# Image Batch Extend With Overlap — blends two image batches at a shared
# overlap region for video generation extension.
#
# When both inputs are connected the overlapping frames are blended and the
# full extended sequence is returned.
# When only one input is connected that batch is returned as-is.
#
# Originally inspired by KJNodes ImageBatchExtendWithOverlap.
#

import math

import torch  # type: ignore
import torch.nn.functional as F  # type: ignore

import comfy.utils  # type: ignore

from comfy_api.latest import io  # type: ignore
from ..core import CATEGORY
from ..core.logger import log

_LOG_PREFIX = "ImageBatchExtendWithOverlap"

_OVERLAP_SIDE_OPTIONS = ["source", "new_images"]
_OVERLAP_MODE_OPTIONS = ["linear_blend", "ease_in_out", "filmic_crossfade", "perceptual_crossfade", "average", "dissolve", "pyramid_blend", "clock_wipe", "clock_wipe_ccw", "cut", "concat"]


def _clock_wipe_mask(n: int, h: int, w: int, device: torch.device, dtype: torch.dtype, clockwise: bool = True) -> torch.Tensor:
    # Returns a boolean mask [N, H, W, 1] where True = use dst (new image).
    # For frame i the swept angle threshold goes from 0 to 2π exclusive,
    # sweeping clockwise (or counter-clockwise) from 12 o'clock.
    cy = (h - 1) / 2.0
    cx = (w - 1) / 2.0
    y = torch.arange(h, device=device, dtype=torch.float32)
    x = torch.arange(w, device=device, dtype=torch.float32)
    yy, xx = torch.meshgrid(y, x, indexing="ij")                  # [H, W]
    # atan2(dx, -dy): 0 at top, increases clockwise; result in (-π, π]
    angle = torch.atan2(xx - cx, cy - yy)
    angle = (angle + 2 * math.pi) % (2 * math.pi)                 # [H, W] in [0, 2π)
    if not clockwise:
        angle = (2 * math.pi - angle) % (2 * math.pi)             # flip direction
    # Per-frame threshold: frame 0 → tiny slice, frame N-1 → almost full circle
    thresholds = torch.linspace(0, 2 * math.pi, n + 2, device=device, dtype=torch.float32)[1:-1]  # [N]
    mask = angle.unsqueeze(0) < thresholds.view(-1, 1, 1)         # [N, H, W]
    return mask.unsqueeze(-1).to(dtype=torch.bool)                 # [N, H, W, 1]


def _pyramid_blend(src: torch.Tensor, dst: torch.Tensor, alpha: torch.Tensor, levels: int = 4) -> torch.Tensor:
    # Multi-scale Laplacian pyramid blend.
    # src, dst: [N, H, W, C]   alpha: [N, 1, 1, 1] in 0..1
    # Each spatial frequency band is blended independently with the same per-frame alpha,
    # which produces sharper edges than a plain pixel-level crossfade.
    src_f = src.float().permute(0, 3, 1, 2)  # NCHW
    dst_f = dst.float().permute(0, 3, 1, 2)

    def _laplacian(x: torch.Tensor) -> list:
        gauss = [x]
        for _ in range(levels - 1):
            gauss.append(F.avg_pool2d(gauss[-1], kernel_size=2, stride=2, padding=0))
        lap = []
        for i in range(levels - 1):
            up = F.interpolate(gauss[i + 1], size=gauss[i].shape[2:], mode="bilinear", align_corners=False)
            lap.append(gauss[i] - up)
        lap.append(gauss[-1])  # coarsest level stored as-is
        return lap

    lap_src = _laplacian(src_f)
    lap_dst = _laplacian(dst_f)

    blended_lap = [(1 - alpha) * ls + alpha * ld for ls, ld in zip(lap_src, lap_dst)]

    result = blended_lap[-1]
    for lap in reversed(blended_lap[:-1]):
        result = F.interpolate(result, size=lap.shape[2:], mode="bilinear", align_corners=False) + lap

    return result.permute(0, 2, 3, 1).to(src.dtype)  # back to NHWC


def _resize_to_match(images: torch.Tensor, target_h: int, target_w: int) -> torch.Tensor:
    # Scale to fill target size (preserving aspect ratio) then center-crop to exact dimensions.
    # Mirrors the "crop" fit mode in RvImage_Resize: scale = max(tw/W, th/H).
    h, w = images.shape[1], images.shape[2]
    if h == target_h and w == target_w:
        return images

    # Scale so both dimensions meet or exceed the target.
    scale = max(target_w / w, target_h / h)
    inter_w = max(int(round(w * scale)), target_w)
    inter_h = max(int(round(h * scale)), target_h)

    # Resize via comfy's upscaler (BHWC → BCHW → upscale → BHWC).
    samples = images.movedim(-1, 1)
    samples = comfy.utils.common_upscale(samples, inter_w, inter_h, "bilinear", "disabled")
    images = samples.movedim(1, -1)

    # Center-crop to exact target dimensions.
    cx = (inter_w - target_w) // 2
    cy = (inter_h - target_h) // 2
    return images[:, cy : cy + target_h, cx : cx + target_w, :]


class RvImage_BatchExtendWithOverlap(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Image Batch Extend With Overlap [Eclipse]",
            display_name="Image Batch Extend With Overlap",
            description=(
                "Extends a video batch by blending two image sequences at an overlapping region.\n"
                "Both inputs connected: blends the overlap and returns the full extended sequence.\n"
                "Only source_images: returned as-is.\n"
                "Only new_images: returned as-is.\n"
                "If the two inputs differ in size, new_images is center-cropped and resized to match source_images."
            ),
            category=CATEGORY.MAIN.value + CATEGORY.IMAGE.value,
            inputs=[
                io.Image.Input(
                    "source_images",
                    optional=True,
                    tooltip="The source (first) image batch. Optional — when not connected, new_images is returned as-is.",
                ),
                io.Int.Input(
                    "overlap",
                    default=5,
                    min=1,
                    max=4096,
                    step=1,
                    tooltip="Number of overlapping frames between source and new images.",
                ),
                io.Combo.Input(
                    "overlap_side",
                    options=_OVERLAP_SIDE_OPTIONS,
                    default="source",
                    tooltip=(
                        "Only affects cut mode — controls which side loses frames.\n"
                        "source: cut drops the last N frames of source_images.\n"
                        "new_images: cut drops the first N frames of new_images (useful to skip a slow scene start).\n"
                        "All blending modes always transition source → new regardless of this setting."
                    ),
                ),
                io.Combo.Input(
                    "overlap_mode",
                    options=_OVERLAP_MODE_OPTIONS,
                    default="pyramid_blend",
                    tooltip=(
                        "How to blend the overlapping region.\n"
                        "linear_blend: linear cross-fade.\n"
                        "ease_in_out: S-curve cross-fade (slow start/end).\n"
                        "filmic_crossfade: gamma-correct (2.2) cross-fade — better in bright regions.\n"
                        "perceptual_crossfade: LAB-space blend — avoids hue shifts across strong color differences (requires kornia).\n"
                        "average: fixed 50/50 mix of all overlap frames — no directional fade, both generations contribute equally.\n"
                        "dissolve: random pixel-level selection per frame (dithered transition, film-grain look).\n"
                        "pyramid_blend: multi-scale Laplacian pyramid — each frequency band blended independently; sharpest quality.\n"
                        "clock_wipe: clockwise sweep from 12 o'clock — a hard edge rotates across the frame like a clock hand.\n"
                        "clock_wipe_ccw: same sweep counter-clockwise.\n"
                        "cut: drops overlap frames from one side — overlap_side=source removes last N from source; overlap_side=new_images removes first N from new_images (useful to skip a slow scene start).\n"
                        "concat: direct concatenation, no frames lost, overlap parameter ignored."
                    ),
                ),
                io.Image.Input(
                    "new_images",
                    optional=True,
                    tooltip="The new (second) image batch to extend with. Optional — when not connected, source_images is returned as-is.",
                ),
            ],
            outputs=[
                io.Image.Output(
                    "images",
                    tooltip="The extended image batch with the overlap region blended, or whichever single input was connected.",
                ),
            ],
        )

    @classmethod
    def execute(cls, overlap, overlap_side, overlap_mode, source_images=None, new_images=None):
        # Single-input passthrough.
        if source_images is None and new_images is None:
            raise ValueError("At least one of source_images or new_images must be connected.")
        if source_images is None:
            return io.NodeOutput(new_images)
        if new_images is None:
            return io.NodeOutput(source_images)

        # Both inputs connected — blend the overlap region.
        actual_overlap = min(overlap, len(source_images))
        if actual_overlap != overlap:
            log.warning(
                _LOG_PREFIX,
                f"overlap ({overlap}) exceeds source length ({len(source_images)}), clamped to {actual_overlap}.",
            )

        target_h, target_w = source_images.shape[1], source_images.shape[2]
        if new_images.shape[1] != target_h or new_images.shape[2] != target_w:
            log.warning(
                _LOG_PREFIX,
                f"new_images size {new_images.shape[2]}x{new_images.shape[1]} differs from "
                f"source_images {target_w}x{target_h} — center-cropping and resizing new_images to match.",
            )
            new_images = _resize_to_match(new_images, target_h, target_w)

        prefix = source_images[:-actual_overlap]

        # Blend always runs source → new. overlap_side only affects cut mode.
        blend_src = source_images[-actual_overlap:]
        blend_dst = new_images[:actual_overlap]

        suffix = new_images[actual_overlap:]

        if overlap_mode == "cut":
            if overlap_side == "source":
                extended_images = torch.cat((source_images[:-actual_overlap], new_images), dim=0)
            else:
                extended_images = torch.cat((source_images, new_images[actual_overlap:]), dim=0)

        elif overlap_mode == "clock_wipe":
            # Clockwise sweep from 12 o'clock: a hard edge rotates across the frame,
            # gradually replacing src pixels with dst pixels each frame.
            N, H, W, _C = blend_src.shape
            mask = _clock_wipe_mask(N, H, W, blend_src.device, blend_src.dtype)  # [N, H, W, 1]
            blended = torch.where(mask.expand_as(blend_src), blend_dst, blend_src)
            extended_images = torch.cat((prefix, blended, suffix), dim=0)

        elif overlap_mode == "clock_wipe_ccw":
            N, H, W, _C = blend_src.shape
            mask = _clock_wipe_mask(N, H, W, blend_src.device, blend_src.dtype, clockwise=False)
            blended = torch.where(mask.expand_as(blend_src), blend_dst, blend_src)
            extended_images = torch.cat((prefix, blended, suffix), dim=0)

        elif overlap_mode == "linear_blend":
            alpha = torch.linspace(0, 1, actual_overlap + 2, device=blend_src.device, dtype=blend_src.dtype)[1:-1]
            alpha = alpha.view(-1, 1, 1, 1)
            blended = (1 - alpha) * blend_src + alpha * blend_dst
            extended_images = torch.cat((prefix, blended, suffix), dim=0)

        elif overlap_mode == "ease_in_out":
            t = torch.linspace(0, 1, actual_overlap + 2, device=blend_src.device, dtype=blend_src.dtype)[1:-1]
            eased = 3 * t * t - 2 * t * t * t
            eased = eased.view(-1, 1, 1, 1)
            blended = (1 - eased) * blend_src + eased * blend_dst
            extended_images = torch.cat((prefix, blended, suffix), dim=0)

        elif overlap_mode == "filmic_crossfade":
            gamma = 2.2
            alpha = torch.linspace(0, 1, actual_overlap + 2, device=blend_src.device, dtype=blend_src.dtype)[1:-1]
            alpha = alpha.view(-1, 1, 1, 1)
            linear_src = torch.pow(blend_src.clamp(min=0), gamma)
            linear_dst = torch.pow(blend_dst.clamp(min=0), gamma)
            blended = torch.pow(((1 - alpha) * linear_src + alpha * linear_dst).clamp(min=0), 1.0 / gamma)
            extended_images = torch.cat((prefix, blended, suffix), dim=0)

        elif overlap_mode == "perceptual_crossfade":
            try:
                import kornia  # type: ignore
            except ImportError:
                log.warning(
                    _LOG_PREFIX,
                    "kornia is required for perceptual_crossfade — falling back to linear_blend. "
                    "Install with: pip install kornia",
                )
                alpha = torch.linspace(0, 1, actual_overlap + 2, device=blend_src.device, dtype=blend_src.dtype)[1:-1]
                alpha = alpha.view(-1, 1, 1, 1)
                blended = (1 - alpha) * blend_src + alpha * blend_dst
                extended_images = torch.cat((prefix, blended, suffix), dim=0)
            else:
                alpha = torch.linspace(0, 1, actual_overlap + 2, device=blend_src.device, dtype=blend_src.dtype)[1:-1]
                alpha = alpha.view(-1, 1, 1, 1)
                src_nchw = blend_src.movedim(-1, 1)
                dst_nchw = blend_dst.movedim(-1, 1)
                lab_src = kornia.color.rgb_to_lab(src_nchw)
                lab_dst = kornia.color.rgb_to_lab(dst_nchw)
                blended_lab = (1 - alpha) * lab_src + alpha * lab_dst
                blended_rgb = kornia.color.lab_to_rgb(blended_lab)
                blended = blended_rgb.movedim(1, -1)
                extended_images = torch.cat((prefix, blended, suffix), dim=0)

        elif overlap_mode == "average":
            # Fixed 50/50 blend across all overlap frames — no directional fade.
            blended = 0.5 * blend_src + 0.5 * blend_dst
            extended_images = torch.cat((prefix, blended, suffix), dim=0)

        elif overlap_mode == "dissolve":
            # Per-pixel random selection: at frame i, alpha[i] fraction of pixels come from dst.
            # Creates a dithered/grain-textured transition instead of a smooth fade.
            alpha = torch.linspace(0, 1, actual_overlap + 2, device=blend_src.device, dtype=blend_src.dtype)[1:-1]
            noise = torch.rand(
                actual_overlap, blend_src.shape[1], blend_src.shape[2], 1,
                device=blend_src.device, dtype=blend_src.dtype,
            )
            mask = noise < alpha.view(-1, 1, 1, 1)
            blended = torch.where(mask, blend_dst, blend_src)
            extended_images = torch.cat((prefix, blended, suffix), dim=0)

        elif overlap_mode == "pyramid_blend":
            # Multi-scale Laplacian pyramid blend — each frequency band blended independently.
            alpha = torch.linspace(0, 1, actual_overlap + 2, device=blend_src.device, dtype=blend_src.dtype)[1:-1]
            alpha = alpha.view(-1, 1, 1, 1)
            blended = _pyramid_blend(blend_src, blend_dst, alpha)
            extended_images = torch.cat((prefix, blended, suffix), dim=0)

        elif overlap_mode == "concat":
            # Direct concatenation — no frame loss, overlap parameter is ignored.
            extended_images = torch.cat((source_images, new_images), dim=0)

        else:
            log.warning(_LOG_PREFIX, f"Unknown overlap_mode '{overlap_mode}', falling back to linear_blend.")
            alpha = torch.linspace(0, 1, actual_overlap + 2, device=blend_src.device, dtype=blend_src.dtype)[1:-1]
            alpha = alpha.view(-1, 1, 1, 1)
            blended = (1 - alpha) * blend_src + alpha * blend_dst
            extended_images = torch.cat((prefix, blended, suffix), dim=0)

        return io.NodeOutput(extended_images)
