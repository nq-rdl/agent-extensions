RPC Mode Reference
==================

Overview
--------

RPC mode (``pi --mode rpc``) communicates via JSONL (newline-delimited
JSON) over stdin/stdout. The Go ConnectRPC service (``pi-server``) wraps
this protocol, exposing it as HTTP/JSON endpoints that agents call with
standard ``curl`` POST requests.

Session Lifecycle
-----------------

::

   Create → SESSION_STATE_IDLE
     → Prompt → SESSION_STATE_RUNNING → (agent completes) → SESSION_STATE_IDLE
     → Prompt → SESSION_STATE_RUNNING → (error) → SESSION_STATE_ERROR
     → Delete → SESSION_STATE_TERMINATED

Each session is a ``pi --mode rpc`` subprocess with stdin/stdout pipes.
The server manages the subprocess lifecycle and event parsing.

Provider and Model Selection
----------------------------

**If the user has not specified a provider and model, ask them.** Do not
assume a default. Use ``pi --list-models`` to show available options.

Before creating RPC sessions, validate the chosen provider/model pair
with a one-shot JSON invocation:

.. code:: bash

   pi --provider <PROVIDER> --model <MODEL> --mode json "Reply with OK."

If this fails, fix the model ID or provider authentication before
calling ``Create``.

ConnectRPC Dispatch Examples
----------------------------

Create a session
~~~~~~~~~~~~~~~~

.. code:: bash

   PI_SERVER="${PI_SERVER_URL:-http://localhost:4097}"
   curl -sf \
     -H 'Content-Type: application/json' \
     -d '{"provider":"<PROVIDER>","model":"<MODEL>","cwd":"/home/user/project"}' \
     "$PI_SERVER/pirpc.v1.SessionService/Create"
   # → {"sessionId":"abc-123","state":"SESSION_STATE_IDLE"}

Send a prompt (synchronous)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Waits until the agent completes (receives ``agent_end`` event):

.. code:: bash

   curl -sf \
     -H 'Content-Type: application/json' \
     -d '{"sessionId":"abc-123","message":"Create a hello world program"}' \
     "$PI_SERVER/pirpc.v1.SessionService/Prompt"
   # → {"state":"SESSION_STATE_IDLE","messages":[...]}

Send a prompt (asynchronous)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Returns immediately — monitor via GetState or StreamEvents:

.. code:: bash

   curl -sf \
     -H 'Content-Type: application/json' \
     -d '{"sessionId":"abc-123","message":"Refactor the auth module"}' \
     "$PI_SERVER/pirpc.v1.SessionService/PromptAsync"

Get messages
~~~~~~~~~~~~

.. code:: bash

   curl -sf \
     -H 'Content-Type: application/json' \
     -d '{"sessionId":"abc-123"}' \
     "$PI_SERVER/pirpc.v1.SessionService/GetMessages"

Check session state
~~~~~~~~~~~~~~~~~~~

.. code:: bash

   curl -sf \
     -H 'Content-Type: application/json' \
     -d '{"sessionId":"abc-123"}' \
     "$PI_SERVER/pirpc.v1.SessionService/GetState"
   # → {"sessionId":"abc-123","state":"SESSION_STATE_IDLE","provider":"...","model":"...",...}

Abort a running session
~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   curl -sf \
     -H 'Content-Type: application/json' \
     -d '{"sessionId":"abc-123"}' \
     "$PI_SERVER/pirpc.v1.SessionService/Abort"

Delete a session
~~~~~~~~~~~~~~~~

.. code:: bash

   curl -sf \
     -H 'Content-Type: application/json' \
     -d '{"sessionId":"abc-123"}' \
     "$PI_SERVER/pirpc.v1.SessionService/Delete"

List all sessions
~~~~~~~~~~~~~~~~~

.. code:: bash

   curl -sf \
     -H 'Content-Type: application/json' \
     -d '{}' \
     "$PI_SERVER/pirpc.v1.SessionService/List"

Event Types
-----------

Events are emitted by the pi.dev subprocess via JSONL on stdout. The
ConnectRPC service parses these and makes them available via
``StreamEvents`` or buffers them for ``GetMessages``.

======================== ==============================
Event Type               Description
======================== ==============================
``agent_start``          Agent begins processing
``agent_end``            Agent completes processing
``turn_start``           New conversation turn begins
``turn_end``             Conversation turn ends
``message_update``       Incremental message content
``tool_execution_start`` Agent invokes a tool
``tool_execution_end``   Tool execution completes
``compaction``           Context window compacted
``retry``                Retrying after transient error
``error``                Error occurred
======================== ==============================

Model Selection
---------------

**No default model.** If the user/human has not specified a provider and
model, ask them before creating sessions. Use ``pi --list-models`` to
enumerate available providers and model IDs.

Common providers include ``openai-codex``, ``anthropic``, and
``google``. Use exact model IDs from ``pi --list-models``.

Health Check
------------

.. code:: bash

   PI_SERVER="${PI_SERVER_URL:-http://localhost:4097}"
   curl -sf \
     -H 'Content-Type: application/json' \
     -d '{}' \
     "$PI_SERVER/pirpc.v1.SessionService/List" > /dev/null && echo "ready"

If this fails, start the server:

.. code:: bash

   cd skills/pi-rpc/scripts && make serve
