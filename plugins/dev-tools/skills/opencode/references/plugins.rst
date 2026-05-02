Plugin Authoring Reference
==========================

Plugins bundle tools and subscribe to lifecycle hooks. They execute
server-side in OpenCode’s Bun runtime.

Placement
---------

::

   .opencode/plugins/<name>.ts       # project-local
   ~/.config/opencode/plugins/<name>.ts  # global

Plugin Function Signature
-------------------------

.. code:: typescript

   import type { Plugin } from "@opencode-ai/plugin"

   export const MyPlugin: Plugin = async ({
     project,    // current project info
     client,     // OpenCode SDK client (pre-connected)
     $,          // Bun's shell API
     directory,  // current working directory
     worktree,   // git worktree root
   }) => {
     // Setup code here (runs once at startup)

     return {
       // Tools and hook handlers
     }
   }

The return value is an object where: - Keys matching a hook name → hook
handler function - Key ``"tool"`` → map of tool name → tool definition

Plugin Context
--------------

+-----------------------+--------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+
| Property              | Type               | Description                                                                                                                                       |
+=======================+====================+===================================================================================================================================================+
| ``project``           | ``Project``        | Project metadata (root path, name, etc.)                                                                                                          |
+-----------------------+--------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+
| ``client``            | ``OpenCodeClient`` | Pre-connected SDK client for API calls                                                                                                            |
+-----------------------+--------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+
| ``$``                 | Bun shell          | ``$\``\ command\`\ ``for shell execution | |``\ directory\ ``|``\ string\ ``| Absolute path to working directory | |``\ worktree\ ``|``\ string\` |
+-----------------------+--------------------+---------------------------------------------------------------------------------------------------------------------------------------------------+

Bundling Tools in Plugins
-------------------------

.. code:: typescript

   import { type Plugin, tool } from "@opencode-ai/plugin"

   export const DevPlugin: Plugin = async (ctx) => {
     return {
       tool: {
         // Tool name (used by LLM): "run_tests"
         run_tests: tool({
           description: "Run the project's test suite and return results",
           args: {
             pattern: tool.schema.string().describe("Test file pattern (optional)"),
           },
           async execute(args, context) {
             const pat = args.pattern || "**/*.test.ts"
             const result = await ctx.$`bun test ${pat}`.text()
             return result
           },
         }),

         lint: tool({
           description: "Run the linter and return any issues",
           args: {},
           async execute(_, context) {
             const result = await ctx.$`bun run lint`.nothrow().text()
             return result
           },
         }),
       },
     }
   }

Hook Events Table
-----------------

Tool Hooks
~~~~~~~~~~

+-------------------------+-----------------+-------------------------------------------------------+
| Event                   | When            | Signature                                             |
+=========================+=================+=======================================================+
| ``tool.execute.before`` | Before any tool | ``(input: { tool, args }, output: { args }) => void`` |
|                         | runs            |                                                       |
+-------------------------+-----------------+-------------------------------------------------------+
| ``tool.execute.after``  | After any tool  | ``(input: { tool, args, result }) => void``           |
|                         | runs            |                                                       |
+-------------------------+-----------------+-------------------------------------------------------+

.. code:: typescript

   // Block reading .env files
   "tool.execute.before": async (input, output) => {
     if (input.tool === "read" && output.args.filePath?.includes(".env")) {
       throw new Error("Reading .env files is not permitted")
     }
   },

   // Log all tool executions
   "tool.execute.after": async (input) => {
     await client.app.log({
       body: { level: "info", message: `Tool ran: ${input.tool}` }
     })
   },

Shell Hooks
~~~~~~~~~~~

+--------------------+-----------------+--------------------------------------+
| Event              | When            | Signature                            |
+====================+=================+======================================+
| ``shell.env``      | Before shell    | ``(input, output: { env }) => void`` |
|                    | commands        |                                      |
|                    | execute         |                                      |
+--------------------+-----------------+--------------------------------------+

.. code:: typescript

   // Inject environment variables for all shell tools
   "shell.env": async (input, output) => {
     output.env.NODE_ENV = "development"
     output.env.API_KEY = process.env.MY_API_KEY ?? ""
   },

Session Hooks
~~~~~~~~~~~~~

+-----------------------+-----------------+-------------------------------------+
| Event                 | When            | Signature                           |
+=======================+=================+=====================================+
| ``session.created``   | New session     | ``(input: { id }) => void``         |
|                       | started         |                                     |
+-----------------------+-----------------+-------------------------------------+
| ``session.updated``   | Session         | ``(input: { id }) => void``         |
|                       | metadata        |                                     |
|                       | changed         |                                     |
+-----------------------+-----------------+-------------------------------------+
| ``session.compacted`` | Context was     | ``(input: { id }) => void``         |
|                       | compacted       |                                     |
+-----------------------+-----------------+-------------------------------------+
| ``session.deleted``   | Session removed | ``(input: { id }) => void``         |
+-----------------------+-----------------+-------------------------------------+
| ``session.idle``      | Session         | ``(input: { id }) => void``         |
|                       | finished        |                                     |
+-----------------------+-----------------+-------------------------------------+
| ``session.error``     | Session errored | ``(input: { id, error }) => void``  |
+-----------------------+-----------------+-------------------------------------+
| ``session.status``    | Status message  | ``(input: { id, status }) => void`` |
|                       | emitted         |                                     |
+-----------------------+-----------------+-------------------------------------+
| ``session.diff``      | File changes    | ``(input: { id, diff }) => void``   |
|                       | applied         |                                     |
+-----------------------+-----------------+-------------------------------------+

.. code:: typescript

   // Log when sessions finish
   "session.idle": async (input) => {
     console.log(`Session ${input.id} finished`)
   },

File Hooks
~~~~~~~~~~

======================== =============================
Event                    When
======================== =============================
``file.edited``          File was modified by OpenCode
``file.watcher.updated`` File system change detected
======================== =============================

Message Hooks
~~~~~~~~~~~~~

======================== ========================
Event                    When
======================== ========================
``message.updated``      Message content changed
``message.removed``      Message deleted
``message.part.updated`` Streaming chunk received
``message.part.removed`` Content part removed
======================== ========================

Other Hooks
~~~~~~~~~~~

========================== =============================
Event                      When
========================== =============================
``command.executed``       Slash command executed
``lsp.client.diagnostics`` LSP diagnostics updated
``lsp.updated``            LSP server state changed
``permission.asked``       Tool permission requested
``permission.replied``     Tool permission answered
``server.connected``       Client connected to server
``installation.updated``   OpenCode installation changed
``tui.prompt.append``      Text appended to TUI prompt
``tui.command.execute``    TUI command executed
``tui.toast.show``         Toast notification shown
========================== =============================

Experimental Hooks
~~~~~~~~~~~~~~~~~~

+-------------------------------------+---------------------------------------+
| Event                               | Purpose                               |
+=====================================+=======================================+
| ``experimental.session.compacting`` | Customise context compaction prompt   |
+-------------------------------------+---------------------------------------+

.. code:: typescript

   "experimental.session.compacting": async (input, output) => {
     // Add custom context for compaction
     output.context.push("## Project-specific context\n...")
     // Or replace the compaction prompt entirely:
     // output.prompt = "Custom compaction instructions..."
   },

Logging from Plugins
--------------------

.. code:: typescript

   await client.app.log({
     body: {
       service: "my-plugin",
       level: "info",    // "info" | "warn" | "error"
       message: "Plugin startup complete",
     }
   })

Per-Project npm Dependencies
----------------------------

Declare dependencies that your plugin needs in
``.opencode/package.json``:

.. code:: json

   {
     "dependencies": {
       "zod": "^3.24.0",
       "date-fns": "^3.0.0"
     }
   }

OpenCode runs ``bun install`` at startup and makes these available to
plugin imports.

Distribution
------------

**Local plugin** — commit ``.opencode/plugins/`` to your project repo.
Team members get it automatically.

**npm package** — publish as a normal npm package: 1. Export the plugin
function as the default or named export 2. Users install:
``bun add my-plugin`` 3. Register in ``opencode.json``:

.. code:: json

   {
     "plugins": ["my-plugin"]
   }

Testing Plugins
---------------

Test plugin tools directly by extracting them and calling with a mock
context:

.. code:: typescript

   import { describe, test, expect } from "bun:test"
   import { MyPlugin } from "../.opencode/plugins/my-plugin"

   const mockCtx = {
     project: { root: "/tmp/test" },
     client: {} as any,
     $: Bun.$,
     directory: "/tmp/test",
     worktree: "/tmp/test",
   }

   describe("MyPlugin", () => {
     test("returns tools", async () => {
       const result = await MyPlugin(mockCtx)
       expect(result.tool).toBeDefined()
     })
   })

Complete Example: Security Plugin
---------------------------------

.. code:: typescript

   import { type Plugin, tool } from "@opencode-ai/plugin"

   export const SecurityPlugin: Plugin = async ({ client, $ }) => {
     return {
       // Block writing to sensitive files
       "tool.execute.before": async (input, output) => {
         const sensitivePatterns = [".env", "secrets", "credentials", ".pem", ".key"]
         const filePath: string = output.args?.filePath ?? output.args?.path ?? ""
         if (input.tool === "write" || input.tool === "edit") {
           for (const pattern of sensitivePatterns) {
             if (filePath.includes(pattern)) {
               throw new Error(`Writing to ${filePath} is blocked by security policy`)
             }
           }
         }
       },

       // Custom security scanning tool
       tool: {
         security_scan: tool({
           description: "Run a quick security audit on a file",
           args: {
             path: tool.schema.string().describe("File to scan"),
           },
           async execute(args) {
             const content = await Bun.file(args.path).text()
             const issues: string[] = []

             if (/password\s*=\s*["'][^"']+["']/i.test(content)) {
               issues.push("Hardcoded password detected")
             }
             if (/api[_-]?key\s*=\s*["'][^"']+["']/i.test(content)) {
               issues.push("Hardcoded API key detected")
             }

             return issues.length
               ? `Security issues found:\n${issues.map(i => `• ${i}`).join("\n")}`
               : "No obvious security issues found"
           },
         }),
       },
     }
   }
