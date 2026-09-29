Migrating from future and parallel
==================================

The key conversion step is the same for both: find every object the
expression uses from the calling environment and pass it explicitly through
``.args`` or ``...``. mirai does not detect globals.

Contents
--------

- `From future <#from-future>`__
- `From parallel <#from-parallel>`__
- `Drop-in cluster backend <#drop-in-cluster-backend>`__

From future
-----------

=================================== ==============================================
future                              mirai
=================================== ==============================================
Detects globals automatically       Pass all dependencies explicitly
``future({expr})``                  ``mirai({expr}, .args = list(...))``
``value(f)``                        ``m[]``, or ``call_mirai(m); m$data``
``plan(multisession, workers = 4)`` ``daemons(4)``
``plan(sequential)`` / reset        ``daemons(0)``
``future_lapply(X, FUN)``           ``mirai_map(X, FUN)[]``
``future_map(X, FUN)`` (furrr)      ``mirai_map(X, FUN)[]``
``future_promise(expr)``            ``mirai(expr, ...)`` (already a promise)
=================================== ==============================================

From parallel
-------------

==================================== ===============================================
parallel                             mirai
==================================== ===============================================
``makeCluster(4)``                   ``daemons(4)`` or ``make_cluster(4)``
``clusterExport(cl, "x")``           Pass via ``.args``/``...``, or ``everywhere()``
``clusterEvalQ(cl, library(pkg))``   ``everywhere(library(pkg))``
``parLapply(cl, X, FUN)``            ``mirai_map(X, FUN)[]``
``parSapply(cl, X, FUN)``            ``mirai_map(X, FUN)[.flat]``
``mclapply(X, FUN, mc.cores = 4)``   ``daemons(4); mirai_map(X, FUN)[]``
``stopCluster(cl)``                  ``daemons(0)``
==================================== ===============================================

Drop-in cluster backend
-----------------------

For code that already uses the ``parallel`` package extensively,
``make_cluster()`` returns a cluster that works with every ``parallel::par*``
function. Executed with mirai 2.7.2 on R 4.5.3.

.. code:: r

   cl <- mirai::make_cluster(4)
   parallel::parLapply(cl, 1:100, my_func)
   mirai::stop_cluster(cl)

   # R >= 4.5: native integration
   cl <- parallel::makeCluster(4, type = "MIRAI")
   parallel::stopCluster(cl)
