#!/usr/bin/env bash
# Install the pinned Vale release without needing Go or Homebrew.
#
# Vale is distributed as a single binary. This downloads the exact release the
# rules were tested against, checks it against a known checksum, and puts it in
# ~/.local/bin. Nothing else on the machine is touched.
set -euo pipefail

VERSION="${VALE_VERSION:-3.9.6}"
DEST="${VALE_DEST:-$HOME/.local/bin}"

case "$(uname -s)/$(uname -m)" in
  Linux/x86_64)  ASSET="Linux_64-bit"  ; SHA="dd8519d9bdf381a3b1a30f1df7f6e589b69ec1e38a495e4bd9af8e450703dde0" ;;
  Linux/aarch64) ASSET="Linux_arm64"   ; SHA="d3da89ad03978db78b1d20bb44440e6942f2c391503786ef0f15ce188640b8da" ;;
  Darwin/x86_64) ASSET="macOS_64-bit"  ; SHA="b08e27d90fb3d0c7089faa074cbd82a30cc113cb061364e7c8b9df581e005903" ;;
  Darwin/arm64)  ASSET="macOS_arm64"   ; SHA="121ec76e2d862cb145416b132e4321cb352de8cf69ad81d4fdb91068b1f40024" ;;
  *) echo "No pinned build for $(uname -s)/$(uname -m)."
     echo "Install Vale yourself from https://vale.sh and re-run."; exit 1 ;;
esac

if [ "$VERSION" != "3.9.6" ]; then
  echo "Note: only 3.9.6 has a pinned checksum here; ${VERSION} will not be verified."
  SHA=""
fi

TARBALL="vale_${VERSION}_${ASSET}.tar.gz"
URL="https://github.com/errata-ai/vale/releases/download/v${VERSION}/${TARBALL}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Downloading Vale ${VERSION} for ${ASSET}..."
curl -sSLf --retry 3 --retry-delay 2 "$URL" -o "$TMP/$TARBALL"

if [ -n "$SHA" ]; then
  echo "Verifying checksum..."
  if command -v sha256sum >/dev/null 2>&1; then
    echo "${SHA}  ${TMP}/${TARBALL}" | sha256sum -c - >/dev/null
  else
    echo "${SHA}  ${TMP}/${TARBALL}" | shasum -a 256 -c - >/dev/null
  fi
fi

tar -xzf "$TMP/$TARBALL" -C "$TMP" vale
mkdir -p "$DEST"
install -m 0755 "$TMP/vale" "$DEST/vale"

echo "Installed: $DEST/vale ($("$DEST/vale" --version))"
case ":$PATH:" in
  *":$DEST:"*) ;;
  *) echo
     echo "$DEST is not on your PATH. Add this line to your shell profile"
     echo "(~/.zshrc on a Mac, ~/.bashrc on Linux), then open a new terminal:"
     echo
     echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
     ;;
esac
