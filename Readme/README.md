# ComfyUI_Eclipse User Documentation

Welcome to the user documentation for ComfyUI_Eclipse! This guide is designed for artists, creators, and users who want to understand how to use the nodes effectively - not for developers.

## Documentation Index

### Model Loaders

**[Checkpoint Loaders Guide](Checkpoint_Loaders.md)**
- Traditional checkpoint loading
- Simple, reliable model loading
- Understanding CLIP and VAE settings
- Basic troubleshooting

**[Smart Loaders Guide](Smart_Loaders.md)**
- Advanced multi-format loaders
- Template system for quick configuration
- Quantized model support (Nunchaku, GGUF)
- CLIP ensemble configuration
- Memory optimization techniques

### Text Processing

**[Prompt Styler Guide](Prompt_Styler.md)** ⭐ NEW
- Apply 108+ pre-built visual styles to prompts
- Three modes: tag_based, natural_language, custom
- Index-based batch processing with control_after_generate
- Create custom style files (CSV/JSON)
- Automatic negative prompt generation

**[Smart Prompt Guide](Smart_Prompt.md)**
- Dropdown-based prompt building
- File-based prompt organization
- Folder filtering and categories
- Seed-controlled random selection
- Creating custom prompt libraries

**[Wildcard Processor Guide](Wildcard_Processor.md)**
- Template-based prompt expansion
- Wildcard syntax and patterns
- Weighted random selection
- Nested wildcards
- Creating wildcard files

**[ReadPromptFiles Guide](ReadPromptFiles_Usage.md)** ⭐ NEW
- Load prompts from multiple text files with index navigation
- Navigation modes: fixed index, random (-1), increment (-2), decrement (-3)
- JavaScript buttons for easy mode switching
- Bounds-safe architecture prevents index errors
- Multi-file support with quoted paths
- Auto file change detection

**[Save Prompt Guide](Save_Prompt.md)** ⭐ NEW
- Save captions/prompts to txt, csv, json
- Source folder integration for batch captioning
- Placeholder system (%source_filename, %date, etc.)
- Auto-numbering and append modes
- NSFW auto-detection for JSON

**[Replace String v3 Guide](Replace_String_v3.md)** ⭐ NEW
- Tag-aware removal options (subject, background, mood, image)
- NSFW content removal
- Age adjustment
- Works with both tags and prose formats
- Regex pattern matching

### Image Processing

**[Load Image From Folder Guide](Load_Image_From_Folder.md)** ⭐ NEW
- Batch image loading from folders
- Auto-increment index for sequential processing
- Metadata extraction (ComfyUI, Auto1111, NovelAI)
- File list caching for consistent ordering
- Auto-stop at end of folder
- Perfect for captioning and tagging workflows

**[Save Images Guide](Save_Images.md)**
- Advanced image saving with metadata
- Placeholder system for dynamic organization
- Generation data preservation
- Civitai-compatible hash embedding
- Multi-format output options

### Installation & Setup

**[Nunchaku Installation Guide](Nunchaku_Installation.md)**
- Installing Nunchaku for quantized Flux models
- Step-by-step installation for ComfyUI Portable
- GPU compatibility information
- Troubleshooting dependency issues
- Understanding performance on different GPU architectures

### Getting Started

If you're new to ComfyUI_Eclipse loaders:

1. **Start Here:** [Checkpoint Loaders Guide](Checkpoint_Loaders.md)
   - Learn the basics with traditional loaders
   - Understand core concepts (CLIP, VAE, model files)
   - Get comfortable with basic settings

2. **Level Up:** [Smart Loaders Guide](Smart_Loaders.md)
   - Move to advanced features
   - Learn template management
   - Explore quantized models
   - Optimize for your system

3. **Text Processing:** [Smart Prompt](Smart_Prompt.md) & [Wildcard Processor](Wildcard_Processor.md)
   - Build prompts efficiently
   - Create prompt templates
   - Generate infinite variations
   - Control randomization

4. **Image Organization:** [Load Image From Folder](Load_Image_From_Folder.md) & [Save Images](Save_Images.md)
   - Batch image loading with metadata
   - Save captions with source folder integration
   - Advanced metadata support

### Quick Help

**I want to...**

