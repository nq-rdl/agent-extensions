#!/usr/bin/env bash
# Preview by default; --yes authorizes package installation and pinned binary download.
set -eu
set -o pipefail
version=3.13.3
case "${1:-}" in
  '') execute=no ;;
  --yes) execute=yes ;;
  *) echo 'Usage: rh-install-sops-age.sh [--yes]' >&2; exit 2 ;;
esac
[ "$#" -le 1 ] || { echo 'Usage: rh-install-sops-age.sh [--yes]' >&2; exit 2; }
case "$(uname -s)" in
  Linux) os=linux ;;
  Darwin) os=darwin ;;
  *) echo 'Supported platforms: Linux and macOS.' >&2; exit 2 ;;
esac
case "$(uname -m)" in
  x86_64|amd64) arch=amd64 ;;
  aarch64|arm64) arch=arm64 ;;
  *) echo 'Supported architectures: amd64 and arm64.' >&2; exit 2 ;;
esac
manager=none
if ! command -v age >/dev/null 2>&1 || ! command -v age-keygen >/dev/null 2>&1; then
  if [ "$os" = darwin ] && command -v brew >/dev/null 2>&1; then manager=brew
  elif [ "$os" = linux ] && command -v dnf >/dev/null 2>&1; then manager=dnf
  elif [ "$os" = linux ] && command -v apt-get >/dev/null 2>&1; then manager=apt-get
  else echo 'Install age and age-keygen via your trusted package manager first.' >&2; exit 2
  fi
fi
asset="sops-v$version.$os.$arch"
checksums="sops-v$version.checksums.txt"
base="https://github.com/getsops/sops/releases/download/v$version"
bin="$HOME/.local/bin"
printf 'sops pin: %s; platform: %s/%s; destination: %s/sops\n' "$version" "$os" "$arch" "$bin"
case "$manager" in
  brew) echo 'brew install age' ;;
  dnf) echo 'sudo dnf install -y age (EL9 requires EPEL already enabled; no repo changes are made)' ;;
  apt-get) echo 'sudo apt-get install -y age' ;;
esac
printf 'Download %s/%s and %s; verify the single exact SHA-256 entry before install -m 0755.\n' "$base" "$asset" "$checksums"
printf 'Ensure %s is on PATH (restart the agent if its launch PATH changes).\n' "$bin"
[ "$execute" = yes ] || { echo 'Preview only. Run this helper with --yes after approving the plan.'; exit 0; }
command -v curl >/dev/null 2>&1 || { echo 'Install curl first.' >&2; exit 2; }
if command -v sha256sum >/dev/null 2>&1; then hash=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then hash=(shasum -a 256)
else echo 'Install sha256sum or shasum first.' >&2; exit 2
fi
case "$manager" in
  brew) brew install age ;;
  apt-get) sudo apt-get install -y age ;;
  dnf)
    if ! sudo dnf install -y age; then
      echo 'dnf failed: age needs EPEL on EL9. An unrelated repo/GPG failure can also block any install; inspect the error and retry manually with --disablerepo=<broken-repo>. Do not disable GPG checks.' >&2
      exit 2
    fi ;;
esac
command -v age >/dev/null 2>&1 && command -v age-keygen >/dev/null 2>&1 || { echo 'Package install did not provide age and age-keygen on PATH.' >&2; exit 2; }
umask 077
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
trap 'exit 2' HUP INT TERM
cd "$tmp"
curl --fail --show-error --silent --location --proto '=https' --proto-redir '=https' -o "$asset" "$base/$asset"
curl --fail --show-error --silent --location --proto '=https' --proto-redir '=https' -o "$checksums" "$base/$checksums"
# No --ignore-missing: require exactly one entry for the selected raw binary.
awk -v asset="$asset" '$2 == asset || $2 == "*" asset {print; n++} END {if (n != 1) exit 1}' "$checksums" > selected.sha256 || { echo 'Missing/duplicate binary checksum; nothing installed.' >&2; exit 2; }
"${hash[@]}" -c selected.sha256 || { echo 'Checksum mismatch; nothing installed.' >&2; exit 2; }
chmod 700 "$asset"
reported="$(./"$asset" --version)"
case "$reported" in
  "sops $version"|"sops $version "*) ;;
  *) echo 'Unexpected sops version (requires pinned 3.13.3, minimum 3.10); nothing installed.' >&2; exit 2 ;;
esac
mkdir -p "$bin"
# Stage on the destination filesystem so a failed copy cannot damage an old binary.
staged="$(mktemp "$bin/.sops.XXXXXX")"
trap 'rm -rf "$tmp"; rm -f "$staged"' EXIT
install -m 0755 "$asset" "$staged"
mv -f "$staged" "$bin/sops"
echo 'Installed verified sops 3.13.3.'
