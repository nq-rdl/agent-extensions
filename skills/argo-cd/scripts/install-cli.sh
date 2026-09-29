#!/bin/bash
set -e

# This script downloads the argocd CLI into the current directory and
# verifies it against the release's cli_checksums.txt.

OS="$(uname | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

if [[ "$ARCH" == "x86_64" ]]; then
    ARCH="amd64"
elif [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]]; then
    ARCH="arm64"
fi

if [[ "$OS" != "linux" && "$OS" != "darwin" ]]; then
    echo "Unsupported OS: $OS"
    exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
    SHA256="sha256sum"
elif command -v shasum >/dev/null 2>&1; then
    SHA256="shasum -a 256"
else
    echo "Neither sha256sum nor shasum is available."
    exit 1
fi

VERSION=$(curl -fsSL https://raw.githubusercontent.com/argoproj/argo-cd/stable/VERSION)
if [[ -z "$VERSION" ]]; then
    echo "Failed to get ArgoCD version."
    exit 1
fi

ASSET="argocd-$OS-$ARCH"
BASE_URL="https://github.com/argoproj/argo-cd/releases/download/v$VERSION"

echo "Downloading ArgoCD version v$VERSION for $OS-$ARCH..."
curl -fsSL -o argocd "$BASE_URL/$ASSET"
curl -fsSL -o argocd-cli_checksums.txt "$BASE_URL/cli_checksums.txt"

echo "Verifying SHA-256 checksum..."
EXPECTED=$(awk -v a="$ASSET" '$2 == a {print $1}' argocd-cli_checksums.txt)
rm -f argocd-cli_checksums.txt
if [[ -z "$EXPECTED" ]]; then
    echo "No checksum for $ASSET in cli_checksums.txt."
    rm -f argocd
    exit 1
fi
ACTUAL=$($SHA256 argocd | awk '{print $1}')

if [[ "$EXPECTED" != "$ACTUAL" ]]; then
    echo "Checksum verification failed!"
    echo "  Expected: $EXPECTED"
    echo "  Got:      $ACTUAL"
    rm -f argocd
    exit 1
fi
echo "Checksum verified."

chmod +x argocd
echo "Installed argocd in the current directory."
echo "You can move it to your PATH: sudo mv argocd /usr/local/bin/"
