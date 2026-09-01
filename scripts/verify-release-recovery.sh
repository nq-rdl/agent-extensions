#!/usr/bin/env bash
# Guarded production drill for release-finalize.yml's recovery paths.
#
# The GitHub workflows call this script in separate jobs so no orchestration job
# holds the shared release-finalize concurrency group while waiting for a
# Finalize re-run. A baseline artifact is uploaded before deletion. A separate
# workflow_run watchdog consumes that artifact after success, failure, timeout,
# or cancellation and restores the supported release metadata when necessary.
set -euo pipefail

GH_BIN="${GH_BIN:-gh}"
GIT_BIN="${GIT_BIN:-git}"
JQ_BIN="${JQ_BIN:-jq}"
POLL_INTERVAL="${POLL_INTERVAL:-5}"
POLL_ATTEMPTS="${POLL_ATTEMPTS:-180}"

fail() {
  echo "::error::$*" >&2
  exit 1
}

usage() {
  echo "usage: $0 {capture|queue-noop|verify-noop|queue-recovery|verify-recovery|watchdog} BASELINE_DIR" >&2
  exit 2
}

[[ $# -eq 2 ]] || usage
COMMAND="$1"
BASELINE_DIR="$2"
case "$COMMAND" in
  capture|queue-noop|verify-noop|queue-recovery|verify-recovery|watchdog) ;;
  *) usage ;;
esac

for name in GITHUB_REPOSITORY GITHUB_TOKEN; do
  [[ -n "${!name:-}" ]] || fail "$name must be set"
