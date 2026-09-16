// .opencode/plugins/starter.ts  (note the PLURAL `plugins/` directory)
//
// Minimal OpenCode plugin showing the two-layer model side by side:
//   - an IMPERATIVE handler key  -> (input, output), mutate output / throw to block
//   - the `event` BUS reader      -> switch on past-tense `event.type`
//
// Verify the Hooks key set against `interface Hooks` in @opencode-ai/plugin
// (packages/plugin/src/index.ts) and https://opencode.ai/docs/plugins/ — the API
// moves fast. There is NO `stop` hook; "session finished" is event.type "session.idle".

import type { Plugin } from "@opencode-ai/plugin"

export const Starter: Plugin = async ({ client, $, directory, worktree }) => {
  return {
    // IMPERATIVE handler: input is read-only, mutate `output` in place, throw to block.
    "tool.execute.before": async (input, output) => {
      if (input.tool === "read" && output.args.filePath?.includes(".env")) {
        throw new Error("Blocked: do not read .env files")
      }
    },

    // BUS reader: one function, switch on the past-tense event.type.
    event: async ({ event }) => {
      if (event.type === "session.idle") {
        // Structured logging — prefer client.app.log over console.log.
        await client.app.log({
          body: { service: "starter", level: "info", message: "session idle" },
        })
      }
    },
  }
}
