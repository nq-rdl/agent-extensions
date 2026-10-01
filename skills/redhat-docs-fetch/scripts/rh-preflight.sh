#!/usr/bin/env bash
# Report what this machine can do for Red Hat docs fetching. Never prints secrets.
#
#   rh-preflight.sh            # one human-readable line
#   rh-preflight.sh --json     # tools (including sops/age/age-plugin-tpm) + credential
#   rh-preflight.sh --require-cred   # exit 3 (with a /redhat:setup hint) when no credential is found
#
# Credential detection honours RH_CRED_SOURCES (default env,keychain,sops,file,bitwarden)
# and RH_OFFLINE_TOKEN_FILE / RH_OFFLINE_TOKEN_SOPS_FILE; reports SOURCE only, never values.
set -u
# shellcheck source=rh-lib.sh
. "$(cd "$(dirname "$0")" && pwd)/rh-lib.sh"
. "$(cd "$(dirname "$0")" && pwd)/rh-age-lib.sh"
tpm="$(rh_tpm_status)"
tpm_hint=''
[ "$tpm" != present ] || tpm_hint='TPM present but inaccessible: ask the administrator about adding your user to the tss group, then log in again; device group policy may differ.'

mode="${1:-text}"
os="$(rh_os)"; arch="$(uname -m 2>/dev/null || echo unknown)"; fetcher="$(rh_fetcher)"
has() { command -v "$1" >/dev/null 2>&1 && echo yes || echo no; }
jq_ok="$(has jq)"; gh_ok="$(has gh)"; bw_ok="$(has bw)"
sops_ok="$(has sops)"; age_ok="$(has age)"; tpm_ok="$(has age-plugin-tpm)"
cred="$(rh_cred_source 2>/dev/null || true)"; [ -n "$cred" ] || cred=none

case "$mode" in
  --json)
    printf '{"os":"%s","arch":"%s","fetcher":"%s","jq":"%s","gh":"%s","bw":"%s","sops":"%s","age":"%s","age-plugin-tpm":"%s","tpm":"%s","tpm_hint":"%s","credential":"%s","setup_hint":"%s"}\n' \
      "$os" "$arch" "$fetcher" "$jq_ok" "$gh_ok" "$bw_ok" "$sops_ok" "$age_ok" "$tpm_ok" "$tpm" "$tpm_hint" "$cred" "$( [ "$cred" = none ] && printf '%s' "$RH_SETUP_HINT" )" ;;
  --require-cred)
    if [ "$cred" = none ]; then
      echo "No Red Hat offline token found (looked in: $RH_CRED_SOURCES). $RH_SETUP_HINT" >&2; exit 3
    fi
    echo "credential=$cred" ;;
  *)
    line="OS=$os/$arch; fetcher=$fetcher; jq=$jq_ok; gh=$gh_ok; bw=$bw_ok; sops=$sops_ok; age=$age_ok; age-plugin-tpm=$tpm_ok; tpm=$tpm; credential=$cred"
    [ -z "$tpm_hint" ] || line="$line; $tpm_hint"
    [ "$cred" = none ] && line="$line (no RH_OFFLINE_TOKEN in $RH_CRED_SOURCES — /redhat:setup guides generating and storing one)"
    [ "$fetcher" = none ] && line="$line; WARNING: neither curl nor wget found"
    printf '%s\n' "$line" ;;
esac
exit 0
