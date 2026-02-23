#!/bin/bash
# Remove passwordless sudo configuration for file cache clearing
# This undoes what setup_cache_clearing.sh configured

set -e

echo "=== ComfyUI Cache Clearing Removal ==="
echo ""
echo "This script will remove the passwordless sudo configuration"
echo "for file cache clearing."
echo ""

SUDOERS_FILE="/etc/sudoers.d/comfyui-cache"
SYSTEM_WRAPPER="/usr/local/bin/comfyui-drop-pagecache"

# Check if anything is installed
if [ ! -f "$SUDOERS_FILE" ] && [ ! -f "$SYSTEM_WRAPPER" ]; then
    echo "Nothing to remove - cache clearing was not configured."
    exit 0
fi

echo "The following will be removed:"
[ -f "$SUDOERS_FILE" ] && echo "  - Sudoers rule: $SUDOERS_FILE"
[ -f "$SYSTEM_WRAPPER" ] && echo "  - Wrapper script: $SYSTEM_WRAPPER"
echo ""

# Remove sudoers rule
if [ -f "$SUDOERS_FILE" ]; then
    echo "Removing sudoers rule..."
    sudo rm -f "$SUDOERS_FILE"
    echo "✓ Removed $SUDOERS_FILE"
fi

# Remove wrapper script
if [ -f "$SYSTEM_WRAPPER" ]; then
    echo "Removing wrapper script..."
    sudo rm -f "$SYSTEM_WRAPPER"
    echo "✓ Removed $SYSTEM_WRAPPER"
fi

echo ""
echo "=== Removal Complete ==="
echo "Cache clearing permissions have been revoked."
echo "The RAM Cleanup node will now skip file cache clearing on Linux"
echo "(other cleanup operations will still work)."
