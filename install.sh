#!/bin/sh
# okapi installer — downloads the latest standalone binary from GitHub Releases.
#   curl -fsSL https://raw.githubusercontent.com/oussamachaabounii/okapi/main/install.sh | sh
set -eu

REPO="oussamachaabounii/okapi"
INSTALL_DIR="${OKAPI_INSTALL_DIR:-$HOME/.local/bin}"

case "$(uname -s)" in
    Darwin)
        case "$(uname -m)" in
            arm64) ASSET="okapi-macos-arm64" ;;
            *)     ASSET="okapi-macos-x64" ;;
        esac ;;
    Linux)  ASSET="okapi-linux-x64" ;;
    *) echo "unsupported OS: $(uname -s) — on Windows, download okapi-windows-x64.exe from https://github.com/$REPO/releases" >&2; exit 1 ;;
esac

URL="https://github.com/$REPO/releases/latest/download/$ASSET"
mkdir -p "$INSTALL_DIR"
echo "downloading $ASSET → $INSTALL_DIR/okapi"
curl -fSL --progress-bar "$URL" -o "$INSTALL_DIR/okapi"
chmod +x "$INSTALL_DIR/okapi"

# macOS Gatekeeper quarantines downloaded binaries; clear it if present.
if [ "$(uname -s)" = "Darwin" ]; then
    xattr -d com.apple.quarantine "$INSTALL_DIR/okapi" 2>/dev/null || true
fi

echo "installed: $("$INSTALL_DIR/okapi" --version)"
case ":$PATH:" in
    *":$INSTALL_DIR:"*) ;;
    *) echo "note: $INSTALL_DIR is not on your PATH — add this to your shell profile:"
       echo "  export PATH=\"$INSTALL_DIR:\$PATH\"" ;;
esac