- **Load a basic model** → [Checkpoint Loader Small](Checkpoint_Loaders.md#checkpoint-loader-small)
- **Save/load configurations** → [Template System](Smart_Loaders.md#template-system)
- **Use quantized models** → [Model Types & Formats](Smart_Loaders.md#model-types--formats)
- **Reduce VRAM usage** → [Quantization Configuration](Smart_Loaders.md#quantization-configuration)
- **Build CLIP ensembles** → [CLIP Configuration](Smart_Loaders.md#clip-configuration)
- **Work with pipes** → [Checkpoint Loader Small (Pipe)](Checkpoint_Loaders.md#checkpoint-loader-small-pipe)
- **Apply visual styles to prompts** → [Prompt Styler Guide](Prompt_Styler.md)
- **Build prompts from files** → [Smart Prompt Guide](Smart_Prompt.md)
- **Create prompt templates** → [Wildcard Processor Guide](Wildcard_Processor.md)
- **Save images with metadata** → [Save Images Guide](Save_Images.md)
- **Organize outputs with placeholders** → [Save Images Guide](Save_Images.md#placeholder-system)
- **Install Nunchaku support** → [ComfyUI-nunchaku](https://github.com/nunchaku-tech/ComfyUI-nunchaku): clone into `custom_nodes/`
- **Reduce VRAM with quantization** → [Smart Loaders Guide](Smart_Loaders.md#quantization-configuration)

### Common Questions

**Q: Which loader should I use?**

A: Start with **Checkpoint Loader Small** for simplicity. Move to **Smart Loader Plus** when you need:
- Multiple model formats (UNet, Nunchaku, GGUF)
- Template management for quick switching
- Quantized models for VRAM savings
- All-in-one latent and sampler configuration

Alternatively, use **Smart Loader Basic** if you only need Standard Checkpoint, UNet, or GGUF without templates or Nunchaku.

**Q: What's the difference between Smart Loader and Smart Loader Plus?**

A: **Smart Loader Plus** includes latent and sampler configuration built-in. **Smart Loader** is the streamlined version without those - you use separate Empty Latent and KSampler nodes instead.

**Q: How do I reduce VRAM usage?**

A: Use quantized models (Nunchaku or GGUF) with Smart Loaders. See [Quantization Configuration](Smart_Loaders.md#quantization-configuration) for details.

**Q: What are templates?**

A: Templates save your complete loader configuration (model, CLIP, VAE, sampler, etc.) so you can restore it instantly later. See [Template System](Smart_Loaders.md#template-system).

**Q: My checkpoint won't load, what do I do?**

A: Check the [Troubleshooting](Checkpoint_Loaders.md#troubleshooting) sections in both guides for solutions to common problems.

**Q: How do I build prompts quickly?**

A: Use [Smart Prompt](Smart_Prompt.md) for dropdown-based selection from organized prompt files, [Wildcard Processor](Wildcard_Processor.md) for template-based generation with infinite variations, or [Prompt Styler](Prompt_Styler.md) to apply pre-built visual styles to your prompts.

**Q: What's the difference between Smart Prompt, Wildcard Processor, and Prompt Styler?**

A: **Smart Prompt** uses numbered text files to create dropdown menus (select from curated options). **Wildcard Processor** uses template syntax like `{option1|option2}` for dynamic expansion (infinite variations from templates). **Prompt Styler** wraps your prompt with style-specific text and negative prompts (100+ pre-built styles for cinematic, anime, photographic, etc.).

**Q: How do I apply styles like "cinematic" or "anime" to my prompts?**

A: Use [Prompt Styler](Prompt_Styler.md). It includes 100+ pre-built styles. Connect your prompt, select a style mode (tag_based, natural_language, or custom), pick a style, and it wraps your prompt with style-specific prefixes/suffixes and adds appropriate negative prompts automatically.

**Q: How do I install Nunchaku for quantized models?**

A: Clone the [ComfyUI-nunchaku](https://github.com/nunchaku-tech/ComfyUI-nunchaku) repository into your `custom_nodes/` folder and restart ComfyUI. The Smart Loaders will automatically detect the extension and enable Nunchaku model options.

**Q: What GPU do I need for Nunchaku/quantized models?**

A: RTX 30 and 40 series GPUs work well with the primary benefit being lower VRAM usage. RTX 50 series (Blackwell) will add native FP4 acceleration for additional speed.

### File Locations Reference

| Item | Location |
|------|----------|
| Standard Checkpoints | `ComfyUI/models/checkpoints/` |
| UNet Models | `ComfyUI/models/diffusion_models/` |
| Nunchaku Models | `ComfyUI/models/diffusion_models/` |
| Qwen Models | `ComfyUI/models/diffusion_models/` |
| GGUF Models | `ComfyUI/models/diffusion_models/` |
| CLIP Files | `ComfyUI/models/clip/`<br>`ComfyUI/models/text_encoders/` |
| VAE Files | `ComfyUI/models/vae/` |
| Templates | `ComfyUI_Eclipse/templates/` (also via `models/Eclipse/templates/` junction) |
| Smart Prompt Files | `ComfyUI_Eclipse/prompts/` (also via `models/Eclipse/prompts/` junction) |
| Wildcard Files | `ComfyUI_Eclipse/wildcards/` |
| Prompt Styler Styles | `ComfyUI_Eclipse/styles/` (also via `models/Eclipse/styles/` junction) |

### Required Extensions

Some features require additional extensions:

**For Nunchaku Models (Quantized Flux/Qwen):**
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/nunchaku-tech/ComfyUI-nunchaku
```

**For GGUF Models:**
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/city96/ComfyUI-GGUF
```

### Recommended File Formats

| Format | Status | Notes |
|--------|--------|-------|
| `.safetensors` | ✅ Recommended | Safe, fast, modern |
| `.sft` | ✅ Recommended | Safetensors alternative |
| `.ckpt` | ⚠️ Legacy | Works but shows warning |
| `.pt` | ⚠️ Legacy | Works but shows warning |
| `.pth` | ⚠️ Legacy | Works but shows warning |
| `.bin` | ⚠️ Risky | PyTorch binary - can execute code |

Always prefer `.safetensors` when available for safety and speed. Avoid `.bin`, `.ckpt`, `.pt`, and `.pth` from untrusted sources as they can contain malicious code.

### Support & Help

- **Main README:** [../README.md](../README.md) - Overview and feature highlights
- **GitHub Issues:** [Report bugs or request features](https://github.com/r-vage/ComfyUI_Eclipse/issues)
- **License:** GPL-3.0 - See [LICENSE](../LICENSE)

### What's Not Covered Here

This user documentation focuses on model loaders, text processing, and image saving. For other Eclipse features:

- **Pipe System** - See main [README](../README.md#the-pipe-ecosystem-of-eclipse)
- **Other Nodes** - See [Files by Category](../README.md#files-by-category)

---

## Contributing to Documentation

Found an error or want to improve these guides?

1. Documentation lives in `Readme/` folder
2. Written in Markdown for easy editing
3. Focus on user-friendly language (not developer jargon)
4. Include examples and step-by-step instructions
5. Submit PRs with improvements

---

**Happy creating!** If these guides helped you, consider starring the [repository](https://github.com/r-vage/ComfyUI_Eclipse) ⭐
