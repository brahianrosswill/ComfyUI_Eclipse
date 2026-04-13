#!/usr/bin/env bash
# Remove extracted default files from Eclipse and SmartLML data folders.
# Re-extracted automatically on next ComfyUI startup from .defaults/

ECLIPSE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SMARTLML_DIR="$(cd "$ECLIPSE_DIR/../ComfyUI_SmartLML" 2>/dev/null && pwd)"

echo "Clearing Eclipse data folders..."
for folder in prompts patterns styles templates wildcards; do
    target="$ECLIPSE_DIR/$folder"
    if [ -d "$target" ]; then
        rm -rf "$target"
        echo "  Removed $folder/"
    fi
done
# Remove root config.json (re-extracted from .defaults/)
[ -f "$ECLIPSE_DIR/config.json" ] && rm -f "$ECLIPSE_DIR/config.json" && echo "  Removed config.json"

if [ -d "$SMARTLML_DIR" ]; then
    echo "Clearing SmartLML data folders..."
    for folder in templates config; do
        target="$SMARTLML_DIR/$folder"
        if [ -d "$target" ]; then
            rm -rf "$target"
            echo "  Removed $folder/"
        fi
    done
    # Remove root configs (re-extracted from .defaults/)
    for cfg in config.json docker_config.json; do
        [ -f "$SMARTLML_DIR/$cfg" ] && rm -f "$SMARTLML_DIR/$cfg" && echo "  Removed $cfg"
    done
else
    echo "SmartLML not found at $SMARTLML_DIR, skipping."
fi

echo "Done. Files will be re-extracted on next ComfyUI startup."
