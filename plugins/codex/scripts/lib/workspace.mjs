import { ensureGitRepository } from "./git.mjs";

export function resolveWorkspaceRoot(cwd) {
  try {
    // An empty toplevel is not a repository root, it is a failed probe:
    // runCommand reports `status: result.status ?? 0`, so a spawn that never
    // ran (EAGAIN under fork pressure) arrives here as a *successful* git with
    // empty stdout. Returning "" would be silently destructive rather than
    // merely wrong -- resolveStateDir slugs it to the literal "workspace" and
    // hashes the empty string, so every workspace that trips this collapses
    // into one shared state directory and concurrent processes split-brain
    // across two different surfaced.json files. Fall back to cwd, which is
    // what an explicitly non-git workspace already resolves to.
    return ensureGitRepository(cwd) || cwd;
  } catch {
    return cwd;
  }
}