done
[[ "$GITHUB_REPOSITORY" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] \
  || fail "invalid GITHUB_REPOSITORY '$GITHUB_REPOSITORY'"
[[ "$POLL_INTERVAL" =~ ^[0-9]+$ && "$POLL_ATTEMPTS" =~ ^[1-9][0-9]*$ ]] \
  || fail "POLL_INTERVAL and POLL_ATTEMPTS must be non-negative/positive integers"

CONTEXT_FILE="$BASELINE_DIR/context.json"
RELEASE_FILE="$BASELINE_DIR/release.json"
BODY_FILE="$BASELINE_DIR/release-body.md"
CURRENT_BODY_FILE="$BASELINE_DIR/current-release-body.md"

run_actions_gh() {
  GH_TOKEN="$GITHUB_TOKEN" "$GH_BIN" "$@"
}

run_release_gh() {
  [[ -n "${RELEASE_TOKEN:-}" ]] || fail "RELEASE_TOKEN must be set for $COMMAND"
  GH_TOKEN="$RELEASE_TOKEN" "$GH_BIN" "$@"
}

remote_main_version() {
  local value
  value="$(run_actions_gh api \
    -H 'Accept: application/vnd.github.raw+json' \
    "repos/$GITHUB_REPOSITORY/contents/VERSION?ref=main")"
  printf '%s' "$value" | tr -d '[:space:]'
}

load_context() {
  [[ -f "$CONTEXT_FILE" && -f "$RELEASE_FILE" && -f "$BODY_FILE" ]] \
    || fail "baseline artifact is incomplete"

  VERSION="$("$JQ_BIN" -r '.version' "$CONTEXT_FILE")"
  TAG="$("$JQ_BIN" -r '.tag' "$CONTEXT_FILE")"
  BRANCH="$("$JQ_BIN" -r '.branch' "$CONTEXT_FILE")"
  PR_NUMBER="$("$JQ_BIN" -r '.pr_number' "$CONTEXT_FILE")"
  PR_HEAD_SHA="$("$JQ_BIN" -r '.pr_head_sha' "$CONTEXT_FILE")"
  MERGE_SHA="$("$JQ_BIN" -r '.merge_sha' "$CONTEXT_FILE")"
  RUN_ID="$("$JQ_BIN" -r '.run_id' "$CONTEXT_FILE")"
  WORKFLOW_ID="$("$JQ_BIN" -r '.workflow_id' "$CONTEXT_FILE")"
  INITIAL_ATTEMPT="$("$JQ_BIN" -r '.initial_attempt' "$CONTEXT_FILE")"
  WAS_LATEST="$("$JQ_BIN" -r '.was_latest' "$CONTEXT_FILE")"

  [[ "$VERSION" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] \
    || fail "baseline version is malformed"
  [[ "$TAG" == "v$VERSION" && "$BRANCH" == "release/v$VERSION" ]] \
    || fail "baseline tag/branch does not match version $VERSION"
  [[ "$PR_NUMBER" =~ ^[1-9][0-9]*$ && "$RUN_ID" =~ ^[1-9][0-9]*$ \
    && "$WORKFLOW_ID" =~ ^[1-9][0-9]*$ && "$INITIAL_ATTEMPT" =~ ^[1-9][0-9]*$ ]] \
    || fail "baseline numeric metadata is malformed"
  [[ "$PR_HEAD_SHA" =~ ^[0-9a-f]{40,64}$ && "$MERGE_SHA" =~ ^[0-9a-f]{40,64}$ ]] \
    || fail "baseline commit metadata is malformed"
  [[ "$WAS_LATEST" == true ]] || fail "baseline release was not Latest"
}

assert_current_main() {
  local remote_version
  remote_version="$(remote_main_version)"
  [[ "$remote_version" == "$VERSION" ]] \
    || fail "main moved to VERSION $remote_version; refusing to alter release $TAG"
}

assert_tag_targets_merge() {
  local tag_line tag_commit
  tag_line="$("$GIT_BIN" ls-remote --exit-code --tags origin "refs/tags/$TAG^{}")" \
    || fail "annotated tag $TAG is missing or could not be read"
  tag_commit="${tag_line%%$'\t'*}"
  [[ "$tag_commit" == "$MERGE_SHA" ]] \
    || fail "$TAG points at $tag_commit, not release PR merge commit $MERGE_SHA"
}

probe_release() {
  local rc=0 output
  output="$(run_actions_gh api "repos/$GITHUB_REPOSITORY/releases/tags/$TAG" 2>&1)" || rc=$?
  if [[ "$rc" -eq 0 ]]; then
    RELEASE_STATE=exists
    RELEASE_JSON="$output"
    return 0
  fi
  if [[ "$rc" -eq 1 && "${output,,}" == *"http 404"* ]]; then
    RELEASE_STATE=missing
    RELEASE_JSON=""
    return 0
  fi
  fail "release probe for $TAG failed (exit $rc): $output"
}

latest_release_tag() {
  local rc=0 output
  output="$(run_actions_gh api "repos/$GITHUB_REPOSITORY/releases/latest" --jq '.tag_name' 2>&1)" || rc=$?
  if [[ "$rc" -eq 0 ]]; then
    printf '%s' "$output"
    return 0
  fi
  if [[ "$rc" -eq 1 && "${output,,}" == *"http 404"* ]]; then
    return 0
  fi
  fail "latest-release probe failed (exit $rc): $output"
}

assert_safe_release_json() {
  local release_json="$1"
  printf '%s' "$release_json" | "$JQ_BIN" -e \
    '.draft == false and .prerelease == false and .immutable == false and
     (.assets | length) == 0 and .discussion_url == null' >/dev/null \
    || fail "$TAG must be published, mutable, non-prerelease, asset-free, and have no linked discussion"
}

release_matches_baseline() {
  local release_json baseline_json field expected actual
  probe_release
  [[ "$RELEASE_STATE" == exists ]] || return 1
  release_json="$RELEASE_JSON"
  baseline_json="$(cat "$RELEASE_FILE")"
  printf '%s' "$release_json" | "$JQ_BIN" -e \
    '.draft == false and .prerelease == false and .immutable == false and
     (.assets | length) == 0 and .discussion_url == null' >/dev/null \
    || return 1

  for field in tag_name name draft prerelease immutable target_commitish discussion_url; do
    expected="$(printf '%s' "$baseline_json" | "$JQ_BIN" -c ".$field")"
    actual="$(printf '%s' "$release_json" | "$JQ_BIN" -c ".$field")"
    [[ "$actual" == "$expected" ]] || return 1
  done
  expected="$(printf '%s' "$baseline_json" | "$JQ_BIN" -r '.author.login')"
  actual="$(printf '%s' "$release_json" | "$JQ_BIN" -r '.author.login')"
  [[ "$actual" == "$expected" ]] || return 1

  printf '%s' "$release_json" | "$JQ_BIN" -j '.body' > "$CURRENT_BODY_FILE"
  cmp -s "$BODY_FILE" "$CURRENT_BODY_FILE"
}

assert_release_matches_baseline() {
  release_matches_baseline \
    || fail "release $TAG is missing or its supported metadata/body differs from the baseline"
}

desired_latest_tag() {
  printf 'v%s' "$(remote_main_version)"
}

assert_latest_is_safe() {
  local latest desired
  latest="$(latest_release_tag)"
  desired="$(desired_latest_tag)"
  [[ "$latest" == "$desired" ]] \
    || fail "Latest release is '$latest'; current main requires '$desired'"
}

reconcile_latest() {
  local latest desired
  latest="$(latest_release_tag)"
  desired="$(desired_latest_tag)"
  if [[ "$latest" == "$desired" ]]; then
    return 0
  fi
  run_release_gh release edit "$desired" --repo "$GITHUB_REPOSITORY" --latest >/dev/null
  [[ "$(latest_release_tag)" == "$desired" ]] \
    || fail "could not reconcile Latest release to $desired"
  echo "::notice::Reconciled Latest release from '$latest' to '$desired'."
}

assert_release_absent() {
  probe_release
  [[ "$RELEASE_STATE" == missing ]] || fail "release $TAG still exists after deletion"
}

read_run() {
  RUN_JSON="$(run_actions_gh api "repos/$GITHUB_REPOSITORY/actions/runs/$RUN_ID")"
  local event head_branch head_sha path workflow_id
  event="$(printf '%s' "$RUN_JSON" | "$JQ_BIN" -r '.event')"
  head_branch="$(printf '%s' "$RUN_JSON" | "$JQ_BIN" -r '.head_branch')"
  head_sha="$(printf '%s' "$RUN_JSON" | "$JQ_BIN" -r '.head_sha')"
  path="$(printf '%s' "$RUN_JSON" | "$JQ_BIN" -r '.path')"
  path="${path%%@*}"
  workflow_id="$(printf '%s' "$RUN_JSON" | "$JQ_BIN" -r '.workflow_id')"
  [[ "$event" == pull_request && "$head_branch" == "$BRANCH" \
    && "$head_sha" == "$PR_HEAD_SHA" && "$workflow_id" == "$WORKFLOW_ID" \
    && "$path" == .github/workflows/release-finalize.yml ]] \
    || fail "Finalize run $RUN_ID no longer matches workflow $WORKFLOW_ID and PR #$PR_NUMBER head $PR_HEAD_SHA"
}

queue_exact_rerun() {
  local previous_attempt="$1" attempt status conclusion
  read_run
  attempt="$(printf '%s' "$RUN_JSON" | "$JQ_BIN" -r '.run_attempt')"
  status="$(printf '%s' "$RUN_JSON" | "$JQ_BIN" -r '.status')"
  conclusion="$(printf '%s' "$RUN_JSON" | "$JQ_BIN" -r '.conclusion // ""')"
  [[ "$attempt" == "$previous_attempt" && "$status" == completed && "$conclusion" == success ]] \
    || fail "Finalize run $RUN_ID is not the expected successful attempt $previous_attempt"
  run_actions_gh api --method POST \
    "repos/$GITHUB_REPOSITORY/actions/runs/$RUN_ID/rerun" >/dev/null
}

wait_for_exact_attempt() {
  local expected_attempt="$1" attempt status conclusion poll
  for ((poll = 1; poll <= POLL_ATTEMPTS; poll++)); do
    read_run
    attempt="$(printf '%s' "$RUN_JSON" | "$JQ_BIN" -r '.run_attempt')"
    status="$(printf '%s' "$RUN_JSON" | "$JQ_BIN" -r '.status')"
    conclusion="$(printf '%s' "$RUN_JSON" | "$JQ_BIN" -r '.conclusion // ""')"
    [[ "$attempt" =~ ^[1-9][0-9]*$ ]] || fail "Finalize run returned malformed attempt '$attempt'"
    ((attempt <= expected_attempt)) \
      || fail "Finalize run advanced to unexpected attempt $attempt; expected exactly $expected_attempt"
    if [[ "$attempt" == "$expected_attempt" && "$status" == completed ]]; then
      [[ "$conclusion" == success ]] \
        || fail "Finalize attempt $attempt completed with conclusion '$conclusion'"
      return 0
    fi
    sleep "$POLL_INTERVAL"
  done
  fail "timed out waiting for Finalize run $RUN_ID attempt $expected_attempt"
}

assert_finalize_steps() {
  local attempt="$1" expected_tag="$2" expected_prepare="$3" expected_release="$4"
  local jobs_json job_count job_conclusion step_count actual step expected
  jobs_json="$(run_actions_gh api \
    "repos/$GITHUB_REPOSITORY/actions/runs/$RUN_ID/attempts/$attempt/jobs?per_page=100")"
  job_count="$(printf '%s' "$jobs_json" | "$JQ_BIN" -r '[.jobs[] | select(.name == "finalize")] | length')"
  [[ "$job_count" == 1 ]] || fail "Finalize attempt $attempt has $job_count finalize jobs"
  job_conclusion="$(printf '%s' "$jobs_json" | "$JQ_BIN" -r '.jobs[] | select(.name == "finalize") | .conclusion')"
  [[ "$job_conclusion" == success ]] || fail "Finalize job attempt $attempt concluded '$job_conclusion'"

  for step in \
    "Derive and verify version:success" \
    "Tag the release commit:$expected_tag" \
    "Prepare release notes:$expected_prepare" \
    "Create GitHub release:$expected_release"; do
    expected="${step##*:}"
    step="${step%:*}"
    step_count="$(printf '%s' "$jobs_json" | "$JQ_BIN" --arg step "$step" -r \
      '[.jobs[] | select(.name == "finalize") | .steps[] | select(.name == $step)] | length')"
    [[ "$step_count" == 1 ]] || fail "Finalize attempt $attempt has $step_count '$step' steps"
    actual="$(printf '%s' "$jobs_json" | "$JQ_BIN" --arg step "$step" -r \
      '.jobs[] | select(.name == "finalize") | .steps[] | select(.name == $step) | .conclusion')"
    [[ "$actual" == "$expected" ]] \
      || fail "Finalize attempt $attempt step '$step' concluded '$actual'; expected '$expected'"
  done
}

restore_baseline_release() {
  local baseline_json latest_flag release_name target_commitish desired
  baseline_json="$(cat "$RELEASE_FILE")"
  release_name="$(printf '%s' "$baseline_json" | "$JQ_BIN" -r '.name')"
  target_commitish="$(printf '%s' "$baseline_json" | "$JQ_BIN" -r '.target_commitish')"
  desired="$(desired_latest_tag)"

  probe_release
  if [[ "$RELEASE_STATE" == exists ]]; then
    if release_matches_baseline; then
      reconcile_latest
      echo "::notice::$TAG already matches the baseline; no metadata compensation required."
      return 0
    fi
    assert_safe_release_json "$RELEASE_JSON"
    run_release_gh release delete "$TAG" --repo "$GITHUB_REPOSITORY" --yes >/dev/null
  fi

  if [[ "$desired" == "$TAG" ]]; then
    latest_flag=--latest
  else
    latest_flag=--latest=false
  fi
  run_release_gh release create "$TAG" \
    --repo "$GITHUB_REPOSITORY" \
    --verify-tag \
    "$latest_flag" \
    --target "$target_commitish" \
    --title "$release_name" \
    --notes-file "$BODY_FILE" >/dev/null
  assert_release_matches_baseline
  reconcile_latest
  echo "::notice::Restored supported metadata for $TAG from the durable baseline."
}

capture_baseline() {
  local version confirmation expected_confirmation repo_owner local_version
  local pulls_json pr_count workflow_json workflow_id runs_json run_count release_json latest
  local pr_number merge_sha pr_head_sha run_id initial_attempt run_status run_conclusion

  version="${VERSION:-}"
  confirmation="${CONFIRMATION:-}"
  [[ "$version" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] \
    || fail "version must be canonical X.Y.Z; got '$version'"
  expected_confirmation="DELETE-AND-RECREATE-v$version"
  [[ "$confirmation" == "$expected_confirmation" ]] \
    || fail "confirmation must be exactly '$expected_confirmation'"
  [[ -f VERSION && -f ".changes/$version.md" ]] || fail "VERSION or .changes/$version.md is missing"
  local_version="$(tr -d '[:space:]' < VERSION)"
  [[ "$local_version" == "$version" ]] \
    || fail "only the current release may be verified: checkout VERSION is $local_version, input is $version"

  VERSION="$version"
  TAG="v$version"
  BRANCH="release/v$version"
  assert_current_main
  repo_owner="${GITHUB_REPOSITORY%%/*}"

  pulls_json="$(run_actions_gh api --method GET "repos/$GITHUB_REPOSITORY/pulls" \
    -f state=closed -f base=main -f head="$repo_owner:$BRANCH" -F per_page=100)"
  pr_count="$(printf '%s' "$pulls_json" | "$JQ_BIN" -r '[.[] | select(.merged_at != null)] | length')"
  [[ "$pr_count" == 1 ]] || fail "expected one merged PR from $BRANCH to main; found $pr_count"
  pr_number="$(printf '%s' "$pulls_json" | "$JQ_BIN" -r '[.[] | select(.merged_at != null)][0].number')"
  merge_sha="$(printf '%s' "$pulls_json" | "$JQ_BIN" -r '[.[] | select(.merged_at != null)][0].merge_commit_sha')"
  pr_head_sha="$(printf '%s' "$pulls_json" | "$JQ_BIN" -r '[.[] | select(.merged_at != null)][0].head.sha')"

  workflow_json="$(run_actions_gh api \
    "repos/$GITHUB_REPOSITORY/actions/workflows/release-finalize.yml")"
  workflow_id="$(printf '%s' "$workflow_json" | "$JQ_BIN" -r '.id')"
  runs_json="$(run_actions_gh api --method GET \
    "repos/$GITHUB_REPOSITORY/actions/workflows/release-finalize.yml/runs" \
    -f event=pull_request -f branch="$BRANCH" -F per_page=100)"
  run_count="$(printf '%s' "$runs_json" | "$JQ_BIN" \
    --arg branch "$BRANCH" --arg head "$pr_head_sha" --argjson workflow_id "$workflow_id" -r \
    '[.workflow_runs[] | select(.event == "pull_request" and .head_branch == $branch and
      .head_sha == $head and .workflow_id == $workflow_id and
      (.path | split("@")[0]) == ".github/workflows/release-finalize.yml")] | length')"
  [[ "$run_count" == 1 ]] \
    || fail "expected one Finalize run bound to workflow $workflow_id and PR head $pr_head_sha; found $run_count"
  run_id="$(printf '%s' "$runs_json" | "$JQ_BIN" --arg head "$pr_head_sha" --argjson workflow_id "$workflow_id" -r \
    '.workflow_runs[] | select(.head_sha == $head and .workflow_id == $workflow_id) | .id')"
  initial_attempt="$(printf '%s' "$runs_json" | "$JQ_BIN" --arg head "$pr_head_sha" --argjson workflow_id "$workflow_id" -r \
    '.workflow_runs[] | select(.head_sha == $head and .workflow_id == $workflow_id) | .run_attempt')"
  run_status="$(printf '%s' "$runs_json" | "$JQ_BIN" --arg head "$pr_head_sha" --argjson workflow_id "$workflow_id" -r \
    '.workflow_runs[] | select(.head_sha == $head and .workflow_id == $workflow_id) | .status')"
  run_conclusion="$(printf '%s' "$runs_json" | "$JQ_BIN" --arg head "$pr_head_sha" --argjson workflow_id "$workflow_id" -r \
    '.workflow_runs[] | select(.head_sha == $head and .workflow_id == $workflow_id) | .conclusion')"
  [[ "$pr_number" =~ ^[1-9][0-9]*$ && "$workflow_id" =~ ^[1-9][0-9]*$ \
    && "$run_id" =~ ^[1-9][0-9]*$ && "$initial_attempt" =~ ^[1-9][0-9]*$ \
    && "$merge_sha" =~ ^[0-9a-f]{40,64}$ && "$pr_head_sha" =~ ^[0-9a-f]{40,64}$ ]] \
    || fail "release PR/workflow/run metadata is malformed"
  [[ "$run_status" == completed && "$run_conclusion" == success ]] \
    || fail "Finalize run $run_id must have a successful completed baseline"

  PR_NUMBER="$pr_number"
  PR_HEAD_SHA="$pr_head_sha"
  MERGE_SHA="$merge_sha"
  RUN_ID="$run_id"
  WORKFLOW_ID="$workflow_id"
  INITIAL_ATTEMPT="$initial_attempt"
  assert_tag_targets_merge

  release_json="$(run_actions_gh api "repos/$GITHUB_REPOSITORY/releases/tags/$TAG")" \
    || fail "release $TAG is missing or unreadable"
  assert_safe_release_json "$release_json"
  latest="$(latest_release_tag)"
  [[ "$latest" == "$TAG" ]] || fail "only the current Latest release may be verified; Latest is '$latest'"

  mkdir -p "$BASELINE_DIR"
  printf '%s' "$release_json" > "$RELEASE_FILE"
  printf '%s' "$release_json" | "$JQ_BIN" -j '.body' > "$BODY_FILE"
  cmp -s "$BODY_FILE" ".changes/$VERSION.md" \
    || fail "release $TAG body differs from .changes/$VERSION.md; refusing a destructive drill"

  "$JQ_BIN" -n \
    --arg version "$VERSION" --arg tag "$TAG" --arg branch "$BRANCH" \
    --argjson pr_number "$PR_NUMBER" --arg pr_head_sha "$PR_HEAD_SHA" \
    --arg merge_sha "$MERGE_SHA" --argjson workflow_id "$WORKFLOW_ID" \
    --argjson run_id "$RUN_ID" --argjson initial_attempt "$INITIAL_ATTEMPT" \
    --argjson was_latest true \
    '{version:$version,tag:$tag,branch:$branch,pr_number:$pr_number,
      pr_head_sha:$pr_head_sha,merge_sha:$merge_sha,workflow_id:$workflow_id,
      run_id:$run_id,initial_attempt:$initial_attempt,was_latest:$was_latest}' > "$CONTEXT_FILE"
  echo "::notice::Captured durable baseline for $TAG before any release mutation."
}

