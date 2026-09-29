Remote and HPC daemons
======================

``daemons(url =, remote =)`` listens at ``url`` and launches daemons with a
launcher configuration. ``host_url()`` gives this machine's address;
``local_url()`` gives a local socket (``local_url(tcp = TRUE)`` for a TCP
port, as needed for SSH tunnelling). Function names and arguments were checked
against mirai 2.7.2 on 2026-09-29; launching was not exercised (no remote
hosts available).

Contents
--------

- `SSH (direct connection) <#ssh-direct-connection>`__
- `SSH (tunnelled) <#ssh-tunnelled>`__
- `HPC cluster <#hpc-cluster>`__
- `HTTP launcher <#http-launcher>`__

SSH (direct connection)
-----------------------

The remote hosts must be able to connect back to this machine.

.. code:: r

   daemons(
     url = host_url(tls = TRUE),
     remote = ssh_config(c("ssh://user@node1", "ssh://user@node2"))
   )

SSH (tunnelled)
---------------

For firewalled environments: the daemons connect back through the SSH
tunnel, so ``url`` must be a local TCP URL.

.. code:: r

   daemons(
     n = 4,
     url = local_url(tcp = TRUE),
     remote = ssh_config("ssh://user@node1", tunnel = TRUE)
   )

HPC cluster
-----------

``cluster_config()`` submits daemons as jobs (Slurm ``sbatch``, SGE/PBS
``qsub``, LSF ``bsub``). ``options`` holds scheduler directives, one per line.

.. code:: r

   daemons(
     n = 1,
     url = host_url(),
     remote = cluster_config(
       command = "sbatch",
       options = "#SBATCH --job-name=mirai\n#SBATCH --mem=8G\n#SBATCH --array=1-50",
       rscript = file.path(R.home("bin"), "Rscript")
     )
   )

HTTP launcher
-------------

For platforms that launch jobs over HTTP, such as Posit Workbench:

.. code:: r

   daemons(n = 2, url = host_url(), remote = http_config())

Remote daemons follow the same rules as local ones: pass every dependency,
qualify package functions, and reset with ``daemons(0)``.
