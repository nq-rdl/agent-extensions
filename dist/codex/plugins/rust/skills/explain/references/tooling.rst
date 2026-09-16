Rust Tooling as a Teaching Aid
==============================

Let the tools do the mechanical work, then explain *why* their output is right.
None of this needs a wrapper script — run the tools directly.

Trust boundary first
--------------------

Compiling Rust runs code — and even *type-checking* can read your machine. Both
are part of the trust boundary, in two layers:

- **Any Cargo command that compiles** — ``cargo check``, ``cargo clippy``,
  ``cargo build``, ``cargo doc``, ``cargo expand``, ``cargo test``, ``cargo
  run`` — **runs** the crate's ``build.rs`` and any procedural macros as part of
  compiling: arbitrary code, executed before you ever run a binary. (``cargo
  expand`` is the sharpest case — expanding a proc-macro *is* executing it — and
  ``cargo doc --open`` also launches a browser.)
- **Plain ``rustc`` on a single file is lower-risk, not safe.** No manifest
  means no ``build.rs``, and with no proc-macro crate to link, none of *those*
  run — but ``rustc`` still expands **built-in** macros at compile time, and
  ``env!``, ``option_env!``, ``include_str!``, ``include_bytes!``, and
  ``include!`` read environment variables and files straight off your machine.
  A snippet can fold them into a diagnostic, and the message — which this skill
  tells you to read back — becomes an exfiltration channel. Verified with rustc
  1.94.1: ``compile_error!(env!("HOME"))`` makes the compiler print your home
  path, and ``compile_error!(include_str!("…/secret"))`` prints a file's
  contents — no binary, build script, or proc-macro required.

So for **untrusted** code, do not compile it on your own machine at all: read
and explain it statically, or compile only inside a disposable sandbox with a
**scrubbed environment** and no access to your home or repo, treating every
diagnostic as attacker-controlled output. Reserve ``rustc`` / Cargo on the real
machine for code you trust. This is the same caution the skill applies to mode 2
("Why does / doesn't this compile").

cargo clippy — the free senior reviewer
---------------------------------------

``cargo clippy`` is Rust's idiom linter. Let it find the non-idiomatic code, then
explain the reasoning instead of merely echoing the fix.

.. code:: text

   warning: the loop variable `i` is only used to index `v`
    --> idiom.rs:3:14
     |
   3 |     for i in 0..v.len() {
     |              ^^^^^^^^^^
     |
     = note: `#[warn(clippy::needless_range_loop)]` on by default
   help: consider using an iterator
     |
   3 -     for i in 0..v.len() {
   3 +     for <item> in &v {
     |

Teach it: "Clippy flags ``needless_range_loop`` (see the `clippy lint index
<https://rust-lang.github.io/rust-clippy/stable/index.html#needless_range_loop>`__).
Indexing ``v[i]`` re-checks bounds every iteration and hides intent; ``for x in
&v`` (equivalently ``v.iter()``) iterates the elements directly — clearer, and
it lets the optimizer elide the per-iteration bounds check in the common case
(bounds-check *elimination* is an LLVM optimization, not a language guarantee).
This is the gap between *works* and *fluent*." For the
idiomatic-rewrite mode, run clippy first, then walk each lint.

rustc errors as teachers
------------------------

Feed the **code and the real compiler message together**, then explain what the
rule protects against. Two canonical examples:

.. code:: text

   error[E0382]: borrow of moved value: `s`
    --> move.rs:4:20
     |
   3 |     let t = s;
     |             - value moved here
   4 |     println!("{}", s);
     |                    ^ value borrowed here after move

"``s`` was *moved* into ``t``, so ``s`` is no longer usable — not emptied,
**invalidated**: the value now lives in ``t`` and the compiler statically
forbids touching ``s``. It is preventing two owners of one heap buffer — which
would double-free at scope end. Fix: borrow (``&s``) if you only need to read,
or ``.clone()`` if you genuinely need a second copy."

.. code:: text

   error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable
    --> borrow.rs:4:5
     |
   3 |     let first = &v[0];
     |                  - immutable borrow occurs here
   4 |     v.push(4);
     |     ^^^^^^^^^ mutable borrow occurs here
   5 |     println!("{first}");
     |                ----- immutable borrow later used here

"``push`` can reallocate the vector, which would leave ``first`` dangling. The
borrow checker forbids a mutable borrow while a shared borrow is still live —
exactly the iterator-invalidation bug that C++ allows silently."

Use ``rustc --explain E0502`` for the long-form explanation of any error code.

Invoking ``rustc`` on a snippet: two defaults will mislead you. Bare
``rustc file.rs`` assumes **edition 2015** and a **binary** crate, so modern
syntax (``async``, ``let … else``) trips an edition error and any snippet
without ``fn main`` trips ``error[E0601]`` — spurious errors that hide the
borrow/lifetime one you actually want. Type-check a snippet like this instead:

.. code:: text

   rustc --edition 2021 --crate-type lib --emit=metadata snippet.rs -o "$(mktemp -d)/meta"

``--edition`` should match the code (read it from ``Cargo.toml`` or ask the
reader; use ``2024`` for the newest); ``--crate-type lib`` drops the ``fn main``
requirement; ``--emit=metadata`` type-checks without producing — or running — a
binary. Send the metadata to a throwaway temp dir rather than ``/dev/null``:
``rustc`` writes its temp files *next to* the ``-o`` path, so a non-writable
location (``/dev``) makes it abort with its own spurious error. Read the
diagnostics it prints — a non-zero exit just means it found the error you were
after. Run this only on code you trust, or inside the scrubbed sandbox from
"Trust boundary first": even this type-check expands ``env!`` / ``include_str!``,
so a hostile snippet can leak local data into the very diagnostics you read
back. Code that pulls in external crates will not compile standalone: that needs
the crate's own build, which means trusted code or a sandbox, not raw ``rustc``.

rust-analyzer — navigation
--------------------------

The IDE language server. For *reading*, its highest-value features are:

- **Hover** — shows the inferred type of any expression. Rust infers most types,
  so hover makes the invisible visible.
- **Inlay hints** — inline type and parameter-name annotations.
- **Go to definition / find references** — trace where a trait impl or value
  actually comes from.

But it is **not** outside the trust boundary. By default rust-analyzer runs the
project's ``build.rs`` and procedural macros (``cargo.buildScripts.enable`` and
``procMacro.enable`` are on) so its analysis is accurate — which means merely
*opening* an untrusted workspace can execute code. "Read-only navigation" is not
read-only (rust-analyzer says as much in its own security note — see
``references/canonical-sources.rst``). On untrusted code, read files statically
instead, or open it in a disposable sandbox with build scripts, proc-macros, and
check-on-save disabled and any project-supplied editor/tool configuration
ignored.

cargo doc & cargo expand
------------------------

- ``cargo doc --open`` builds and opens the API docs for the crate *and all its
  dependencies* — the fastest way to learn what an unfamiliar type offers.
- ``cargo expand`` shows what a macro expands to. When ``#[derive(...)]`` or a
  ``name!()`` macro is opaque, expand it to read the generated code (requires the
  ``cargo-expand`` tool).

Both compile the crate, so the **trust boundary above applies** — run them only
on trusted code or in a sandbox. For *untrusted* code, the non-executing
substitutes are: read the prebuilt docs on `docs.rs <https://docs.rs/>`__
(already built in a sandbox) or the crate source directly instead of
``cargo doc``; and read the macro's definition by hand (or expand it inside a
throwaway container) instead of running ``cargo expand``, since expansion
*executes* the macro.
