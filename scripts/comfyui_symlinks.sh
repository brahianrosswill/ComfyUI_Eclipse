#!/bin/bash
# ============================================================
# Linux Symlinks for ComfyUI
# ============================================================
# Custom nodes: /mnt/data/AI/ComfyUI/custom_nodes
# Models:       /mnt/data/AI/models
#
# 1. Copies files from node folders into the shared model folders
#    (merges new files, skips existing ones)
# 2. Removes the now-empty original directories
# 3. Creates symlinks pointing back to the shared locations
#
# Safe to re-run — skips folders that are already symlinks.
# ============================================================

set -e

COMFY="/mnt/data/AI/ComfyUI"
NODES="$COMFY/custom_nodes"
MODELS="/mnt/data/AI/models"

# ------------------------------------------------------------------
# Helper: copy contents from source to destination, then remove source
#   - Skips if source doesn't exist or is already a symlink
#   - Creates destination if it doesn't exist
#   - Uses cp -rn (no-clobber) so existing files are never overwritten
# ------------------------------------------------------------------
merge_and_remove() {
    local src="$1"
    local dst="$2"
    local label="$3"

    # Skip if source doesn't exist or is already a symlink
    if [[ -L "$src" ]] || [[ ! -d "$src" ]]; then
        return
    fi

    mkdir -p "$dst"
    # Copy new files only (no-clobber), preserve attributes
    cp -rn "$src"/* "$dst"/ 2>/dev/null && echo "  Merged $label → $dst" || true
    # Remove the original directory (now safe to delete)
    rm -rf "$src" && echo "  Removed $label" || true
}

echo "=== Merging files into shared folders ==="

# Wildcards
merge_and_remove "$NODES/ComfyUI-Impact-Pack/wildcards"     "$MODELS/wildcards"                 "Impact-Pack wildcards"

# Raffle lists → wildcards
merge_and_remove "$NODES/ComfyUI-Raffle/lists"               "$MODELS/wildcards"                 "Raffle lists"

# WD14 Tagger models → LLM folder (SmartLML backend also uses this path)
merge_and_remove "$NODES/ComfyUI-WD14-Tagger/models"        "$MODELS/LLM"                       "WD14 Tagger models"

# ControlNet aux checkpoints
merge_and_remove "$NODES/comfyui_controlnet_aux/ckpts"       "$MODELS/controlnet_ckpts"           "controlnet_aux ckpts"

# Frame Interpolation
merge_and_remove "$NODES/ComfyUI-Frame-Interpolation/ckpts"  "$MODELS/Frame_Interpolation/ckpts"  "Frame-Interpolation ckpts"

# RMBG (multiple nodes share the same model)
merge_and_remove "$NODES/ComfyUI_LayerStyle/RMBG-1.4"       "$MODELS/rembg/RMBG-1.4"             "LayerStyle RMBG-1.4"
merge_and_remove "$NODES/ComfyUI-Video-Matting/ckpts"        "$MODELS/rembg/RMBG-1.4"             "Video-Matting ckpts"
merge_and_remove "$NODES/ComfyUI-BRIA_AI-RMBG/RMBG-1.4"     "$MODELS/rembg/RMBG-1.4"             "BRIA RMBG-1.4"

# Fonts (multiple nodes share fonts)
merge_and_remove "$COMFY/comfy_extras/fonts"                  "$MODELS/fonts"                      "comfy_extras fonts"
merge_and_remove "$NODES/ComfyUI_Comfyroll_CustomNodes/fonts" "$MODELS/fonts"                      "Comfyroll fonts"
merge_and_remove "$NODES/Comfyui-ergouzi-Nodes/fonts"         "$MODELS/fonts"                      "ergouzi fonts"
merge_and_remove "$NODES/ComfyUI_LayerStyle/font"             "$MODELS/fonts"                      "LayerStyle font"
merge_and_remove "$NODES/ComfyUI_LayerStyle_Advance/font"     "$MODELS/fonts"                      "LayerStyle_Advance font"
merge_and_remove "$NODES/ComfyUI_essentials/fonts"            "$MODELS/fonts"                      "essentials fonts"
merge_and_remove "$NODES/ComfyUI_essentials_mb/fonts"         "$MODELS/fonts"                      "essentials_mb fonts"
merge_and_remove "$NODES/ComfyUI-KJNodes/fonts"               "$MODELS/fonts"                      "KJNodes fonts"

# LUTs
merge_and_remove "$NODES/ComfyUI_essentials/luts"             "$MODELS/luts"                       "essentials luts"
merge_and_remove "$NODES/ComfyUI_essentials_mb/luts"          "$MODELS/luts"                       "essentials_mb luts"
merge_and_remove "$NODES/ComfyUI_LayerStyle/lut"              "$MODELS/luts"                       "LayerStyle lut"

echo ""
echo "=== Creating symlinks ==="

# ------------------------------------------------------------------
# Helper: create symlink only if the parent node folder exists
#   - Skips if parent dir doesn't exist (node not installed)
#   - Skips if link already exists
# ------------------------------------------------------------------
make_link() {
    local target="$1"
    local link="$2"
    local label="$3"
    local parent
    parent="$(dirname "$link")"

    # Skip if parent node folder doesn't exist (node not installed)
    if [[ ! -d "$parent" ]]; then
        echo "  Skipped $label (node not installed)"
        return
    fi

    # Skip if symlink already exists
    if [[ -L "$link" ]]; then
        echo "  Skipped $label (already linked)"
        return
    fi

    # Fail if a real directory still exists (merge_and_remove didn't run or failed)
    if [[ -d "$link" ]]; then
        echo "  ERROR: $link still exists as a directory — remove it first"
        return
    fi

    ln -s "$target" "$link" && echo "  Linked $label"
}

# Main symlinks (output & models already linked)
# make_link /mnt/data/AI/output "$COMFY/output"   "output"
# make_link /mnt/data/AI/models "$COMFY/models"    "models"

make_link "$MODELS/wildcards"                    "$NODES/ComfyUI-Impact-Pack/wildcards"        "Impact-Pack wildcards"
make_link "$MODELS/wildcards"                    "$NODES/ComfyUI-Raffle/lists"                 "Raffle lists"
make_link "$MODELS/LLM"                          "$NODES/ComfyUI-WD14-Tagger/models"           "WD14 Tagger models"
make_link "$MODELS/controlnet_ckpts"             "$NODES/comfyui_controlnet_aux/ckpts"         "controlnet_aux ckpts"
make_link "$MODELS/Frame_Interpolation/ckpts"    "$NODES/ComfyUI-Frame-Interpolation/ckpts"    "Frame-Interpolation ckpts"

# RMBG
make_link "$MODELS/rembg/RMBG-1.4"              "$NODES/ComfyUI_LayerStyle/RMBG-1.4"          "LayerStyle RMBG"
make_link "$MODELS/rembg/RMBG-1.4"              "$NODES/ComfyUI-Video-Matting/ckpts"           "Video-Matting ckpts"
make_link "$MODELS/rembg/RMBG-1.4"              "$NODES/ComfyUI-BRIA_AI-RMBG/RMBG-1.4"        "BRIA RMBG"

# Fonts
make_link "$MODELS/fonts"                        "$NODES/ComfyUI_Comfyroll_CustomNodes/fonts"  "Comfyroll fonts"
make_link "$MODELS/fonts"                        "$NODES/Comfyui-ergouzi-Nodes/fonts"          "ergouzi fonts"
make_link "$MODELS/fonts"                        "$NODES/ComfyUI_LayerStyle/font"              "LayerStyle font"
make_link "$MODELS/fonts"                        "$NODES/ComfyUI_LayerStyle_Advance/font"      "LayerStyle_Advance font"
make_link "$MODELS/fonts"                        "$NODES/ComfyUI_essentials/fonts"             "essentials fonts"
make_link "$MODELS/fonts"                        "$NODES/ComfyUI_essentials_mb/fonts"          "essentials_mb fonts"
make_link "$MODELS/fonts"                        "$NODES/ComfyUI-KJNodes/fonts"                "KJNodes fonts"

# LUTs
make_link "$MODELS/luts"                         "$NODES/ComfyUI_essentials/luts"              "essentials luts"
make_link "$MODELS/luts"                         "$NODES/ComfyUI_essentials_mb/luts"           "essentials_mb luts"
make_link "$MODELS/luts"                         "$NODES/ComfyUI_LayerStyle/lut"               "LayerStyle lut"

echo ""
echo "=== Done ==="
