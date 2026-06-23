# Changelog

All notable changes to ComfyUI Eclipse are documented in this file.

Entries follow conventional commit prefixes:

## 2026-06-23

### Version: 3.7.10

- **fix:** Set/Get and Mode Bridge conflict renaming — duplicate name suffixes now start at `_1` (e.g. `model_detailer_1`) instead of `_0` (e.g. `model_detailer_0`), matching standard user workflow numbering conventions.

**Changed files:**

- `js/eclipse-set-get.js`
- `js/eclipse-mode-nodes.js`

---

## 2026-06-22

### Version: 3.7.9

- **feat: new** Image Upscale With Model v2 — created a new v2 version of the upscale node containing:
  - `"None"` selection in the model list to perform direct upscaling without loading a model.
  - `resolution_steps` input to round output dimensions to the nearest multiple of the specified value.
  - Post-processing Smart Sharpen filter (with `sharpen_enabled`, `sharpen_amount`, `sharpen_ratio`, `noise_radius`, and `preserve_edges` controls) utilizing bilateral filtering and Kornia contrast-based sharpness.
- **feat: new** SEGS Preview Simple — created a simplified version of the SEGS preview node with only `segs` and `fallback_image_opt` inputs, `IMAGE` output, and hardcoded settings (`alpha_mode=True`, `min_alpha=0.2`, and no crop padding).
- **refactor:** Align the order of `resample_options` (`nearest-exact`, `bilinear`, `area`, `bicubic`, `lanczos`) across all resizing/scaling nodes with ComfyUI core nodes.

**Changed files:**

- `py/RvImage_UpscaleWithModel.py`
- `py/RvImage_UpscaleWithModel_v2.py`
- `py/RvImage_SEGSPreview_Simple.py`
- `py/RvImage_Rescale.py`
- `py/RvImage_Resize.py`
- `py/RvImage_AlignSize.py`
- `py/RvImage_CropByMask.py`
- `__init__.py`

---

### Version: 3.7.8

- **fix:** Show Text — set `serialize: false` on the frontend DOM widget to prevent it from serializing to the execution prompt's `inputs` on subsequent runs. This fixes the execution caching bug where downstream nodes were forced to re-execute once after the first run.

**Changed files:**

- `js/eclipse-show-text.js`

---

## 2026-06-21

### Version: 3.7.7

**feat:** Show Text — accepts any input type (AnyType) instead of STRING-only; converts values to readable text using json/torch-aware serialization (mirrors ComfyUI core PreviewAny logic)
**feat:** Show Text — new STRING output so text value persists in subgraphs; DOM widget serialization enabled for cross-graph persistence

**Changed files:**

- `py/RvTools_ShowText.py, js/eclipse-show-text.js`

---

## 2026-06-20

### Version 3.7.6

- **fix:** IO Sampler Settings v2.1 — preserve `_allow_overwrite` flag in returned pipe context so downstream IO nodes respect connected value overrides

**Changed files:**

- `py/RvPipe_IO_Sampler_Settings_v21.py`

---

### Version 3.7.5

- **feat:** Save Images v2 — reads cached model hashes and Civitai AIR metadata from `.eclipse.json` sidecar files via `read_expected`, skipping expensive hashing calls and automatically injecting retrieved AIRs into the output image's workflow metadata (`extra.airs`)

**Changed files:**

- `py/RvImage_SaveImages.py`

---

### Version 3.7.4

- **feat:** Image Resolution — added `batch_size` input and output widget
- **refactor:** Sampler Settings — fully migrated `image_seed` to standard `seed` and removed backward compatibility shims

**Changed files:**

- `py/RvPipe_IO_Sampler_Settings_v22.py`
- `py/RvSettings_Image_Resolution.py`
- `py/RvSettings_SmartSamplerSettings_v2.py`

---

## 2026-06-16

### Version 3.7.3

- **fix:** Smart Model Loader — restored the integrity file hashing backend that was accidentally wiped out during local file reversion

**Changed files:**

- `js/eclipse-smart-model-loader.js`
- `py/RvLoader_SmartModelLoader.py`

---

### Version 3.7.2

- **fix:** Smart Model Loader — restored missing default resolution strings in JS templates and Python backend to avoid fallback failures and `UnboundLocalError`
- **fix:** Image Resolution — corrected `io.Int.Input` schema typing error for ComfyUI V3 API causing startup crashes
- **refactor:** Constants — sorted `RESOLUTION_PRESETS` and `RESOLUTION_MAP` sequentially by width in `core/common.py` for better UI organization

**Changed files:**

- `js/eclipse-smart-model-loader.js`, `js/eclipse-smart-loader-plus-v2.js`, `js/eclipse-smart-model-loader-legacy.js`
- `py/RvLoader_SmartModelLoader.py`
- `core/common.py`

---

### Version 3.7.1

- **fix:** Smart Model Loader — decoupled `latent` and `seed` states from template loading; templates no longer overwrite user-selected chip states (e.g. width/height or seed values) when switching models
- **fix:** Smart Model Loader — fixed `TypeError` when latent/seed chips were enabled after being disabled by providing proper fallbacks internally
- **fix:** Smart Model Loader — fixed `1024x1024 (1:1)` default resolution string mismatch causing fallback failures with the internal `RESOLUTION_MAP`

**Changed files:**

- `js_src/eclipse-smart-model-loader.js`, `js/eclipse-smart-model-loader.js`
- `py/RvLoader_SmartModelLoader.py`, `py/RvSettings_Image_Resolution.py`
- `py/legacy/legacy_SmartModelLoader.py`, `py/legacy/legacy_SmartLoader_Plus.py`, `py/legacy/legacy_SmartLoader_Plus_v2.py`

---

## 2026-06-13

### Version 3.7.0

- **feat: new** model integrity system — `core/model_integrity.py` provides shared SHA256 hashing with canonical `<file.ext>.sha256` sidecars, legacy `<file-no-ext>.sha256` read compatibility, stale-sidecar invalidation by file/sidecar mtime, an expected-metadata store in `<file.ext>.eclipse.json` (read/write), and `verify()` with `ok`/`mismatch`/`no-expected`/`missing`/`unverifiable` statuses
- **feat: new** CivitAI client — `core/civitai_client.py` resolves files by AIR (`urn:air:...`) or SHA256 (`by-hash`), parses AIR (model/version/file id), picks the file by fileId/SHA/primary, and streams downloads with auth + `.part` atomic rename
- **feat:** Smart Model Loader v2 — add `verify_file` (`off`/`sidecar`/`verify`), `expected_hashes` map, a single `air_or_hash` editor field (annotates the currently selected model file, or drives a locator-only download when the file is missing), `download_locators`, and `download_target_role`; `execute()` warms SHA sidecars and warn+continue verifies active files (`.eclipse.json` first, `expected_hashes` fallback)
- **feat:** Smart Model Loader v2 — CivitAI download button (filename resolved from metadata), dynamic model selection state, switching models loads that file's stored value (no stale carry-over), missing-file auto-reveal of the integrity editor + download button independent of verify mode, and pending/missing file-selection preservation across template load + list refresh
- **feat:** Smart Model Loader v2 — dual-mode action button: present file → `✓ Verify now` (hashes + compares immediately, shows ok/mismatch inline), missing file or locator → `⬇ Download from CivitAI`; label/action swap automatically with the model selection
- **feat:** Smart Model Loader v2 — missing-file UX: `verify_file` auto-promoted from `off` → `verify` when a file is missing; `download_target_role` shown and auto-filled (via `getRoleForTarget`) when the selected model file is absent
- **feat:** Smart Model Loader v2 — download_preference combo filters available file variants (e.g., fp8/fp16/bf16) and prioritizes the primary file when multiple match the selected precision; fallback to SHA256 when present, otherwise AIR

- **fix:** block_swap chip disabling — update dynamic VRAM detection for ComfyUI 0.23.0+; `ModelPatcherDynamic` subclass replaces the `model_mmap_residency` attribute from 0.18.x; detection now checks `hasattr(module, 'ModelPatcherDynamic')` with 0.18.x fallback

- **refactor:** Save Images v2 — `get_sha256` now delegates to `core.model_integrity.sha256_for`, unifying hashing + sidecar conventions and adding size/mtime-aware cache invalidation

**Changed files:**

- `core/model_integrity.py` (new), `core/civitai_client.py` (new, resume support)
- `core/server_endpoints.py` (run_in_executor for download progress)
- `js/eclipse-smart-model-loader.js` (✓ Verified state, auto-save template, update target widget on download)
- `py/RvLoader_SmartModelLoader.py`
- `py/RvImage_SaveImages.py`

---

## 2026-06-10

### Version 3.6.4

- **fix:** Folder Path — date/time sub-widgets (`date_time_format`, `date_time_position`) now show on fresh add when `create_date_time_folder` defaults to yes; deferred the initial visibility pass to the next frame so `node.id` is assigned before `updateVisibility` runs

**Changed files:**

- `js/eclipse-folder-path.js`

---

### Version 3.6.3

- **feat:** Image Rescale — dynamic widget visibility: `rescale` mode hides `resize_width`/`resize_height`, `resize` mode hides `rescale_factor`, and `supersample_factor` hides when `supersample` is off; shrinks the node and hides unused values
- **fix:** Load Audio — `start_time`/`duration` now constrain preview playback via HTML5 media fragment (`#t=start,end`) and re-seek to the window start when edited, so pressing play only plays the selected segment (mirrors VHS LoadAudioUpload)

**Changed files:**

- `js/eclipse-image-rescale.js` (new)
- `js/eclipse-load-audio.js`

---

## 2026-06-09

### Version 3.6.2

- **fix:** Image Rescale — supersample now applies when enlarging too (upscale to target × supersample_factor, then downscale to target); previously skipped with a warning whenever the output was larger than the source

**Changed files:**

- `py/RvImage_Rescale.py`

---

### Version 3.6.1

- **feat:** Smart Model Loader v2 — replace the seed-mode chips (🎲 random / ⏫ increment / ⏬ decrement) with dedicated seed buttons (`🎲 Randomize Each Time`, `🎲 New Fixed Random`, `♻️ Use Last Queued Seed`) like Smart LM Loader; the `seed` chip still toggles the seed widget
- **fix:** Smart Model Loader v2 — `stop_at_clip_layer` now hides when `enable_clip_layer` is off (was always visible while clip was enabled)
- **chore:** deprecate **Smart Model Loader v1** — cloned to `py/legacy` (`node_id` `Smart Model Loader [Eclipse]` unchanged so existing workflows still resolve)

**Changed files:**

- `py/RvLoader_SmartModelLoader.py` (now v2), `js/eclipse-smart-model-loader.js` (now v2)
- `py/legacy/legacy_SmartModelLoader.py` (new), `js/eclipse-smart-model-loader-legacy.js` (new)
- `__init__.py`

---

### Version 3.6.0

- **feat:** Smart Model Loader — new `audio_vae` chip loads an LTXV/LTX2 audio VAE (**Baked** from a Standard Checkpoint or UNet Model all-in-one file, or **External** from the `vae` folder); filters `audio_vae.`/`vocoder.` keys like ComfyUI's `LTXVAudioVAELoader` and routes the result through a new `audio_vae` pipe field
- **feat:** Smart Model Loader — new CLIP source `External + Model File` appends the loaded checkpoint/UNet file to `comfy.sd.load_clip` so a baked text-projection (LTXAV gemma recipe) is auto-detected
- **feat:** Smart Model Loader + Clip Loader — add new ComfyUI 0.23 CLIP types: `cogvideox`, `lens`, `longcat_image`, `pixeldit`
- **feat:** new **VAE Loader Video+Audio** node — loads a video/image VAE and an LTXV/LTX2 audio VAE in one node (both from the `vae` folder) with separate outputs; for the GGUF LTX2 flow where neither VAE is baked into the model file
- **feat:** new **IO Checkpoint Loader v2** node — adds an `audio_vae` output (after `vae`) for LTXV/LTX2; separate node from v1 so existing workflows keep their slot indices
- **chore:** deprecate **IO Checkpoint Loader v1** — moved to `py/legacy` (node_id unchanged so old workflows still resolve); use **IO Checkpoint Loader v2** for new workflows
- **feat:** Model Loader + Model Loader Pipe — optional `ltx_text_encoder` widget combines an external gemma with the loaded Standard Checkpoint/UNet file's baked text-projection to build a correct LTXAV CLIP (overrides the empty baked CLIP); auto-extracted baked `audio_vae` output via cheap safetensors header-peek for LTX2 all-in-one files
- **chore:** replace deprecated `HF_HUB_ENABLE_HF_TRANSFER` env var with `HF_XET_HIGH_PERFORMANCE`; remove dead `hf_transfer` auto-install block (`hf_transfer` is no longer used by `huggingface_hub`)

**Changed files:** `py/RvLoader_SmartModelLoader.py`, `js/eclipse-smart-model-loader.js`, `core/model_loader_common.py`, `py/RvPipe_IO_Context_Image.py`, `py/RvLoader_ClipLoader.py`, `py/RvLoader_ModelLoader.py`, `py/RvLoader_ModelLoaderPipe.py`, `py/RvLoader_VaeLoaderVideoAudio.py` (new), `py/RvPipe_IO_CheckpointLoader_v2.py` (new), `py/legacy/legacy_IO_CheckpointLoader.py` (moved from py/), `js/eclipse-model-loader.js`, `__init__.py`, `py/RvLoader_SmartDetection.py`, `py/RvLoader_SmartModelLoader_LM.py`, `core/sml/model_files.py`

---

## 2026-06-07

### Version 3.5.46

- **fix:** DOM preview grid mode — replace `gridAutoRows='1fr'` + `overflow-y:auto` (circular size dependency causing scroll-instead-of-fit) with explicit pixel row height computed from container dimensions; `ResizeObserver` now recalculates both columns and row height on every node resize so all images always fill the available space
- **fix:** DOM preview grid mode — dynamic column count: replace hard cap of 4 with `ideal=sqrt(n×w/h/avgAR) ±2` so wide nodes with many portrait images pick the correct number of columns; skip column counts where `cellH/cellW ≤ 0` (gaps exceed container) to prevent 1-column fallback with large image counts
- **fix:** Image Batch Extend With Overlap — allow `overlap=0` as a hard cut (concatenate directly, ignore mode); previously `min=1`; `source[:-0]` in Python returns an empty tensor so `overlap=0` is intercepted with an early return before any slicing
- **fix:** Image Batch Extend With Overlap — clamp `actual_overlap` to `min(overlap, len(source), len(new_images))`; previously only clamped to source length so `overlap > len(new_images)` silently produced an empty batch

- **feat:** new **Image Selector** node — pauses workflow on first run and shows all images in an interactive grid; click to toggle, Shift+click for range, Ctrl+A / Esc; Confirm auto-requeues; outputs selected images as `batch` (resized to first) and `list` (original sizes); selection persists across re-queues until Discard; page reload resets to first run; hidden `execution_trigger` widget forces re-execution; fingerprint detects upstream `resize_mode` changes
- **feat:** new **Batch Slice** node — slices a batch [B,H,W,C] by start/end index; 0-based, negatives count from end, `end=0` means last frame
- **feat:** new **Batch Interleave** node — merges two batches frame by frame (a[0], b[0], a[1], b[1], …); remaining frames from the longer batch are appended at the end
- **feat:** new **Load Batch From Folder** node — loads images (folder scan) and video frames (explicit file path, PyAV) from one or more paths per line; `frame_start`/`frame_end` range with seek-optimised per-file loading; `resize_mode` (first/largest/smallest/none/list); Refresh File List button invalidates cache; progress bar; outputs images and masks
- **feat:** Preview Image, Preview Image DOM, Image Selector — progress bar added to temp-file save loop; allows cancelling large batches
- **feat:** new **Video Frame Consistency** node — six independently switchable post-processing steps to reduce quality and colour drift between sliding context windows in WAN / CogVideo generation: Section Colour Normalise (mean+std alignment per window), Histogram Match (per-frame to reference, blended strength), Luminance Normalise (LAB L-channel only), Boundary Crossfade (smooth cuts at window edges), Temporal Smooth (Gaussian-weighted neighbour blend), Sharpen Recover (adaptive unsharp mask with per-frame ramp)

- **chore:** move Load Image, Load Image (Pipe), Load Image From Folder, Load Image From Folder (Pipe), Load Batch From Folder to category `🌒 Eclipse/ Loader` (was `🌒 Eclipse/ Image`)

**Changed files:**

- `js/eclipse-dom-preview.js`, `js/eclipse-image-selector.js` (new), `js/eclipse-load-batch-from-folder.js` (new), `py/RvImage_BatchExtendWithOverlap.py`, `py/RvImage_BatchInterleave.py` (new), `py/RvImage_BatchSlice.py` (new), `py/RvImage_LoadBatchFromFolder.py` (new), `py/RvImage_LoadImage.py`, `py/RvImage_LoadImage_Pipe.py`, `py/RvImage_LoadImageFromFolder.py`, `py/RvImage_LoadImageFromFolder_Pipe.py`, `py/RvImage_Preview_Image.py`, `py/RvImage_Preview_Image_DOM.py`, `py/RvImage_Selector.py` (new), `py/RvVideo_FrameConsistency.py` (new), `core/server_endpoints.py`, `__init__.py`

---

## 2026-06-06

### Version 3.5.45

- **fix:** Wan 2.2 CN Atomic system prompt — camera movement is now conditional (only when user explicitly requests it); previously forced strong dynamic camera movement on every output

**Changed files:**

- `config/system_prompts.json`, `.defaults/config/system_prompts.json.example`, `.defaults/.manifest.json`

---

### Version 3.5.44

- **feat:** Mode Relay — right-click context menu to switch group scope: `Root nodes only` (default, matches native ComfyUI behavior) or `All nodes incl. subgraphs` (recurses into subgraph internals); setting persisted in node properties

**Changed files:**

- `js_src/eclipse-mode-nodes.js`, `js/eclipse-mode-nodes.js`

---

### Version 3.5.43

- **fix:** Smart LM all backends — few-shot JSON stores every level as list-of-pairs; `_load_few_shot_configs` now recursively normalizes entries and their nested example messages to plain dicts; fixes `'list' has no attribute 'get'` (top-level) and Ollama `cannot unmarshal array into Go struct field messages` (nested messages sent as arrays)

**Changed files:**

- `core/sml/config_templates.py`

---

### Version 3.5.42

- **fix:** Smart LM vision few-shot — example messages are stored as list-of-pairs; `get_vision_few_shot_messages` now converts each example to a dict before use; previously passed raw lists into the message chain causing `TypeError: list indices must be integers or slices, not str` when the backend iterated them

**Changed files:**

- core/sml/config_templates.py

---

### Version 3.5.41

- **fix:** Smart LM few-shot — `wan_2.2_cn_atomic` entry was using dict format instead of list-of-pairs like all other tasks; caused `'list' has no attribute 'get'` crash on any vision task; converted both SFW and NSFW JSON files to the consistent format; added list-to-dict guard in `get_vision_few_shot_messages`

**Changed files:**

- core/sml/config_templates.py
- config/llm_few_shot_training.json
- config/llm_few_shot_training_nsfw.json

---

### Version 3.5.40

- **feat:** new `Any Multi-Switch Lazy` node — lazy variant of Any Multi-Switch that evaluates upstream inputs one at a time in priority order; only the first connected, non-None slot's upstream graph executes; all other branches are skipped entirely; dynamically expands inputs via `inputcount` widget like the regular multi-switch
- **feat:** new `Any Multi-Switch Lazy Purge` node — same as above with optional VRAM purge before switching

- **feat:** Image Filter Adjustments — vectorize brightness/contrast ops over the full batch tensor; PIL ops (saturation, sharpness, blur, etc.) process one frame at a time by default (`per_frame=true`, avoids OOM on large batches); set `per_frame=false` to run all frames in parallel via threads; drop numpy dependency

- **fix:** Image Comparer — normalize inputs to 4-D tensors at execute time; handles image-list connections (Python list of tensors) and 3-D single-frame tensors; only first frame shown in display for batches and lists
- **fix:** Color Match — only use the first frame of `image_ref` as the color reference; batches are no longer treated as per-frame reference sequences

**Changed files:**

- py/RvRouter_Any_MultiSwitch_lazy.py (new)
- py/RvRouter_Any_MultiSwitch_lazy_purge.py (new)
- py/RvImage_ImageComparer.py
- py/RvImage_ColorMatch.py
- py/RvImage_FilterAdjustments.py
- js/eclipse-dynamic-inputs.js

---

### Version 3.5.39

- **feat:** new Smart LM task "Wan 2.2 CN Atomic" — Chinese-language Wan 2.2 video prompt writer using the 逻辑原子化 (logical atomization) principle; structured output: initial state anchor → ordered action sequence with degree adverbs → final freeze-frame → professional camera instruction; built-in cinematography vocabulary reference (light sources, shot types, framing, movement, style)

**Changed files:**

- config/system_prompts.json
- config/llm_few_shot_training.json
- config/llm_few_shot_training_nsfw.json
- core/sml/tasks.py
- py/RvLoader_SmartModelLoader_LM.py

---

## 2026-06-04

### Version 3.5.38

- **feat: new** Folder Path node — builds an output folder path from root folder, optional date/time subfolder, and optional batch subfolder; single `STRING` output; widget visibility hides sub-widgets when toggles are off

- **feat:** IF A Else B — `on_false` is now optional (unconnected returns `None`); `boolean` is now a widget (default `False`) with fallback when upstream is muted/bypassed; lazy evaluation added (only the selected branch executes)
- **feat:** Save Images v2 — `output_path` now accepts absolute paths outside the ComfyUI output folder; images saved to final destination via temp-then-copy so UI preview still works
- **feat:** Save Video — `filename_prefix` now accepts absolute paths outside the ComfyUI output folder; video encoded to temp then copied to final destination so UI preview still works
- **feat:** Image Batch Extend With Overlap — eight new hybrid match+blend modes (`match_ncc+linear`, `match_ncc+pyramid`, `match_mse+linear`, `match_mse+pyramid`, `match_luminance_mse+linear`, `match_luminance_mse+pyramid`, `match_gradient_mse+linear`, `match_gradient_mse+pyramid`): finds the best-matching frame pair as before, then applies a linear or pyramid blend window of `overlap` frames at that cut point instead of hard-cutting; smooths the model ramp-in freeze that made pure match modes appear to stutter before the cut
- **feat:** Image Batch Extend With Overlap — four new directional wipe modes (`wipe_left`, `wipe_right`, `wipe_top`, `wipe_bottom`): hard edge sweeps across the frame in the named direction over the overlap window, similar to `clock_wipe` but axis-aligned
- **feat:** Color Match — new `per_frame` bool (default `False`): when enabled, processes each frame independently instead of the whole batch at once; caps VRAM to one frame at a time for GPU methods at the cost of extra dispatches
- **chore:** deprecate IF A Else B (Fallback) — superseded by IF A Else B which now has identical capabilities

**Deprecated nodes:**

- IF A Else B (Fallback) [Eclipse] (1)

**Changed files:**

- `py/RvFolder_FolderPath.py` (new)
- `js/eclipse-folder-path.js` (new)
- `py/RvRouter_IfElse.py`
- `py/legacy/legacy_IfElse_Fallback.py` (new)
- `py/RvImage_SaveImages.py`
- `py/RvImage_Save_Video.py`
- `py/RvImage_BatchExtendWithOverlap.py`
- `py/RvImage_ColorMatch.py`
- `__init__.py`

---

### Version 3.5.37

- **feat: new** Get First Image node — returns the first image from a batch `[B,H,W,C]` or list; mirrors Get Last Image
- **feat: new** Image Batch Strip node — removes N frames from `start`, `end`, or `both` ends of a batch `[B,H,W,C]`; safe-guarded against over-stripping
- **feat:** Image Batch Extend With Overlap — four new `overlap_mode` entries (`match_ncc`, `match_mse`, `match_luminance_mse`, `match_gradient_mse`): scan frames of source against frames of new_images (window size = `overlap`) and hard-cut at the most visually similar pair; `overlap_side` controls which window(s) are searched: `both` = scan both ends (default), `source` = pin `new_images[0]` as reference, `new_images` = pin `source[-1]` as reference
- **feat:** Image Batch Extend With Overlap — `overlap_side=both` for `cut` mode: drops last N frames of `source_images` AND first N frames of `new_images` simultaneously — removes generated ramp/fade frames from both edges at once
- **feat:** Smart LM Loader — two new Wan 2.2 tasks: `Wan 2.2 Scene 10s` (two 5s scene paragraphs, 10s total) and `Wan 2.2 Timeline 10s` (two 5s per-second timeline paragraphs, 10s total); SFW and NSFW few-shot examples; matching system prompts

- **fix:** seed nodes inside ComfyUI subgraphs — "Use Last Queued Seed" button now enables and shows the resolved seed correctly; affects Seed, Seed 32-bit, Sampler Settings+Seed, Sampler Settings NI+Seed, Smart Sampler Settings, Smart Sampler Settings v2, Smart Folder v2, Smart LM Loader, Smart Model Loader
- **fix:** seed write-back to workflow metadata now works for subgraph-inner nodes (colon-path `unique_id` traversal via `get_workflow_node()` in Python; `findWorkflowNode()` in JS)

**Changed files:**

- `py/RvImage_GetFirstImage.py` (new)
- `py/RvImage_BatchStrip.py` (new)
- `py/RvImage_BatchExtendWithOverlap.py`
- `py/RvLogic_Seed.py`, `py/RvLogic_Seed_32bit.py`
- `core/common.py`
- `js/eclipse-seed-utils.js`, `js/eclipse-seed.js`, `js/eclipse-seed-v2.js`
- `js/eclipse-smart-sampler-settings.js`, `js/eclipse-smart-sampler-settings-v2.js`
- `js/eclipse-smart-folder-v2.js`, `js/eclipse-sml-loader.js`, `js/eclipse-smart-model-loader.js`
- `__init__.py`
- `core/sml/tasks.py`, `py/RvLoader_SmartModelLoader_LM.py`
- `config/system_prompts.json`, `config/llm_few_shot_training.json`, `config/llm_few_shot_training_nsfw.json`

---

## 2026-06-03

### Version 3.5.36

- **fix:** Nunchaku glue — `apply_rotary_emb` import compat with ComfyUI v0.22.0+ (`apply_rotary_emb` was moved from `comfy.ldm.qwen_image.model` to `comfy.ldm.omnigen.omnigen2`; falls back to old location for older ComfyUI)

**Changed files:**

- `extern/nunchaku/models/qwenimage.py`

---

## 2026-05-30

### Version 3.5.35

- **feat:** Mode Relay — output can now connect to Bridge Set input; relay mode changes propagate through the full Set → Gets wireless chain via the Toggler stabilize hook
- **fix:** Mode Relay group scan — use direct `.mode=` assignment (no subgraph propagation), matching native ComfyUI "Set Group Nodes to Never/Bypass" behavior

**Changed files:**

- `js/eclipse-mode-nodes.js`

---

### Version 3.5.34

- **feat:** Smart LM Loader — new `LTX 2.3 I2V` task (image-to-video prompt engineer for LTX 2.3)

**Changed files:**

- `core/sml/tasks.py`, `py/RvLoader_SmartModelLoader_LM.py`
- `config/system_prompts.json`, `config/llm_few_shot_training.json`, `config/llm_few_shot_training_nsfw.json`

---
✨ **feat** (new feature) · 🐛 **fix** (bug fix) · ♻️ **refactor** (restructure) · ⚡ **perf** (performance) · 🧹 **chore** (maintenance) · 📚 **docs** (documentation) · 💥 **BREAKING** (breaking change).

---

### Version 3.5.33

- **fix:** Preview Image / Preview Image (DOM) / Preview Mask — remove auto-focus on hover; preview widget now only captures keyboard focus on click

**Changed files:**

- `js/eclipse-dom-preview.js`

---

### Version 3.5.32

- **feat:** Text Image With FX, Image With FX, Image Rescale — per-frame ComfyUI progress bar during batch processing
- **feat:** Image Rescale — `supersample_factor` combo (`2×`/`4×`/`6×`/`8×`) replaces hardcoded 8×; supersample automatically skipped when upscaling (would be counterproductive)
- **feat:** new Image Upscale With Model — combines Load Upscale Model + Upscale Image (using Model) + Upscale Image By into a single node; optional post-model rescale to a target multiplier

- **refactor:** centralize `ComfyTqdm` into `make_comfy_tqdm_class()` in `core/common.py` — removes three identical inner class definitions from LM Loader, Smart Detection, and YOLO backend
- **refactor:** add `make_comfy_progress()` to `core/common.py` for convenient `ProgressBar` creation in batch loops

**Changed files:**

- `py/RvImage_TextImageWithFX.py`
- `py/RvImage_ImageWithFX.py`
- `py/RvImage_Rescale.py`
- `core/common.py`
- `py/RvLoader_SmartModelLoader_LM.py`
- `py/RvLoader_SmartDetection.py`
- `core/sml/backend_yolo.py`
- `pyproject.toml`

---

### Version 3.5.31

- **feat:** Text Image With FX — batch awareness for `background_image`; text layer, shadow, and glow pre-computed once; only compositing loops over frames
- **feat:** Image With FX — batch awareness for `background_image`; `input_image` remains single-frame; shadow and glow pre-computed once
- **feat:** Preview Image — unified under DOM preview widget (same grid/single/arrow-nav as DOM variant)
- **feat:** Preview Image, Preview Image (DOM), Preview Mask — arrow key navigation when multiple frames are shown; hover to auto-focus, ←/→ to cycle; first arrow press in grid mode switches to single view