case "$COMMAND" in
  capture)
    capture_baseline
    ;;
  queue-noop)
    load_context
    assert_current_main
    assert_tag_targets_merge
    assert_release_matches_baseline
    assert_latest_is_safe
    queue_exact_rerun "$INITIAL_ATTEMPT"
    echo "::notice::Queued Finalize attempt $((INITIAL_ATTEMPT + 1)) for the no-op check."
    ;;
  verify-noop)
    load_context
    noop_attempt=$((INITIAL_ATTEMPT + 1))
    wait_for_exact_attempt "$noop_attempt"
    assert_finalize_steps "$noop_attempt" skipped skipped skipped
    assert_tag_targets_merge
    assert_release_matches_baseline
    assert_latest_is_safe
    echo "::notice::Finalize attempt $noop_attempt proved the tag-plus-release no-op path."
    ;;
  queue-recovery)
    load_context
    noop_attempt=$((INITIAL_ATTEMPT + 1))
    recovery_attempt=$((INITIAL_ATTEMPT + 2))
    assert_current_main
    assert_tag_targets_merge
    assert_release_matches_baseline
    assert_latest_is_safe

    # Queue the recovery attempt while this job owns the same concurrency group
    # as Finalize. It cannot begin until this job exits. Re-check main after the
    # POST: a concurrently merged newer release would already have changed
    # VERSION and its Finalize run would be ahead in the shared FIFO queue.
    queue_exact_rerun "$noop_attempt"
    assert_current_main
    assert_tag_targets_merge
    assert_release_matches_baseline

    cleanup_armed=true
    cleanup_on_exit() {
      local rc=$?
      trap - EXIT INT TERM
      if [[ "$cleanup_armed" == true && "$rc" -ne 0 ]]; then
        restore_baseline_release || rc=1
      fi
      exit "$rc"
    }
    trap cleanup_on_exit EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM

    run_release_gh release delete "$TAG" --repo "$GITHUB_REPOSITORY" --yes >/dev/null
    assert_tag_targets_merge
    assert_release_absent
    cleanup_armed=false
    echo "::notice::Deleted only $TAG's release; Finalize attempt $recovery_attempt is queued to recreate it."
    ;;
  verify-recovery)
    load_context
    recovery_attempt=$((INITIAL_ATTEMPT + 2))
    wait_for_exact_attempt "$recovery_attempt"
    assert_finalize_steps "$recovery_attempt" skipped success success
    assert_tag_targets_merge
    assert_release_matches_baseline
    assert_latest_is_safe

    recreated_json="$RELEASE_JSON"
    baseline_database_id="$("$JQ_BIN" -r '.id' "$RELEASE_FILE")"
    recreated_database_id="$(printf '%s' "$recreated_json" | "$JQ_BIN" -r '.id')"
    {
      echo "## Release Finalize recovery verified"
      echo
      echo "- Release: \`$TAG\`"
      echo "- Release PR: #$PR_NUMBER (merge \`$MERGE_SHA\`)"
      echo "- Finalize run: [$RUN_ID](https://github.com/$GITHUB_REPOSITORY/actions/runs/$RUN_ID)"
      echo "- Attempt $((INITIAL_ATTEMPT + 1)): existing tag + release produced a clean no-op"
      echo "- Attempt $recovery_attempt: existing tag + missing release recreated the release only"
      echo "- Supported metadata/body match the baseline; tag still targets the merge commit"
      echo "- Release database ID changed from \`$baseline_database_id\` to \`$recreated_database_id\` (expected after deletion)"
    } >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
    echo "::notice::Verified both Finalize recovery paths for $TAG."
    ;;
  watchdog)
    load_context
    assert_tag_targets_merge
    if release_matches_baseline; then
      reconcile_latest
      echo "::notice::$TAG matches the durable baseline; watchdog found no metadata to restore."
    else
      restore_baseline_release
    fi
    ;;
esac
