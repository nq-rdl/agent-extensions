#!/usr/bin/env bash
# ensure-deps.sh — Portable dependency bootstrap.
#
# Detects the user's preferred Python package manager and installs
# dependencies from this skill's requirements.txt. Falls back through:
#   pixi > uv > mamba > conda > pip
#
# If no tool is found, prints install suggestions and exits non-zero
# so the calling agent can relay the message to the user.
#
# Usage:
#   bash scripts/ensure-deps.sh [--check-only]
#
# The script is idempotent — safe to call on every script invocation.
# It checks whether packages are already importable before installing.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REQ_FILE="${SKILL_DIR}/requirements.txt"

CHECK_ONLY=false
[[ "${1:-}" == "--check-only" ]] && CHECK_ONLY=true

if [[ ! -f "$REQ_FILE" ]]; then
  echo "Error: ${REQ_FILE} not found" >&2
  exit 1
fi

# ── Read package names (strip version specs + comments) ───────────────
PACKAGES=()
while IFS= read -r line; do
  line="${line%%#*}"           # strip comments
  line="${line// /}"           # strip spaces
  [[ -z "$line" ]] && continue
  pkg="${line%%[>=<~!]*}"     # strip version specifier
  PACKAGES+=("$pkg")
done < "$REQ_FILE"

[[ ${#PACKAGES[@]} -eq 0 ]] && exit 0

# ── Check if all packages are already importable ──────────────────────
all_importable() {
  local python_cmd="${1:-python3}"
  for pkg in "${PACKAGES[@]}"; do
    local import_name="$pkg"
    case "$pkg" in
      pymupdf4llm)     import_name="pymupdf4llm" ;;
      pdfminer-six)    import_name="pdfminer" ;;
      pdfminer.six)    import_name="pdfminer" ;;
      python-docx)     import_name="docx" ;;
      Pillow|pillow)   import_name="PIL" ;;
      scikit-learn)    import_name="sklearn" ;;
      beautifulsoup4)  import_name="bs4" ;;
    esac
    import_name="${import_name//-/_}"
    if ! "$python_cmd" -c "import ${import_name}" 2>/dev/null; then
      return 1
    fi
  done
  return 0
}

if all_importable python3; then
  exit 0
fi

if [[ "$CHECK_ONLY" == true ]]; then
  echo "Missing dependencies. Run: bash scripts/ensure-deps.sh" >&2
  exit 1
fi

# ── Detect available package managers (priority order) ────────────────
install_with_pixi() {
  echo "Installing deps with pixi..."
  local tmp_toml="${SKILL_DIR}/pixi.toml"
  local created_toml=false

  if [[ ! -f "$tmp_toml" ]] && [[ ! -f "${SKILL_DIR}/pyproject.toml" ]]; then
    created_toml=true
    cat > "$tmp_toml" <<TOML
[project]
name = "$(basename "$SKILL_DIR")-deps"
version = "0.1.0"
channels = ["conda-forge"]
platforms = ["$(pixi info --json 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin).get("platform","linux-64"))' 2>/dev/null || echo linux-64)"]

[pypi-dependencies]
TOML
    while IFS= read -r line; do
      line="${line%%#*}"; line="${line// /}"
      [[ -z "$line" ]] && continue
      local pkg_name="${line%%[>=<~!]*}"
      local version_spec="${line#"$pkg_name"}"
      if [[ -n "$version_spec" ]]; then
        echo "${pkg_name} = \"${version_spec}\"" >> "$tmp_toml"
      else
        echo "${pkg_name} = \"*\"" >> "$tmp_toml"
      fi
    done < "$REQ_FILE"
  fi

  (cd "$SKILL_DIR" && pixi install)
  local rc=$?
  [[ "$created_toml" == true ]] && [[ $rc -ne 0 ]] && rm -f "$tmp_toml"
  return $rc
}

install_with_uv()    { echo "Installing deps with uv...";    uv pip install -r "$REQ_FILE"; }
install_with_mamba() { echo "Installing deps with mamba..."; mamba install -y --file "$REQ_FILE" -c conda-forge; }
install_with_conda() { echo "Installing deps with conda..."; conda install -y --file "$REQ_FILE" -c conda-forge; }
install_with_pip()   { echo "Installing deps with pip...";   pip install -r "$REQ_FILE"; }

TOOLS=(pixi uv mamba conda pip)
INSTALLERS=(install_with_pixi install_with_uv install_with_mamba install_with_conda install_with_pip)

for i in "${!TOOLS[@]}"; do
  if command -v "${TOOLS[$i]}" &>/dev/null; then
    if ${INSTALLERS[$i]}; then
      echo "Dependencies installed successfully with ${TOOLS[$i]}."
      exit 0
    else
      echo "Warning: ${TOOLS[$i]} install failed, trying next tool..." >&2
    fi
  fi
done

cat >&2 <<'MSG'
No supported Python package manager found.

Install one of the following (recommended first):

  pixi:  curl -fsSL https://pixi.sh/install.sh | bash
  uv:    curl -LsSf https://astral.sh/uv/install.sh | sh
  conda: https://docs.conda.io/projects/conda/en/latest/user-guide/install/
  pip:   Usually ships with Python — try: python3 -m ensurepip

Then re-run the script that triggered this message.
MSG
exit 1