**Changed files:**

- `py/RvImage_TextImageWithFX.py`
- `py/RvImage_ImageWithFX.py`
- `js/eclipse-dom-preview.js`
- `js/eclipse-dom-preview-nodes.js`

---

## 2026-05-29

### Version 3.5.30

- **fix:** IF A Else B, IF A Else B Fallback, Any Dual Switch, Any Dual Switch Purge, Pipe Any Type, Show Any — crash on paste/copy when `graph.links` entry doesn't exist yet during `configure()`
- **fix:** IF A Else B, Any Dual Switch, Any Dual Switch Purge — crash on paste into subgraph when `origin_slot` is out of range (`sourceNode.outputs` slot undefined)

**Changed files:**

- `js/eclipse-ifelse.js`
- `js/eclipse-any-dualswitch.js`
- `js/eclipse-any-dualswitch-purge.js`
- `js/eclipse-pipe-any-type.js`
- `js/eclipse-show-any.js`

---

## 2026-05-26

### Version 3.5.29

- **feat:** new `Inset & Crop` — merges WAS Image Bounds + Inset Image Bounds + Bounded Image Crop into a single node; crops by removing a fixed pixel count from each edge, pass-through when all insets are 0; batch-aware
- **feat:** new `Image Filter Adjustments` — brightness, contrast, saturation, sharpness, box blur, gaussian blur, edge enhance, detail enhance; ported from WAS Node Suite (MIT)
- **feat:** new `Image Rescale` — rescale by factor or resize to exact dimensions with optional 8× super-sampling; ported from WAS Node Suite (MIT)

**Changed files:** `py/RvImage_InsetCrop.py` (new), `py/RvImage_FilterAdjustments.py` (new), `py/RvImage_Rescale.py` (new), `__init__.py`

---

## 2026-05-25

### Version 3.5.28

- **feat:** `Save Video` — add `loop_match` and `loop_match_blend` trim modes with multi-metric frame matching
— `loop_metric` combo: `ncc` (default), `mse`, `luminance_mse`, `gradient_mse`; NCC is brightness-invariant, ideal for AI video with color/luminance drift between start and end
— `loop_search_pct` controls scan window size as % of total frames
— `loop_trim_start` bool: when on, simultaneously scans both a head window and a tail window and picks the globally best-matching pair via a pairwise [H×T] score matrix (matmul trick); when off, tail-only search anchored to frame 0
— `loop_blend_frames` crossfades the tail into the start for a seamless loop (loop_match_blend only)
— IMAGE output passes the final (trimmed/looped) frame batch downstream
— loop widgets hidden in the UI unless a loop_match mode is active; `loop_blend_frames` only visible for `loop_match_blend`

**Changed files:** `py/RvImage_Save_Video.py`, `js/eclipse-save-video.js`, `pyproject.toml`

---

### Version 3.5.27

- **fix:** `Save Video` — add `movflags=use_metadata_tags` to MP4 container open so workflow/prompt metadata is embedded correctly; drag-and-drop back into ComfyUI now restores the workflow
- **fix:** `Preview Video` — same fix: workflow/prompt now embedded in temp file so right-click “Save video as” also carries the workflow
- **feat:** `Save Video` — add `preset` combo (`ultrafast` → `veryslow`) for encoder speed/quality trade-off

**Changed files:** `py/RvImage_Save_Video.py`, `py/RvImage_Preview_Video.py`, `pyproject.toml`

---

## 2026-05-24

### Version 3.5.26

- **fix:** `Image Batch Extend With Overlap` — `overlap_side` no longer reverses blend direction; all blending modes always transition source→new; `overlap_side` only affects `cut` mode (determines which side loses frames)

**Changed files:** `py/RvImage_BatchExtendWithOverlap.py`, `pyproject.toml`

---

### Version 3.5.25

