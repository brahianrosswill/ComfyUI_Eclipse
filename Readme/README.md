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

**[Smart Language Model Loader v2 Guide](Smart_Language_Model_Loader_v2_Guide.md)** ⭐ NEW
- **What it does:** Single unified node for vision-language and text AI with multiple backend support
- **Backends:** Transformers (quality), vLLM Docker (fast), vLLM Native (Linux), GGUF (low VRAM)
- **Vision models:** QwenVL (detailed analysis, video), Mistral/Pixtral (vision), Florence-2 (fast tagging, OCR)
- **Text models:** Qwen, Mistral, LLaMA, and other LLMs for text processing
- **Key features:** Family-based task filtering, pre-configured templates, auto-download from HuggingFace
- **Use cases:** Auto-tag generations, training captions, video summaries, OCR, object detection
- **Getting started:** Quick start guides for each backend, model comparison, VRAM requirements
- **Advanced:** vLLM Docker/Native setup, quantization options, performance optimization

### Image Processing

**[Save Images Guide](Save_Images.md)**
- Advanced image saving with metadata
- Placeholder system for dynamic organization
- Generation data preservation
- Civitai-compatible hash embedding
- Multi-format output options

### Installation & Setup

**[Docker Installation Guide](Docker_Installation_Guide.md)** ⭐ NEW
- Complete WSL2 setup for Windows
- Docker Desktop installation and configuration
- NVIDIA GPU setup for containers
- Native vLLM installation in WSL2
- Performance optimization tips
- Troubleshooting common issues

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

3.5. **Vision & Language AI:** [Smart Language Model Loader v2 Guide](Smart_Language_Model_Loader_v2_Guide.md) ⭐ NEW
   - Unified node with multiple backends (Transformers, vLLM, GGUF)
   - QwenVL, Mistral/Pixtral (vision), Florence-2 (fast tags), LLMs (text)
   - Pre-configured templates, auto-download models
   - vLLM Docker for fast inference
   - Comprehensive setup guides

3.6. **Docker & vLLM Setup:** [Docker Installation Guide](Docker_Installation_Guide.md)
   - WSL2 installation and configuration
   - Docker Desktop setup for Windows
   - NVIDIA GPU passthrough
   - Native vLLM in WSL2 (alternative to Docker)

4. **Advanced Setup:** [Nunchaku Installation](Nunchaku_Installation.md)
   - Install quantized model support (optional)
   - Reduce VRAM usage significantly
   - Understand GPU compatibility
   - Optimize for your hardware

### Quick Help

**I want to...**

