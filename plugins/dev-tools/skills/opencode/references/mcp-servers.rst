MCP Server Configuration Reference
==================================

MCP (Model Context Protocol) servers expose external tools to OpenCode
agents. Configure them in ``opencode.json``.

Server Types
------------

Local (stdio)
~~~~~~~~~~~~~

Runs a process on the local machine and communicates via stdin/stdout:

.. code:: json

   {
     "mcp": {
       "my-server": {
         "type": "local",
         "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"],
         "environment": {
           "NODE_ENV": "production"
         },
         "timeout": 5000
       }
     }
   }

Remote (HTTP)
~~~~~~~~~~~~~

Connects to an HTTP endpoint:

.. code:: json

   {
     "mcp": {
       "remote-server": {
         "type": "remote",
         "url": "https://mcp.example.com",
         "headers": {
           "Authorization": "Bearer {env:MY_API_KEY}"
         },
         "timeout": 5000,
         "enabled": true
       }
     }
   }

Environment Variables in Config
-------------------------------

Use ``{env:VAR_NAME}`` to inject environment variables — keeps secrets
out of the config file:

.. code:: json

   {
     "mcp": {
       "jira": {
         "type": "remote",
         "url": "https://jira.example.com/mcp",
         "headers": {
           "Authorization": "Bearer {env:JIRA_TOKEN}"
         }
       }
     }
   }

OAuth Authentication
--------------------

OpenCode supports three OAuth flows:

**1. Automatic (no config needed)** When a server returns a 401,
OpenCode detects it and launches the OAuth flow in the browser.

**2. Dynamic Registration (RFC 7591)** For servers that support dynamic
client registration — no pre-configuration needed. OpenCode handles it
automatically.

**3. Pre-configured credentials**

.. code:: json

   {
     "mcp": {
       "my-server": {
         "type": "remote",
         "url": "https://mcp.example.com",
         "oauth": {
           "clientId": "my-client-id",
           "clientSecret": "{env:OAUTH_SECRET}",
           "scope": "read write"
         }
       }
     }
   }

**Disable OAuth** (for API-key-based servers):

.. code:: json

   {
     "mcp": {
       "api-server": {
         "type": "remote",
         "url": "https://api.example.com/mcp",
         "oauth": false,
         "headers": { "X-API-Key": "{env:API_KEY}" }
       }
     }
   }

CLI Management Commands
-----------------------

.. code:: bash

   # Authenticate with a server (opens browser for OAuth)
   opencode mcp auth <server-name>

   # List all configured servers and their auth status
   opencode mcp list

   # Clear stored credentials
   opencode mcp logout <server-name>

   # Debug OAuth issues
   opencode mcp debug <server-name>

Tool Naming Convention
----------------------

MCP tools are named: ``<servername>_<toolname>``

Example: server ``jira`` with tool ``create_issue`` → LLM sees it as
``jira_create_issue``

This namespace prevents collisions between multiple servers.

Enabling and Disabling Tools
----------------------------

**Disable all tools from a server globally:**

.. code:: json

   {
     "tools": {
       "jira_*": false
     }
   }

**Enable per-agent while disabled globally:**

.. code:: json

   {
     "tools": {
       "jira_*": false
     },
     "agent": {
       "project-manager": {
         "description": "Manages Jira tickets",
         "tools": {
           "jira_*": true
         }
       }
     }
   }

**Disable a specific tool only:**

.. code:: json

   {
     "tools": {
       "jira_delete_issue": false
     }
   }

Per-Agent MCP Control
---------------------

In agent frontmatter (``.opencode/agents/<name>.md``):

.. code:: markdown

   ---
   description: Agent that can use Jira tools
   tools:
     jira_*: true
     github_*: false
   ---

Common MCP Servers
------------------

+-----------------------+---------------------------------------------+--------------------+
| Server                | Package                                     | Tools              |
+=======================+=============================================+====================+
| Filesystem            | ``@modelcontextprotocol/server-filesystem`` | read, write, list  |
|                       |                                             | files              |
+-----------------------+---------------------------------------------+--------------------+
| GitHub                | ``@modelcontextprotocol/server-github``     | repos, PRs, issues |
+-----------------------+---------------------------------------------+--------------------+
| Postgres              | ``@modelcontextprotocol/server-postgres``   | SQL queries        |
+-----------------------+---------------------------------------------+--------------------+
| Fetch                 | ``@modelcontextprotocol/server-fetch``      | HTTP requests      |
+-----------------------+---------------------------------------------+--------------------+
| Memory                | ``@modelcontextprotocol/server-memory``     | key-value store    |
+-----------------------+---------------------------------------------+--------------------+

.. code:: json

   {
     "mcp": {
       "filesystem": {
         "type": "local",
         "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/home/user/projects"]
       },
       "github": {
         "type": "local",
         "command": ["npx", "-y", "@modelcontextprotocol/server-github"],
         "environment": {
           "GITHUB_PERSONAL_ACCESS_TOKEN": "{env:GITHUB_TOKEN}"
         }
       }
     }
   }

Troubleshooting
---------------

+------------------------------+---------------------------------------+
| Issue                        | Solution                              |
+==============================+=======================================+
| Server not starting          | Check ``command`` array — each arg    |
|                              | must be a separate string             |
+------------------------------+---------------------------------------+
| Tools not visible            | Run ``opencode mcp list`` to verify   |
|                              | server connected                      |
+------------------------------+---------------------------------------+
| Auth failing                 | Run ``opencode mcp debug <server>``   |
|                              | for details                           |
+------------------------------+---------------------------------------+
| Token expired                | Run ``opencode mcp logout <server>``  |
|                              | then ``opencode mcp auth <server>``   |
+------------------------------+---------------------------------------+
| Timeout errors               | Increase ``timeout`` value            |
|                              | (milliseconds)                        |
+------------------------------+---------------------------------------+