- **feat:** new `Image Batch Extend With Overlap` node — blends two image batches at a shared overlap region for video generation extension
- **feat:** 11 `overlap_mode` options: `linear_blend`, `ease_in_out`, `filmic_crossfade`, `perceptual_crossfade` (kornia, falls back to linear_blend), `average`, `dissolve`, `pyramid_blend` (Laplacian multi-scale), `clock_wipe` (clockwise sweep from 12 o'clock), `clock_wipe_ccw` (counter-clockwise), `cut` (drop overlap frames from one side), `concat` (direct join, no frame loss)
- **feat:** `source_images` is optional — returns `new_images` as-is when source not connected, and vice versa; raises error only when both inputs are disconnected
- **feat:** auto-resize `new_images` to match `source_images` resolution using scale-to-fill + center-crop when sizes differ
- **feat:** defaults: `overlap=5`, `overlap_mode=pyramid_blend`

**Changed files:**

- `py/RvImage_BatchExtendWithOverlap.py` (new)
- `pyproject.toml`

---

## 2026-05-22

### Version 3.5.24

- **feat:** `%date:FORMAT%` placeholder support in Save Video `filename_prefix` — e.g. `video/%date:dd_hh-mm-ss%/60FPS_%date:dd_hh-mm-ss%` expands to `video/22_14-30-45/60FPS_22_14-30-45`; format codes: `yyyy`, `yy`, `MM`, `dd`, `hh`, `mm`, `ss`
- **feat:** `resolve_date_tokens()` helper added to `core/common.py` for reuse across nodes
- **feat:** `Lora Stack Apply` — CLIP input is now optional; node skips clip encoding when CLIP is not connected (model-only LoRA workflows)

**Changed files:** `core/common.py`, `py/RvImage_Save_Video.py`, `py/RvTools_LoraStack_Apply.py`, `pyproject.toml`

---

## 2026-05-21

### Version 3.5.23

- **feat:** new `RIFE Multiplier` node — calculates the nearest integer RIFE interpolation multiplier from `source_fps` + `target_fps`; outputs `multiplier` (INT) for direct connection to RIFE nodes and `actual_fps` (FLOAT) showing the resulting frame rate

**Changed files:** `py/RvConversion_RIFEMultiplier.py` (new), `__init__.py`, `pyproject.toml`

---

### Version 3.5.22

- **feat:** new `Boolean Passer` node — passes boolean input through; outputs `False` when input is muted or bypassed

**Changed files:** `py/RvRouter_Boolean_Passer.py` (new), `__init__.py`, `pyproject.toml`

---

## 2026-05-17

### Version 3.5.21

- **fix:** `GetNode` + `GetAllActive` + `GetFirst` — sibling-subgraph Set/Get resolution: extend `findSetterByName()` with a 4th search tier (root-reachable siblings) so a Get in SG-B can resolve a Set in sibling SG-A. Previously `getVisibleSetNames()` advertised sibling setters in the combo (labeled `(child)`) but `findSetterByName()` couldn't resolve them, causing a spurious "Set node not found" alert on export.

**Changed files:**

- `js/eclipse-set-get-utils.js`
- `pyproject.toml`

---

### Version 3.5.20

- **fix:** `Mode Bridge` + `Mode Bridge Set/Get` — align paste-rename orchestration with Set/Get system: centralized debounced two-phase pass (bridges/sets first, gets second), delayed shared map clear (500ms), root-graph map isolation, and subgraph-op guard to skip rename during convert/unpack operations.

**Changed files:**

- `js/eclipse-mode-nodes.js`
- `pyproject.toml`

---

### Version 3.5.19

- **fix:** `SetNode` + `GetNode` + `GetAllActive` + `GetFirst` — subgraph-duplication stability pass: scope-aware lookup (local → ancestors → descendants), shared paste-rename map for all getter variants, delayed centralized map clear (500ms), and root-graph ID isolation to prevent cross-workflow stale mappings.
- **fix:** `SetNode` + `GetNode` + `GetAllActive` + `GetFirst` — paste-rename orchestration refactor: replaced per-node lifecycle timing with a debounced centralized two-phase pass (setters populate map, getters consume map) scheduled from node `onAdded`, eliminating `_nodes`-order and `graph-changed` timing races.

**Changed files:**

- `js/eclipse-set-get-utils.js`
- `js/eclipse-set-get.js`
- `js/eclipse-getallactive.js`
- `js/eclipse-getfirst.js`

---

### Version 3.5.18

- **feat:** new `Fast Mode Toggle [Eclipse]` — unified mute/bypass toggle node with pill-style 2-state widget (active ↔ mute/bypass). Off-mode (Mute vs Bypass) is selectable per-node from the right-click context menu (default: Bypass). Inherits the `Fast Mode Switcher`'s appearance, nav arrows, restriction modes, and subgraph-promoted widget bindings (stable `target_<idx>` widget names).
- **feat:** `GetNode [Eclipse]` — clicking the `Constant` widget now opens a filterable dropdown with a search input at the top (matches `Bridge Get`'s searchable combo behavior). Implemented as a custom HTML overlay; LiteGraph's built-in `ContextMenu` has no filter, and Vue's searchable combo is only available to Python-registered nodes. Keyboard: type to filter, Up/Down to navigate, Enter to select, Esc to close.
- **fix:** `Fast Mode Switcher` + `Fast Mode Toggle` — widget click/cycle/callback was bound to the originally-connected node via closure capture, so re-routing a connection to a different upstream node into the same slot would toggle the wrong (old) node. Both widgets now resolve their live target via `widget._eclipse_targetId` (graph lookup at call time).
- **chore:** deprecate `Fast Muter` and `Fast Bypasser` — moved to `py/legacy/`. Existing workflows continue to load and work unchanged; the nodes now show under the Legacy category with the ⚠ prefix and `is_deprecated=True`. Will be removed in v4.0.0. Use `Fast Mode Toggle` as the replacement.

**Deprecated nodes:**

- `Fast Muter [Eclipse]`
- `Fast Bypasser [Eclipse]`

**Changed files:**

- `py/RvTools_FastModeToggle.py` (new)
- `py/legacy/legacy_FastMuter.py` (moved from `py/RvTools_FastMuter.py`)
- `py/legacy/legacy_FastBypasser.py` (moved from `py/RvTools_FastBypasser.py`)
- `js_src/eclipse-mode-nodes.js`, `js/eclipse-mode-nodes.js`
- `js_src/eclipse-set-get.js`, `js/eclipse-set-get.js`
- `pyproject.toml`

---

## 2026-05-14

### Version 3.5.17

- **chore:** restore `Fast Muter` and `Fast Bypasser` as active nodes under the Tools category (no longer deprecated) — kept alongside `Fast Mode Switcher`.

- **feat:** `Smart LM Loader` — new "⚠ Trust Remote Code" mode-bar chip (default OFF) gates HuggingFace `trust_remote_code=True`. Combined with a new per-model `trust_remote_code` registry flag, the effective trust = `registry_flag OR chip_override`. Florence-2 (8 entries) and Ministral-3 / Mistral-Small-3.1 (5 entries) are pre-flagged in the registry as legitimate consumers; all other models default to False.

- **fix:** SML — removed 11 hardcoded `trust_remote_code=True` sites across `vlm_loader.py`, `florence2_wrapper.py`, `backend_vllm_native.py`, and `backend_vllm_docker.py`. All paths are now caller-controlled via `load_model_with_backend(trust_remote_code=...)` from `loader_base.py`.
- **fix:** `Smart Detection` — now consults the per-model registry `trust_remote_code` flag automatically (no chip needed). Florence-2 loads with `True` (pre-flagged), Qwen VL with `False`. Without this, the v3.5.17 default-deny refactor would have broken Florence-2 detection loading.
- **fix:** SML — server endpoint `/smartlml/config/update` now validates `llm_models_path`: rejects length > 4096, null bytes, and any `..` path segment (after normalizing backslashes). Absolute paths are still allowed (USB drive use case preserved).
- **fix:** SML — Docker image references are now validated against a conservative whitelist regex (`[a-z0-9._/-]+(:tag)?(@sha256:...)?`) before being passed to subprocess. Rejects shell metacharacters, leading `-`, and length > 512.
- **fix:** SML — Docker containers now bind to `127.0.0.1` by default (was `0.0.0.0`), keeping the unauthenticated OpenAI-compatible APIs (vLLM, SGLang, Ollama, llama.cpp) local-only. Configurable via the new global `docker_bind_host` in `docker_config.json`.

- **docs:** move `LLM_SECURITY_WARNING.md` (and Civitai variant) from `docs/` into `Readme/` as `LLM_Security_Warning.md`; linked from main `README.md` and `Readme/README.md`.
- **docs:** `LLM_Security_Warning` — add a *Baseline hygiene* section that honestly frames `venv` as hygiene / blast-radius (not a security sandbox), explains why to never use system Python, and calls out the `sudo pip install` root-execution pitfall.

**Changed files:**

- `py/RvTools_FastMuter.py` (moved from `py/legacy/`)
- `py/RvTools_FastBypasser.py` (moved from `py/legacy/`)
- `py/RvLoader_SmartModelLoader_LM.py`
- `py/RvLoader_SmartDetection.py`
- `core/sml/model_registry.py`
- `core/sml/vlm_loader.py`, `core/sml/florence2_wrapper.py`
- `core/sml/backend_vllm_native.py`, `core/sml/backend_vllm_docker.py`
- `core/sml/backend_sglang_docker.py`, `core/sml/backend_llamacpp_docker.py`, `core/sml/backend_ollama_docker.py`
- `core/sml/loader_base.py`, `core/sml/docker_utils.py`, `core/sml/server_endpoints.py`
- `js/eclipse-sml-loader.js`
- `registry/transformers_models.json`, `registry/vllm_models.json`
- `docker_config.json`
- `Readme/LLM_Security_Warning.md` (moved from `docs/LLM_SECURITY_WARNING.md`)
- `Readme/LLM_Security_Warning_Civitai.md` (moved from `docs/`, gitignored)
- `README.md`, `Readme/README.md`
- `__init__.py`
- `pyproject.toml`

---

## 2026-05-13

### Version 3.5.16

- **feat:** new `Save Video [Eclipse]` — Eclipse replacement for ComfyUI's built-in `SaveVideo`. Accepts `IMAGE` + optional `AUDIO` + `fps` directly (no `VIDEO` type required) and adds a `trim_mode` widget to align video/audio length before writing: `none`, `video_to_audio` (cut frames to audio length), `audio_to_video` (cut audio to frame length), `shortest` (both). Output: mp4/h264 with `crf` control, written to ComfyUI's output folder with embedded prompt/workflow metadata. `format` and `codec` widgets are hidden (single option each, kept in schema for future expansion).
- **feat:** `Save Video` / `Preview Video` — shared DOM video preview helper: widget is fully hidden when no video is loaded (node collapses to inputs), and once a video is loaded it letterboxes inside the current node size via `object-fit: contain` instead of resizing the node. Drag the node corner to resize the preview.

**Changed files:**

- `py/RvImage_Save_Video.py` (new)
- `py/RvImage_Preview_Video.py`
- `js/eclipse-video-preview-common.js` (new)
- `js/eclipse-save-video.js` (new)
- `js/eclipse-preview-video.js` (new)
- `__init__.py`
- `pyproject.toml`

---

## 2026-05-12

### Version 3.5.15

- **feat:** new `Preview Video [Eclipse]` — encodes IMAGE batch (+ optional AUDIO, fps) to a temporary mp4 preview and passes the images through as IMAGE output. Designed for use inside easy forLoop bodies: wire its IMAGE output into `forLoopEnd.initial_value` to force per-iteration execution. Filename includes a per-execution timestamp so the browser's `<video>` element always fetches a fresh URL (avoids the `VHS_VideoCombine` in-loop cached-preview issue). Writes to ComfyUI's temp folder, not output. Uses PyAV (h264, yuv420p, crf 23, veryfast preset) with optional AAC audio mux trimmed to video duration (`num_frames / fps × sample_rate`). `not_idempotent=True` ensures re-execution every iteration.
- **feat:** new `Load Audio [Eclipse]` — drop-in replacement for ComfyUI's built-in `LoadAudio` with `start_time` and `duration` (seconds) widgets, similar to VHS `LoadAudioUpload`. Uses PyAV directly with container seek + sample-precise trimming for efficient handling of long audio/video files. `duration = 0` loads to end-of-file; `start_time = 0` loads from the beginning. Returns `AUDIO` + loaded `duration` (`FLOAT`, seconds) — matches VHS `LoadAudioUpload` output shape. JS extension adds an HTML5 `<audio>` preview + upload button + start/duration playback window (mirrors built-in `LoadAudio` UI which is hardcoded to a class-name whitelist).
- **feat:** new `Loop Calculator (Audio) [Eclipse]` — calculates a `loop_count` from an audio duration. Inputs: `duration` (float seconds), `fps`, `context_length`, optional `AUDIO` (overrides the duration widget when wired). Outputs: `loop_count`, `total_frames`, `duration`. Math: `loop_count = ceil(ceil(duration × fps) / context_length)`. Provides an automatic alternative to entering `loop_count` by hand on any loop-driven node.
- **feat:** `Smart Folder v2` — `loop_count` (user-entered value) is now included in the pipe and exposed as a new bottom `loop_count` output on `Pipe Out Smart Folder`. The pipe stores the raw widget value (calc only affects `frame_load_cap`), so it can be wired directly into loop nodes without recomputation.

**Changed files:**

- `py/RvImage_Preview_Video.py` (new)
- `py/RvLoader_LoadAudio.py` (new), `js/eclipse-load-audio.js` (new)
- `py/RvTools_LoopCalcAudio.py` (new)
- `py/RvFolder_SmartFolder.py`, `py/RvPipe_Out_SmartFolder.py`
- `__init__.py`
- `pyproject.toml`

---

## 2026-05-10

### Version 3.5.14

- **fix:** Smart LM "Song Lyrics" task — instead of fighting the model with ever-stronger prompt rules, the cleanup now happens automatically in the output pipeline. Added `clean_song_lyrics()` in `core/sml/common.py`, wired into `strip_llm_prefixes()` so every backend (Transformers, GGUF, vLLM, SGLang, Ollama, llama.cpp) benefits with no per-call-site changes. Auto-detects lyric output by presence of ≥2 distinct section labels (Verse / Chorus / Pre-Chorus / Bridge / Intro / Outro / Solo / Final Chorus / Hook / Refrain) in any common form (`[X]`, `(X)`, `**X**`, `**(X)**`) — no-op for non-lyric output. When detected, strips Markdown bold (`**…**`, `__…__`) and italic (`*…*`, `_…_`) wrappers keeping inner content, drops leading `#` heading markers, converts round-bracket labels `(Verse 1)` / `(Chorus)` to canonical `[Verse 1]` / `[Chorus]`, strips line-prefix labels `Title:` / `Style:` / `Genre:` / `Song:` / `Tempo:`, and collapses 3+ blank lines.

**Changed files:**

- `core/sml/common.py`
- `pyproject.toml`

---

### Version 3.5.13

- **fix:** Smart LM "Song Lyrics" task — small/medium models still emitted Markdown bold (`**Title:**`, `**Style:**`) and round-bracket section labels (`(Verse 1)`, `**(Pre-Chorus)**`) despite the v3.5.12 "no Markdown" rule. The system prompt now enforces plain-text output via a token-level **FORBIDDEN OUTPUT** block enumerating exact sequences the model must never produce: `**`, `__`, single `*`/`_` for emphasis, `#` at line start, round brackets around section labels, and `Title:` / `Style:` / `Genre:` / `Song:` line prefixes. Round brackets remain allowed inside the `Structure:` line for bar counts and inside performance hints like `[Bridge — half-time]`. Both SFW and NSFW few-shot examples rewritten to demonstrate the strict plain-text format (raw title on line 1, raw tempo line on line 2, `[Section]` labels, ASCII `->` arrows in `Structure:`).

**Changed files:**

- `.defaults/config/system_prompts.json.example`, `.defaults/config/llm_few_shot_training.json.example`, `.defaults/config/llm_few_shot_training_nsfw.json.example`, `.defaults/.manifest.json`
- `pyproject.toml`

---

### Version 3.5.12

- ✨ **feat:** new Smart LM task **"Song Lyrics"** — converts a freeform concept into fully structured rock/metal/pop song lyrics in **plain text** (no Markdown), with section labels in **square brackets** on their own line (`[Verse 1]`, `[Pre-Chorus]`, `[Chorus]`, `[Bridge]`, `[Guitar Solo]`, etc.), enforced rhyme scheme and syllable consistency, and a trailing `Structure:` line listing each section with bar counts. Task is registered in `core/sml/tasks.py` under the `text` category — visible in the Smart LM Loader task dropdown alongside Short Story, Summarize, etc. System prompt added to `system_prompts.json` (shared between SFW and NSFW training files) and a few-shot example added to BOTH `llm_few_shot_training.json` (SFW: Batman vigilante) and `llm_few_shot_training_nsfw.json` (NSFW: explicit one-night-stand demo with direct anatomical terms and profanity) so the in-context guidance is present regardless of which training file is loaded. The system prompt explicitly forbids Markdown (no `#` headings, no `**bold**`, no `*italic*`) and forbids round brackets / parentheses for section labels — only `[Section]` is allowed. A dedicated **FORBIDDEN OUTPUT** block lists exact tokens the model must never produce: `**`, `__`, single `*`/`_` for emphasis, `#` at line start, `(Verse 1)` / `(Chorus)` / `**(Pre-Chorus)**` round-bracket labels, `Title:` / `Style:` / `Genre:` line prefixes, code fences, blockquote / bullet markers. (Round brackets remain allowed inside the `Structure:` line for bar counts and inside performance hints like `[Bridge — half-time]`.) Both few-shot examples now demonstrate the plain-text format. The system prompt also contains a **CONTENT POLICY** clause instructing the model to write directly and uncensored — using direct anatomical terms, profanity, and visceral imagery — when the user's concept involves sexual / violent / dark themes, with no softening, sanitizing, euphemizing, or refusals. The NSFW few-shot example demonstrates this concretely so models trained on the NSFW file do not mince words on explicit user prompts.

**Changed files:**

- `core/sml/tasks.py`
- `.defaults/config/system_prompts.json.example`, `.defaults/config/llm_few_shot_training.json.example`, `.defaults/config/llm_few_shot_training_nsfw.json.example`, `.defaults/.manifest.json`
- `pyproject.toml`

---

### Version 3.5.11

- 🐛 **fix:** Smart LM **few-shot examples** were loaded ONCE at module import — page refresh and `/eclipse/reload_all` and `/smartlml/reload_all` did not pick up edits to `llm_few_shot_training.json` / `llm_few_shot_training_nsfw.json`. Now `get_llm_few_shot_examples()` auto-reloads when the source JSON's mtime changes (or when the configured file name is switched between SFW / NSFW), and both reload endpoints explicitly call the new `reload_few_shot_configs()` helper. System prompts (`system_prompts.json`) already auto-reload via mtime check, so they are unaffected.
- 🐛 **fix:** Smart LM **Wan 2.2** prompts — reduce environment / lighting padding AND ensure **action starts at beat 0**. Added FOCUS RULES block to all six Wan 2.2 system prompts (Scene 5s, Timeline 5s, Timeline 5s 2s / 3s, Scene 20s, Timeline 20s) instructing the model to (1) establish setting once and focus subsequent beats on subject and action, and (2) make the very first beat already show the requested motion in progress — not setup or scene staging (previously the action often started 2–3 seconds in, wasting most of a 5-second clip on preparation). Reinforced via the few-shot instruction templates so the user-side message also carries the rule. Rewrote the timeline 5s, 5s 2s, and 5s 3s few-shot examples to demonstrate action-at-beat-0 (cat already mid-leap; candle wick already catching). Eliminates filler like *"light intensifies"*, *"shadows shift"*, *"warm intimate atmosphere"* repeated in every beat.

**Changed files:**

- `core/sml/config_templates.py`, `core/sml/server_endpoints.py`, `core/server_endpoints.py`
- `config/system_prompts.json`, `config/llm_few_shot_training.json`, `config/llm_few_shot_training_nsfw.json`
- `.defaults/config/system_prompts.json.example`, `.defaults/config/llm_few_shot_training.json.example`, `.defaults/config/llm_few_shot_training_nsfw.json.example`, `.defaults/.manifest.json`
- `pyproject.toml`

---

## 2026-05-09

### Version 3.5.10

- ✨ **feat:** Smart LM — 2 new **Wan 2.2 Timeline 5s** pacing variants. *Wan 2.2 Timeline 5s 2s* uses 3 beats `(At 0s)(At 2s)(At 4s)`; *Wan 2.2 Timeline 5s 3s* uses 2 beats `(At 0s)(At 3s)`. Slower pacing lets each action unfold before the next begins instead of changing every second.

**Changed files:**

- `core/sml/tasks.py`, `py/RvLoader_SmartModelLoader_LM.py`
- `config/system_prompts.json`, `config/llm_few_shot_training.json`, `config/llm_few_shot_training_nsfw.json`
- `.defaults/config/system_prompts.json.example`, `.defaults/config/llm_few_shot_training.json.example`, `.defaults/config/llm_few_shot_training_nsfw.json.example`, `.defaults/.manifest.json`
- `README.md`, `Readme/Smart_LM_Loader_Guide.md`
- `pyproject.toml`

---

### Version 3.5.9

- 🐛 **fix:** Fast Mode Switcher — widget identity is now keyed off the input **slot index** (`target_0`, `target_1`, …) instead of the live target node id (`target_<id>`). Slot indices survive copy/paste and subgraph duplication; target node ids do not (paste assigns new ids, which renamed the widgets and broke parent-subgraph promoted bindings that referenced the old `target_<id>` names). Existing widgets are now reused across target swaps / renames / id changes — only `widget.label` and the runtime `_eclipse_targetId` are updated, so promoted inputs in parent subgraphs survive paste cleanly.

**Changed files:**

- `js_src/eclipse-mode-nodes.js`, `js/eclipse-mode-nodes.js`
- `pyproject.toml`

---

### Version 3.5.8

- ✨ **feat:** Fast Mode Switcher — per-target tri-state widgets are now real LiteGraph `BaseWidget`s (combo type) instead of plain custom-drawn objects. They render in the subgraph / Vue side panel as `active / muted / bypass` dropdowns **and** are eligible for right-click *Convert widget to input* / subgraph promotion (toggles can be exposed as inputs from outside a subgraph). Widget identity is keyed off the connected target's node-id (`target_<id>`) instead of its title, so renaming a connected node only updates the displayed label (`widget.label`) and subgraph-promoted bindings survive renames. `widget.value` is now the state label string (`'active' / 'muted' / 'bypass'`) instead of a numeric index; legacy workflows saved with numeric indices are auto-coerced. Canvas paint and clicks use BaseWidget's `drawWidget(ctx, opts)` and `onClick({e, node, canvas})` API (legacy plain-object `draw` / `mouse` hooks don't apply to concrete ComboWidget instances), so the tri-state pill, colored state indicator, nav arrow, and cycle-on-click are preserved alongside the new side-panel dropdown. Restriction rules (`max one` / `always one`) are enforced from the callback path, so they apply equally to canvas clicks and side-panel selections.

**Changed files:**

- `js_src/eclipse-mode-nodes.js`, `js/eclipse-mode-nodes.js`
- `pyproject.toml`

---

### Version 3.5.7

- ✨ **feat:** new **Get Last Image** node — returns only the last frame from an image batch `[B,H,W,C]` or list. Useful for feeding the most recent frame of a video / chain into Smart LM image-description tasks without forcing video summarisation.
- 🐛 **fix:** Smart LM image-batch handling — Docker backends (Ollama / vLLM / SGLang / llama.cpp) ignored `frame_count` and forwarded every frame of a multi-frame batch. Now respects `frame_count` like the Transformers and GGUF backends.
- ♻️ **refactor:** Smart LM frame trimming — when the input batch exceeds `frame_count`, all backends now keep the **last** N frames instead of the **first** N (preserves recent context for chained / video workflows; single-image tasks unaffected).

**Changed files:**

- `py/RvLoader_SmartModelLoader_LM.py`
- `py/RvImage_GetLastImage.py` *(new)*
- `core/sml/backend_transformers.py`, `core/sml/backend_gguf.py`
- `__init__.py`, `pyproject.toml`

---

### Version 3.5.6

- ✨ **feat:** Smart LM — 4 new **Wan 2.2** video-prompt tasks (Scene 5s, Timeline 5s, Scene 20s, Timeline 20s) in the Custom category. Flexible input: accept image, `user_prompt` text, or both. Scene formats produce one cinematic paragraph (5s) or four continuous paragraphs (20s); Timeline formats use `(At N seconds: ...)` per-second markers. 20s variants enforce character / scene / style continuity across all four prompts. Includes system prompts + few-shot examples (SFW + NSFW with explicit-content guidance).

**Changed files:**

- `core/sml/tasks.py`, `py/RvLoader_SmartModelLoader_LM.py`
- `config/system_prompts.json`, `config/llm_few_shot_training.json`, `config/llm_few_shot_training_nsfw.json`
- `.defaults/config/system_prompts.json.example`, `.defaults/config/llm_few_shot_training.json.example`, `.defaults/config/llm_few_shot_training_nsfw.json.example`, `.defaults/.manifest.json`
- `README.md`, `Readme/Smart_LM_Loader_Guide.md`
- `pyproject.toml`

---

## 2026-05-08

### Version 3.5.5

- ✨ **feat:** Smart LM — new **Prompt Variations** text task. Identifies the core subject and action in the input, then generates 5 variations of the SAME action performed with a different manner (speed, intensity, emotion, body language) — keeping subject, setting, and explicit details unchanged. Output separated by `---` on its own line. Includes system prompt + few-shot examples (SFW + NSFW variants).

- 🐛 **fix:** Smart LM Loader — removed runtime `smartResize()` call from the visibility refresh. The `user_prompt` textarea now fills available space, so auto-shrinking the node on every mode/task switch was overriding the user's manually-set node height (most visibly: F5 reload collapsed the node back to its minimum). Detection node keeps `smartResize` since it has no fill-widget.

**Changed files:**

- `core/sml/tasks.py`, `py/RvLoader_SmartModelLoader_LM.py`
- `config/system_prompts.json`, `config/llm_few_shot_training.json`, `config/llm_few_shot_training_nsfw.json`
- `.defaults/config/system_prompts.json.example`, `.defaults/config/llm_few_shot_training.json.example`, `.defaults/config/llm_few_shot_training_nsfw.json.example`, `.defaults/.manifest.json`
- `js/eclipse-sml-loader.js`
- `README.md`, `Readme/Smart_LM_Loader_Guide.md`

---

### Version 3.5.4

- 🐛 **fix:** Fast Mode Switcher — `toggleRestriction` (`max one` / `always one`) was effectively a no-op. Individual switch clicks now enforce the restriction (activating one mutes other active widgets in `max one` / `always one`; cycling the last active widget away is refused in `always one`). Menu actions (Enable all / Mute all / Bypass all) previously updated only the visual state for restricted indices without changing the actual node mode — now they apply correct modes (others muted on Enable all + `max one`; first stays active on Mute/Bypass all + `always one`).

**Changed files:**

- `js/eclipse-mode-nodes.js`
- `pyproject.toml`

---

## 2026-05-07

### Version 3.5.3

- ♻️ **refactor:** Smart Model Loader / VAE Loader — removed the `CustomVAE` subclass entirely. After the 3.5.2 fix it was a no-op pass-through to `comfy.sd.VAE`, so it served no purpose. `load_custom_vae()` now constructs and returns a plain `comfy.sd.VAE` directly, matching the stock `VAELoader` node 1:1. Deleted the obsolete `core/wan_vae.py` (adapted from ComfyUI-VAE-Utils, no longer imported anywhere — upstream's `comfy.ldm.wan.vae` handles Wan 2.1 natively).

**Changed files:**

- `core/model_loader_common.py`
- `core/wan_vae.py` (deleted)
- `py/RvLoader_VaeLoader.py`
- `pyproject.toml`

---

### Version 3.5.2

- 🐛 **fix:** Smart Model Loader / VAE Loader — external VAE now decodes identically to the stock `VAELoader` node for **all architectures including Wan 2.1**. Two upstream-divergence bugs were fixed:
  1. `load_custom_vae()` previously called `comfy.utils.load_torch_file(path)` and `CustomVAE(sd=sd)`, dropping the safetensors metadata. Upstream `comfy.sd.VAE.__init__` reads `metadata["config"]` to override `vae_config` for some checkpoints (`comfy/sd.py` L625-626), so omitting it could pick a different architecture/scale and produce visibly different decodes.
  2. `CustomVAE` carried a custom Wan 2.1 branch that instantiated `core/wan_vae.py:WanVAE` (adapted from ComfyUI-VAE-Utils) with **hardcoded `dim=96`** and a different ddconfig key set (`in_channels`/`out_channels` vs upstream `image_channels`/`conv_out_channels`). Upstream now natively handles Wan 2.1 via `comfy.ldm.wan.vae.WanVAE` with `dim` read dynamically from `sd["decoder.head.0.gamma"].shape[0]`. The custom branch produced decodes that visibly diverged from the stock `VAELoader` node fed the same Wan 2.1 VAE.

  Now: `load_torch_file(path, return_metadata=True)` + `CustomVAE(sd=sd, metadata=metadata)`, and `CustomVAE` is a thin pass-through to `comfy.sd.VAE` (no architecture-specific branches). The custom `decode_tiled_3d` override (which used a non-upstream `real_output_channels` attribute) was also removed. Default `disable_offload` changed from forced `True` to `None` (preserves upstream per-VAE default — only audio VAEs internally set `True`); existing `disable_offload=` callers still work. `core/wan_vae.py` is no longer imported (file retained for reference).

**Changed files:**

- `core/model_loader_common.py`
- `pyproject.toml`

---

## 2026-05-05

### Version 3.5.1

- 🐛 **fix:** Smart LM Loader — Multi-Task chip toggle now resets chained tasks. When the Multi-Task mode chip is switched OFF while `task_2`/`task_3`/`task_4` are set to non-`None` values, those task widgets are now auto-reset to `None`. Previously the values lingered hidden; toggling Multi-Task back ON (or simply re-running the node) would silently re-execute the stale chain. Tracks previous state via `node._SML_prevMultiTask` so the reset only fires on the OFF transition (not on every callback).

- 🐛 **fix:** llama.cpp Docker backend — LLM (Text-Only) mode now honors system prompts and few-shot training. Previously the text-only path ignored `llm_mode` entirely and dumped the raw prompt into a user message with no system role, silently bypassing wired `system_prompt` overrides, JSON-defined task system prompts, and LLM few-shot examples. Now mirrors the Ollama / vLLM / SGLang pattern: builds `[system, examples..., user]` messages via `get_system_prompt(display_name)` and `get_llm_few_shot_examples()`. Pre-existing gap discovered while auditing the empty-user_prompt fix.

- 🐛 **fix:** Smart LM Loader — LLM (Text-Only) family now accepts an empty `user_prompt` when a system prompt is available (wired `system_prompt` override OR JSON-defined task system prompt). Previously raised "LLM requires a prompt" even when the wired system_prompt carried complete instructions for Direct Chat. The model now responds to the system instruction alone. Strict empty-input check is preserved when no system prompt is available.

- 🐛 **fix:** Smart LM Loader — flexible tasks (Direct Chat / Custom / Question Answering) with image + `user_prompt` now correctly use the task system. The task's system prompt (either the JSON entry, or a wired `system_prompt` override via the ContextVar) drives the system slot, `user_prompt` becomes the user message, and any vision few-shot training defined for the task is injected. Previously this branch always stuffed `user_prompt` into the system slot regardless of whether a system prompt was available, shadowing both wired overrides and JSON-defined task prompts. Legacy fallback (no override, no JSON entry) is preserved.

- 🐛 **fix:** Smart LM Loader — wired `user_prompt` is no longer dropped when image+text is sent to a non-flexible task whose JSON system prompt contains paragraph breaks. Affected all 7 vision backends.

- ♻️ **refactor:** Smart LM Loader — pass `system_prompt` and `user_message` as separate kwargs through the dispatch chain instead of marshalling them into a combined `"system\n\nuser"` string. `_build_vlm_prompt` now returns a `(system_prompt, user_message, is_text_only)` triple; `_dispatch_generate` forwards `system_prompt=` to all vision-capable backends (Ollama, vLLM Docker, vLLM Native, SGLang Docker, llama.cpp Docker, Transformers, GGUF). Each backend's vision parser block is bypassed when `system_prompt` is provided explicitly, eliminating an entire class of bugs where JSON system prompts containing blank-line paragraphs (e.g. "Ultra Detailed Description") had their first `\n\n` mis-parsed as the system/user separator, silently dropping the wired user prompt. The legacy split-on-`\n\n` parser remains as a fallback for any external callers.

**Changed files:**

- js/eclipse-sml-loader.js
- py/RvLoader_SmartModelLoader_LM.py
- core/sml/backend_ollama_docker.py
- core/sml/backend_vllm_docker.py
- core/sml/backend_vllm_native.py
- core/sml/backend_sglang_docker.py
- core/sml/backend_llamacpp_docker.py
- core/sml/backend_transformers.py
- core/sml/backend_gguf.py
- pyproject.toml

---

### Version 3.5.0

- ✨ **feat:** Smart LM Loader — new `system_prompt` connectable string input. When wired, the task widget is forced to "Direct Chat" and locked, and the connected string is used as the system prompt for the first task — overriding the task's JSON-defined system prompt and disabling its few-shot training. Backends are unchanged: override is plumbed via a `ContextVar` in `core/sml/tasks.py:get_system_prompt()` so all 7 backend dispatch paths (Transformers, vLLM Docker/Native, SGLang Docker, Ollama Docker, llama.cpp Docker, GGUF) transparently pick up the override at the single read site. Override is scoped strictly to the first task — multi-task chain (tasks 2/3/4) runs after the override is reset, so chained tasks retain their own JSON system prompts and few-shot. WD14 + Florence ignore the override (Florence has no system role; WD14 has no LLM stage). Forward-compat: unknown families are assumed to support system role (only `Florence` is in the no-system allow-list). `system_prompt` is included in `fingerprint_inputs` so upstream changes trigger re-execution.

- ♻️ **refactor:** Smart LM Loader — removed the `text` connectable input (slot superseded by direct upstream wiring into `user_prompt`). User prompts now flow through a single channel: type into the `user_prompt` widget OR wire a string upstream (the widget supports native string connections via `multiline=True`). Simplifies `_build_vlm_prompt` and `_generate_for_family` (one fewer parameter, no `text if text is not None else user_prompt` branching). JS visibility logic simplified — `user_prompt` no longer hides when the dropped `text` slot was connected.

- 💥 **BREAKING:** Smart LM Loader — the `text` input slot was removed. Workflows that wired a string into `text` must rewire that connection into `user_prompt` (which now accepts the same upstream string). Reload existing nodes after upgrading.

**Changed files:**

- core/sml/tasks.py
- py/RvLoader_SmartModelLoader_LM.py
- js/eclipse-sml-loader.js
- pyproject.toml

---

## 2026-05-04

### Version 3.4.0

- ✨ **feat:** Smart LM Loader — new `Use Advanced` chip gates whether advanced sampling values (temperature, top_p, top_k, repetition_penalty, num_beams, do_sample) are actually applied. Default ON (preserves existing behavior). When OFF, conservative defaults (0.7 / 0.9 / 50 / 1.0 / 1 / True) are used regardless of widget values — makes the existing `Advanced` visibility chip safe as a set-and-forget collapse: hiding the widgets no longer silently keeps tuned values in the request. Persist-on-execute also skips sampling params when the chip is OFF so the user's saved tuning isn't overwritten by the gated defaults. Not gated: seed, max_tokens, context_size, device, frame_count, use_torch_compile, attention_mode, WD14 params.
- ✨ **feat:** Smart LM Loader — 6 new advanced sampling widgets: `min_p`, `mirostat` (off / v1 / v2), `mirostat_eta`, `mirostat_tau`, `repeat_last_n`, `stop_sequences` (newline-separated). All gated by `Use Advanced` (reset to safe defaults when OFF). Per-backend visibility: `min_p` + `stop_sequences` show for all generative backends (hidden for WD14 and Florence); mirostat triplet + `repeat_last_n` only show for llama.cpp-family backends (gguf, llamacpp, ollama). Threaded through the full dispatch chain (`execute` → `_generate_for_family` / `_run_multi_task_chain` → `_dispatch_generate`) and into each backend's request:
- ✨ **feat:** Ollama — adds `min_p`, `mirostat` (+ `mirostat_eta`/`mirostat_tau` when on), `repeat_last_n`, `stop` to text + vision + fallback `/api/generate` options dicts. Sentinel-gated.
- ✨ **feat:** vLLM Docker / vLLM Native / SGLang — `min_p` via `extra_body` (Docker/SGLang) or `SamplingParams` (Native); `stop_sequences` via OpenAI `stop=` / `SamplingParams.stop`. Mirostat / repeat_last_n not supported by these backends — widgets hidden client-side.
- ✨ **feat:** llama.cpp Docker — `min_p`, `mirostat` (+ `eta`/`tau`), `repeat_last_n`, `stop` added to chat-completions payload.
- ✨ **feat:** GGUF (llama-cpp-python) — `min_p`, `mirostat_mode` (+ `eta`/`tau`), `repeat_last_n`, `stop` passed to `create_chat_completion()` via runtime-built extras dict.

- 💥 **BREAKING:** Smart LM Loader — Python schema reordered into logical UI order: model → quantization → (mode bar) → tasks → prompt/context → advanced sampling (incl. `min_p`, `mirostat`, `repeat_last_n`, `stop_sequences`) → seed → WD14 → hidden backing booleans. JS no longer reorders the seed cluster, and the legacy by-name remap was removed. ⚠️ Reload existing Smart LM Loader nodes after upgrading — widget order changed and old saves' `widgets_values` no longer line up.
- 💥 **BREAKING:** Smart LM Loader — dropped the hidden `auto_stop_container` widget. Container auto-stop logic now reads `keep_model_loaded` directly (Keep Loaded OFF → stop container; ON → keep running). Removes one widget slot and the bind-to-chip glue.
- 📚 **docs:** Smart Detection — tooltips on `temperature`, `top_p`, `top_k`, `repetition_penalty` now note that Florence-2 ignores sampling (uses deterministic decoding); these widgets only affect Qwen-VL backends.
- ✨ **feat:** chip tooltips — added per-chip hover tooltips across 10 nodes that previously had bare labels: Smart Sampler Settings v1 + v2, Replace String v3, Save Images v2, Smart Folder v2, Model Loader (+ pipe variant), Smart Model Loader, Load Image (input/output/url), Lora Stack (standard/model_only/simple), Show Any (show/hide). Combo-chip nodes now pass `{label, tooltip}` objects to `createComboChipWidget`; custom mode bars set `chip.title` directly.

- 🐛 **fix:** Smart LM backends — `top_k` and `repetition_penalty` were accepted as kwargs but silently dropped by 4 of 6 backends, plus Ollama also dropped `seed`, plus llama.cpp also dropped `top_k`. Now wired through:
- 🐛 **fix:** Ollama Docker — text + vision + fallback `/api/generate` paths all forward `top_k`, `seed`, `repeat_penalty` (mapped from `repetition_penalty`); vision path also gains the previously-missing `top_p`. Sentinel-gated (top_k>0, seed>=0, repeat_penalty!=1.0) so omitted values fall back to model defaults instead of overriding them.
- 🐛 **fix:** vLLM Docker — `top_k` + `repetition_penalty` now sent via `extra_body` on the OpenAI-compat endpoint (vLLM accepts non-OpenAI fields there).
- 🐛 **fix:** vLLM Native — `repetition_penalty` now added to `SamplingParams` (`top_k` was already wired).
- 🐛 **fix:** SGLang Docker — `top_k` + `repetition_penalty` now sent via `extra_body`.
- 🐛 **fix:** llama.cpp Docker — `top_k` now added to chat-completions payload (`repeat_penalty` was already wired).
- 🐛 **fix:** vLLM / SGLang Docker — `repetition_penalty` was only forwarded for text-only `llm_mode` calls; vision-mode requests silently dropped it. Now always forwarded regardless of mode.

**Changed files:**

- py/RvLoader_SmartModelLoader_LM.py
- py/RvLoader_SmartDetection.py
- js/eclipse-sml-loader.js
- js/eclipse-smart-sampler-settings.js, js/eclipse-smart-sampler-settings-v2.js
- js/eclipse-replace-string-v3.js, js/eclipse-save-images-v2.js
- js/eclipse-smart-folder-v2.js, js/eclipse-model-loader.js
- js/eclipse-smart-model-loader.js, js/eclipse-load-image.js
- js/eclipse-lora-stack.js, js/eclipse-show-any.js
- core/sml/backend_ollama_docker.py
- core/sml/backend_vllm_docker.py
- core/sml/backend_vllm_native.py
- core/sml/backend_sglang_docker.py
- core/sml/backend_llamacpp_docker.py
- core/sml/backend_gguf.py

---

## 2026-05-03

### Version 3.3.6

- 🐛 **fix:** Preview culling — muted nodes (`mode === 2`) were excluded from both culling and acting as occluders, so a muted node on top failed to cull nodes underneath, and a muted node underneath failed to be culled. Bypass (`mode === 4`) already worked because it wasn't special-cased. Muted nodes are still visually rendered (with the mute overlay), so they now participate in occlusion like any other visible node — only `flags.collapsed` is excluded.

**Changed files:**

- js/eclipse-preview-culling.js

---

### Version 3.3.5

- 🐛 **fix:** Preview culling — promoted widgets on subgraph host nodes were never culled. `PromotedWidgetView` (the proxy used for widgets exposed from inside a subgraph) implements `draw(...)` instead of `drawWidget(...)`, so the existing wrap never installed; for promoted DOM widgets, `widget.node` is the inner (hidden) node, so the `isVisible` patch couldn't see the visible host's culled flag. Now `wrapNodeWidgets` wraps both `drawWidget` and `draw`, the scan loop detects `PromotedWidgetView` via `sourceNodeId` / `sourceWidgetName`, resolves the inner widget via `resolveDeepest()` and tags it with `_eclipseHostCulled`, and `isVisible` honors that tag. zIndex pass forwards the host node's z-order to the inner DOM element's wrapper so subgraph DOM widgets stack correctly when subgraph hosts overlap.

**Changed files:**

- js/eclipse-preview-culling.js

---

## 2026-05-01

### Version 3.3.4

- ✨ **feat:** Smart LM Loader — new `Training` chip in the mode bar makes few-shot training examples optional. Default ON (preserves existing behavior). When OFF, system prompts and instruction templates still load, but example messages are skipped — saves ~1–3KB per prompt and reduces context pressure on small-context GGUFs. Threaded `use_few_shot` kwarg through dispatch to all 6 backends (transformers, gguf, ollama, vllm-native, vllm-docker, sglang, llamacpp). Legacy workflows saved before this feature restore with the chip ON: `onConfigure` detects when `use_few_shot_training` is missing from the saved `widgets_values` array (shorter than the serialized-widget index of the new boolean) and forces it back to `true`.
- ✨ **feat:** Docker backends (vLLM / SGLang / Ollama / llama.cpp) — apply the same per-model-type pre-resize cap to JPEG temp files sent over HTTP. Previously a flat 2MP cap was used everywhere, which under-utilized QwenVL (native ceiling ~12MP) and over-spent bandwidth on LLaVA/Florence2 models that downsample internally. Now `_tensor_to_temp_jpegs()` resolves the cap from `instance.model_type` via `get_max_pixels_for_model_type()`, matching the transformers path. Verified against official vLLM / SGLang / Ollama / llama.cpp docs — none of these enforce a server-side pixel cap; sizing is governed entirely by each model's HF processor / mmproj.
- ✨ **feat:** Smart LM Loader + Smart Detection — R-key refresh now reloads the SML model registry. Both extensions add a `refreshComboInNodes` hook gated on the presence of at least one matching node in the graph (so users without these nodes don't trigger registry reloads on every R press). The hook POSTs `/smartlml/registry/reload`, then refetches `/smartlml/model_list` (loader) / `/smartlml/detection/model_list` (detection) and updates the model dropdown on every existing node. The loader groups dict entries by `has_vision`/`backend` and re-inserts the same separator tokens (`__SEP__VISION_MODELS__`, `__SEP__TEXT_MODELS__`, `__SEP__WD14_MODELS__`) that Python emits at registration time before passing through `mapModelSeparators`. Both extensions hit the same endpoint, so `/smartlml/registry/reload` got a server-side 2 s debounce: repeat calls short-circuit with `{"success": true, "debounced": true}` and skip `invalidate_cache()` + `load_all_registries(force=True)`. New models added to `core/sml/registry/` JSONs are now picked up without a ComfyUI restart — same UX as the wildcard processor and prompt styler refresh paths.
- ✨ **feat:** Transformers backend — per-model-type pre-resize cap. The processor always re-resizes internally, so our pre-resize is a sanity guard only. New `VLM_MAX_PIXELS_BY_MODEL_TYPE` table sets reasonable upstream caps per family (QwenVL=12MP, Mistral3=2.5MP, mLLaMA=2MP, LLaVA=1MP, Florence2=0.78MP) instead of a flat 1MP/2MP split. Capable models keep more detail; tiny-image models (LLaVA 336², Florence2 768²) avoid wasted CPU resize work.

- 🐛 **fix:** Groups Panel — drop deprecated `defaultValue` argument from `app.ui.settings.getSettingValue()` calls (`Comfy.UseNewMenu`, sort-by). The frontend now logs a deprecation warning per call; the legacy-button injector ran on every monitor refresh, flooding the console. Use the documented setting default and `??` fallback instead.
- 🐛 **fix:** Show Text — drop deprecated `import { ComfyWidgets } from '../../scripts/widgets.js'` (frontend warned `"scripts/widgets.js" is an internal module`). Replaced with a direct `node.addDOMWidget('customtext', textarea)` for the read-only multiline text widget.
- 🐛 **fix:** `/eclipse/reload_all` — server-side 2 s debounce. Wildcard Processor and Prompt Styler both register `refreshComboInNodes` hooks that hit this endpoint on R-press, so wildcards / styles / pattern processor were reloading twice (visible as duplicate "Loaded 470 wildcard groups" + "Loading styles" + "Invalidating processor cache" log lines). Endpoint now caches the previous result and returns it with `"debounced": true` for repeat calls inside the window, skipping all four reload steps.
- 🐛 **fix:** Transformers backend — `family=VLM` no longer raises `Unknown model family: VLM`. The dispatcher only listed `QWEN / MISTRAL / LLAVA / FLORENCE / LLM_TEXT` for transformers loading, so generic VLM entries from `user_models.json` (where the user doesn't know the exact arch) failed at the family branch even though the underlying `_load_vlm_transformers` auto-detects the architecture from `config.json`. Added `ModelFamily.VLM` to the unified VLM loader tuple, matching the other backends (gguf/ollama/vllm/sglang/llamacpp), which already handle it via `family == VLM or ctx.has_vision`.
- 🐛 **fix:** Transformers backend — Qwen3.5 hybrid architecture (`model_type=qwen3_5`, mixed `linear_attention`/`full_attention` Mamba-style layers) crashed generation with CUDA `multinomial: probability tensor contains either inf, nan` when loaded with `flash_attention_2`. SDPA produces stable logits on the same model + same quantization. Added a `qwen3_5` quirk in `vlm_loader.py` that downgrades `flash_attention_2` → `sdpa`, mirroring the existing Mllama quirk.
- 🐛 **fix:** Transformers backend — Qwen-VL family (Qwen2-VL / Qwen2.5-VL / Qwen3-VL / Qwen3.5-VL) generation overhaul. Fixes `ValueError: Image features and image tokens do not match, tokens: 0, features: N` from the two-step `apply_chat_template(tokenize=False)` → `processor(text, images)` path which dropped the image during template expansion. Switched to the canonical all-in-one `processor.apply_chat_template(messages, tokenize=True, return_dict=True, return_tensors="pt", add_generation_prompt=True)` and always pass Eclipse's bundled official Qwen3.5-VL jinja (`core/sml/templates/qwen_vl_chat_template.jinja`) via the `chat_template=` kwarg — works as a universal Qwen-VL template across all variants and fixes abliterated/merged variants (e.g. `Huihui-Qwen3.5-4B-Claude-...-abliterated`) whose bundled text-only Qwen jinja silently drops list-content (image+text) messages. Vision few-shot examples now return content as `[{"type": "text", "text": ...}]` to match Qwen3-VL/Qwen3.5-VL list-content templates (string-content shape was raising `string indices must be integers, not 'str'` inside the jinja). Added `use_cache=True` to QWENVL `gen_kwargs` (previously only on LLAVA/MLLAMA) — critical for Qwen3.5 hybrid linear_attention + Mamba SSM layers, which without explicit cache fall back to O(n²) per-step recomputation and hang for 30+ minutes on a 4B model.

- 📚 **docs:** `registry/user_models.json.example` template — added a 2nd `_example_*` entry to every backend section (transformers, gguf, ollama, vllm, sglang, wd14) so the comma between sibling entries is visible at a glance, plus a `_hint_json_format` field documenting JSON's "comma between, none after the last" rule. Migration auto-applies the new template only to users who hadn't customized their copy (Case 4a in `core/migration.py`); user-edited files are preserved (Case 4b) and the manifest hash is silently bumped.
- 📚 **docs:** Readme/ — replaced all `SmartLML` / `ComfyUI SmartLML` / `ComfyUI_SmartLML` references with Eclipse equivalents across 5 guide files. Folder paths updated (`ComfyUI_SmartLML/` → `comfyui_eclipse/`); section headers, TOC anchor links, table cells, and footers updated; version footers bumped to `v3.3.4`.

**Changed files:**

- py/RvLoader_SmartModelLoader_LM.py
- js/eclipse-sml-loader.js
- js/eclipse-sml-detection.js
- js/eclipse-groups-panel.js
- js/eclipse-show-text.js
- core/sml/vlm_loader.py
- core/sml/vlm_detection.py
- core/sml/backend_transformers.py
- core/sml/backend_gguf.py
- core/sml/backend_ollama_docker.py
- core/sml/backend_vllm_native.py
- core/sml/backend_vllm_docker.py
- core/sml/backend_sglang_docker.py
- core/sml/backend_llamacpp_docker.py
- core/sml/server_endpoints.py
- core/sml/loader_base.py
- core/sml/backend_transformers.py
- core/sml/config_templates.py
- core/sml/vlm_loader.py
- core/sml/templates/qwen_vl_chat_template.jinja (new)
- core/server_endpoints.py
- .defaults/registry/user_models.json.example
- .defaults/.manifest.json

---

### Version 3.3.3

- 🐛 **fix:** SML hash verification — `verify_model_integrity` now passes the configured `hf_token` (or `HF_TOKEN`/`HUGGING_FACE_HUB_TOKEN` env vars) to `get_hf_file_metadata`, eliminating "unauthenticated requests to the HF Hub" warnings and avoiding rate limits / gated-repo failures when fetching SHA256 from HuggingFace after download.

**Changed files:**

- core/sml/model_files.py

---

## 2026-04-27

### Version 3.3.2

- ✨ **feat:** Image Comparer — right-click menu adds "Default output: A / B" to choose which side feeds the `image` output. Persisted in `node.properties.default_output`; Python reads it from `extra_pnginfo['workflow']` by `unique_id`. Default is `b` (the new/result image in typical wiring).

**Changed files:**

- py/RvImage_ImageComparer.py
- js/eclipse-image-comparer.js

---

### Version 3.3.1

- ✨ **feat:** new Show Text — lightweight text-only display node (terminal, no output). Read-only multiline widget per input list entry, persists displayed text into workflow metadata, simpler/smaller than Show Any (no image/mask/JSON branches). Adapted from pysssss ShowText (MIT) for V3 API.
- ✨ **feat:** Smart Detection — advanced/adjust widget values now persisted to `registry/defaults.json` on execute (mirrors Smart LM Loader behavior). Detection-specific params (`confidence`, `nms_iou_threshold`, `detection_filter`, `drop_size`, `crop_factor`, `dilation`, `select_index`, `use_torch_compile`, `convert_to_bboxes`) now load from defaults so new instances start with last-used values. Values are always applied regardless of `Advanced`/`Adjust` chip visibility (chips control UI only).

- 🐛 **fix:** Smart Detection — Docker backends (Ollama/vLLM/SGLang/llama.cpp) now stop the container when `Keep Loaded` chip is OFF. Bound to existing chip instead of adding a separate `auto_stop_container` widget — semantics match (OFF = release VRAM/container, ON = persist across runs).
- 🐛 **fix:** Smart LM Loader — `auto_stop_container` widget now bound to `Keep Loaded` chip (auto_stop = NOT keep_loaded). Widget hidden permanently via JS `hideInitially()` (Python `extra_dict={"hidden": True}` alone does not suppress widget rendering for Boolean inputs without `socketless=True`).

**Changed files:**

- py/RvLoader_SmartDetection.py
- py/RvLoader_SmartModelLoader_LM.py
- py/RvTools_ShowText.py (new)
- js/eclipse-sml-loader.js
- js/eclipse-show-text.js (new)
- pyproject.toml

---

## 2026-04-25

### Version 3.3.0

- ✨ **feat:** new Eclipse Groups Panel — dual surface (sidebar tab in new menu via `app.extensionManager.registerSidebarTab`, slide-out floating panel in legacy menu mode) listing every group in the active workflow with a tri-state Active/Mute/Bypass control per group (reuses Fast Mode Switcher palette). Sort dropdown (workflow / A→Z / Z→A / position / color / node count / state) persisted via `Comfy.Eclipse.GroupsPanel.SortBy`, live case-insensitive title filter, footer batch buttons (Set all Active/Bypass/Mute), click-title to recenter canvas on group. Floating panel widened to 420px and shifts the legacy menu left on open (snapshot/restore inline styles, never touches localStorage). Sidebar tab id `eclipse-groups`, icon `pi pi-objects-column`. Command `Eclipse.GroupsPanel.Toggle` routes to `Workspace.ToggleSidebarTab.eclipse-groups` in new-menu mode, else toggles the floating panel.

- ⚡ **perf:** Groups Panel refresh tick slowed 500ms → 2000ms with fingerprint-diff guard (sortId, search, group titles/states/colors). Static workflows do zero DOM work between ticks — fixes button hover-flicker on the Active/Mute/Bypass segments.

- 🧹 **chore:** deprecate Fast Muter, Fast Bypasser (superseded by Fast Mode Switcher) and Fast Groups Muter, Fast Groups Bypasser (superseded by the Eclipse Groups Panel). Moved to `py/legacy/`, marked `is_deprecated=True`, recategorised under `🌒 Eclipse/ Legacy`. node_ids preserved for workflow compat.

**Deprecated nodes:**

- Fast Muter, Fast Bypasser, Fast Groups Muter, Fast Groups Bypasser (4)

**Changed files:**

- js/eclipse-groups-panel.js (new)
- py/legacy/legacy_FastMuter.py (moved from py/RvTools_FastMuter.py)
- py/legacy/legacy_FastBypasser.py (moved from py/RvTools_FastBypasser.py)
- py/legacy/legacy_FastGroupsMuter.py (moved from py/RvTools_FastGroupsMuter.py)
- py/legacy/legacy_FastGroupsBypasser.py (moved from py/RvTools_FastGroupsBypasser.py)
- pyproject.toml

---

### Version 3.2.26

- 🐛 **fix:** Smart Detection — IndexError "too many indices" when Qwen/Ollama returns a single bbox as a flat list `[x1,y1,x2,y2]` instead of `[[x1,y1,x2,y2]]`. `_normalize_bboxes` now wraps flat 4-int lists; `nms_filter` defensively reshapes 1-D input.

**Changed files:**

- core/sml/vlm_detection.py

---

## 2026-04-23

### Version 3.2.25

- ⚡ **perf:** preview-culling scan now early-exits when graph geometry + selection are unchanged since the last pass (fingerprint check over node count, positions, sizes, collapsed/mode flags, selection). The 700ms tick becomes near-free while the graph is static — culling is graph-space so pan/zoom don't invalidate it.

**Changed files:**

- js/eclipse-preview-culling.js

---

### Version 3.2.24

- ⚡ **perf:** `setVisible` now seeds its state cache from `widget.hidden` on first encounter — default-matching calls during `onConfigure` hit a fast-path exit with no DOM mutation. This was the biggest single win of the entire perf pass — ~3,060 redundant calls per cold load now skip all work.
- ⚡ **perf:** split `vis.setVisible` diagnostic counter into real writes vs fast-path skips (`vis.setVisible.skip`) so the dump shows actual DOM-mutation cost instead of invocation count.

**Measured impact — real DOM writes (Vue Nodes 2.0, ~500-node workflow, cold load):**

| Metric                                    |  v3.2.22 |  v3.2.23 | v3.2.24 |     Δ vs 22 |
| ----------------------------------------- | -------: | -------: | ------: | ----------: |
| Total `setVisible` writes (all nodes)     |    4,838 |    4,158 |   1,098 |  **−77% ✨** |
| `setVisible` writes during load           |    3,687 |    3,148 |     780 |  **−79% ✨** |
| Smart Model Loader `setVisible` writes    |    1,600 |    1,088 |     511 |      −68% ✨ |
| `canvasDirtyBatcher.markDirty` calls      |       94 |       26 |      26 |         −72% |
| `notifyVue` calls                         |      110 |        0 |       0 |        −100% |
| `batchedNotifyVue` calls                  |       25 |        0 |       0 |        −100% |

*v3.2.22 "after" counts include redundant invocations; v3.2.24 counts only real DOM mutations since the counter now excludes fast-path skips (~3,060 calls/load).*

**Changed files:**

- js/eclipse-widget-performance-utils.js

---

### Version 3.2.23

- ⚡ **perf:** gated all `notifyVue` / `batchedNotifyVue` calls across the entire JS codebase behind `isVueMode()` (~60 sites in ~25 files). Classic canvas renderer redraws from model state each frame, so the Vue-reactivity nudge is pure overhead there. One consistent discipline in every Eclipse JS file.
- ⚡ **perf:** gated `eclipse-node-size-fix` entirely to Vue mode — all its paths depend on per-node DOM elements that don't exist in classic mode. Skips collapse-wrap closure allocation per node and double-rAF `fixAllNodes()` on workflow load.
- ⚡ **perf:** applied `isConfiguringGraph()` gate to 17 nodes whose initial visibility pass duplicated the `onConfigure` pass during workflow load (~60 `setVisible` calls per node skipped on cold load). Gated nodes include Smart Model Loader, Smart Prompt v1/v2, Lora Stack, Model Loader, Replace String v3, Image/Text with FX, Smart Sampler Settings v1/v2, Smart LM Loader, image/video-resolution, and others. Fresh adds from the menu still run the initial pass.
- ⚡ **perf:** applied `hideInitially()` to ~15 additional nodes with conditional widgets — Vue's first render now paints the final layout directly instead of rendering-then-hiding 10–30 widgets per node, removing the "tall node then shrink" flash on cold workflow loads.
- ⚡ **perf:** widget-performance-utils improvements:
- `setVisible` bypasses Vue reactivity entirely in classic mode.
- Classic-only gating for input-slot prototype patches (~1400 closures skipped per 355-node workflow load in Vue mode).
- `setVisible` routes through shared `batchedNotifyVue` so many managers notifying in the same microtask collapse into one flush.
- `smartResize` classic-mode fast-path (no more 60-frame spin waiting for nonexistent DOM); suspends during `configuringGraph` so serialized sizes aren't overridden.
- Workflow-load flash fix via native `app.configuringGraph` counter; new `isConfiguringGraph()` / `hideInitially()` helpers.
- Opt-in diagnostic logger (zero overhead when off, independent of `log_level`) — enable via `localStorage.eclipse_perf_log = '1'` (or `'verbose'`) and reload. Dump via `window.eclipsePerfDump()`.

- 🐛 **fix:** Lora Stack / Smart LM Loader / Smart Detection — sync size-shrink after initial visibility refresh so fresh-added nodes don't paint full-height then shrink. Lora Stack additionally defers its initial refresh to rAF so `node.id` is assigned in time (regression from `hideInitially()` rollout).
- 🐛 **fix:** Smart Prompt v1 + v2 — sync `computeSize()` + `setSize()` after initial folder-visibility refresh so fresh-added nodes paint at their compact height on frame 1. v1 defers to rAF so `node.id` is set before the `id === -1` guard runs.
- 🐛 **fix:** Smart Prompt v2 — `folders` default changed from "all folders pre-selected" to empty so fresh-added nodes start compact.
- 🐛 **fix:** wildcard-processor + prompt-styler R-key refresh — prepend `/eclipse/reload_all` to refresh hooks so wildcard dict, styles cache, and pattern processor re-read from disk before combo options refetch (no more stale data until restart).

**Measured impact (Vue Nodes 2.0, ~500-node workflow, cold load):**

| Metric                                    | Before | After |       Δ |
| ----------------------------------------- | -----: | ----: | ------: |
| `notifyVue` calls                         |    110 |     0 |   −100% |
| `batchedNotifyVue` calls                  |     25 |     0 |   −100% |
| `canvasDirtyBatcher.markDirty` calls      |     94 |    26 |    −72% |
| Smart Model Loader `setVisible` calls     |  1,600 | 1,088 |    −32% |
| Total `setVisible` calls (all nodes)      |  4,838 | 4,158 |    −14% |
| `setVisible` during `configuringGraph`    |  3,687 | 3,148 |    −15% |
| `smartResize` calls                       |    201 |   183 |     −9% |
| `hideInitially` coverage (nodes pre-hid.) |      9 |    41 | +356% ✨ |

> **Measure it yourself:** run `localStorage.eclipse_perf_log = '1'` in the browser console and reload. Call `window.eclipsePerfDump()` after your workflow loads. Disable with `localStorage.removeItem('eclipse_perf_log')`. Fully opt-in, independent of Eclipse `log_level`.

**Changed files:**

- js/eclipse-widget-performance-utils.js, js/eclipse-preview-culling.js, js/eclipse-smart-prompt.js, js/eclipse-smart-prompt-v2.js, js/eclipse-lora-stack.js, js/eclipse-smart-model-loader.js, js/eclipse-smart-sampler-settings.js, js/eclipse-smart-sampler-settings-v2.js, js/eclipse-model-loader.js, js/eclipse-replace-string-v3.js, js/eclipse-clip-loader.js, js/eclipse-smart-folder.js, js/eclipse-smart-folder-v2.js, js/eclipse-sampler-overwrite.js, js/eclipse-image-resolution.js, js/eclipse-video-resolution.js, js/eclipse-wildcard-processor.js, js/eclipse-prompt-styler.js, js/eclipse-sml-loader.js, js/eclipse-sml-detection.js, js/eclipse-load-image.js, js/eclipse-load-image-folder.js, js/eclipse-save-images-v2.js, js/eclipse-save-prompt.js, js/eclipse-image-with-fx.js, js/eclipse-text-image-with-fx.js, js/eclipse-image-resize.js, js/eclipse-smart-loader-v2.js, js/eclipse-smart-loader-plus-v2.js, js/eclipse-read-prompt-files.js, js/eclipse-mode-nodes.js, js/eclipse-seed.js, js/eclipse-seed-v2.js, js/eclipse-detection-to-bboxes.js, js/eclipse-node-size-fix.js, py/RvText_SmartPromptV2.py

---

### Version 3.2.22

- 🐛 **fix:** Fast Muter / Fast Bypasser / Fast Mode Switcher / Fast Groups Muter+Bypasser — menu actions ("Enable all", "Mute all", "Bypass all", "Toggle all", "Restriction: *") did not visually update in Vue Nodes 2.0 until the node was collapsed/expanded. Two independent Vue reactivity gaps:
1. The owner node's own custom-drawn switch widgets — synchronous `notifyVue` + `setDirtyCanvas` fired inside a PrimeVue menu callback was clobbered by Vue's reflow on menu overlay teardown. Fixed by deferring notify+redraw past menu close via `batchedNotifyVue` (microtask) + double-rAF full redraw (`setDirtyCanvas(true, true)`), and calling `w.triggerDraw?.()` on each widget so its per-widget canvas (Vue renders each custom widget into its own canvas) redraws with the new state.
2. The downstream linked nodes whose `.mode` was mutated — direct `node.mode = X` assignment bypasses each node's Vue reactive proxy, so the mute/bypass visual state stayed stale on the connected nodes. Fixed by calling `batchedNotifyVue(node)` per changed node inside `changeModeOfNodes` and `propagateToInnerNodes` (covers subgraph inner nodes too). Microtask batching avoids per-node reflow overhead when many nodes change at once. Classic canvas renderer was unaffected because it repaints all nodes from model state on each frame.

- ⚡ **perf:** mode-nodes — switched all load-time / stabilize / sync paths from immediate `notifyVue` to `batchedNotifyVue` (5 sites: `refreshToggleWidgetsFromConnections`, `modeChangerStabilize`, `groupsRefreshWidgets`, `syncModeSwitcherWidgets`, `modeSwitcherStabilize`). With many Fast Muter/Bypasser/Switcher nodes in the same workflow, the simultaneous stabilize burst during graph load previously fired N independent widget-array pokes; batching dedupes via Set and flushes all pending nodes in a single microtask.
- ⚡ **perf:** widget-performance-utils `_applyResize` — early-return when DOM element isn't mounted yet (common during Vue workflow load). Previously the sync pass ran `computeSize()` + `setSize()` even when the CSS `setProperty` block was a no-op (no el). The trailing rAF pass still runs after Vue mounts. Halves the work at workflow load time for any node calling `smartResize()` (Set/Get, Lora Stack, Smart Folder v2, mode-changer nodes, etc.).
- ⚡ **perf:** preview-culling — removed per-frame `wrapNodeWidgets(node)` call from both `onDrawBackground` patch variants (beforeRegisterNodeDef + lazy). The function is idempotent but was iterating the widget list on every draw frame for every culling-enabled node. Now `wrapNodeWidgets` runs only during `runCullingScan` (every 700ms) when widgets could have changed.

**Changed files:**

- js/eclipse-mode-nodes.js, js/eclipse-widget-performance-utils.js, js/eclipse-preview-culling.js

---

### Version 3.2.21

- 🐛 **fix:** combo-chip absorbing dynamic vertical space in Vue Nodes 2.0 (frontend 1.42.11) — restored `featWidget.computeLayoutSize = undefined` override in Vue mode so `_arrangeWidgets` routes the chip to the fixed-height else branch instead of the distribute-space pool; chip bar now stays at WIDGET_TOTAL_HEIGHT and extra node height goes to the preview/textarea as intended. Regression from 3.1.21 when tooltip support was added.
- 🐛 **fix:** combo-chip floating panel now uses a fixed 320px width instead of deriving min/max width from the zoomed trigger `getBoundingClientRect()` — chip wrapping/row count stays consistent across canvas zoom levels.
- 🐛 **fix:** narrow nodes in Vue Nodes 2.0 (frontend 1.41+) had empty clickable area extending past the rendered pill body — frontend hardcodes `--min-node-width: 225px` inline on the outer `.lg-node` container, so nodes with actual width < 225px (Set/Get pills, compact utility nodes) were force-expanded to 225px. Fix overrides `--min-node-width` inline to match `node.size[0]` when narrower; re-applies on uncollapse so expand transitions restore the correct tight fit.

**Changed files:**

- js/eclipse-combo-chip.js, js/eclipse-node-size-fix.js

---

## 2026-04-21

### Version 3.2.20

- ✨ **feat:** Set/Get — GetAllActive, GetFirst, GetNode now resolve SetNodes in ANY graph (ancestor, descendant, or sibling) as long as the setter's path to root is active
- ✨ **feat:** sibling subgraph scoping — Get in subgraph A can read a var set in sibling subgraph B (previously blocked)

- ♻️ **refactor:** new isSetterPathToRootActive() gate replaces the ancestor/descendant split — single check that matches exactly what the frontend requires for DTO existence (every SubgraphNode from setterGraph up to root must be neither muted nor bypassed)

**Changed files:**

- js/eclipse-set-get-utils.js, js/eclipse-set-get.js, js/eclipse-getallactive.js, js/eclipse-getfirst.js

---

### Version 3.2.19

- ✨ **feat:** Set/Get — GetAllActive, GetFirst, GetNode now resolve SetNodes inside child subgraphs (descendant-aware resolution)
- ✨ **feat:** bidirectional subgraph scoping — Get nodes can read vars set in ancestor OR descendant subgraphs; sibling subgraphs still blocked

- 🐛 **fix:** isDescendantPathActive — now walks via real SubgraphNode instances and checks mode 2 (MUTE) in addition to mode 4 (BYPASS); returns false when any wrapper link is missing
- 🐛 **fix:** prevents "No DTO found for virtual source node" crash when a setter resides in an orphan subgraph definition or under a muted/bypassed SubgraphNode — frontend graphToPrompt skips inner-node DTO creation in those cases
- 🐛 **fix:** all three Get nodes now use isDescendantPathActive as the single gate instead of getGraphAncestors().includes() which produced false positives for non-instantiated subgraph definitions

**Changed files:**

- js/eclipse-set-get-utils.js, js/eclipse-set-get.js, js/eclipse-getallactive.js, js/eclipse-getfirst.js

---

### Version 3.2.18

- 🐛 **fix:** Set/Get — resolveVirtualOutput now supports ancestor SetNodes; blocks sibling and descendant subgraphs
- 🐛 **fix:** GetAllActive / GetFirst — same ancestor-only scope in resolveVirtualOutput
- 🐛 **fix:** all three — resolveVirtualOutput uses resolveBypassedLink for bypass chain traversal on source nodes (prevents "No DTO found" when source feeding SetNode is bypassed)
- 🐛 **fix:** GetAllActive / GetFirst — getInputLink restricted to same-graph only; cross-graph (ancestor) resolved exclusively via resolveVirtualOutput
- 🐛 **fix:** prevents "No DTO found for virtual source node" crash on frontend 1.42.11+ (natively calls resolveVirtualOutput for all virtual nodes)
- 🐛 **fix:** prevents "InvalidLinkError: Virtual node failed to resolve parent" when findSetter searched all graphs causing LLink.resolve(this.graph) to fail when SetNode was in a different graph
- 🐛 **fix:** utils — add isDescendantPathActive() helper (reserved for future use)
- 🧹 **chore:** migrate canvas menu from deprecated getCanvasMenuOptions monkey-patch to getCanvasMenuItems hook (Eclipse.nodeMenuItems extension)

**Changed files:**

- js/eclipse-set-get-utils.js, js/eclipse-set-get.js, js/eclipse-getallactive.js, js/eclipse-getfirst.js, js/eclipse-ui-enhancements.js

---

## 2026-04-19

### Version 3.2.17

- 🐛 **fix:** duplicate Eclipse.PreviewCulling extension name — broke comma-chained registrations in eclipse-ui-enhancements.js, killing color menu and everything after it
- 🐛 **fix:** preview culling — move config fetch to init() to avoid setup() timing race

**Changed files:**

- js/eclipse-preview-culling.js, js/eclipse-ui-enhancements.js

---

### Version 3.2.15

- ✨ **feat:** preview culling — configurable via Eclipse settings panel (default: enabled, requires page reload)

- 🧹 **chore:** remove unused dev_mode setting from Eclipse + SML endpoints, config, and settings panel

**Changed files:**

- core/server_endpoints.py, core/common.py
- core/sml/server_endpoints.py, core/sml/config_templates.py
- js/eclipse-preview-culling.js, js/eclipse-ui-enhancements.js
- .defaults/config.json.example

---

### Version 3.2.14

- ✨ **feat:** Get First, Get All Active — Show/Hide Nav Arrows right-click menu toggle
- ✨ **feat:** Fast Mode Switcher — Show/Hide Nav Arrows right-click menu toggle, default changed to hidden

- 📚 **docs:** new Set/Get & Bridge user guide (Readme/Set_Get_Bridge.md)
- 📚 **docs:** README — added v4.0.0 legacy removal warning + Set/Get guide link

**Changed files:**

- js/eclipse-getfirst.js, js/eclipse-getallactive.js, js/eclipse-mode-nodes.js
- Readme/Set_Get_Bridge.md (new), README.md

---

### Version 3.2.13

- ✨ **feat:** new Mode Bridge Set + Mode Bridge Get — split Bridge into publisher/subscriber pair. Set publishes mode wirelessly to all same-named Gets across all graphs. Get has a dynamic combo listing all Set names with orphan detection (⚠). Supports consensus logic for repeater-driven Gets and paste dedup for Sets. Get titles use "Get: {name}" prefix for visual distinction
- ✨ **feat:** Fast Mode Switcher — jump-to nav arrow on each widget row. Resolves through Mode Bridge (finds sibling bridge by bridgeName → containing group) and Mode Relay (containing group) with zoom-to-fit. Direct nodes jump to the node itself. Togglable via showNav property (default: on)
- ✨ **feat:** Get All Active — nav arrow on each var widget row, click to jump to the matching Setter node. Var combos shrunk by 18px to create a dedicated nav lane. Togglable via showNav property (default: on)
- ✨ **feat:** Get First — nav arrow on each var widget row, click to jump to the matching Setter node. Same dedicated nav lane and showNav toggle as Get All Active
- ✨ **feat:** Add SetNode / Add GetNode / Add Bridge Set / Add Bridge Get in canvas right-click Eclipse submenu
- ✨ **feat:** Add Bridge Set / Add Bridge Get in node right-click Eclipse submenu

- 🐛 **fix:** canvas right-click Add SetNode/GetNode added to root graph instead of current subgraph

- 🧹 **chore:** deprecate Mode Bridge (replaced by Mode Bridge Set + Mode Bridge Get)
- 🧹 **chore:** move legacy Mode Bridge to py/legacy/ subfolder

**Changed files:**

- py/RvTools_ModeBridgeSet.py (new), py/RvTools_ModeBridgeGet.py (new)
- py/legacy/legacy_ModeBridge.py (moved from py/RvTools_ModeBridge.py)
- js/eclipse-getallactive.js, js/eclipse-getfirst.js, js/eclipse-mode-nodes.js, js/eclipse-set-get.js

---

## 2026-04-18

### Version 3.2.12

- 🐛 **fix:** stale _Eclipse_queuedSeed when switching fixed→random — queued seed from previous execution persisted, so consumers in inner graphToPrompt hooks reused the old value. Now cleared at the start of each seed-source's graphToPrompt before calling inner hooks
- ♻️ **refactor:** centralize seed resolution into eclipse-seed-utils.js — single source of truth for getResolvedSeedFromGraph (was duplicated in 5 consumer files), clearQueuedSeeds, and storeQueuedSeed (was inline in 9 producer files)

**Changed files:**

- js/eclipse-seed-utils.js (new)
- js/eclipse-smart-sampler-settings.js, js/eclipse-smart-sampler-settings-v2.js
- js/eclipse-smart-model-loader.js
- js/eclipse-seed.js, js/eclipse-seed-v2.js
- js/eclipse-smart-prompt.js, js/eclipse-smart-prompt-v2.js
- js/eclipse-wildcard-processor.js, js/eclipse-smart-folder-v2.js
- js/eclipse-load-image-folder.js, js/eclipse-read-prompt-files.js

---

### Version 3.2.11

- 🐛 **fix:** Smart LM Loader — WD14 exclude_tags widget not populated with saved defaults from defaults.json. Schema default was hardcoded to empty string instead of reading wd14_exclude_tags from registry/defaults.json
- 🐛 **fix:** Smart LM Loader — WD14 exclude_tags not persisted on execute. Added persist-on-execute so user changes are saved back to defaults.json
- 🐛 **fix:** Smart LM Loader — JS frontend not populating exclude_tags widget when switching to a WD14 model. Added wd14_exclude_tags to model entry API response and JS applies it on model change when widget is empty
- 🐛 **fix:** seed double-resolution in graphToPrompt — when SamplerSettings/SmartModelLoader resolved a seed and cleared cache, downstream nodes (LoadImageFromFolder, SmartPrompt, WildcardProcessor, ReadPromptFiles) called _resolveSeed again and got a different random value. Now stores queued resolved seed so consumers read the same value. Fixes: image advancing once when switching from random to fixed seed
- 🐛 **fix:** seed double-resolution — extended _Eclipse_queuedSeed storage to ALL remaining seed-source nodes (Seed v1/v2, SmartPrompt v1/v2, WildcardProcessor, SmartFolder v2) so any node acting as a seed source for downstream consumers provides a stable resolved value

**Changed files:**

- py/RvLoader_SmartModelLoader_LM.py
- core/sml/model_registry.py
- js/eclipse-sml-loader.js
- js/eclipse-smart-sampler-settings-v2.js, js/eclipse-smart-sampler-settings.js
- js/eclipse-smart-model-loader.js
- js/eclipse-load-image-folder.js, js/eclipse-smart-prompt.js
- js/eclipse-smart-prompt-v2.js, js/eclipse-wildcard-processor.js
- js/eclipse-read-prompt-files.js
- js/eclipse-seed.js, js/eclipse-seed-v2.js, js/eclipse-smart-folder-v2.js

---

### Version 3.2.10

- ✨ **feat:** new Fast Mode Switcher node — unified 3-state mode control (Active / Bypass / Mute) per connected node. Click cycles through states. Replaces needing separate Fast Muter + Fast Bypasser when both modes are required. Context menu: Enable all, Mute all, Bypass all, Toggle all. Supports collapse connections and toggle restrictions (default, max one, always one)
- ✨ **feat:** Mode Relay — allow output connection to Mode Bridge for wireless group control

- 🐛 **fix:** Mode Bridge — preserve custom node title when bridge name changes. Title only auto-updates from default ("Mode Bridge") or when manually changed via "Set Bridge Name..." menu and title still matches the old name. Paste collision renames (e.g. Model Loader → Model Loader_0) no longer overwrite the displayed title
- 🐛 **fix:** Text Image with FX / Image with FX — color swatch custom draw leaked ctx state (textBaseline, textAlign, font) to subsequent widgets, causing bottom-aligned text. Wrapped in ctx.save/restore

- ♻️ **refactor:** Preview Mask — remove Show_Masks input (always previews all masks). Removes unused `sys` import

**Changed files:**

- py/RvTools_FastModeSwitcher.py (new), __init__.py
- py/RvImage_Preview_Mask.py
- js/eclipse-mode-nodes.js, js/eclipse-text-image-with-fx.js, js/eclipse-image-with-fx.js

---

## 2026-04-17

### Version 3.2.9

- ✨ **feat:** new Image Align Size node — adjusts image dimensions to be divisible by a given number. Fixes models requiring specific divisibility (e.g. BiRefNet needs dims divisible by 31). Modes: shrink (center crop), grow (pad with black/white/edge), resize (interpolate). Handles optional mask

- ♻️ **refactor:** String Multiline, String Multiline List, String Dual — remove custom DOM textarea widgets, use native ComfyUI multiline textarea with CSS-only monospace styling. Fixes input_string slot rendered at wrong position above the text widget
- ♻️ **refactor:** remove eclipse-dom-text.js helper (no remaining consumers)

- 🐛 **fix:** culling — lazy-patch onDrawBackground for group/subgraph nodes with dynamic type names not in static culling set. Fixes auto-exposed preview images from inner samplers rendering when fully occluded

**Changed files:**

- py/RvImage_AlignSize.py (new)
- js/eclipse-string-nodes.js, js/eclipse-preview-culling.js
- js/eclipse-dom-text.js (deleted)
- __init__.py

---

## 2026-04-16

### Version 3.2.8

- ✨ **feat:** new Text Image with FX node — combined text rendering with outer glow, drop shadow, and stroke outline. 9-anchor positioning, native color picker with canvas swatch, text_scale %, auto-size canvas, dynamic widget visibility (glow/shadow/stroke toggles), bundled default fonts
- ✨ **feat:** new Image with FX node — composites an input image (logo, signature, watermark) with outer glow and drop shadow. Uses input alpha as shape mask. 9-anchor positioning, image_scale %, color picker, dynamic visibility
- ✨ **feat:** new core/image_helpers.py — centralized tensor2pil, pil2tensor, image2mask, hex_to_rgb, hex_to_rgb_float, rgb_to_hex, expand_mask, shift_image, lerp, step_color
- ✨ **feat:** opacity widget on Text Image with FX and Image with FX — controls overall visibility of the composited construct (text/image + glow + shadow) via Image.blend in RGB space

- ♻️ **refactor:** TextImageWithFX imports from centralized core/image_helpers.py instead of inline helpers

- 📚 **docs:** added core/image_helpers.py reference to AGENTS.md Centralized Functions section

**Changed files:**

- py/RvImage_TextImageWithFX.py (new), py/RvImage_ImageWithFX.py (new), core/image_helpers.py (new)
- js/eclipse-text-image-with-fx.js (new), js/eclipse-image-with-fx.js (new)
- fonts/ (new — bundled default fonts)
- __init__.py

---

## 2026-04-15

### Version 3.2.7

- ✨ **feat:** preview culling for KSampler, KSamplerAdvanced, SamplerCustom — added to culled node list
- ✨ **feat:** updated culled node names — replaced stale SmartLML names with Smart LM Loader/Smart Detection [Eclipse]

- 🐛 **fix:** preview culling missed late-added widgets (e.g. KSampler ImagePreviewWidget) — switched from per-node flag to per-widget tracking so dynamically added preview widgets are wrapped on next onDrawBackground
- 🐛 **fix:** Mode Bridge and Set/Get nodes renamed when converting selection to subgraph — convertToSubgraph internally calls graph.configure() which triggered paste-rename validation; added subgraphOpState flag that wraps convertToSubgraph/unpackSubgraph to suppress rename logic during subgraph operations

**Changed files:**

- js/eclipse-preview-culling.js
- js/eclipse-mode-nodes.js, js/eclipse-set-get.js, js/eclipse-set-get-utils.js

---

### Version 3.2.6

- 🐛 **fix:** Mode Bridge paste allows creating/completing a pair — only renames when 2+ pre-existing (non-pasted) bridges already have the same name; copying a single bridge to create its pair keeps the name unchanged

**Changed files:**

- js/eclipse-mode-nodes.js

---

## 2026-04-14

### Version 3.2.5

- ✨ **feat:** Mode Bridge paste auto-rename for nodes inside subgraphs — added onAfterGraphConfigured hook which fires after all paste items with configuringGraph=false
- ✨ **feat:** Mode Bridge paired bridges share the same renamed name on paste — _bridgePasteRenameMap ensures the first bridge's rename is reused by all paired bridges with the same original name

- 🐛 **fix:** Set/Get paste auto-rename failed inside subgraphs — extracted shared _handlePasteValidation/_handlePasteRename methods, added onAfterGraphConfigured for both Set and Get nodes

**Changed files:**

- js/eclipse-mode-nodes.js
- js/eclipse-set-get.js

---

### Version 3.2.4

- 🐛 **fix:** Any Multi-Switch wrong type detection inside subgraphs — used app.graph (root) instead of node.graph for link/node resolution, causing wrong type propagation on first connection and types not restoring on reload
- 🐛 **fix:** AnyType handler (passer, purge, conversion, stop nodes) same app.graph vs node.graph issue inside subgraphs
- 🐛 **fix:** GetAllActive/GetFirst virtual nodes failed to resolve inside subgraphs — added resolveVirtualOutput() for cross-graph Set/Get resolution
- 🐛 **fix:** cross-graph resolveOutput patch on ExecutableNodeDTO to support resolveVirtualOutput for all virtual nodes inside subgraphs

- ✨ **feat:** Set/Get variables now have global scope — Sets created inside subgraphs are visible from root and all other graphs; Get dropdown shows child-subgraph variables labeled "(child)"
- 🐛 **fix:** Set node paste/add inside subgraph now checks entire graph tree for name collisions (was only checking same subgraph)
- 🐛 **fix:** isSetterActive/resolveBypassedLink use setter.graph for correct link resolution when setter is in a different graph
- 🐛 **fix:** Mode Bridge paste/clone auto-renames bridge name when duplicate exists — prevents unintended cross-group sync when copying groups with bridges

**Changed files:**

- js/eclipse-dynamic-inputs.js
- js/eclipse-any-type-handler.js
- js/eclipse-set-get.js
- js/eclipse-set-get-utils.js
- js/eclipse-getallactive.js
- js/eclipse-getfirst.js
- js/eclipse-mode-nodes.js

---

### Version 3.2.3

- ✨ **feat:** new ROUTER_TYPED subcategory ("Router / Typed") for type-specific passers
- ✨ **feat:** new typed passers re-integrated from RvTools_v2 — Model, Clip, VAE, SEGS, Audio, Conditioning, ControlNet, Image, Latent, Mask, WAN Model, Basic Pipe, Detailer Pipe, Pipe
- ✨ **feat:** Mode Bridge node colored with dedicated bridge category (#005a88 title / #0070a8 body)

- ♻️ **refactor:** Float, Int, String passers moved from Router to Router / Typed category

**Changed files:**

- core/keys.py
- py/RvRouter_Model_Passer.py, py/RvRouter_Clip_Passer.py, py/RvRouter_Vae_Passer.py (new)
- py/RvRouter_Segs_Passer.py, py/RvRouter_Audio_Passer.py (new)
- py/RvRouter_Conditioning_Passer.py, py/RvRouter_ControlNet_Passer.py (new)
- py/RvRouter_Image_Passer.py, py/RvRouter_Latent_Passer.py, py/RvRouter_Mask_Passer.py (new)
- py/RvRouter_WanVideoModel_Passer.py, py/RvRouter_BasicPipe_Passer.py (new)
- py/RvRouter_DetailerPipe_Passer.py, py/RvRouter_Pipe_Passer.py (new)
- py/RvRouter_Float_Passer.py, py/RvRouter_Int_Passer.py, py/RvRouter_String_Passer.py
- js/eclipse-ui-enhancements.js
- __init__.py

---

### Version 3.2.2

- ✨ **feat:** new Mode Bridge node — cross-subgraph mode sync by name; place same-named bridges in different graphs to propagate Mute/Bypass/Active state across subgraph boundaries
- ✨ **feat:** Mode Bridge has dynamic inputs for selective node control (no group fallback unlike Repeater)
- ✨ **feat:** Mode Bridge oc output connects to Fast Muter/Bypasser, Repeater, Collector

- ♻️ **refactor:** Repeater no longer falls back to group control when no inputs connected — use Mode Relay for group-based control

**Changed files:**

- py/RvTools_ModeBridge.py (new)
- py/RvTools_NodeModeRepeater.py
- js_src/eclipse-mode-nodes.js, js/eclipse-mode-nodes.js
- __init__.py

---

## 2026-04-13

### Version 3.2.1

- 🐛 **fix:** Load Image From Folder + Read Prompt Files — seed freeze not working when prompt_seed comes through IO Pipe + Set/Get from Smart Sampler Settings v2; traversal now follows pipe IO nodes (multi-input) and recognizes dual-seed _resolveSeed pattern
- 🐛 **fix:** Smart Prompt + Smart Prompt v2 — seed_input via Get node not resolved; graphToPrompt now traverses graph to resolve connected seed, patches prompt, and deletes seed_input link reference
- 🐛 **fix:** Wildcard Processor — connected seed widget via Get node used stale widget value for both wildcard expansion and prompt patching; now traverses graph to resolve actual seed value

**Changed files:**

- js/eclipse-load-image-folder.js
- js/eclipse-read-prompt-files.js
- js/eclipse-smart-prompt.js
- js/eclipse-smart-prompt-v2.js
- js/eclipse-wildcard-processor.js

---

### Version 3.2.0

- ♻️ **refactor:** SmartLML merged back into Eclipse as core/sml/ subpackage

- ✨ **feat:** Smart Sampler Settings v2 — seed mode chips (🎲/⏫/⏬) now momentary instead of radio; click flashes + sets seed, chip doesn't stay selected
- ✨ **feat:** Smart Sampler Settings v2 — image_seed defaults to -1 (random) for new nodes
- ✨ **feat:** DOM preview min height reduced from 200px to 100px — all preview nodes can now be resized smaller
- ✨ **feat:** new Smart LM Loader — VLM/LLM generation, WD14 tagging, multi-task chaining across 8 backends (Transformers, GGUF, vLLM, SGLang, Ollama, llama.cpp)
- ✨ **feat:** new Smart Detection — Florence-2, Qwen VL, and YOLO object detection; outputs bboxes, masks, and SEGS
- ✨ **feat:** new core/sml/ subsystem — 27-file LLM backend engine (backends, model registry, Docker integration, device management, task definitions)
- ✨ **feat:** new extern/florence2/ — vendored Florence-2 model implementation
- ✨ **feat:** legacy [SML] node_id wrappers — existing SmartLML workflows load transparently via deprecated forwarders
- ✨ **feat:** legacy wrappers for pre-v3 SML node_ids — Smart Language Model Loader v2/v3 [SmartLML]/[Eclipse] and Pipe Out LM Advanced Options [SmartLML]/[Eclipse]
⚠ NOTE: legacy nodes are load-only shims — workflows load without errors but the nodes must be manually replaced with
their current equivalents. Legacy nodes are marked ⚠ in the UI and will be removed in v4.0.0.

- ✨ **feat:** Eclipse UI settings panel includes SML LLM configuration (models path, retry, HF token)
- ✨ **feat:** dual-install safety check — warns if standalone SmartLML is still active
- ✨ **feat:** SML migration helpers in core/migration.py — user folder migration and junction/symlink creation for registry/config/scripts
- ✨ **feat:** all legacy nodes display a compact ⚠ prefix while keeping original node names for cleaner workflow layout
- ✨ **feat:** new Tile Split — VAE-aware image tiler (replaces TTP_Tile_imageSize + TTP_Image_Tile_Batch)
- ✨ **feat:** new Tile Assembly — gradient-blend tile stitcher (replaces TTP_Image_Assy)
- ✨ **feat:** new Tile Decode & Assembly — all-in-one VAE tiled decode + list→batch + tile assembly
Tile Split auto-detects spatial compression from VAE (8 for SD/SDXL/Flux1, 16 for Flux2).
Fixes TTP tile size mismatch where Flux2's 16x VAE silently crops tiles rounded to 8.
Single tile_pipe output bundles positions/original_size/grid_size/tile_size (4 wires → 1 pipe).
Tile Decode & Assembly eliminates 3 separate nodes (VAE Decode Tiled + L2b + Tile Assembly).
Tile Decode & Assembly auto-calculates optimal VAE decode tile_size from pipe (0 = auto).

- 🐛 **fix:** dev_mode GGUF debug blocks replaced with log.debug(); removed dead _get_dev_mode() method from server_endpoints.py
- 🐛 **fix:** ComboWidget substring crash on workflow load — hidden features backing widget with array value caused TypeError; drawWidgets proto patch coerces array→string before LiteGraph draws
- 🐛 **fix:** save-images-v2 backward compat — old workflows with features saved as array now load cleanly
- 🐛 **fix:** legacy SML v2/v3 nodes register a drawWidgets coerce patch so old multi-select array values don't crash the canvas
- 🐛 **fix:** preview culling scan disabled until workflow fully settles (1.2 s after loadGraphData, 2.4 s on initial page load)
- 🐛 **fix:** config migration — field-level merge adds missing keys without overwriting existing paths/tokens, preserves user values
- 🐛 **fix:** SML config value migration preserves old standalone user settings (hf_token, paths, retry, few-shot selection) when Eclipse still has defaults
- 🐛 **fix:** default `few_shot_training_file` now points to `llm_few_shot_training.json` (SFW) instead of NSFW by default
- 🐛 **fix:** Load Image delete button — added confirmation dialog to prevent accidental deletion when resizing node

- 📚 **docs:** Smart LM Loader Guide, Smart Detection Guide, Docker Installation (Windows + Linux), Model Repository Reference
- 📚 **docs:** README.md updated with Smart LM subsystem section, supported models, backends, tasks, Docker scripts
- 📚 **docs:** Readme/README.md documentation index updated with all SML guide links

- 🧹 **chore:** pyproject.toml — version 3.2.0, added SML core dependencies, [sml] optional-dependencies group
- 🧹 **chore:** config.json — merged SML keys (llm_models_path, hf_token, retry_download_attempts, few_shot_training_file)
- 🧹 **chore:** .defaults/.manifest.json — 353 entries (added 13 SML registry/config/docker entries)
- 🧹 **chore:** .gitignore — added SML data paths (registry/*.json, config/*.json, docker_config.json, scripts/*.sh)

**Changed files:**

- core/sml/ (27 files, new)
- core/migration.py, prestartup_script.py (new)
- extern/florence2/ (4 files, new)
- py/RvLoader_SmartModelLoader_LM.py, py/RvLoader_SmartDetection.py (new)
- py/legacy/ (30 display_name updates + 3 new wrapper files: legacy_SmartLML_v2.py, legacy_SmartLML_v3.py, legacy_PipeOut_LM_AdvancedOptions.py)
- py/legacy/__init__.py, py/legacy/legacy_SmartModelLoader_LM.py, py/legacy/legacy_SmartDetection.py (new)
- js_src/eclipse-sml-loader.js, js_src/eclipse-sml-detection.js, js_src/eclipse-ui-enhancements.js (new/edited)
- js/eclipse-sml-loader.js, js/eclipse-sml-detection.js, js/eclipse-ui-enhancements.js
- registry/ (9 JSON, new), config/ (3 JSON, new), scripts/ (4 SML scripts, new), docker_config.json (new)
- .defaults/ (13 new .example files, updated .manifest.json and config.json.example)
- __init__.py, config.json, pyproject.toml, .gitignore
- README.md, Readme/README.md
- Readme/Smart_LM_Loader_Guide.md, Readme/Smart_Detection_Guide.md (new)
- Readme/Docker_Installation_Guide.md, Readme/Docker_Installation_Guide_Linux.md (new)
- Readme/Model_Repos_Reference_Links.md, Readme/Model_Repos_Reference_CP.md (new)
- py/RvImage_TileSplit.py, py/RvImage_TileAssembly.py, py/RvImage_TileDecodeAssembly.py (new)

---

### Version 3.1.35

- 🐛 **fix:** shared global vue-mode watcher — prevent Eclipse and SmartLML from overwriting each other's onVueModeChange defineProperty; first repo to load installs watcher, second piggybacks on shared callback set (window.__comfy_vueModeCallbacks)

**Changed files:**

- js_src/eclipse-widget-performance-utils.js, js/eclipse-widget-performance-utils.js

---

### Version 3.1.34

- ✨ **feat:** Image Crop by Mask — rotation (arbitrary int degrees) and mirror (horizontal/vertical/both) pre-edit options applied before crop processing

**Changed files:**

- py/RvImage_CropByMask.py

---

### Version 3.1.33

- ✨ **feat:** new Image Crop by Mask — lightweight mask-guided crop with expansion, threshold filter, context growth, and target-resolution resize (inspired by InpaintCropAndStitch)

**Changed files:**

- py/RvImage_CropByMask.py (new)
- __init__.py

---

### Version 3.1.32

- ✨ **feat:** FilenameProcessor — added %y placeholder for 2-digit year (e.g. "26" for 2026) in Save Images, Save Prompt, and legacy Save Images nodes
Note: Smart Folder and Filename Prefix nodes already support %y natively via strftime syntax

**Changed files:**

- py/RvImage_SaveImages.py, py/RvText_SavePrompt.py, py/legacy/legacy_SaveImages.py

---

### Version 3.1.31

- ✨ **feat:** consolidated Eclipse context menu — all Eclipse items grouped under single "🌒 Eclipse" submenu in both node and canvas right-click menus
- ✨ **feat:** canvas context menu — positioned after first separator via getCanvasMenuOptions prototype patch; includes bulk Set/Get operations (convert selected outputs/inputs to Set/Get, convert selected Set/Get to links)
- ✨ **feat:** node context menu — uses getNodeMenuItems hook with provider pattern; Node Dimensions, Reload Node, and Set/Get items collected from _eclipseMenuProviders
- ✨ **feat:** Image Comparer — Open Image A/B and Save Image A/B context menu actions for quick viewing/downloading compared images

- 🐛 **fix:** Image Comparer — removed Slide/Click mode switch; always uses Slide mode (image_a shown full, image_b slides in from left following cursor position, split at slider line; entering the node from right shows image_b full size for fast preview of image_b)

- ♻️ **refactor:** Set/Get menu items — moved from direct getNodeMenuItems registration to _eclipseMenuProviders / _eclipseCanvasMenuProviders pattern; removed "Eclipse: " prefix from labels (redundant inside Eclipse submenu)
- ♻️ **refactor:** removed legacy LiteGraph showContextMenu patch fallback — replaced by new menu injection approach

**Changed files:**

- js_src/eclipse-ui-enhancements.js, js/eclipse-ui-enhancements.js
- js_src/eclipse-image-comparer.js, js/eclipse-image-comparer.js
- js_src/eclipse-set-get.js, js/eclipse-set-get.js

---

### Version 3.1.30

- ✨ **feat:** new Image Resize node — scale by longest/shortest side, width, height, total pixels, or custom W×H with aspect ratio presets (1:1, 3:2, 4:3, 16:9, etc.), fit modes (resize/crop/pad/pad_edge/pad_edge_pixel/pillarbox_blur/stretch), crop position, pad color, divisible-by alignment, and CPU/GPU device switch
- ✨ **feat:** Image Resize dynamic widget visibility — hides irrelevant inputs based on scale_to, aspect_ratio, and fit selections
- ✨ **feat:** combo-chip factory — new `momentaryChips` parameter for fire-and-forget action chips that pulse on click without staying selected (never enter selectedSet, never serialized)
- ✨ **feat:** Smart Model Loader — seed mode chips (🎲/⏫/⏬) are now momentary actions instead of radio toggles; click sets seed value instantly, chip doesn't stay highlighted

- 🐛 **fix:** Smart Model Loader re-executes every queue — deselecting seed mode chips (🎲/⏫/⏬) left seed widget at special value (-1/-2/-3), causing graphToPrompt to resolve a new random seed each queue; momentary chip design eliminates this class of bugs entirely
- 🐛 **fix:** Smart Model Loader fingerprint_inputs — time.time() fallback when no templates exist forced perpetual re-execution; replaced with static "0"

- ✨ **feat:** Image Comparer — show image dimensions (W × H) overlay labels for both A and B images, matching DOM Preview style; works in Vue mode (bottom-left/right divs) and canvas mode (drawn pills)
- 🐛 **fix:** Smart Folder v2, Smart Sampler Settings, Smart Sampler Settings v2 — deselecting seed chip now resets seed widget to last resolved seed (or 0) instead of leaving stale -1/-2/-3 special values that cause re-execution
- 🐛 **fix:** classic renderer slot type serialization — stop mutating slot.type to '__eclipse_hidden__' (gets persisted in workflow JSON but _eclipse_origType recovery info is runtime-only and lost on reload); use _eclipse_hidden boolean flag instead with 5-layer targeting interception
- 🐛 **fix:** classic renderer hidden input slots — getInputPos returns off-screen coords, getInputOnPos/getSlotInPosition return null, findFreeSlotOfType skips hidden slots, disconnect-on-hide when user-driven
- 🐛 **fix:** all nodes — add markUserDriven() to every JS file with user-driven visibility toggles so hiding a connected widget auto-disconnects its input link (prevents stale connections after user changes)
- 🐛 **fix:** legacy workflow recovery — detect and repair slots with __eclipse_hidden__ type from prior serialization by resolving correct type from nodeData

- ♻️ **refactor:** createWidgetVisibilityManager — 5-layer classic renderer slot-hiding with _eclipse_hidden flag (no type mutation), findFreeSlotOfType override, markUserDriven() API, and legacy __eclipse_hidden__ recovery

- 🧹 **chore:** Smart Folder v2 — update image_size default label to "832x1216 (2:3 XL/SD3/Flux/HiDream)"

**Changed files:**

- py/RvImage_Resize.py, js_src/eclipse-image-resize.js, js/eclipse-image-resize.js (new)
- py/RvFolder_SmartFolder.py
- py/RvLoader_SmartModelLoader.py
- js_src/eclipse-combo-chip.js, js/eclipse-combo-chip.js
- js_src/eclipse-smart-model-loader.js, js/eclipse-smart-model-loader.js
- js_src/eclipse-widget-performance-utils.js, js/eclipse-widget-performance-utils.js
- js_src/eclipse-smart-model-loader.js, js/eclipse-smart-model-loader.js
- js_src/eclipse-model-loader.js, js/eclipse-model-loader.js
- js_src/eclipse-smart-loader-v2.js, js/eclipse-smart-loader-v2.js
- js_src/eclipse-smart-loader-plus-v2.js, js/eclipse-smart-loader-plus-v2.js
- js_src/eclipse-smart-loader-basic-v2.js, js/eclipse-smart-loader-basic-v2.js
- js_src/eclipse-smart-folder.js, js/eclipse-smart-folder.js
- js_src/eclipse-smart-folder-v2.js, js/eclipse-smart-folder-v2.js
- js_src/eclipse-smart-prompt.js, js/eclipse-smart-prompt.js
- js_src/eclipse-smart-prompt-v2.js, js/eclipse-smart-prompt-v2.js
- js_src/eclipse-smart-sampler-settings.js, js/eclipse-smart-sampler-settings.js
- js_src/eclipse-smart-sampler-settings-v2.js, js/eclipse-smart-sampler-settings-v2.js
- js_src/eclipse-replace-string-v3.js, js/eclipse-replace-string-v3.js
- js_src/eclipse-save-images-v2.js, js/eclipse-save-images-v2.js
- js_src/eclipse-prompt-styler.js, js/eclipse-prompt-styler.js
- js_src/eclipse-clip-loader.js, js/eclipse-clip-loader.js
- js_src/eclipse-sampler-overwrite.js, js/eclipse-sampler-overwrite.js
- js_src/eclipse-lora-stack.js, js/eclipse-lora-stack.js
- js_src/eclipse-image-comparer.js, js/eclipse-image-comparer.js
- __init__.py

---

### Version 3.1.29

- ✨ **feat:** new Set/Get context menu — "Eclipse: Add SetNode" / "Eclipse: Add GetNode" on all nodes
- ✨ **feat:** new "Eclipse: Convert all outputs to Set/Get" — creates 1 Set per output slot + 1 Get per connected target; reuses existing SetNode on source output; skips Set/Get nodes
- ✨ **feat:** new "Eclipse: Convert all inputs to Set/Get" — creates 1 Get per input slot + reuses shared Set when multiple inputs come from the same source output; skips Set/Get nodes
- ✨ **feat:** new "Eclipse: Convert all to Set/Get" — combined: converts all outputs + inputs in one click
- ✨ **feat:** new "Eclipse: Convert to links" — replace a Set+Get chain with direct links (available on Set and Get nodes)
- ✨ **feat:** new "Eclipse: Convert all to links" — finds all Set/Get nodes connected to a node (outputs→SetNodes, inputs→GetNodes) and converts them back to direct links
- ✨ **feat:** GetNode combo type filter — filters setter list by connected output's target type
- ✨ **feat:** GetNode resolveVirtualOutput warns on duplicate SetNode names in same scope
- ✨ **feat:** GetNode double-click navigation — jump to setter node
- ✨ **feat:** cross-pack name collision detection — checks both Eclipse and KJNodes setter types

- ✨ **feat:** AnyType audit — add JS type propagation to VRAM Cleanup, RAM Cleanup (setupAnyTypeHandling)
- ✨ **feat:** AnyType audit — add JS type propagation to IF A Else B, IF A Else B Fallback (dual-input sync)
- ✨ **feat:** AnyType audit — add JS type propagation to Show Any (input↔output slot sync)
- ✨ **feat:** AnyType audit — add multi-channel JS type propagation to Pipe 12CH/24CH/36CH Any

- ♻️ **refactor:** SetNode.update() now notifies all getter types (Eclipse GetNode, KJNodes GetNode, GetFirst, GetAllActive) directly
- ♻️ **refactor:** replace per-instance monkey-patch on KJNodes SetNode with one-shot prototype-level extension in setup()
- ♻️ **refactor:** move cross-pack notification logic from eclipse-getfirst.js setup() into eclipse-set-get.js
- ♻️ **refactor:** remove deferred setTimeout resolution (100ms/200ms) from Set/Get/GetFirst/GetAllActive — rely on LiteGraph serialized slot types
- ♻️ **refactor:** getLink compat shim — add graph._links fallback for older LiteGraph versions
- ♻️ **refactor:** GetFirst/GetAllActive — cache TTL (500ms) so green dot indicators refresh on mute/bypass changes

- 🧹 **chore:** move Set/Get/GetFirst/GetAllActive nodes from "Primitives" to new "Set-Get" category
- 🧹 **chore:** remove Set/Get auto-color feature — nodes use default category color; drop setget_auto_color config key and Eclipse.SetGetAutoColor setting
- 🧹 **chore:** Set/Get/GetFirst/GetAllActive nodes always render black (#000000)

**Changed files:**

- core/keys.py, core/server_endpoints.py, config.json
- js_src/eclipse-set-get.js, js_src/eclipse-set-get-utils.js
- js_src/eclipse-getfirst.js, js_src/eclipse-getallactive.js
- js_src/eclipse-ui-enhancements.js
- js_src/eclipse-cleanup-nodes.js (new), js_src/eclipse-ifelse.js (new), js_src/eclipse-pipe-any-type.js (new)
- js_src/eclipse-show-any.js
- js/eclipse-set-get.js, js/eclipse-set-get-utils.js
- js/eclipse-getfirst.js, js/eclipse-getallactive.js
- js/eclipse-ui-enhancements.js
- js/eclipse-cleanup-nodes.js (new), js/eclipse-ifelse.js (new), js/eclipse-pipe-any-type.js (new)
- js/eclipse-show-any.js

---

### Version 3.1.28

- ✨ **feat:** new Color Match node — transfer color grading from a reference image onto a target image. Target image is first input so bypass passes the correct image through. 9 methods: mkl, hm, reinhard, mvgd, hm-mvgd-hm, hm-mkl-hm (CPU/color-matcher), reinhard_lab_gpu (GPU/Kornia), wavelet (Haar wavelet LAB transfer — preserves detail), scattersort (exact per-channel histogram matching).
- ✨ **feat:** new Image Soften node — soften or sharpen an image. Positive strength softens, negative sharpens (unsharp mask). 6 methods: gaussian (uniform blur), bilateral (edge-preserving), wavelet (Haar frequency-band attenuation), median (noise removal), anisotropic (Perona-Malik diffusion), edge_blur (Sobel edge detection + selective Gaussian at hard edges only)

**Changed files:**

- py/RvImage_ColorMatch.py (new), py/RvImage_Soften.py (new)
- __init__.py

---

## 2026-04-09

### Version 3.1.27

- ✨ **feat:** new Resolution Scale node — multiply width/height by a factor, snap to divisible step (default 8)
- ✨ **feat:** new Int Passer, Float Passer, and String Passer router nodes — typed pass-through for fixed connections

**Changed files:**

- py/RvTools_ResolutionScale.py (new)
- py/RvRouter_Int_Passer.py (new), py/RvRouter_Float_Passer.py (new), py/RvRouter_String_Passer.py (new)
- __init__.py

---

## 2026-04-09

### Version 3.1.26

- 🐛 **fix:** Load Image / Load Image Pipe — infinite loop when selecting clipspace images; onDrawBackground bypassed imgs setter on every frame, falsely triggering MaskEditor-save detection → 300+ re-fetches

**Changed files:**

- js_src/eclipse-load-image.js, js/eclipse-load-image.js

---

### Version 3.1.25

- ✨ **feat:** new Mode Relay node — relays mode state (Mute/Bypass/Active) to overlapping group AND connected outputs; supports star topology (multiple Relays → Repeater) for cascading mute/bypass across groups

- 🐛 **fix:** Repeater — shared-Relay conflict resolution via `_eclipse_repeaterDriven` flag: Repeater-driven changes trigger force-back when active, manual/group changes use all-agree consensus, muted/bypassed Repeater is deaf to all input changes
- 🐛 **fix:** Model Loader / Smart Model Loader JS — add `lora_switch_N` callbacks so toggling switch immediately shows/hides name+weight widgets
- 🐛 **fix:** Lora Stack JS — add `switch_N` callbacks for immediate visibility update on toggle

**Changed files:**

- py/RvTools_ModeRelay.py (new)
- __init__.py
- js_src/eclipse-model-loader.js, js/eclipse-model-loader.js
- js_src/eclipse-smart-model-loader.js, js/eclipse-smart-model-loader.js
- js_src/eclipse-lora-stack.js, js/eclipse-lora-stack.js
- js_src/eclipse-mode-nodes.js, js/eclipse-mode-nodes.js
- __init__.py

---

### Version 3.1.24

- 🐛 **fix:** Model Loader / Smart Model Loader — LoRA applied regardless of on/off switch (`collect_lora_params` never checked `lora_switch_N`)
- 🐛 **fix:** Model Loader — add missing `lora_switch_N` boolean inputs to `get_model_loader_inputs()`
- 🐛 **fix:** Model Loader / Smart Model Loader JS — hide LoRA name+weight widgets when switch is OFF; add switch callbacks for immediate visibility update
- 🐛 **fix:** Lora Stack JS — hide LoRA name+weight+clip_weight widgets when switch is OFF; add switch callbacks for dynamic visibility
- 🐛 **fix:** Mute/Bypass Repeater — allow chaining repeaters (output → input of another repeater); upstream repeater mode changes always propagate regardless of input count

**Changed files:**

- core/model_loader_common.py
- js_src/eclipse-model-loader.js, js/eclipse-model-loader.js
- js_src/eclipse-smart-model-loader.js, js/eclipse-smart-model-loader.js
- js_src/eclipse-lora-stack.js, js/eclipse-lora-stack.js
- js_src/eclipse-mode-nodes.js, js/eclipse-mode-nodes.js

---

### Version 3.1.23

- ✨ **feat:** Load Image nodes — right-click preview context menu (Open Image, Save Image, Open in MaskEditor)
- ✨ **feat:** Load Image nodes — auto-refresh after MaskEditor save (detects clipspace output, selects new file)
- ✨ **feat:** Load Image From Folder nodes — "preview" chip toggle to show/hide DOM image preview
- ✨ **feat:** Load Image From Folder (Pipe) — added to DOM preview and canvas culling systems
- ✨ **feat:** Concat Pipe Multi — `tensor_size_mismatch` dropdown (match/crop/letterbox/ignore) for merging different-sized image tensors
- ✨ **feat:** DOM preview — grid mode default for multi-image output, dynamic column layout via ResizeObserver
- ✨ **feat:** DOM preview — double-click toggles grid/single mode (right-click now opens native context menu)

- 🐛 **fix:** DOM preview z-order — removed redundant z-index hook (culling system handles it globally)
- 🐛 **fix:** Save Images v2 — pipe image extraction looks for both "image" and "images" keys (fixes "no images data" error with Load Image pipe nodes)
- 🐛 **fix:** Save Images v2 — flatten 4D tensors in image list (fixes PIL "Cannot handle this data type" error from ConcatMulti list-mode output)
- 🐛 **fix:** Save Images (legacy) — same "image"/"images" dual-key fix
- 🐛 **fix:** Concat Pipe Multi — add "image" (singular) to `_TENSOR_KEYS` so merge mode concatenates image tensors from Load Image pipes instead of overwriting
- 🐛 **fix:** LoRA switch ignored — `collect_lora_params()` now checks `lora_switch_N` before applying LoRAs (affects Model Loader, Model Loader Pipe, Smart Model Loader)
- 🐛 **fix:** Model Loader — add missing `lora_switch_N` boolean inputs to `get_model_loader_inputs()`
- 🐛 **fix:** Model Loader / Smart Model Loader JS — hide LoRA name+weight widgets when switch is OFF

- 🧹 **chore:** move 30 deprecated nodes to `py/legacy/`, strip `Rv{Category}_` prefix from filenames (e.g. `legacy_SmartLoader.py`)
- 🧹 **chore:** rename active nodes — strip version suffixes (SmartFolder_v2→SmartFolder, SaveImages_v2→SaveImages, ReplaceStringV3→ReplaceString_Adv)
- 🧹 **chore:** BlockSwap — add obsolete-on-0.18+ note to node description

**Changed files:**

- js_src/eclipse-load-image.js, js/eclipse-load-image.js
- js_src/eclipse-load-image-folder.js, js/eclipse-load-image-folder.js
- js_src/eclipse-dom-preview.js, js/eclipse-dom-preview.js
- js_src/eclipse-dom-preview-nodes.js, js/eclipse-dom-preview-nodes.js
- js_src/eclipse-preview-culling.js, js/eclipse-preview-culling.js
- py/RvImage_SaveImages.py (renamed from _v2), py/RvFolder_SmartFolder.py (renamed from _v2), py/RvText_ReplaceString_Adv.py (renamed from V3)
- py/RvConversion_ConcatMulti.py, py/RvTools_BlockSwap.py
- core/model_loader_common.py
- js_src/eclipse-model-loader.js, js/eclipse-model-loader.js
- js_src/eclipse-smart-model-loader.js, js/eclipse-smart-model-loader.js
- py/legacy/legacy_SaveImages.py
- __init__.py
- py/legacy/ (30 files renamed + moved)

---

### Version 3.1.22

- ✨ **feat:** Load Image nodes — drag-and-drop + paste image upload support (no IMAGEUPLOAD widget dependency)
- ✨ **feat:** Load Image nodes — DOM-based image preview (replaces canvas-based node.imgs rendering)

- 🐛 **fix:** Load Image delete — allow deleting images from input subfolders (e.g. clipspace/filename.png)

**Changed files:**

- core/server_endpoints.py
- js_src/eclipse-load-image.js, js/eclipse-load-image.js

---

### Version 3.1.21

- ✨ **feat:** combo-chip tooltip support — options accept `{label, tooltip}` objects alongside plain strings, renders native browser tooltip on hover via `chip.title`

- 🐛 **fix:** Load Image nodes — input folder now lists images from subfolders (recursive walk), matching output folder behavior
- 🐛 **fix:** combo-chip floating panel viewport clamping — panel now stays within viewport bounds (shifts left if overflowing right edge, flips above trigger if overflowing bottom)

- ♻️ **refactor:** remove SmartLML node coloring from Eclipse.appearance — SML nodes now handle their own category-specific coloring independently

**Changed files:**

- py/RvImage_LoadImage.py, py/RvImage_LoadImage_Pipe.py
- core/server_endpoints.py
- js_src/eclipse-combo-chip.js, js/eclipse-combo-chip.js
- js_src/eclipse-ui-enhancements.js, js/eclipse-ui-enhancements.js

---

## 2026-04-05

### Version 3.1.20

- 🐛 **fix:** LATENT_TYPE_MAP — rename "Wan 2.2" → "Wan 2.2 TI2V" (only TI2V-5B uses the high-compression VAE; A14B models use Wan2.1 VAE)
- 🐛 **fix:** LATENT_TYPE_MAP — rename "SD3 / Flux / Wan 2.1 / HunyuanVideo" → "SD3 / Flux / Wan / HunyuanVideo" (covers both Wan 2.1 and Wan 2.2 A14B models)

**Changed files:**

- core/common.py, py/RvFolder_SmartFolder_v2.py

---

### Version 3.1.19

- ✨ **feat:** resolution presets — add all 7 Qwen-Image-2512 training buckets (1328², 928×1664, 1104×1472, 1056×1584 + landscape)
- ✨ **feat:** resolution presets — add 17 Flux 2 / Z-Image presets (×16 aligned, exact ratios): ~1 MP (9:16, 2:3, 3:4, 4:5 + landscape) and ~2 MP (same + 1:1 square)

- 🐛 **fix:** resolution presets — remove off-budget HiDream entries (832×1408, 896×1536 exceed 1.05 MP)

**Changed files:**

- core/common.py

---

### Version 3.1.18

- 🐛 **fix:** Smart Sampler Settings v2 — seed mode chips (random/increment/decrement) persisted in saved workflows alongside resolved concrete seeds, causing inconsistent state on reload (chip shows random but seed is fixed); on next Queue the stale chip could re-randomize the seed producing a different image

- ⚡ **perf:** GetFirst/GetAllActive bypass walk limited to 4 nodes depth to prevent overhead during serialization
- 🐛 **fix:** Smart Sampler Settings v2 — strip mode chips from workflow features at save time (preventive) and deselect them on configure when the seed is a concrete value (defensive)
- 🐛 **fix:** Smart Model Loader — same stale seed mode chip fix applied (strip from workflow features + deselect on configure)
- 🐛 **fix:** Load Image From Folder / Pipe — workflow saved special index mode (-1 random etc.) instead of resolved index, making image unreproducible on reload; now saves resolved index and deselects mode chips on configure

- 📚 **docs:** README documentation overhaul

**Changed files:**

- js_src/eclipse-smart-sampler-settings-v2.js, js/eclipse-smart-sampler-settings-v2.js
- js_src/eclipse-smart-model-loader.js, js/eclipse-smart-model-loader.js
- js_src/eclipse-load-image-folder.js, js/eclipse-load-image-folder.js
- README.md, Readme/README.md
- Readme/Smart_Loaders.md, Readme/Checkpoint_Loaders.md
- Readme/Save_Images.md, Readme/Replace_String_v3.md
- Readme/Load_Image_From_Folder.md, Readme/Smart_Prompt.md
- Readme/Smart_Folder_v2.md (new), Readme/Smart_Sampler_Settings_v2.md (new)
- Readme/GetFirst_GetAllActive.md (new)
- Readme/Utility_Nodes.md (new)
- js_src/eclipse-set-get-utils.js, js/eclipse-set-get-utils.js

---

## 2026-04-03

### Version 3.1.17

- 🧹 **chore:** Smart Prompt — remove redundant/wasteful tokens from prompt descriptor files (weird shapes, verbose phrasing)

**Changed files:**

- .defaults/.manifest.json + corresponding .example files

---

### Version 3.1.16

- 🐛 **fix:** Smart Model Loader — GGUF text encoders (.gguf CLIP files) failed with torch.load weights_only error; now routes through GGUF-specific clip loader with GGMLOps and GGUFModelPatcher
- 🐛 **fix:** CLIP Loader — same GGUF text encoder fix applied to standalone CLIP Loader node
- 🐛 **fix:** deprecated Smart Loaders (Basic/Basic v2/Plus/Plus v2/v1/v2) — same GGUF text encoder fix applied to all 6 deprecated loader variants

**Changed files:**

- core/gguf_wrapper.py, py/RvLoader_SmartModelLoader.py, py/RvLoader_ClipLoader.py
- py/deprecated/RvLoader_SmartLoader_Basic.py, py/deprecated/RvLoader_SmartLoader_Basic_v2.py
- py/deprecated/RvLoader_SmartLoader_Plus.py, py/deprecated/RvLoader_SmartLoader_Plus_v2.py
- py/deprecated/RvLoader_SmartLoader.py, py/deprecated/RvLoader_SmartLoader_v2.py

---

## 2026-04-02

### Version 3.1.15

- 🐛 **fix:** Nunchaku PuLID Apply — KeyError 'comfy_config' when model passed through LoRA Stack Apply (ctx_for_copy was dropped during wrapper re-creation)
- 🐛 **fix:** Nunchaku PuLID Apply — shape mismatch crash when model has LoRA with x_embedder modification (copy_with_ctx now preserves LoRA state to prevent stripping on shared transformer)
- 🐛 **fix:** Nunchaku PuLID + LoRA — load_state_dict strict=True crash from pulid_ca keys; temporarily detach PuLID cross-attention modules during LoRA update_lora_params and restore after
- 🐛 **fix:** copy_with_ctx — add defensive validation for required ctx_for_copy keys with actionable error message

**Changed files:**

- py/RvTools_LoraStack_Apply.py, extern/nunchaku/wrappers/flux.py

---

### Version 3.1.14

- ✨ **feat:** new CLIP Text Encode node — clone of standard CLIPTextEncode with text as forced input (connection only, no widget)
- ✨ **feat:** new Conditioning Zero Out node — zeros all conditioning tensors including pooled output, works with any model (DiT, Flux, SD3.5, SDXL)

- ✨ **feat:** Set/Get subgraph support — SetNode propagates down to descendant subgraphs, GetNode looks up through ancestor graphs
- ✨ **feat:** Set/Get resolveVirtualOutput — enables cross-subgraph execution on frontends that support it
- ✨ **feat:** Set/Get CrossGraphSetGet compat patch — monkey-patches graphToPrompt for older frontends without native resolveVirtualOutput
- ✨ **feat:** Set/Get improved paste coordination — _pasteRenameMap prevents name drift when pasting Set+Get pairs
- ✨ **feat:** Set/Get improved disconnect handling — keeps type when other side still connected
- ✨ **feat:** Set/Get getLink() compat shim — handles older frontends where graph.getLink() may not exist
- ✨ **feat:** GetFirst/GetAllActive subgraph-aware — findSetter and getSetterVars now search ancestor graphs

- 🐛 **fix:** Set/Get/GetFirst/GetAllActive type propagation on workflow load — deferred type resolution restores concrete types from setter links after LiteGraph finishes link restoration (previously showed * instead of correct type)

- ♻️ **refactor:** extract shared subgraph traversal into eclipse-set-get-utils.js (findSetterByName, getGraphAncestors, getGraphDescendants, getVisibleSetNames, isSetterActive, resolveBypassedLink, getLink)
- ♻️ **refactor:** Set/Get nodes use proper class methods instead of constructor-assigned functions

**Changed files:**

- js_src/eclipse-set-get-utils.js (new), js_src/eclipse-set-get.js, js_src/eclipse-getfirst.js, js_src/eclipse-getallactive.js
- js/eclipse-set-get-utils.js (new), js/eclipse-set-get.js, js/eclipse-getfirst.js, js/eclipse-getallactive.js
- py/RvText_CLIPTextEncode.py (new), py/RvText_ConditioningZeroOut.py (new), __init__.py

---

## 2026-04-01

### Version 3.1.13

- ✨ **feat:** new String DeDuplicate node — combines multiple strings and removes duplicates (case-insensitive, underscore-normalized), supports both tag and prose formats. dynamic input count (2–20) via inputcount widget, dedup_inputs toggle to deduplicate within each input before combining, weight_handling combo (None / Remove Weights / Normalize) with 1.4 cap, auto-expand bracket groups with commas into individual weighted tags, Normalize converts all bracket depths to explicit weight syntax for readability
- ✨ **feat:** new IF A Else B Fallback node — optional boolean input, unconnected or muted defaults to false path
- ✨ **feat:** GetAllActive — added PIPE to type filter and color map
- ✨ **feat:** Any Multi-Switch — updated description to mention returns first non-None input

- ♻️ **refactor:** rename RvRouter_IfExecute → RvRouter_IfElse (class RvSwitch_IfExecute → RvRouter_IfElse), node_id unchanged

- 🧹 **chore:** delete 5 V2 autogrow router/conversion nodes (ConcatMulti v2, Join v2, MergeStrings v2, MultiSwitch v2, MultiSwitch purge v2) — broken copy/paste with io.Autogrow

**Changed files:**

- py/RvText_DeDuplicate.py (new)
- py/RvRouter_IfElse.py (renamed from RvRouter_IfExecute.py)
- py/RvRouter_IfElse_Fallback.py (new)
- py/RvRouter_Any_MultiSwitch.py
- py/RvConversion_ConcatMulti_v2.py (deleted)
- py/RvConversion_Join_v2.py (deleted)
- py/RvConversion_MergeStrings_v2.py (deleted)
- py/RvRouter_Any_MultiSwitch_v2.py (deleted)
- py/RvRouter_Any_MultiSwitch_purge_v2.py (deleted)
- py/RvRouter_IfExecute.py (deleted), py/RvRouter_IfExecute_v2.py (deleted)
- js_src/eclipse-ui-enhancements.js, js/eclipse-ui-enhancements.js
- js_src/eclipse-getallactive.js, js/eclipse-getallactive.js
- js_src/eclipse-dynamic-inputs.js, js/eclipse-dynamic-inputs.js

---

## 2026-03-31

### Version 3.1.12

- 🐛 **fix:** IF A Else B — robust boolean handling when AnyType is connected to boolean input; now uses `is not None` instead of Python truthiness to avoid false negatives with valid falsy values (0, "", [])
- 🐛 **fix:** AnyType handler — guard against undefined source output slots during workflow configure; prevents crash when subgraph/dynamic nodes haven't been configured yet

**Changed files:**

- py/RvRouter_IfExecute.py
- js/eclipse-any-type-handler.js

---

### Version 3.1.11

- 🐛 **fix:** SetNode — clone/copy-paste now preserves widget value, slot types, and title instead of resetting to defaults; validateName still deduplicates on conflict
- 🐛 **fix:** smartResize — no longer changes node width; only height is adjusted when toggling widget visibility

**Changed files:**

- js_src/eclipse-set-get.js
- js_src/eclipse-widget-performance-utils.js

---

## 2026-03-30

### Version 3.1.10

- 🐛 **fix:** Smart Prompt v2 — comma-separated folders string not split, causing empty prompt output

**Changed files:**

- py/RvText_SmartPromptV2.py

---

### Version 3.1.9

- 🐛 **fix:** Smart Prompt — deduplicate prompt folders when both numbered and unnumbered versions exist (e.g. `01_subjects/` and `subjects/`)
- 🐛 **fix:** Smart Prompt — widget order now follows numeric folder prefix instead of alphabetical sort

- ✨ **feat:** migration to rename prompt folders to numbered format (`subjects/` → `01_subjects/`) for sorted display order
- ✨ **feat:** migration updates manifest keys to match renamed folders (preserves user edit tracking)

**Changed files:**

- py/RvText_SmartPrompt.py, py/RvText_SmartPromptV2.py
- core/migration.py
- .defaults/prompts/ (folders renamed to numbered format)
- .defaults/.manifest.json

---

### Version 3.1.8

- 🐛 **fix:** SetNode — clone() now properly resets widget value, slots, and title for fresh input; `validateName` deduplicates on user input (appends `_0`, `_1`…) and syncs title

**Changed files:**

- js_src/eclipse-set-get.js, js/eclipse-set-get.js

---

## 2026-03-29

### Version 3.1.7

- ✨ **feat:** new Smart Prompt v2 — combo-chip multi-folder selection, multiple folders visible simultaneously

- 🐛 **fix:** phantom input slots on socketless widgets in canvas mode
- 🐛 **fix:** combo-chip trigger bar disappears on Vue → Canvas mode switch

- ♻️ **refactor:** **BREAKING** — combo-chip multi-select switched from `io.Combo.Input` to `io.String.Input` across all nodes. Eliminates the dual-widget backing problem (hidden native widget + visible combo-chip) that caused widget value corruption during Canvas↔Vue mode switching and workflow loading. Features/folders now serialize as comma-separated strings. Old workflows with array-format features will NOT load correctly — re-add or right click and reload affected nodes to update.
- ♻️ **refactor:** combo-chip factory — removed `backingWidget` parameter, `onVueModeChange` backing toggle, `onSerialize` densification hook, `configure` backward-compat hook. Added default `serializeValue()` returning comma-separated string. `setValue()` now accepts both string and array input. Added internal `onVueModeChange` handler that toggles `computeLayoutSize` between Vue/Canvas modes (with cleanup in `onRemove`).
- ♻️ **refactor:** all 7 JS combo-chip callers converted from dual-path (Vue removes / Canvas hides) to single-path (always destroy native widget in both modes). Removed `_Eclipse_backingFeaturesW` / `_Eclipse_backingFoldersW` references and backing sync in callbacks.
- ♻️ **refactor:** removed `validate_inputs → True` from Smart Sampler Settings, Smart Sampler Settings v2, Replace String v3, Save Images v2 — no longer needed since `io.String.Input` passes normal validation. Kept on Smart Model Loader, Model Loader, Model Loader Pipe, Smart Prompt v2 (dynamic file/folder combos).

know issue: load image: when adding/reloading the node it shows an almost full screen preview of the image until the mouse leaves it (classic canvas renderer).

**Changed files:**

- py/RvText_SmartPromptV2.py, js_src/eclipse-smart-prompt-v2.js (new)
- core/model_loader_common.py (Combo→String — affects Model Loader + Model Loader Pipe)
- py/RvLoader_SmartModelLoader.py (Combo→String)
- py/RvSettings_SmartSamplerSettings.py (Combo→String, remove validate_inputs)
- py/RvSettings_SmartSamplerSettings_v2.py (Combo→String, remove validate_inputs)
- py/RvText_ReplaceStringV3.py (Combo→String, remove validate_inputs)
- py/RvImage_SaveImages_v2.py (Combo→String, remove validate_inputs)
- py/RvText_SmartPromptV2.py (Combo→String for folders)
- js_src/eclipse-combo-chip.js (factory refactor: remove backingWidget, hooks, add string serialization)
- js_src/eclipse-smart-model-loader.js (single-path, string serializeValue)
- js_src/eclipse-model-loader.js (single-path)
- js_src/eclipse-smart-sampler-settings.js (single-path)
- js_src/eclipse-smart-sampler-settings-v2.js (single-path, string serializeValue)
- js_src/eclipse-replace-string-v3.js (single-path)
- js_src/eclipse-save-images-v2.js (single-path)
- js_src/eclipse-smart-prompt-v2.js (single-path)
- js_src/eclipse-widget-performance-utils.js (removeSocketlessInputs + tooltip fix)
- js_src/eclipse-ui-enhancements.js (global socketlessFix hook)
- py/RvTools_ShowAny.py, py/RvImage_LoadImage.py, py/RvImage_LoadImage_Pipe.py (socketless)
- py/RvTools_LoraStack.py (socketless)
- py/RvImage_LoadImageFromFolder.py, py/RvImage_LoadImageFromFolder_Pipe.py (socketless)
- py/RvConversion_ConcatMulti.py, py/RvConversion_Join.py, py/RvConversion_MergeStrings.py (socketless)
- py/RvRouter_Any_MultiSwitch.py, py/RvRouter_Any_MultiSwitch_purge.py (socketless)
- js_src/eclipse-load-image.js, js_src/eclipse-prompt-styler.js
- js_src/eclipse-dynamic-inputs.js (remove converted-widget type override for inputcount)
- js_src/eclipse-dom-preview.js (add getMinHeight/getMaxHeight to widget options)

---

### Version 3.1.6

- 🐛 **fix:** Save Images v2 — add `validate_inputs` to bypass combo validation rejecting empty `features` list (`[]` not in options)

**Changed files:**

- py/RvImage_SaveImages_v2.py

---

### Version 3.1.5

- 🐛 **fix:** Save Images v2 — combo-chip feature toggles with `socketless=True` backing booleans (fixes connection bug where phantom input slots blocked wire connections)
- 🐛 **fix:** Save Images v2 — DOM preview respects `show_previews` chip (hidden when chip is off)
- 🐛 **fix:** `socketless=True` on chip-replaced widgets across all combo-chip nodes — prevents phantom input slots on Replace String v3, Smart Model Loader, Smart Sampler Settings v1+v2, Smart Folder v2
- 🐛 **fix:** widget visibility timing — remove `node.id === -1` guard and deferred `setTimeout` init pattern across all 11 JS files; call `updateVisibility()` synchronously in `onNodeCreated` so backing booleans and conditional widgets are hidden before first render
- 🐛 **fix:** `onConfigure` visibility — remove `setTimeout(100)` delays; apply visibility synchronously on workflow load

- 🧹 **chore:** move Set/Get/GetFirst/GetAllActive nodes to `🌒 Eclipse/ Primitives` category
- 🧹 **chore:** remove `[DEPR]` prefix from display_name of all 30 deprecated nodes

**Changed files:**

- py/RvImage_SaveImages_v2.py
- py/RvText_ReplaceStringV3.py, py/RvLoader_SmartModelLoader.py
- py/RvSettings_SmartSamplerSettings.py, py/RvSettings_SmartSamplerSettings_v2.py
- py/RvFolder_SmartFolder_v2.py
- py/deprecated/*.py (30 files — display_name cleanup)
- js_src/eclipse-save-images-v2.js (new)
- js_src/eclipse-set-get.js, js_src/eclipse-getfirst.js, js_src/eclipse-getallactive.js
- js_src/eclipse-replace-string-v3.js, js_src/eclipse-smart-folder-v2.js
- js_src/eclipse-smart-folder.js, js_src/eclipse-clip-loader.js
- js_src/eclipse-sampler-overwrite.js, js_src/eclipse-model-loader.js
- js_src/eclipse-smart-model-loader.js
- js_src/eclipse-image-resolution.js, js_src/eclipse-video-resolution.js
- js_src/eclipse-save-prompt.js

---

## 2026-03-28

### Version 3.1.4

- ✨ **feat:** new Set/Get tunnel nodes (JS-only virtual) — bypass-aware: values resolve through bypassed nodes (fixes KJNodes limitation where bypassed → SetNode silently fails)
- ✨ **feat:** new `setget_auto_color` config option (default: false) — auto-color Set/Get/GetFirst/GetAllActive nodes by data type, with Eclipse settings toggle
- ✨ **feat:** new Preview Image (DOM) [Eclipse] — DOM-based image preview variant with click-to-cycle, grid view, dimension labels
- ✨ **feat:** new DOM-based image previews — replaces canvas deferred rendering with DOM `<img>` widgets, eliminating image bleed-through behind overlapping nodes
- Converted nodes: Preview Mask, Save Images v2, Load Image From Folder, Load Image, Load Image Pipe, Show Any
- Click-to-cycle through multiple images, right-click toggles grid view
- Dimension label (e.g. 1497 × 2188) with semi-transparent background for readability
- Index indicator for multi-image nodes (e.g. 1 / 4)
- ✨ **feat:** new preview culling — suppresses image previews and DOM widgets when a node is fully covered by another node (z-order aware)
- ✨ **feat:** DOM z-index sync — fixes DOM widget bleed-through by synchronizing wrapper z-index to current visual z-order (selected nodes boosted)
- ✨ **feat:** Show Any — inline radio mode bar (show/hide) embedded in text widget, replacing native combo
- ✨ **feat:** Load Image From Folder — styled folder_path textarea to match Eclipse look
- ✨ **feat:** Load Image / Load Image Pipe — URL mode in mode bar: paste URL, download to input folder, auto-switch to input mode with preview

- ✨ **feat:** GetFirst/GetAllActive cross-compat — recognize both KJNodes SetNode and Eclipse SetNode [Eclipse] setter types
- ✨ **feat:** culling — added SEGSPreview and SEGS Preview [Eclipse] to canvas culling list, increased overlap margin to 50px

- 🐛 **fix:** GetFirst/GetAllActive `isSetterActive()` — walk past bypassed source nodes instead of treating them as inactive (setter with bypassed source is still active)
- 🐛 **fix:** refresh_list chip not deselecting after execution (was deleting wrong chip name)

- ♻️ **refactor:** Show Any — replace ComfyWidgets.STRING canvas text with DOM textarea (native text selection/copy, auto-sizing height)
- ♻️ **refactor:** Show Any — merge mode bar + textarea into single combined DOM widget (eliminates layout gap)
- ♻️ **refactor:** new shared DOM textarea helper (eclipse-dom-text.js) — value interception auto-syncs backing widget ↔ DOM, supports readOnly toggle
- ♻️ **refactor:** String Multiline, String Multiline List, String Dual — replace native canvas text with DOM textareas via eclipse-string-nodes.js
- ♻️ **refactor:** merge eclipse-load-image-folder.js + eclipse-load-image-folder-pipe.js into single config-driven file (NODE_CONFIGS pattern)

- ⚡ **perf:** culling throttled to ~1.5 Hz global scan on canvas.visible_nodes

**Changed files:**

- js_src/eclipse-set-get.js, js/eclipse-set-get.js (new)
- js_src/eclipse-dom-preview.js, js/eclipse-dom-preview.js (new)
- js_src/eclipse-dom-preview-nodes.js, js/eclipse-dom-preview-nodes.js (new)
- js_src/eclipse-dom-text.js, js/eclipse-dom-text.js (new)
- js_src/eclipse-string-nodes.js, js/eclipse-string-nodes.js (new)
- js_src/eclipse-preview-culling.js, js/eclipse-preview-culling.js (new)
- py/RvImage_Preview_Image_DOM.py (new)
- js_src/eclipse-show-any.js, js/eclipse-show-any.js
- js_src/eclipse-load-image.js, js/eclipse-load-image.js
- js_src/eclipse-load-image-folder.js, js/eclipse-load-image-folder.js (merged)
- js_src/eclipse-load-image-folder-pipe.js, js/eclipse-load-image-folder-pipe.js (deleted)
- js_src/eclipse-getfirst.js, js/eclipse-getfirst.js
- js_src/eclipse-getallactive.js, js/eclipse-getallactive.js
- js_src/eclipse-ui-enhancements.js, js/eclipse-ui-enhancements.js
- core/server_endpoints.py, config.json

---

### Version 3.1.3

- ✨ **feat:** new JS build/minification system
- ⚡ **perf:** minify all 47 JS files via rjsmin — 660KB → 357KB (46% reduction)

**Changed files:**

- js/*.js (minified)

---

## 2026-03-27

### Version 3.1.2

- ✨ **feat:** dynamic input nodes auto-grow on last-slot connect, auto-shrink on trailing disconnect (V1 nodes: MultiSwitch, MergeStrings, Join, ConcatMulti)
- ✨ **feat:** AnyType nodes enforce same-type connections — reject mismatched types on connect, propagate types after paste/load

- 🧹 **chore:** v2 Autogrow nodes (Any Multi-Switch v2, Any Multi-Switch Purge v2, Join v2, Merge Strings v2, Concat Pipe Multi v2) moved to _for_testing category
- 🧹 **chore:** Preview Image — remove Show_Images widget (always preview all images)
- 🧹 **chore:** hide inputcount widget on dynamic input nodes (auto-grow/shrink manages slot count)

- ♻️ **refactor:** rewrite eclipse-dynamic-inputs.js — slot colors resolved from LiteGraph type defaults (clear color_on/color_off overrides), link.type synced alongside link.color, output link colors propagated, setDirtyCanvas on all type changes

- 🐛 **fix:** duplicate extension registration error — eclipse-model-loader-pipe.js was a leftover duplicate of eclipse-model-loader.js which already handles both Model Loader and Model Loader Pipe

**Changed files:**

- js/eclipse-dynamic-inputs.js
- py/RvImage_Preview_Image.py
- js/eclipse-model-loader-pipe.js (deleted)

---

## 2026-03-25

### Version 3.1.1

- 🐛 **fix:** widget visibility broken on deprecated Smart Loaders — leftover v1 JS files (eclipse-smart-loader-basic.js, eclipse-smart-loader.js, eclipse-smart-loader-plus.js) conflicted with merged v2 files by registering duplicate extension names, causing onNodeCreated hooks to be overwritten

**Changed files:**

- js/eclipse-smart-loader-basic.js (deleted)
- js/eclipse-smart-loader.js (deleted)
- js/eclipse-smart-loader-plus.js (deleted)

---

### Version 3.1.0

Hard reset to v2.4.51 — versions 3.0.0 through 3.0.6 were published prematurely and are incomplete. This release rebuilds from the stable 2.4.51 base.

- ✨ **feat:** new Smart Model Loader — unified all-in-one loader with multi-select chip widget (templates/clip/vae/latent/sampler/lora/model_sampling/block_swap/memory_cleanup), template preservation across loads, seed feature with mode chips (random/increment/decrement), ♻️ Use Last Queued button
- ✨ **feat:** new Smart Sampler Settings — multi-select feature toggling and seed management
- ✨ **feat:** new Smart Sampler Settings v2 — dual-seed system with image_seed + prompt_seed, mode chips per seed with radio groups, ♻️ Use Last Queued buttons per seed
- ✨ **feat:** new Smart Folder v2 — combo-chip with radio-exclusive image/video + date_time/batch/image_size/seed toggles
- ✨ **feat:** new Model Loader + Model Loader Pipe — standalone loaders with multi-select chip widget (lora/model_sampling/block_swap/memory_cleanup)
- ✨ **feat:** new CLIP Loader and VAE Loader standalone nodes with Flux 2 auto-detection
- ✨ **feat:** new IO Checkpoint Loader — data-driven pipe IO with pass-through and overrides
- ✨ **feat:** new Save Images v2 — combo-chip toggles for all options, save/preview mode, embed_workflow in temp PNGs
- ✨ **feat:** new Pipe IO Sampler Settings v2.2 — image_seed + prompt_seed channels, backward compat with v2.1 pipes
- ✨ **feat:** new Load Image (Pipe) node — pipe-only output (image + mask + metadata), inline mode-bar, delete button, shared cache
- ✨ **feat:** new IO Load Image node — data-driven pipe IO with pass-through and overrides
- ✨ **feat:** new Load Image From Folder (Pipe) node — pipe-only output with execution preview, combo-chip toggles, metadata extraction

- ✨ **feat:** Preview Image node embeds workflow metadata in temp PNGs (drag-back support)
- ✨ **feat:** Load Image node — folder source inline mode-bar (input/output), two-combo architecture, 📁 Upload, 🔄 Refresh, delete button, shared global file list cache with cross-node synchronization
- ✨ **feat:** Load Image From Folder — execution preview, combo-chip toggles, index mode radio chips (🎲 random, ⏫ increment, ⏬ decrement, 🔀 shuffle), "Use Last Queued Index" button
- ✨ **feat:** v2 Autogrow nodes — Any Multi-Switch v2, Any Multi-Switch Purge v2, Join v2, Merge Strings v2, Concat Pipe Multi v2. Native V3 Autogrow + MatchType API (Requires latest ComfyUI/Frontend Version)
- ✨ **feat:** CustomVAE support — all Smart Loaders use CustomVAE for external VAE loading (Wan 2.1/2.2); Flux 2 uses standard comfy.sd.VAE
- ✨ **feat:** SLIDER_DISPLAY — configurable slider mode via "use_sliders" in config.json + UI toggle
- ✨ **feat:** Replace String v3 — replace 12 boolean toggles with multi-select chip widget, age widget visibility controlled by chip
- ✨ **feat:** latent_type combo preset in Smart Folder v2 — full list of model architectures (SD 1.5/SDXL, SD3/Flux, Flux 2, Wan 2.1/2.2, HunyuanVideo/1.5, HunyuanImage 2.1, LTXV, Mochi, etc.) sets correct channels + downscale for empty latent creation
- ✨ **feat:** Lora Stack — replace model_only_lora + simple booleans with inline mode-bar (standard / model_only / simple) — chips directly visible on node like Load Image, backward compat for old workflows

- 🐛 **fix:** Any Multi-Switch + Purge — skip empty strings, dicts, tuples, and lists as if disconnected
- 🐛 **fix:** Concat Pipe Multi — pipe_1 now optional so muted/disconnected first slot no longer causes validation error
- 🐛 **fix:** Nunchaku Qwen-Image loader — use getattr for scaled_fp8 to suppress "you accessed scaled_fp8 which doesn't exist" warning from ComfyUI model config
- 🐛 **fix:** custom pipe type renamed "pipe" → "PIPE" to match ComfyUI type convention
- 🐛 **fix:** Flux 2 latent sizing — detect spatial downscale ratio from VAE (16 for Flux 2 vs 8 for SD/SDXL), embed downscale_ratio_spacial in latent dict; IO Checkpoint Loader reads it back for correct pixel dimension derivation
- 🐛 **fix:** Pipe Out Smart Folder — use latent_channels/latent_downscale from pipe for correct empty latent creation, embed downscale_ratio_spacial
- 🐛 **fix:** combo-chip trigger bar inconsistent styling on reload — apply critical styles inline to avoid CSS cascade race with Vue DOMWidgetImpl
- 🐛 **fix:** BlockSwap — detect ComfyUI 0.18.0+ native dynamic VRAM (DynamicModelPatcher with backup_buffers) and skip offloading; keeps working on older ComfyUI versions
- 🐛 **fix:** BlockSwap — disable block_swap chip in UI when native dynamic VRAM detected; add disabledChips capability to combo-chip widget (grayed out, unclickable)

- ⚡ **perf:** Save Images v2 preview-only mode skips pipe metadata processing
- ⚡ **perf:** replace wildcard-processor 5-second global polling with refreshComboInNodes hook (R-key refresh)
- ⚡ **perf:** replace dynamic-inputs 200ms setInterval with direct widget callback hook — resize only on actual inputcount change
- ⚡ **perf:** add refreshComboInNodes hooks to all 15 loader/styler/folder JS extensions — press R to refresh file lists, no page reload needed
- ⚡ **perf:** Smart Loader Basic + Basic v2 — use shared fetchSharedModelFiles() with pending-fetch dedup and cache-busting
- ⚡ **perf:** Groups Muter/Bypasser — add graph._version + group fingerprint dirty-check to 500ms polling; skip recomputeInsideNodes and widget sync when graph is idle

- ♻️ **refactor:** centralize Smart Loader shared code into model_loader_common.py (~1900 lines removed)
- ♻️ **refactor:** extract shared fetchSharedModelFiles, fetchSharedTemplateList, broadcastTemplateListChanged into eclipse-loader-shared.js — imported by 10 loader JS files
- ♻️ **refactor:** merge deprecated Smart Loader Basic v1/v2 into single file (eclipse-smart-loader-basic-v2.js)
- ♻️ **refactor:** merge deprecated Smart Loader v1/v2 into single file (eclipse-smart-loader-v2.js)
- ♻️ **refactor:** merge deprecated Smart Loader Plus v1/v2 into single file (eclipse-smart-loader-plus-v2.js)
- ♻️ **refactor:** merge Model Loader + Model Loader Pipe into single file (eclipse-model-loader.js)
- ♻️ **refactor:** merge Load Image + Load Image Pipe into single file (eclipse-load-image.js)
- ♻️ **refactor:** CLIP Loader, Model Loader, Model Loader Pipe use shared fetchSharedModelFiles() instead of raw fetch
- ♻️ **refactor:** CustomVAE delegates to upstream comfy.sd.VAE for all non-Wan-2.1 architectures — adds Flux 2, LTXV, HunyuanVideo, Cosmos, audio VAE support
- ♻️ **refactor:** extract_image_metadata now omits empty/zero fields at source

- 🧹 **chore:** rename IO pipe node display_names to add "IO" prefix
- 🧹 **chore:** deprecate 30 legacy nodes — moved to py/deprecated/ with [DEPR] prefix, CATEGORY.DEPRECATED, is_deprecated=True

- 💥 **BREAKING:** Load Image node — removed pipe output and metadata extraction (use Load Image Pipe)
- 💥 **BREAKING:** Load Image From Folder — removed pipe output and extract_metadata option (use Pipe variant)

**Deprecated nodes:**

- Smart Loader v1 + v2, Smart Loader Basic v1 + v2, Smart Loader Plus v1 + v2 (6)
- 10 Sampler Settings variants (base/NI/Seed/NI+Seed/NI+Seed v2/NI+Seed v2.1/NI v2/Seed v2/Small/Small+Seed)
- Smart Folder v1, Save Images v1, Replace String v2
- Checkpoint Loader Small (+ Pipe), Pipe Out Checkpoint Loader
- Load Directory Settings, Pipe Out Load Directory Settings, Pipe Out Sampler Settings
- IO Sampler Settings v1/v2
- Pipe Out Load Image (Metadata Pipe), Load Image from Path (Metadata), Load Image from Path (Metadata Pipe)

**Changed files:**

- py/RvLoader_SmartModelLoader.py, js/eclipse-smart-model-loader.js (new)
- py/RvSettings_SmartSamplerSettings.py, js/eclipse-smart-sampler-settings.js (new)
- py/RvSettings_SmartSamplerSettings_v2.py, js/eclipse-smart-sampler-settings-v2.js (new)
- py/RvPipe_IO_Sampler_Settings_v22.py (new)
- py/RvFolder_SmartFolder_v2.py, js/eclipse-smart-folder-v2.js (new)
- py/RvLoader_ModelLoader.py, py/RvLoader_ModelLoaderPipe.py (new)
- js/eclipse-model-loader.js, js/eclipse-model-loader-pipe.js (new → merged into eclipse-model-loader.js)
- py/RvLoader_ClipLoader.py, py/RvLoader_VaeLoader.py (new)
- py/RvPipe_IO_CheckpointLoader.py (new)
- py/RvImage_SaveImages_v2.py, js/eclipse-save-images-v2.js (new)
- py/RvImage_Preview_Image.py
- py/RvImage_LoadImage.py, js/eclipse-load-image.js (merged with eclipse-load-image-pipe.js)
- py/RvImage_LoadImage_Pipe.py, js/eclipse-load-image-pipe.js (new → merged into eclipse-load-image.js)
- py/RvPipe_IO_LoadImage.py (new)
- py/RvImage_LoadImageFromFolder.py, js/eclipse-load-image-folder.js
- py/RvImage_LoadImageFromFolder_Pipe.py, js/eclipse-load-image-folder-pipe.js (new)
- py/RvRouter_Any_MultiSwitch.py, py/RvRouter_Any_MultiSwitch_purge.py
- py/RvRouter_Any_MultiSwitch_v2.py, py/RvRouter_Any_MultiSwitch_purge_v2.py (new)
- py/RvConversion_ConcatMulti.py
- py/RvConversion_Join_v2.py, RvConversion_MergeStrings_v2.py, RvConversion_ConcatMulti_v2.py (new)
- py/RvText_ReplaceStringV3.py, js/eclipse-replace-string-v3.js
- py/RvText_SavePrompt.py
- core/model_loader_common.py, core/wan_vae.py, core/common.py
- core/image_metadata.py, core/server_endpoints.py
- js/eclipse-combo-chip.js (new)
- js/eclipse-widget-performance-utils.js
- py/*.py, py/deprecated/*.py (54 files — io.Custom("pipe") → io.Custom("PIPE"))
- py/deprecated/*.py (30 nodes moved)
- core/model_loader_common.py (detect_latent_downscale)
- js/eclipse-mode-nodes.js (dirty-check optimization)
- core/nunchaku_wrapper.py (scaled_fp8 getattr fix)
- js/eclipse-smart-model-loader.js (seed preservation in template load/save)
- js/eclipse-loader-shared.js (new — shared fetch helpers)
- js/eclipse-smart-loader-basic.js (deleted — merged into basic-v2)
- js/eclipse-smart-loader.js (deleted — merged into v2)
- js/eclipse-smart-loader-plus.js (deleted — merged into plus-v2)
- js/eclipse-model-loader-pipe.js (deleted — merged into model-loader)
- js/eclipse-load-image-pipe.js (deleted — merged into load-image)
- js/eclipse-clip-loader.js (shared fetchSharedModelFiles)
- py/RvTools_LoraStack.py, js/eclipse-lora-stack.js (combo-chip mode bar)
- py/RvLoader_SmartModelLoader.py, py/RvPipe_IO_CheckpointLoader.py (Flux 2 latent fix)
- py/RvFolder_SmartFolder_v2.py, js/eclipse-smart-folder-v2.js (latent_type combo)
- py/RvPipe_Out_SmartFolder.py (latent_channels/latent_downscale from pipe)
- core/common.py (LATENT_TYPE_PRESETS, LATENT_TYPE_MAP)
- js/eclipse-combo-chip.js (inline trigger styles, DOM-based CSS injection check)
- js/eclipse-wildcard-processor.js, js/eclipse-dynamic-inputs.js (polling → event-driven)
- js/eclipse-smart-loader-basic.js, js/eclipse-smart-loader-basic-v2.js (fetchSharedModelFiles)
- js/eclipse-model-loader.js, js/eclipse-model-loader-pipe.js, js/eclipse-clip-loader.js (refreshComboInNodes)
- js/eclipse-smart-model-loader.js, js/eclipse-smart-loader.js, js/eclipse-smart-loader-v2.js (refreshComboInNodes)
- js/eclipse-smart-loader-plus.js, js/eclipse-smart-loader-plus-v2.js (refreshComboInNodes)
- js/eclipse-load-image-folder.js, js/eclipse-load-image-folder-pipe.js (refreshComboInNodes)
- js/eclipse-prompt-styler.js, js/eclipse-read-prompt-files.js (refreshComboInNodes)

---

## 2026-03-18

### Version 2.4.51

- 🐛 **fix:** graceful fallback when nunchaku package is unavailable — no longer crashes entire extension

**Changed files:**

- __init__.py

---

## 2026-03-17

### Version 2.4.50

- ✨ **feat:** add SEGS Preview node (from impact) with crop padding & additional image output
- 🐛 **fix:** DetectionToBboxes now handles coord_range denormalization for Qwen detection data

**Changed files:**

- py/RvImage_SEGSPreview.py (new), __init__.py, py/RvConversion_DetectionToBboxes.py

---

### Version 2.4.49

upd: face_desc, eyes_desc
- 🐛 **fix:** sync 05_Pose_desc.txt to .defaults/ and update manifest hash

**Changed files:**

- .defaults/prompts/subjects_desc/10_Face_desc.txt.example, .defaults/prompts/subjects_desc/11_Eyes_desc.txt.example, .defaults/prompts/subjects_desc/05_Pose_desc.txt.example, .defaults/.manifest.json

---

### Version 2.4.48

- ✨ **feat:** add emotional tears variants — 4 sad entries with eyebrow detail (knitted/pinched/scrunched brows + heavy tears), 3 calm quiet-crying entries (silent tears, reflective gaze, single tear), 2 angry tears entries (frustrated hot tears, rage-filled tears)

**Changed files:**

- .defaults/prompts/subjects_desc/10_Face_desc.txt.example, .defaults/.manifest.json

---

### Version 2.4.47

- ✨ **feat:** rewrite face descriptions — 231 T5-friendly entries with emotion-context prefixes, organized by 17 categories with blank-line separators for readability

**Changed files:**

- prompts/subjects_desc/10_Face_desc.txt
- .defaults/prompts/subjects_desc/10_Face_desc.txt.example, .defaults/.manifest.json

---

### Version 2.4.46

- ✨ **feat:** expand face descriptions — add 17 new entries (5 happy: beaming, carefree, cheerful, giggling, warm contented; 5 love: affectionate, devoted, passionate, romantic, smitten; 7 seductive: alluring, bedroom eyes, come-hither, coy, flirtatious, inviting, sultry); reorder all 237 entries by category (happy → love → seductive → playful → calm → determined → embarrassment → sad → fear → anger → combat → pain → unstable → blush → features → actions → stylized)
- 🐛 **fix:** deduplicate shot style descriptions — remove 19 near-identical entries (aerial view, angle from above/below, birds-eye view, body shot, close-up portrait/shot, face close-up, first-person view, from above/below, from behind diagonal view, full shot, medium close-up shot, overhead angle, panoramic landscape, telephoto shot, Waist Shot, wide angle)

**Changed files:**

- prompts/subjects_desc/10_Face_desc.txt
- .defaults/prompts/settings_desc/01_Shotstyle_desc.txt.example, .defaults/.manifest.json

---

### Version 2.4.45

- 🐛 **fix:** branch execution — remove is_output_node from VRAM Cleanup and RAM Cleanup nodes

**Changed files:**

- py/RvTools_VRAMCleanUp.py, py/RvTools_RAMCleanup.py

---

### Version 2.4.44

- 🐛 **fix:** branch execution — remove is_output_node from Seed nodes; remove not_idempotent from VCNameGen nodes; replace not_idempotent with fingerprint_inputs in video clip nodes

**Changed files:**

- py/RvLogic_Seed.py, py/RvLogic_Seed_32bit.py
- py/RvSettings_VCNameGen_v1.py, py/RvSettings_VCNameGen_v2.py
- py/RvTools_VideoClips_SeamlessJoin.py, py/RvTools_VideoClips_Combine.py

---

### Version 2.4.43

- ✨ **feat:** Sampler Settings NI+Seed v2.1, Sampler Settings+Seed v2, Sampler Settings NI v2, and Pipe IO Sampler Settings v2.1 — adds upscale_steps, upscale_denoise, upscale_value; renames denoise_upscale to upscale_denoise; reorders upscale fields (upscale_steps, upscale_denoise, upscale_value)

- ✨ **feat:** allow_overwrite toggle hides sampler_name, scheduler, steps, cfg widgets on all Sampler Settings nodes

**Changed files:**

- py/RvSettings_Sampler_Settings_NI_Seed_v21.py (new)
- py/RvSettings_Sampler_Settings_Seed_v2.py (new)
- py/RvSettings_Sampler_Settings_NI_v2.py (new)
- py/RvPipe_IO_Sampler_Settings_v21.py (new)
- js/eclipse-sampler-overwrite.js (new)
- js/eclipse-seed-v2.js
- py/RvPipe_IO_Sampler_Settings.py, py/RvPipe_IO_Sampler_Settings_v2.py
- __init__.py

---

## 2026-03-15

### Version 2.4.42

- ✨ **feat:** expand clothing prompts — add 42 new outfit tags (profession: nurse, doctor, chef, firefighter, pilot, etc.; cosplay: batman, spiderman, catwoman, harley quinn, wonder woman; fantasy: gladiator, samurai, viking, ninja, pirate, witch; other: catsuit, cheerleader, maid, nun); restructure underwear as sets with color/action/sheer variants (black/white/red/pink lingerie set, lace lingerie set, sheer lingerie, sheer babydoll, sheer negligee, lingerie lift, lingerie under clothes); move individual pieces to correct files (bra/lace bra/sports bra → Upper Body, lace thong → Lower Body)

- ✨ **feat:** clean up shot style prompts — remove 6 duplicate entries (rear angle, shot from behind, shot from side, side profile, side view shot, sideways); add 18 new entries using T5-friendly phrasing: 15 directional angle combinations (front view, from the front diagonal view, from behind diagonal view, from above/below with front/shown from behind/side/diagonal variants, from behind over the shoulder) + 3 from research (foreground obstruction, reflection shot, worm's-eye view)

**Changed files:**

- prompts/subjects/15_Clothing.txt, prompts/subjects_desc/15_Clothing_desc.txt
- prompts/subjects/16_Upper_Body_Decoration.txt, prompts/subjects_desc/16_Upper_Body_Decoration_desc.txt
- prompts/subjects/17_Lower_Body_Decoration.txt, prompts/subjects_desc/17_Lower_Body_Decoration_desc.txt
- prompts/settings/01_Shotstyle.txt, prompts/settings_desc/01_Shotstyle_desc.txt
- .defaults/prompts/ *.example files, .defaults/.manifest.json

---

### Version 2.4.41

- ♻️ **refactor:** move eye-only entries from Face prompts to Eyes prompts — 27 unique descs added to 11_Eyes_desc, 36 removed from 10_Face_desc (9 were duplicates); 33 unique tags added to 11_Eyes, 45 removed from 10_Face (12 were duplicates); update manifest hashes

**Changed files:**

- .defaults/prompts/subjects/10_Face.txt.example, .defaults/prompts/subjects/11_Eyes.txt.example
- .defaults/prompts/subjects_desc/10_Face_desc.txt.example, .defaults/prompts/subjects_desc/11_Eyes_desc.txt.example
- .defaults/.manifest.json

---

## 2026-03-14

### Version 2.4.40

- ✨ **feat:** add ethereal creature energy forms to 11_Magic_Elements — body-anchored energy (fist wrap, body spiral, ember scatter, dragon coil, phoenix blaze), creature auras (ethereal dragon/phoenix, spirit beasts), combination tags (phoenix+dragon wrap, dragon+ember, phoenix+arm energy), rewrite all creature descs for body-integrated energy flow (16 new tags, 11 new descs)

**Changed files:**

- .defaults/prompts/settings/11_Magic_Elements.txt.example, .defaults/prompts/settings_desc/11_Magic_Elements_desc.txt.example

---

### Version 2.4.38

- ♻️ **refactor:** rewrite 10_Face descriptions with unique visual T5-focused format, broader emotional range, combat/defense expressions, eliminate near-duplicates (200 → 256 entries)
- ✨ **feat:** expand environment prompts — add 28 indoor combat/lost-place locations (boxing ring, dojo, octagon, catacombs, etc.), 21 outdoor fighting/terrain locations (battleground, warzone, junkyard, swamp, etc.), 38 background color and atmospheric variations
- 🐛 **fix:** remove 14 wrongly-named .example files (missing .txt extension) from .defaults/prompts/environment*

**Changed files:**

- .defaults/prompts/subjects/10_Face.txt.example, .defaults/prompts/subjects_desc/10_Face_desc.txt.example
- .defaults/prompts/environment/02_Indoor.txt.example, .defaults/prompts/environment_desc/02_Indoor_desc.txt.example
- .defaults/prompts/environment/03_Outdoor.txt.example, .defaults/prompts/environment_desc/03_Outdoor_desc.txt.example
- .defaults/prompts/environment/07_Background.txt.example, .defaults/prompts/environment_desc/07_Background_desc.txt.example

---

### Version 2.4.37

- ♻️ **refactor:** rewrite 05_Pose descriptions with visual T5-focused format, add 23 combat stance variants (archer, assassin, knight, boxing, martial arts, etc.)

**Changed files:**

- .defaults/prompts/subjects/05_Pose.txt.example, .defaults/prompts/subjects_desc/05_Pose_desc.txt.example

---

### Version 2.4.36

- ✨ **feat:** add 03_Age (12 entries) and 04_Ethnicity (32 entries) subject prompt categories — age uses named ranges from young child to elderly, ethnicity descs focus on facial structure and eye shape (no hair/skin)
- ♻️ **refactor:** renumber subject prompt files 03-18 → 05-20 to accommodate new categories, migration auto-renames existing user files on startup

**Changed files:**

- .defaults/prompts/subjects/03_Ethnicity.txt.example (new), .defaults/prompts/subjects_desc/03_Ethnicity_desc.txt.example (new)
- .defaults/prompts/subjects/04_Age.txt.example (new), .defaults/prompts/subjects_desc/04_Age_desc.txt.example (new)
- .defaults/prompts/subjects/*.example: all files 03-18 renumbered to 05-20
- .defaults/prompts/subjects_desc/*.example: all files 03-18 renumbered to 05-20
- core/migration.py (added _migrate_subject_numbering)

---

### Version 2.4.35

- ♻️ **refactor:** massive overhaul of all prompt files (subjects, settings, environment) — removed duplicates, fixed typos, cleaned non-category entries, added missing entries, sorted alphabetically, rewrote all descriptions with visual-focused format for better T5 encoder output
- ✨ **feat:** smart .example file updates — hash-based manifest tracks extracted versions; auto-updates unmodified user files on pull while preserving user-edited files
- ✨ **feat:** add reset_prompts.sh (Linux) and reset_prompts.bat (Windows) scripts for manual force-extraction of prompt files

---

### Version 2.4.34

- ✨ **feat:** Image Comparer node now outputs the image (image_b if available, else image_a)
- ♻️ **refactor:** RAM Cleanup node is now Windows-only, removed all Linux/macOS code paths

**Changed files:**

- py/RvImage_ImageComparer.py
- py/RvTools_RAMCleanup.py
- scripts/setup_cache_clearing.sh (deleted)

シ

---

### Version 2.4.33

- 🐛 **fix:** Use 2^64-1 seed range in SmartPrompt and WildcardProcessor to match all other seed nodes

**Changed files:**

- py/RvText_SmartPrompt.py, py/RvText_WildcardProcessor.py
- js/eclipse-smart-prompt.js, js/eclipse-wildcard-processor.js

---

### Version 2.4.32

- ♻️ **refactor:** Rename RvPrimitive_Seed to RvLogic_Seed, use 2^64-1 seed range matching KSampler
- ✨ **feat:** Add Seed 32-bit [Eclipse] node — clamped 2^32-1 range for LLM/text backends
- 🐛 **fix:** Sampler settings nodes use 2^64-1 range matching KSampler (reverts 2.4.31 restriction)

**Changed files:**

- py/RvLogic_Seed.py (renamed from py/RvPrimitive_Seed.py, range 2^64-1)
- py/RvLogic_Seed_32bit.py (new, range 2^32-1 + clamp)
- py/RvSettings_Sampler_Settings_Seed.py, py/RvSettings_Sampler_Settings_NI_Seed.py, py/RvSettings_Sampler_Settings_NI_Seed_v2.py, py/RvSettings_Sampler_Settings_Small_Seed.py
- js/eclipse-seed.js, js/eclipse-seed-v2.js
- __init__.py

---

### Version 2.4.31

- 🐛 **fix:** Standardize seed range to 0 - 2^32-1 across all nodes and JS frontends — replaces inconsistent old values (1125899906842624, 2^64-1) with uniform 2^32-1 max

**Changed files:**

- py/RvPrimitive_Seed.py, py/RvSettings_Sampler_Settings_Seed.py, py/RvSettings_Sampler_Settings_NI_Seed.py, py/RvSettings_Sampler_Settings_NI_Seed_v2.py, py/RvSettings_Sampler_Settings_Small_Seed.py, py/RvText_SmartPrompt.py, py/RvText_WildcardProcessor.py
- js/eclipse-seed.js, js/eclipse-seed-v2.js, js/eclipse-smart-prompt.js, js/eclipse-wildcard-processor.js

---

## 2026-03-12

### Version 2.4.30

- 🐛 **fix:** SaveImages clip_skip metadata leaking stale values from previous runs — set_global_values now resets fields to empty on None instead of skipping, preventing module-level global state from persisting across executions; also fix remove_prompts branch always writing Clip skip regardless of value

**Changed files:**

- py/RvImage_SaveImages.py

---

## 2026-03-11

### Version 2.4.29

- 🐛 **fix:** seed freeze resolves actual seed from graph instead of unresolved prompt data — graphToPrompt execution order meant LoadImageFromFolder/ReadPromptFiles saw raw -1/-2/-3 before eclipse-seed.js resolved them; now follows graph links to source Seed node and calls getSeedToUse() directly; supports KJNodes virtual Set/Get nodes via getInputLink(), reroute nodes, and non-Eclipse seed widgets
- ✨ **feat:** add Pipe 24CH Any node — 24-channel version of Pipe 12CH Any for workflows needing more slots
- ✨ **feat:** add Pipe 36CH Any node — 36-channel version
- ♻️ **refactor:** Pipe 12CH Any — use loop-based pattern for channel definitions

**Changed files:**

- js/eclipse-load-image-folder.js (replace _resolvePromptValue with _getResolvedSeedFromGraph)
- js/eclipse-read-prompt-files.js (replace _resolvePromptValue with _getResolvedSeedFromGraph)
- py/RvPipe_IO_12CH_Any.py (refactor to loop-based)
- py/RvPipe_IO_24CH_Any.py (new)
- py/RvPipe_IO_36CH_Any.py (new)
- __init__.py

---

### Version 2.4.28

- 🐛 **fix:** seed_input causing unnecessary re-execution — button widgets with dynamic names leaked into prompt data, invalidating ComfyUI's cache between runs; also strip seed_input link from prompt since it's consumed by JS only

**Changed files:**

- js/eclipse-load-image-folder.js (strip button widgets + seed_input from prompt data)
- js/eclipse-read-prompt-files.js (strip seed_input from prompt data)

---

## 2026-03-10

### Version 2.4.27

- ✨ **feat:** Load Image (Metadata Pipe) — 🗑️ Delete Image button removes selected image from input folder

**Changed files:**

- core/server_endpoints.py (LoadImageEndpoints class + /eclipse/load_image/delete and /list endpoints)
- js/eclipse-load-image.js (new)

---

### Version 2.4.26

- ✨ **feat:** New None primitive node — outputs None as AnyType for use as explicit empty input
- ✨ **feat:** New Generation Data (Gated) pipe node — boolean gates per field for controlled pass-through, designed for FastMuter + NodeModeRepeater control
- ✨ **feat:** Smart Loader+ pipes now carry configure_sampler state; Pipe Out Checkpoint Loader exposes it as boolean output
- ✨ **feat:** Load Image From Folder gains seed_input — freeze current index until connected seed changes (same as Read Prompt Files)

**Changed files:**

- py/RvLogic_None.py (new), py/RvPipe_IO_Generation_Data_Gated.py (new), __init__.py
- py/RvLoader_SmartLoader_Plus.py, py/RvLoader_SmartLoader_Plus_v2.py, py/RvPipe_Out_CheckpointLoader.py
- py/RvImage_LoadImageFromFolder.py, js/eclipse-load-image-folder.js

---

## 2026-03-09

### Version 2.4.25

- 🐛 **fix:** Detection to Bboxes crashes when bbox has x1 > x2

**Changed files:**

- py/RvConversion_DetectionToBboxes.py

---

## 2026-03-08

### Version 2.4.24

- 🐛 **fix:** LoRA Stack Apply passes CLIP through unchanged in model_only_lora mode

Previously, even when clip_strength was None (model-only LoRA), the CLIP
object was still passed through load_lora_for_models with strength 0,
which could wrap/modify it. Now passes None for clip so it remains untouched.

**Changed files:**

- py/RvTools_LoraStack_Apply.py

---

## 2026-03-06

### Version 2.4.23

- ✨ **feat:** categorized title colors for Eclipse node appearance

Node title bars now use category-specific colors instead of uniform gray.
Categories: loader (steel blue), text/prompt (forest green), image (plum),
settings (amber), pipe (teal), router/logic (burnt orange), video (slate blue),
folder (dark rose), tools (gray default). Also detects [SmartLML] nodes.

- 🐛 **fix:** halve BlockSwap default and add per-architecture block count tooltips

Default blocks_to_swap reduced from 20 to 10 — swapping 20 blocks left only
50-58% VRAM used on most GPUs. Tooltips now show suggested values and max
block counts per architecture (e.g. flux/chroma ~10 max 57, wan ~10 max 30-40).
Added HiDream block detection (double_stream_blocks + single_stream_blocks).

**Changed files:**

- py/RvTools_BlockSwap.py, py/RvLoader_SmartLoader_v2.py
- py/RvLoader_SmartLoader_Plus_v2.py, py/RvLoader_SmartLoader_Basic_v2.py
- js/eclipse-smart-loader-v2.js, js/eclipse-smart-loader-plus-v2.js
- templates/*.json, .defaults/templates/*.json.example

---

### Version 2.4.22

- ✨ **feat:** Smart Loader v2 nodes with integrated BlockSwap
New v2 variants of Smart Loader, Smart Loader Plus, and Smart Loader Basic
with built-in configure_blockswap toggle. When enabled, shows blocks_to_swap
and offload_embeddings widgets. Uses ON_LOAD callback from BlockSwap node
to offload transformer blocks to CPU for VRAM savings.
Removed model_device, clip_device, vae_device widgets from v2 nodes —
BlockSwap handles VRAM offloading, making manual device selection redundant.
BlockSwap settings (configure_blockswap, blocks_to_swap, offload_embeddings)
are saved/loaded with loader templates in Smart Loader v2 and Smart Loader Plus v2.
BlockSwap widgets are hidden for Nunchaku model types (Flux/Qwen/ZImage) which
have their own CPU offloading system.
Original v1 loader nodes remain unchanged for backward compatibility.

**Changed files:**

- py/RvLoader_SmartLoader_v2.py (new — copied from v1, added BlockSwap integration)
- py/RvLoader_SmartLoader_Plus_v2.py (new — copied from v1, added BlockSwap integration)
- py/RvLoader_SmartLoader_Basic_v2.py (new — copied from v1, added BlockSwap integration)
- js/eclipse-smart-loader-v2.js (new — NODE_NAME/ext v2, configure_blockswap visibility)
- js/eclipse-smart-loader-plus-v2.js (new — NODE_NAME/ext v2, configure_blockswap visibility)
- js/eclipse-smart-loader-basic-v2.js (new — NODE_NAME/ext v2, configure_blockswap visibility)
- __init__.py (register v2 node classes)
- templates/*.json, .defaults/templates/*.json.example (added blockswap fields, default off)

---

### Version 2.4.21

- ✨ **feat:** Smart Loader template matching — filename-only suffix fallback
When an exact model path from a template doesn't match the widget dropdown
(e.g. subfolder moved or stripped), falls back to matching by filename only.
Applied to setter, model-file refresh, and visibility refresh in both loaders.
Default templates already have subfolder prefixes stripped.

**Changed files:**

- js/eclipse-smart-loader.js, js/eclipse-smart-loader-plus.js

---

### Version 2.4.20

- ✨ **feat:** Universal Block Swap node — offloads transformer blocks to CPU for VRAM savings

Supports WAN, Flux, Chroma, SD3, LTXV, HunyuanVideo, Cosmos, ZImage/NextDiT, QwenImage.
Uses ComfyUI's ON_LOAD callback (non-invasive, works alongside LoRA/hooks).
Auto-detects architecture and block count. Optional embedding offloading.
Leverages ComfyUI's native comfy_cast_weights lowvram system — each operation
temporarily casts its weight to GPU, runs, then releases. No forward hooks or
block-level .to() calls during inference (avoids CUDA async stream conflicts).
Updates model_loaded_weight_memory so ComfyUI's memory manager knows the true GPU
footprint (prevents OOM when loading controlnets/other models alongside).
Uses model_patcher.pin_weight_to_device() for tracked pinning — prevents stale
cudaHostRegister entries and CUDA errors when switching models.
Duplicate callback guard skips re-offloading if blocks are already on CPU.
Cleanup handled automatically by ComfyUI's unpatch_model()/wipe_lowvram_weight().

**Changed files:**

- py/RvTools_BlockSwap.py (new)
- __init__.py
- core/keys.py

---

## 2026-03-05

### Version 2.4.19

- 🐛 **fix:** Fast Muter/Bypasser/Repeater now propagates mode to inner nodes of subgraph/component nodes

Uses isSubgraphNode() + recursive traversal via subgraph._nodes/subgraph.nodes to match
ComfyUI's own toggleSelectedNodesMode implementation.

- 🐛 **fix:** Fast Bypasser/Muter losing connections to Node Collector on page reload

_eclipse_onChainChange ran stabilize immediately during loading, which could cancel the
deferred 300ms timer and run before all graph links were committed. Now respects
_eclipse_loading/_eclipse_configuring flags and defers via scheduleStabilize during load.

**Changed files:**

- js/eclipse-mode-nodes.js

---

## 2026-03-04

### Version 2.4.18 (published)

- ✨ **feat:** Dynamic node title for GetFirst/GetAllActive based on type filter
- ✨ **feat:** Var combo dropdowns exclude already-assigned vars from other slots
- 🐛 **fix:** Type filter now strict — SetNodes with unresolved type '*' no longer pass through all filters

**Changed files:**

- js/eclipse-getfirst.js, js/eclipse-getallactive.js

---

### Version 2.4.17 (published)

- 🐛 **fix:** Restore Linux file cache clearing in RAM Cleanup node

Re-added _check_sudo_available() and _clear_file_cache_linux() functions.
Restored Linux branch in execute() for file cache clearing via secure wrapper.
All widgets visible on all platforms; no-op options are skipped in Python with tooltips explaining.

Security hardening (addresses community feedback):
- Replaced direct `sudo tee /proc/sys/vm/drop_caches` with a root-owned wrapper script
(/usr/local/bin/comfyui-drop-pagecache) that hardcodes value 1 — value 3 is impossible
- Sudoers rule now ONLY permits the wrapper, not arbitrary tee calls
- Added memory pressure heuristic: cache drop only fires when >91% used or <2GB available
- Linux cache drop capped to first attempt only (repeated drops are no-ops)
- retry_times forced to 1 on non-Windows (retries have no effect)
- All widgets visible on all platforms with platform-specific tooltips
- Removed eclipse-ram-cleanup.js and /eclipse/system_info endpoint (no longer needed)
- setup_cache_clearing.sh rewritten to install wrapper + locked-down sudoers

**Changed files:**

- py/RvTools_RAMCleanup.py, core/server_endpoints.py
- js/eclipse-ram-cleanup.js (deleted)
- scripts/setup_cache_clearing.sh (rewritten, moved from root), scripts/remove_cache_clearing.sh

---

### Version 2.4.16

- ✨ **feat:** Increase GetFirst and GetAllActive max var slots from 10 to 20

**Changed files:**

- js/eclipse-getfirst.js, js/eclipse-getallactive.js

- 🐛 **fix:** Any Passer crashes when moved into a subgraph

onConnectionsChange fires before origin node exists in the subgraph.
Added null check for getNodeById result.

- 🐛 **fix:** ReplaceStringV3 leaves "The image is a" prefix and orphaned "of" after shot style removal

- image_styles.json: added "is a", "is an", "is of" to image_verbs so the_medium_verb
preset matches "The image is a ..." as a removable prefix
- shot_styles.json: added [prepositions?] to core_term_suffix, hyphenated_suffix,
hyphenated_with_suffix, direction_suffix, standalone_core so "close-up of" is
consumed as a unit instead of leaving orphaned "of"
- shot_styles.json: added core_medium_prep preset (priority 80) to match
"close-up illustration of", "overhead image of" etc. without requiring an article

**Changed files:**

- js/eclipse-any-type-handler.js
- patterns/image_styles.json
- patterns/shot_styles.json

---

### Version 2.4.15

- 🐛 **fix:** Delete Template button broken in Smart Loader and Smart Loader+

Variable shadowing bug: local boolean variable `C` inside the visibility
function shadowed the outer `C` (delete handler). The button callback
received a boolean instead of the delete function. Renamed local vars
to avoid collision.

**Changed files:**

- js/eclipse-smart-loader-plus.js (C → W for vae external check)
- js/eclipse-smart-loader.js (C → W for LCM check)

---

### Version 2.4.14

- ✨ **feat:** Sampler Settings NI+Seed v2 and Pipe IO Sampler Settings v2

New node variants with additional denoise_upscale parameter for upscale pass denoise control. IO Pipe v2 carries the new channel without breaking existing v1 pipe outputs.

**Changed files:**

py/RvSettings_Sampler_Settings_NI_Seed_v2.py (new)

py/RvPipe_IO_Sampler_Settings_v2.py (new)

js/eclipse-seed-v2.js (new, compact seed handler without Randomize button)

init.py (registration)

- 🧹 **chore:** remove dead template_sync setting

The template_sync config toggle was never consumed by any code — migration runs unconditionally. Removed the UI setting, server endpoint references, and validation.

**Changed files:**

js/eclipse-ui-enhancements.js (Eclipse.TemplateSync extension block)

core/server_endpoints.py (config/all, config/update)

---

### Version 2.4.13

- 🐛 **fix:** seed input with special mode (-1/-2/-3) incorrectly froze index

Moved graphToPrompt patch from beforeRegisterNodeDef to setup() so it
runs AFTER the Seed node has resolved special values. Previously, the
ReadPromptFiles node saw the raw -1 instead of the resolved seed number,
causing the signature to never change and the index to freeze. Now it
sees the actual resolved seed value, so: special seeds → index advances,
fixed seeds → index freezes (including transition from special→fixed).

**Changed files:**

- js/eclipse-read-prompt-files.js (_getConnectedSeedSignature)

---

## 2026-03-02

### Version 2.4.12

- 🐛 **fix:** prevent default values leaking from pipe when configure_sampler is off

Smart Loader+ now only adds flux_guidance to pipe when configure_sampler
is enabled. Pipe Out no longer returns fallback defaults (20/8.0) for
steps/cfg when they are absent from the pipe.

**Changed files:**

- py/RvLoader_SmartLoader_Plus.py (move flux_guidance into sampler block)
- py/RvPipe_Out_CheckpointLoader.py (remove default fallbacks for steps/cfg)

- ✨ **feat:** var reorder context menu for GetFirst and GetAllActive

Right-click → "Reorder Vars" submenu per var slot: Move to Top, Move Up,
Move Down, Move to Bottom, and Insert Above. Moves swap values in-place
without creating new slots.

**Changed files:**

- js/eclipse-getfirst.js (swapVars, moveVarToTop/Bottom, insertVarAt, menu)
- js/eclipse-getallactive.js (same reorder methods and menu)

- ⚡ **perf:** cache setter lookups and add viewport culling for GetFirst/GetAllActive

Draw methods now read from a cached `_resolvedSetters` array instead of
scanning graph._nodes on every frame. Cache is invalidated only on var
changes, type filter changes, and setter rename/remove events. Off-screen
nodes skip drawing entirely via visible_area bounds check.

---

## 2026-03-02

### Version 2.4.11

- ✨ **feat:** GetAllActive virtual node — multi-output Set/Get collector

New "Get All Active" node (JS-only virtual node). Same UI as GetFirst but
with one output per var slot — each resolves independently to its SetNode
source. Green dot on every active var (not just first). Connect outputs to
a Join Strings node for string collection. Shares SetNode rename tracking
via ECLIPSE_GETTER_TYPES array.

**Changed files:**

- js/eclipse-getallactive.js (new)
- js/eclipse-getfirst.js (ECLIPSE_GETTER_TYPES support, var reorder)
- js/eclipse-dynamic-inputs.js (null guard for origin_slot during configure)

- ✨ **feat:** var reorder context menu for GetFirst and GetAllActive

Right-click → "Reorder Vars" submenu with Move Up, Move Down, and Insert
Above per var slot. No more manual reshuffling when adding a higher-priority
var.

---

### Version 2.4.10

- ✨ **feat:** GetFirst auto-rename tracking

GetFirst var widgets now auto-update when a SetNode is renamed or removed.
Uses LiteGraph prototype patching on SetNode (onConfigure, onNodeCreated,
onRemoved) — fully event-driven, no polling.

**Changed files:**

- js/eclipse-getfirst.js
- js/eclipse-widget-performance-utils.js

---

### Version 2.4.9

- ✨ **feat:** GetFirst virtual node — priority-based Set/Get resolution

New "Get First" node (JS-only virtual node, no backend cost) that replaces
N GetNodes + 1 Multi-Switch. Resolves to the first active SetNode from a
user-defined priority list. Features: type filter, ordered var combos,
green dot indicator on active var, connection drawing, go-to-setter menu.

- ✨ **feat:** transport image through metadata pipe

All 3 Load Image nodes (LoadImage, LoadImageFromFolder, LoadImagePath)
now store the image tensor in the pipe dict. Pipe Out Load Image gains
a new image output to retrieve it.

**Changed files:**

- js/eclipse-getfirst.js (new)
- py/RvImage_LoadImage.py, py/RvImage_LoadImageFromFolder.py
- py/RvImage_LoadImagePath_Pipe.py, py/RvPipe_Out_LoadImage.py

---

## 2026-03-01

### Version 2.4.8

- 🐛 **fix:** Fast Bypasser/Muter/Collector/Repeater lose connections on paste

During workflow paste or load, onConnectionsChange fired immediate
stabilize for each link being restored. With collapsed connections,
stabilizeInputs removed all not-yet-linked inputs before later links
could connect. Added _eclipse_loading flag: set in configure(), checked
in onConnectionsChange() to defer stabilize, cleared when stabilize
finally runs.

**Changed files:**

- js/eclipse-mode-nodes.js

---

## 2026-02-28

### Version 2.4.7

- 🐛 **fix:** Smart Loader combo validation blocks stale filenames

Add validate_inputs(**kwargs) to all three Smart Loader nodes so
ComfyUI skips built-in combo validation. Prevents "Value not in list"
errors for LoRA/model files that were moved or deleted from the
filesystem while the workflow still references them. File existence
is still checked at execution time.

**Changed files:**

- py/RvLoader_SmartLoader_Plus.py, py/RvLoader_SmartLoader.py,
py/RvLoader_SmartLoader_Basic.py

- ✨ **feat:** add Eclipse PuLID Loader & Apply nodes for Nunchaku models

Eclipse-native PuLID nodes that use the vendored ComfyFluxWrapper,
avoiding isinstance failures when models are loaded via Eclipse's
Smart Loader Plus. PuLID Loader supports CPU/CUDA/ROCm provider
selection for InsightFace. Also fix copy_with_ctx in vendored
wrappers/flux.py with archive_model_dtypes workaround.

**Changed files:**

- py/RvTools_NunchakuPuLID.py (new), __init__.py,
extern/nunchaku/wrappers/flux.py

- ⚡ **perf:** add batchedNotifyVue for microtask-coalesced Vue updates

Add batchedNotifyVue to widget-performance-utils — uses queueMicrotask
to coalesce multiple notifyVue calls within the same sync frame. Use it
in group _eclipse_doMode and _eclipse_handleAction where bulk operations
fire N times in a loop.

**Changed files:**

- js/eclipse-widget-performance-utils.js, js/eclipse-mode-nodes.js

- 🐛 **fix:** Fast Groups Muter/Bypasser state detection and Vue reactivity

Always call recomputeInsideNodes in the 500ms refresh poll so _nodes
is populated in both Vue and canvas renderers. Add notifyVue calls in
groupsRefreshWidgets, _eclipse_doMode, and _eclipse_handleAction so
widget value changes trigger Vue reactivity updates.

**Changed files:**

- js/eclipse-mode-nodes.js

- 🐛 **fix:** Context pipe new_context() debug logging + tuple-None safety

Add debug logging to trace pipe key overwrites (visible at debug log
level). Fix potential crash when pipe is a tuple containing None.
Applied to all three context nodes.

**Changed files:**

- py/RvPipe_IO_Context_Image.py, py/RvPipe_IO_Context_Video.py,
py/RvPipe_IO_Context_WanVideoWrapper.py

- 🐛 **fix:** Smart Loader pipe omits disabled-feature keys for ConcatMulti compat

Build pipe dict conditionally — keys for disabled features (clip, vae,
latent, width, height, batch_size, clip_skip, vae_name) are now omitted
instead of set to None. Prevents ConcatMulti from overwriting existing
pipe values with empty/default data.

**Changed files:**

- py/RvLoader_SmartLoader_Plus.py, py/RvLoader_SmartLoader.py,
py/RvLoader_SmartLoader_Basic.py

## 2026-02-27

- 🐛 **fix:** ConcatMulti wrapping image tensors in lists

Split _KNOWN_LIST_KEYS into _TENSOR_KEYS (merged via torch.cat) and
true list keys. Prevents image/mask tensors from being converted to
Python lists, which broke downstream nodes expecting .shape attribute.

**Changed files:**

- py/RvConversion_ConcatMulti.py

- ♻️ **refactor:** split String Multiline into two nodes

String Multiline now outputs a single joined string (no list output).
New String Multiline List node keeps the list output. Both nodes gain
an optional input_string input that prepends to the content.

**Changed files:**

- py/RvText_Multiline.py
- py/RvText_Multiline_List.py (new)

## 2026-02-26

- 🐛 **fix:** migration messages appearing every startup

Use .migrated marker file in repo root to run user-folder migration
exactly once. Replaces fragile backup/junction-container detection.
Simplified create_model_junctions guard — _create_junction already
skips existing links.

**Changed files:**

- core/migration.py
- .gitignore

- ✨ **feat:** add Image Comparer node (V3 API)

New node that compares two images with Slide (hover) or Click mode.
Inspired by rgthree's Image Comparer, rewritten for V3 API / Nodes 2.0.

**Changed files:**

- py/RvImage_ImageComparer.py (new)
- js/eclipse-image-comparer.js (new)
- __init__.py

- 📚 **docs:** comprehensive documentation audit against actual code

Fixed 25+ discrepancies across all documentation files. Key corrections:
- Rewrote Eclipse Folder Structure (repo-only .defaults/ pattern with junctions)
- Fixed all file paths from old models/Eclipse/ to repo-based paths
- Smart_Loaders.md: 25 CLIP types (was 8), fixed Nunchaku options, GGUF dequant_dtype,
added Smart Loader Basic, fixed template delete instructions, Three Variants
- Replace_String_v3.md: remove_image→remove_image_style, remove_nsfw→nsfw_handling combo,
added remove_lighting/remove_watermark, fixed order of operations, cleanup description
- Smart_Prompt.md: fixed 18 stale path references
- Load_Image_From_Folder.md: include_subfolders default True, index special modes,
multi-folder pipe fields, auto-stop condition
- Wildcard_Processor.md: fixed 6 wrong paths, removed ghost seed_input,
added negative_prompt, fixed __wildcard__ syntax advice
- Save_Prompt.md: added missing append_batch write mode
- ReadPromptFiles_Usage.md: added -4 shuffle mode, stop_at_end, seed_input
- Checkpoint_Loaders.md: removed broken doc links
- README.md: fixed Contents, added missing nodes (20+), added Smart Loader Basic
- Readme/README.md: fixed file locations table, removed Nunchaku Installation link

**Changed files:**

- README.md, Readme/README.md, Readme/Smart_Loaders.md, Readme/Prompt_Styler.md,
Readme/Smart_Prompt.md, Readme/Replace_String_v3.md, Readme/Load_Image_From_Folder.md,
Readme/Wildcard_Processor.md, Readme/Save_Prompt.md, Readme/ReadPromptFiles_Usage.md,
Readme/Checkpoint_Loaders.md

- 🐛 **fix:** wildcards/smart_prompt junction handles orphaned directories

The create_wildcards_junction() function now detects orphaned regular
directories (from old approach) and replaces them with proper symlinks.
Previously, an empty directory would pass the exists check and be kept
as-is, breaking wildcard integration.

**Changed files:**

- core/migration.py

- ♻️ **refactor:** repo-only architecture with root .defaults/ and model junctions

Eliminate models/Eclipse/ user folder entirely. All data (templates, patterns,
prompts, styles, wildcards) lives directly in repo folders. Git-tracked defaults
stored in single root .defaults/ folder that mirrors repo structure. Extracted
to repo locations on first run (never overwrites user edits).

- .defaults/ root folder (161 .example files mirroring full repo structure)
- core/migration.py: full migration module with run_migrations() entry point
(6 steps: ancient folder migration, user folder → repo, config rename,
.defaults/ extraction, wildcards junction, model folder junctions)
- Rename: eclipse_config.json → config.json (auto-migrated)
- Model junctions: models/Eclipse/{templates,patterns,styles,prompts} → repo
- Wildcards junction: models/wildcards/smart_prompt → repo prompts/

- ⚡ **perf:** migrate 7 JS files to use createWidgetVisibilityManager

Replace O(n) widget .find() lookups with O(1) Map-backed cached
lookups via createWidgetVisibilityManager in all files that use
setWidgetVisible/getWidgetValue patterns.

**Changed files:**

- eclipse-smart-loader.js
- eclipse-smart-loader-plus.js
- eclipse-smart-loader-basic.js
- eclipse-lora-stack.js
- eclipse-smart-folder.js
- eclipse-prompt-styler.js
- eclipse-smart-prompt.js

Manual notifyVue() calls removed from visibility update functions -
the manager auto-batches Vue notifications via queueMicrotask,
coalescing multiple setVisible() calls into a single DOM update.

## 2026-02-20

- 🐛 **fix:** mode node event propagation, canvas dot alignment, null-safety

Mode Nodes (eclipse-mode-nodes.js):
- Fix collapsed input dots misaligned with output dot on canvas renderer
- Add hookTitleProperty() and syncTitleHooks() for event-driven title
rename propagation across Repeater → Collector → Muter/Bypasser chains
- Add mode hooks on Repeater resolved input nodes so external mute/bypass
changes propagate inward to the Repeater
- Add _eclipse_propagating guard flag to prevent infinite mode sync loops
- Add multi-connection guard: skip inward mode sync when Repeater has
multiple inputs to prevent cascading bypass of unrelated nodes
- Clean up _eclipse_hookedNodes and _eclipse_hookedTitles in all
onRemoved handlers (modeChanger, repeater, collector)

Smart Loader Plus (eclipse-smart-loader-plus.js):
- Fix null-safety crash: wrap widget value with String() before
calling .replace() to handle null/undefined values

Config:
- Bump version to 2.3.12

- 🐛 **fix:** Fast Muter/Bypasser toggle & collapse across both renderers

- Fix Toggle/Bypass/Enable all actions not updating toggle switches in
Vue renderer (Fast Muter/Bypasser)

- Fix Fast Groups Muter/Bypasser toggle/enable/mute all not visually
updating in Vue renderer — group widgets are custom-drawn (type
"custom" with draw()), widget.value is a plain property not backed by
Pinia store.

- Fix Collapse Connections not working in Canvas (LiteGraph) renderer —
CSS-based approach only affects Vue DOM.

- Fix toggle switches not visually updating when nodes are bypassed via
group operations (Vue renderer)

- Load Image From Folder: move file cache log messages (refreshing,
building, cached, folder count) from log.msg to log.debug to reduce
console noise during normal operation

- 🐛 **fix:** Vue node size shrinking, collapsed width, and z-order on workflow reload

Fix three issues in ComfyUI's Vue frontend node renderer that occur when
loading workflows from file or image:

1. Node size shrinking: layoutStore.initializeFromLiteGraph() clears all
layouts then repopulates in a transaction, but Vue components mounting
during the gap read NODE_LAYOUT_DEFAULTS {width:100, height:50}.
Float64Array mutations on node._size bypass Vue's Proxy reactivity,
so CSS variables stay locked at the tiny default values.
Fix: afterConfigureGraph + double rAF re-syncs --node-width/--node-height
from node.size after Vue settles (restoreSize=true on load only).

2. Collapsed nodes too wide: Vue renderer uses a hardcoded min-w-[225px]
CSS floor for collapsed nodes. The old canvas renderer computed
collapsed width dynamically via ctx.measureText() (as small as 80px).
Fix: offscreen canvas measurement with matching font (600 14px Inter),
stored in custom CSS variable --eclipse-cw. Attribute selector
[style*="--eclipse-cw"] auto-activates with !important — survives Vue
re-renders (selection changes, etc.) because Vue only manages its own
CSS variables. On expand, --eclipse-cw is removed and normal 225px
floor returns. Runtime collapse/expand patched via node.collapse()
monkey-patch (restoreSize=false to let Vue's own watcher restore
expanded dimensions from --node-width-x).

3. Z-order flattening: initializeFromLiteGraph() correctly sets
zIndex = arrayIndex, but handleNodeAdded's deferred
onAfterGraphConfigured callback overwrites every node's z-index with
node.order || 0, bringing all collapsed/hidden nodes to the foreground.
Fix: collapsed nodes get --eclipse-z: -1 via same attribute selector
pattern, pinning them behind non-collapsed nodes (z-index >= 0).
No sendToBack exists in the Vue renderer — only bringNodeToFront.
On expand, --eclipse-z is removed and Vue resumes normal z management.

All three fixes use custom CSS variables (--eclipse-cw, --eclipse-z) with
attribute selectors and !important, which survive Vue's reactive re-renders.
The afterConfigureGraph hook with double requestAnimationFrame ensures DOM
elements exist before patching. Runtime collapse/expand is handled by
monkey-patching node.collapse() via nodeCreated/loadedGraphNode hooks.

New file: web-src/eclipse-node-size-fix.js (+ minified js/ output)

- ✨ **feat:** mode nodes, video resolution, lora model-only, wildcard negative prompt, Vue fixes

Mode nodes (based on rgthree-comfy, V3 API + Vue 2.0):
- Add Fast Muter, Fast Bypasser, Fast Groups Muter, Fast Groups Bypasser,
Mute/Bypass Repeater, Node Collector (6 virtual nodes)
- New eclipse-mode-nodes.js with full Canvas + Vue renderer compatibility
- Dynamic inputs with shallowReactive-safe stabilization, toggle restrictions,
group filtering by color/title, custom sort, collapse connections, nav buttons

Video Resolution node:
- New RvSettings_Video_Resolution.py + eclipse-video-resolution.js
- Standalone preset selector with Custom mode (show/hide width/height)
- Move VIDEO_RESOLUTION_PRESETS/MAP to core/common.py (shared constants)

SmartFolder refactor:
- Remove inline video resolution lists, use shared constants from common.py
- Add use_image_size toggle (disable when Smart Loader handles latent size)
- Image pipe only includes width/height when use_image_size=True

LoraStack model-only mode:
- Add model_only_lora toggle to RvTools_LoraStack
- clip_weight=None signals Apply node to skip CLIP (strength 0)
- New shared _build_lora_string() in LoraStack_Apply replaces 4 duplicate blocks
- Model-only format: <lora:name:weight> (no clip weight)

Wildcard negative prompt filtering:
- Add negative_prompt input to WildcardProcessor (force_input, optional)
- Raffle-style tag filtering: normalize, compare, remove matching tags
- Add strip_raffle_prefix() to wildcard_engine for taglist cleanup

Vue/frontend fixes:
- Smart Prompt: move onResize inside canvas guard (prevents Vue errors)
- UI Enhancements: dialog appended to document.body (not canvas.parentNode)
- UI Enhancements: dialog positioning via stored _eclipseLastMouse coordinates
- UI Enhancements: Node Dimensions updates Vue DOM via data-node-id CSS props
- UI Enhancements: Number() falsy check fix (|| instead of ternary)
- Add smartResize() utility to eclipse-widget-performance-utils.js

- ✨ **feat:** Convert all nodes to ComfyUI V3 schema

Python:
- Migrate all node files to V3 API (io.ComfyNode, define_schema, io.NodeOutput)
- Add backward compat classes with [Eclipse] suffix for old workflows
- Pass vision_task to all generation backends for few-shot style guidance
- Add vision_task param to generate_vllm() for native vLLM few-shot injection
- Improve system prompts: direct anatomical terms, anti-prefix instructions

JavaScript:
- Full Vue renderer compatibility (Nodes 2.0): use widget.hidden + widget.options.hidden
- Replace type-swapping (converted-widget) with native hidden flags for widget visibility
- Add notifyVue() pop+push to trigger shallowReactive array updates
- Remove onDrawForeground/isNodeVisible/setupLazyInit performance overhead
- Add pre-queue model download confirmation dialog
- Fix Advanced Options node type detection for [SmartLML] suffix
- Clean up widget-performance-utils (remove unused throttle, batch updater)

Config:
- Add few-shot examples for all vision tasks (simple/detailed/ultra/cinematic/tags/video)
- Add NSFW-inclusive few-shot examples for uncensored output
- Enhance system prompts with pose/action/interaction specificity

Scripts:
- Add setup_swap.sh for Linux swap file management (distro-independent)

- ✨ **feat:** Convert all nodes to ComfyUI V3 schema

- Migrate all 86 node files to V3 API (io.ComfyNode, define_schema, io.NodeOutput)
- Full compatibility with Vue renderer (Nodes 2.0)
- Standardize class names to match filenames (22 Eclipse_* -> Rv*_*)
- Fix: Performance Clash between SmartLML & Eclipse
- Endpoint Optimizations
- Harden RAM Cleanup: sync before drop_caches, use value 1 (pagecache only)
- Add setup_cache_clearing.sh for Linux passwordless sudo configuration
- Remove dangerous /bin/sh -c sudoers rule
- Bump version to 2.3.0

- ✨ **feat:** comprehensive regex pattern enhancement and code quality improvements

- Regex Enhancement: Complete pattern system overhaul with 262-prompt real-world validation
* NSFW Detection: 100.0% (+48% improvement) - added swimwear, medical, maternal, educational contexts
* Image Descriptions: 100.0% (+75% improvement) - added "an image of", "photo depicts", "artistic rendering", "digital painting showing", "artistic study"
* Shot Styles: 100.0% (+94.3% improvement) - added bird's eye, dolly, crane, environmental, candid shots with proper apostrophe handling
* Instructions: 100.0% (+10% improvement) - added "expansion", "design", "version" headers
- Security: Fix path traversal, URL validation, shell injection, YAML loader vulnerabilities
- Performance: Pre-compile regex patterns, add TTL caching (config, templates, models)
- Text Processing: Enhanced smart phrase removal with context-aware grammar preservation and boundary protection
- Architecture: Centralized regex patterns in core/, fixed core/py imports, complete V2/V3 integration with individual NSFW pattern usage
- Quality: Replace bare except, convert docstrings to # comments, remove logger wrappers
- UI/UX: Fix LoadImageFromFolder and PromptStyler index handling to respect manual changes
- Testing: Comprehensive 262-prompt dataset validation with boundary analysis and over-matching prevention
- Deduplication: Centralize AnyType, loader templates, cleanup functions
- Unicode Support: Fixed apostrophe handling for smart quotes and Unicode characters in shot style patterns
- Created: core/loader_templates.py, core/file_cache.py, core/styles.py, core/regex_patterns.py, core/regex_helper.py

Enhanced regex patterns achieve 100% detection across all categories with zero false positives.
Added 25+ new NSFW patterns, 8+ new image patterns, 30+ shot style terms with Unicode support.
Validated against diverse real-world prompts with comprehensive boundary testing framework.
Complete V2/V3 integration ensures all imported patterns are properly utilized in text processing.
Centralizes pattern architecture with proven extensible design and robust edge case handling.
Fixes 100+ bare except statements, 50+ code duplications, 8 security issues across 50+ files.

- ✨ **feat:** Standardize system prompts and add few-shot support for multi-task chains

- Centralize system prompts in smartlm_prompt_defaults.json (authoritative source)
- Remove redundant system_prompt from llm_few_shot_training.json
- Add /eclipse/reload_all endpoint for config hot-reload without restart
- Add /eclipse/model_files_all endpoint for Smart Loader dropdown refresh
- Fix cross-backend cache clearing (GGUF ↔ Transformers ↔ Docker)
- Add uncensored language to text task prompts (tags_to_natural_language, etc.)
- Add uncensored few-shot examples to preserve content during transformations
- Fix multi-task chain: Task 2/3/4 now receive llm_mode for few-shot support
- Add llm_mode parameter to generate_gguf() for few-shot examples
- Add _build_few_shot_prompt() for vision models doing text-only chained tasks
- Fix model_family routing: handle both "Qwen" and "QwenVL" in generate_transformers
- Fix Qwen cached model looping: add seed setting and KV cache clearing
- Simplify "Tags" system prompt to prevent verbose output

- 🐛 **fix:** Use ComfyUI temp folder for temp images & stop Docker on backend switch
- Affects vLLM, SGLang, Ollama, and llama.cpp Docker backends

Backend switching:
- Added stop_all_docker_containers() to free GPU VRAM when switching backends
- Stops vLLM, SGLang, Ollama, and llama.cpp containers on backend change
- Prevents OOM errors when switching between Docker and local backends