- **Load a basic model** → [Checkpoint Loader Small](Checkpoint_Loaders.md#checkpoint-loader-small)
- **Save/load configurations** → [Template System](Smart_Loaders.md#template-system)
- **Use quantized models** → [Model Types & Formats](Smart_Loaders.md#model-types--formats)
- **Reduce VRAM usage** → [Quantization Configuration](Smart_Loaders.md#quantization-configuration)
- **Build CLIP ensembles** → [CLIP Configuration](Smart_Loaders.md#clip-configuration)
- **Work with pipes** → [Checkpoint Loader Small (Pipe)](Checkpoint_Loaders.md#checkpoint-loader-small-pipe)
- **Build prompts from files** → [Smart Prompt Guide](Smart_Prompt.md)
- **Create prompt templates** → [Wildcard Processor Guide](Wildcard_Processor.md)
- **Analyze images with AI** → [Smart Language Model Loader v2 Guide](Smart_Language_Model_Loader_v2_Guide.md)
- **Generate image descriptions/tags** → [Smart Language Model Loader v2 Guide](Smart_Language_Model_Loader_v2_Guide.md)
- **Understand video content** → [Smart Language Model Loader v2 Guide](Smart_Language_Model_Loader_v2_Guide.md) (QwenVL models)
- **Auto-tag generated images** → [Smart Language Model Loader v2 Guide](Smart_Language_Model_Loader_v2_Guide.md) (Florence-2 models)
- **Process text with LLM** → [Smart Language Model Loader v2 Guide](Smart_Language_Model_Loader_v2_Guide.md) (LLM models)
- **Setup Docker for vLLM** → [Docker Installation Guide](Docker_Installation_Guide.md)
- **Install WSL2 on Windows** → [Docker Installation Guide](Docker_Installation_Guide.md)
- **Save images with metadata** → [Save Images Guide](Save_Images.md)
- **Organize outputs with placeholders** → [Save Images Guide](Save_Images.md#placeholder-system)
- **Install Nunchaku support** → [Nunchaku Installation](Nunchaku_Installation.md)
- **Reduce VRAM with quantization** → [Nunchaku Installation](Nunchaku_Installation.md)

### Common Questions

**Q: Which loader should I use?**

A: Start with **Checkpoint Loader Small** for simplicity. Move to **Smart Loader Plus** when you need:
- Multiple model formats (UNet, Nunchaku, GGUF)
- Template management for quick switching
- Quantized models for VRAM savings
- All-in-one latent and sampler configuration

**Q: What's the difference between Smart Loader and Smart Loader Plus?**

A: **Smart Loader Plus** includes latent and sampler configuration built-in. **Smart Loader** is the streamlined version without those - you use separate Empty Latent and KSampler nodes instead.

**Q: How do I reduce VRAM usage?**

A: Use quantized models (Nunchaku or GGUF) with Smart Loaders. See [Quantization Configuration](Smart_Loaders.md#quantization-configuration) for details.

**Q: What are templates?**

A: Templates save your complete loader configuration (model, CLIP, VAE, sampler, etc.) so you can restore it instantly later. See [Template System](Smart_Loaders.md#template-system).

**Q: My checkpoint won't load, what do I do?**

A: Check the [Troubleshooting](Checkpoint_Loaders.md#troubleshooting) sections in both guides for solutions to common problems.

**Q: How do I build prompts quickly?**

A: Use [Smart Prompt](Smart_Prompt.md) for dropdown-based selection from organized prompt files, or [Wildcard Processor](Wildcard_Processor.md) for template-based generation with infinite variations.

**Q: What's the difference between Smart Prompt and Wildcard Processor?**

A: **Smart Prompt** uses numbered text files to create dropdown menus (select from curated options). **Wildcard Processor** uses template syntax like `{option1|option2}` for dynamic expansion (infinite variations from templates).

**Q: How do I analyze images or videos with AI?**

A: Use the [Smart Language Model Loader v2](Smart_Language_Model_Loader_v2_Guide.md) node. It supports multiple backends (Transformers, vLLM Docker, vLLM Native, GGUF) and models including QwenVL, Mistral/Pixtral, Florence-2, and text-only LLMs. Connect an image, select backend/model, choose a task, and run. Models download automatically.

**Q: What can Smart Language Model Loader v2 do?**

A: **Image Analysis:** Detailed descriptions, SD/Flux tags, composition analysis. **Video:** Summarize content across frames (QwenVL). **Text Extraction:** OCR for documents (Florence-2). **Object Detection:** Find objects with bounding boxes. **Training Data:** Create LoRA/DreamBooth captions. **Text Processing:** Refine prompts (LLM models). See [Smart Language Model Loader v2 Guide](Smart_Language_Model_Loader_v2_Guide.md) for examples.

**Q: Which backend should I use?**

A: **Transformers:** Best quality, works everywhere, moderate speed. **vLLM Docker:** 2-3x faster inference, requires Docker setup. **vLLM Native:** Linux/WSL2 only, fastest. **GGUF:** Lowest VRAM usage, good for limited hardware. See [Smart Language Model Loader v2 Guide](Smart_Language_Model_Loader_v2_Guide.md#backend-comparison) for details.

**Q: How do I set up Docker for vLLM?**

A: Follow the [Docker Installation Guide](Docker_Installation_Guide.md). It covers WSL2 setup, Docker Desktop installation, NVIDIA GPU configuration, and native vLLM installation as an alternative.

**Q: How do I install Nunchaku for quantized models?**

A: Follow the detailed [Nunchaku Installation Guide](Nunchaku_Installation.md). It includes step-by-step commands for ComfyUI Portable, dependency management, and GPU compatibility information.

**Q: What GPU do I need for Nunchaku/quantized models?**

A: RTX 30 and 40 series GPUs work well with the primary benefit being lower VRAM usage. RTX 50 series (Blackwell) will add native FP4 acceleration for additional speed. See [GPU Compatibility](Nunchaku_Installation.md#gpu-compatibility) for details.

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
| Templates | `ComfyUI/models/Eclipse/loader_templates/` (primary)<br>`ComfyUI_Eclipse/templates/loader_templates/` (bundled) |
| Smart Prompt Files | `ComfyUI/models/Eclipse/smart_prompt/` (primary)<br>`ComfyUI/models/wildcards/smart_prompt/` (junction)<br>`ComfyUI_Eclipse/templates/prompt/` (bundled) |
| Wildcard Files | `ComfyUI/models/wildcards/` |
| Smart LML v2 Models | `ComfyUI/models/LLM/` (QwenVL, Mistral, Florence-2, LLM) |
| Smart LML v2 Templates | `ComfyUI/models/Eclipse/smartlm_templates/` (user)<br>`ComfyUI_Eclipse/templates/smartlm_templates/` (bundled) |

### Required Extensions

Some features require additional extensions:

**For Smart Language Model Loader v2 (QwenVL, Mistral, Florence-2, LLM):**

The Smart LML v2 node requires Python packages based on backend:
- `transformers` (HuggingFace models - all vision and text models)
- `llama-cpp-python` (GGUF backend - low VRAM option)
- Docker + WSL2 (vLLM Docker backend - see [Docker Installation Guide](Docker_Installation_Guide.md))
- vLLM (vLLM Native backend - Linux/WSL2 only)

For Transformers/GGUF backends:
```bash
# For ComfyUI Portable (Windows):
python_embeded\python.exe -m pip install transformers llama-cpp-python

# For standard Python environments:
pip install transformers llama-cpp-python
```

For vLLM backends, see [Docker Installation Guide](Docker_Installation_Guide.md) for complete setup instructions.

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
