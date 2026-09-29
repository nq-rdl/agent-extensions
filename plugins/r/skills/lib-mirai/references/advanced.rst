Advanced mirai patterns
=======================

Executed with mirai 2.7.2 on R 4.5.3 on 2026-09-29.

Contents
--------

- `Switching compute profiles <#switching-compute-profiles>`__
- `Nested parallelism <#nested-parallelism>`__

Switching compute profiles
--------------------------

``local_daemons()`` and ``with_daemons()`` **switch** the active compute
profile to one that already exists. They do not create daemons.

.. code:: r

   daemons(4, .compute = "workers")

   # Switch the active profile for the rest of the calling function
   my_func <- function() {
     local_daemons("workers")
     mirai(task())[]  # uses the "workers" profile
   }

   # Switch the active profile for one block
   with_daemons("workers", {
     m <- mirai(task())
     m[]
   })

   daemons(0, .compute = "workers")

Nested parallelism
------------------

Inside daemon callbacks (for example in ``mirai_map()``), start a separate
local pool with ``local_url()`` and ``launch_local()`` rather than
``daemons(n)``, so it does not conflict with the outer pool. mirai is not
attached on the daemon: qualify every call with ``mirai::``, or the callback
fails with ``could not find function "daemons"``.

.. code:: r

   daemons(2)
   mirai_map(1:10, function(x) {
     mirai::daemons(url = mirai::local_url())
     mirai::launch_local(2)
     result <- mirai::mirai_map(1:5, function(y, x) x * y, .args = list(x = x))[]
     mirai::daemons(0)
     result
   })[]
   daemons(0)
