#!/bin/bash
set -e

# This script downloads the argocd CLI.

OS="$(uname | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

if [[ "$ARCH" == "x86_64" ]]; then
    ARCH="amd64"
elif [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]]; then
    ARCH="arm64"
fi

if [[ "$OS" == "linux" || "$OS" == "darwin" ]]; then
    VERSION=$(curl -L -s https://raw.githubusercontent.com/argoproj/argo-cd/stable/VERSION)
    if [[ -z "$VERSION" ]]; then
        echo "Failed to get ArgoCD version."
        exit 1
    fi
    BINARY_URL="https://github.com/argoproj/argo-cd/releases/download/v$VERSION/argocd-$OS-$ARCH"
    CHECKSUM_URL="$BINARY_URL.sha256"

    echo "Downloading ArgoCD version v$VERSION for $OS-$ARCH..."
    curl -sSL -o argocd "$BINARY_URL"
    curl -sSL -o argocd.sha256 "$CHECKSUM_URL"

    echo "Verifying SHA-256 checksum..."
    EXPECTED=$(awk '{print $1}' argocd.sha256)
    ACTUAL=$(sha256sum argocd | awk '{print $1}')
    rm -f argocd.sha256

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
else
    echo "Unsupported OS: $OS"
    exit 1
fi
