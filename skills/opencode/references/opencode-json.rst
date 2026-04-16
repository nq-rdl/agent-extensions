opencode.json Reference
=======================

The ``opencode.json`` file lives at the project root (or
``~/.config/opencode/opencode.json`` for global config). Multiple config
files merge with precedence: remote → global → custom → project →
inline.

Schema
------

.. code:: json

   {
     "$schema": "https://opencode.ai/config.json"
   }

Top-Level Fields
----------------

+-------------------+----------------+-----------------------------------+
| Field             | Type           | Description                       |
+===================+================+===================================+
| ``model``         | string         | Default model:                    |
|                   |                | ``provider/model-id``             |
+-------------------+----------------+-----------------------------------+
| ``small_model``   | string         | Fast model for lightweight tasks  |
+-------------------+----------------+-----------------------------------+
| ``default_agent`` | string         | Agent to use by default (e.g.,    |
|                   |                | ``"build"``)                      |
+-------------------+----------------+-----------------------------------+
| ``autoupdate``    | boolean        | Auto-update OpenCode on startup   |
+-------------------+----------------+-----------------------------------+
| ``instructions``  | string[]       | Paths/globs to rule files to      |
|                   |                | include as context                |
+-------------------+----------------+-----------------------------------+
| ``share``         | ``"manual"``   | Session sharing mode              |
|                   | \| ``"auto"``  |                                   |
|                   | \|             |                                   |
|                   | ``"disabled"`` |                                   |
+-------------------+----------------+-----------------------------------+

Provider Configuration
----------------------

.. code:: json

   {
     "provider": {
       "anthropic": {
         "timeout": 300000,
         "chunkTimeout": 30000,
         "setCacheKey": true
       },
       "bedrock": {
         "region": "us-east-1",
         "profile": "my-aws-profile"
       },
       "openai": {
         "apiKey": "{env:OPENAI_API_KEY}"
       }
     }
   }

Model Selection
---------------

.. code:: json

   {
     "model": "anthropic/claude-sonnet-4-5",
     "small_model": "anthropic/claude-haiku-4-5-20251001"
   }

Model format: ``provider/model-id``

Common models: - ``anthropic/claude-opus-4-5`` -
``anthropic/claude-sonnet-4-5`` -
``anthropic/claude-haiku-4-5-20251001`` - ``openai/gpt-4o`` -
``openai/o3-mini`` - ``google/gemini-2.5-pro`` - ``ollama/llama3.2``
(requires Ollama running locally)

Agent Configuration
-------------------

Define custom agents inline:

.. code:: json

   {
     "agent": {
       "security-reviewer": {
         "description": "Reviews code for security vulnerabilities",
         "mode": "subagent",
         "model": "anthropic/claude-opus-4-5",
         "temperature": 0.1,
         "tools": {
           "write": false,
           "bash": false,
           "edit": false
         },
         "permission": {
           "bash": "deny"
         }
       },
       "doc-writer": {
         "description": "Writes and updates documentation",
         "model": "anthropic/claude-sonnet-4-5",
         "tools": {
           "bash": false
         }
       }
     }
   }

Agent fields: ``description``, ``mode``, ``model``, ``temperature``,
``top_p``, ``steps``, ``tools``, ``permission``, ``prompt``, ``color``,
``hidden``, ``disable``

Tools Configuration
-------------------

Enable or disable specific tools globally:

.. code:: json

   {
     "tools": {
       "write": true,
       "bash": false,
       "edit": true,
       "mcp-server_*": false
     }
   }

Permissions
-----------

.. code:: json

   {
     "permission": {
       "edit": "ask",
       "bash": "ask",
       "write": "allow"
     }
   }

Bash supports command-level granularity:

.. code:: json

   {
     "permission": {
       "bash": {
         "*": "ask",
         "git status": "allow",
         "git log *": "allow",
         "git diff *": "allow",
         "rm *": "deny"
       }
     }
   }

Permission values: ``"ask"``, ``"allow"``, ``"deny"``

MCP Servers
-----------

.. code:: json

   {
     "mcp": {
       "local-server": {
         "type": "local",
         "command": ["node", "path/to/server.js"],
         "environment": { "KEY": "value" },
         "timeout": 5000
       },
       "remote-server": {
         "type": "remote",
         "url": "https://mcp.example.com",
         "headers": { "Authorization": "Bearer {env:API_TOKEN}" },
         "enabled": true
       }
     }
   }

Server Settings
---------------

.. code:: json

   {
     "server": {
       "port": 4096,
       "hostname": "0.0.0.0",
       "mdns": true,
       "mdnsDomain": "myproject.local",
       "cors": ["http://localhost:5173", "http://localhost:3000"]
     }
   }

Instructions (Rule Files)
-------------------------

Inject additional context into every session:

.. code:: json

   {
     "instructions": [
       "CONTRIBUTING.md",
       "docs/architecture/*.md",
       ".opencode/rules/**/*.md"
     ]
   }

Glob patterns are supported. Files are read relative to the project
root.

Custom Commands
---------------

Define slash commands available in the TUI:

.. code:: json

   {
     "commands": {
       "review": {
         "description": "Review staged changes",
         "template": "Review my staged changes for correctness and style",
         "agent": "security-reviewer"
       },
       "standup": {
         "description": "Summarise recent commits for standup",
         "template": "Summarise commits from the last 24 hours in bullet points"
       }
     }
   }

Invoke: ``/review`` or ``/standup`` in the TUI.

Formatter Configuration
-----------------------

.. code:: json

   {
     "formatter": {
       "*.ts": {
         "command": ["biome", "format", "--write"],
         "onSave": true
       },
       "*.py": {
         "command": ["ruff", "format"],
         "onSave": true
       }
     }
   }

Compaction Settings
-------------------

.. code:: json

   {
     "compaction": "auto"
   }

Values: ``"auto"`` (default), ``"prune"`` (remove old messages),
``"reserved"`` (keep all)

Variable Substitution
---------------------

======================= =============================
Syntax                  Replaced with
======================= =============================
``{env:VAR_NAME}``      Value of environment variable
``{file:path/to/file}`` Contents of the file
======================= =============================

Provider Lists
--------------

.. code:: json

   {
     "disabled_providers": ["openai", "google"],
     "enabled_providers": ["anthropic", "ollama"]
   }

Minimal Starter Config
----------------------

.. code:: json

   {
     "$schema": "https://opencode.ai/config.json",
     "model": "anthropic/claude-sonnet-4-5",
     "autoupdate": true
   }

Full Example
------------

.. code:: json

   {
     "$schema": "https://opencode.ai/config.json",
     "model": "anthropic/claude-sonnet-4-5",
     "small_model": "anthropic/claude-haiku-4-5-20251001",
     "default_agent": "build",
     "autoupdate": true,
     "instructions": [
       "CLAUDE.md",
       ".opencode/rules/*.md"
     ],
     "permission": {
       "bash": {
         "*": "ask",
         "git status": "allow",
         "git log": "allow",
         "git diff": "allow"
       }
     },
     "tools": {
       "bash": true,
       "write": true,
       "edit": true
     },
     "agent": {
       "fast": {
         "description": "Quick one-shot tasks",
         "model": "anthropic/claude-haiku-4-5-20251001",
         "steps": 5
       }
     },
     "mcp": {
       "github": {
         "type": "local",
         "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
         "environment": {
           "GITHUB_PERSONAL_ACCESS_TOKEN": "{env:GITHUB_TOKEN}"
         }
       }
     },
     "server": {
       "port": 4096
     }
   }
