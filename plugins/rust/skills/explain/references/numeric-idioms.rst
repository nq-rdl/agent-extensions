Numeric & Scientific Rust
=========================

A recognition guide for numeric Rust, plus the highest-value job: catching code
that compiles but is **quietly wrong**. The reader has a computational-science
background — correctness is the deliverable.

Ecosystem Idioms to Recognize
-----------------------------

- **ndarray** — N-dimensional arrays (the NumPy of Rust). ``Array2<f64>`` is an
  owned 2-D array; ``ArrayView2<f64>`` borrows one. Watch for ``.slice()`` with
  the ``s![..]`` indexing macro.
- **nalgebra** — linear algebra where *statically sized* types carry their
  dimensions in the type: ``Matrix3<f64>``, ``Vector4<f64>``, ``SMatrix`` — there
  a shape mismatch is a *compile-time* type error. But nalgebra also has
  **dynamically sized** ``DMatrix<f64>`` / ``DVector<f64>`` (and mixed
  static/dynamic shapes) whose dimensions are known only at runtime: there a
  mismatch is a **runtime panic**, not a type error. Don't read "nalgebra" as
  "shapes proven at compile time" — check whether the types are static or
  dynamic, and guard or test dynamic operations the way you would any runtime
  bound.
- **faer** — high-performance dense linear algebra (decompositions, solves) built
  for speed; recognize ``faer::Mat``.
- **polars** — dataframes (the Rust pandas): a lazy ``LazyFrame`` query plan and
  an eager ``DataFrame``.
- **rayon** — data parallelism by changing ``.iter()`` to ``.par_iter()``. If you
  see ``par_iter`` / ``par_bridge`` / ``into_par_iter``, the loop runs on a
  thread pool.

FFI Reading: Rust Calling Native Libraries
------------------------------------------

A call into a C-ABI library (BLAS / LAPACK, a vendor kernel) looks like this on
the **2024 edition**:

.. code:: rust

   unsafe extern "C" {               // 2024 edition: the extern block is `unsafe`
       // a function provided by a C library, linked at build time;
       // an unmarked item defaults to `unsafe` to call
       fn cblas_ddot(n: i32, x: *const f64, incx: i32, y: *const f64, incy: i32) -> f64;
   }

   let dot = unsafe {                 // unsafe: the compiler cannot verify the C side
       cblas_ddot(n, x.as_ptr(), 1, y.as_ptr(), 1)
   };

Reading rules:

- ``extern "C"`` = "this uses the C ABI" (the calling convention for FFI).
- **Editions differ — expect both forms.** Since the 2024 edition the block
  must be written ``unsafe extern "C" { … }``, and each item may be marked
  ``safe`` (callable without an ``unsafe`` block) or ``unsafe`` / left unmarked
  (the caller upholds the contract). Crates on the 2015/2018/2021 editions still
  use a bare ``extern "C" { … }``. If the form looks unfamiliar, confirm against
  the Edition Guide (``references/canonical-sources.rst``) rather than guessing
  — this is exactly the kind of syntax that drifts between editions.
- Raw pointers ``*const T`` / ``*mut T`` are the C-facing types; ``.as_ptr()``
  hands a slice's buffer to C.
- ``unsafe`` does **not** mean "wrong." It means *the compiler's guarantees stop
  here; a human asserts the contract*. Read every ``unsafe`` block as a claim to
  audit: are the pointers valid, the lengths right, the data still live?

Silent-Bug Radar (highest value)
--------------------------------

Rust's compiler eliminates whole bug classes — but **only in safe code, and
never your math.** Anchor every review on this split.

**In safe Rust, memory safety is not yours to re-audit** — but mind *how* each
class is ruled out. The compiler **rejects at compile time**: use-after-free,
double-free, data races on shared memory, null dereferences, uninitialized
reads. **Out-of-bounds is different** — the compiler does *not* catch it; safe
Rust instead **converts it into a guaranteed runtime panic** (or a ``None`` from
``.get()``), never silent corruption. So indexing is safe from *corruption*, but
a wrong index still panics — a production failure to handle, and a correctness
bug to chase (the stencil off-by-ones below).

**Inside ``unsafe`` / FFI they come back.** A wrong pointer, length, or lifetime
in an ``unsafe`` block or a C call can reintroduce every one of those — the
``unsafe`` contract, not the compiler, is what holds them off. Audit each
``unsafe`` region for exactly the bugs safe Rust had ruled out (Nomicon, via
``references/canonical-sources.rst``).

**The compiler never catches** (audit these every time): *your math.* Code that
satisfies the borrow checker can still compute the wrong number.

Look hard at:

- **Stencil / index off-by-ones.** Loop bounds such as ``1..n-1`` versus
  ``1..n``, halo / ghost-cell handling, ``len()`` versus ``len()-1``. A bounds
  check turns a bad index into a *panic*, not a silently wrong result — but the
  wrong-but-in-range index is silent.
- **Aliasing & bounds promises in ``unsafe`` / FFI.** Read the contract
  precisely — the common constructs promise *different* things. ``split_at_mut``
  is **safe**: it hands back two slices the compiler *guarantees* do not
  overlap, so trust it. ``get_unchecked`` / ``get_unchecked_mut`` are
  **unsafe**: they drop the bounds check, so the *caller* must guarantee the
  index is in bounds (a wrong index is undefined behavior, not a panic). The
  **aliasing** rule constrains *live references*, and it bites on every *access*
  to that memory while a reference is live — not only when a second reference is
  created. Holding several ``*mut T`` is fine in itself, but *reading or writing*
  through a raw pointer (or letting C/FFI write) while a ``&mut`` to the same
  bytes is live — or mutating while a non-``UnsafeCell`` ``&`` is live — is
  undefined behavior, even though no second ``&mut`` ever exists. So audit the
  *accesses*: every raw-pointer load/store and FFI write that touches memory a
  live reference still covers, not just where unsafe code hands out another
  reference (and ``split_at_mut`` itself stays safe — its two slices are
  disjoint by construction). A broken aliasing assumption corrupts results
  silently (Reference → Behavior considered undefined; std ``slice`` docs).
- **Parallel-reduction nondeterminism.** Floating-point ``+`` is not associative,
  so a ``rayon`` reduction can give a *different sum* per run depending on
  chunking — correct-looking, not reproducible. Flag when a ``par_iter().sum()``
  or a custom ``reduce`` feeds a result that must be bit-reproducible.
- **Concurrency beyond data races.** Safe Rust rules out *data races*, not
  concurrency bugs in general — ``Arc<Mutex<T>>`` and ``rayon`` code that
  compiles can still **deadlock**, **poison a lock** (``.lock()`` returns
  ``Err`` after a holder panics mid-critical-section), use the wrong atomic
  ``Ordering`` (``Relaxed`` where ``Acquire``/``Release`` was needed), or lose a
  **check-then-act race** across two locks or atomics. The symptom is a hang or
  a nondeterministic wrong result, never a compile error — so audit the *logic*,
  not just the types.
- **Integer / float casts.** ``as`` is silent and the rule depends on the
  types. A **narrowing** integer→integer cast keeps the low bits
  (``300_i32 as u8`` is ``44``). A **widening** cast that stays in the same
  signedness preserves the value (``-1_i8 as i32`` is ``-1``; ``200_u8 as u32``
  is ``200``). But casting a **signed value into an unsigned type** turns a
  negative number into a large positive one — ``-1_i32 as u32`` is
  ``4294967295`` and ``-1_i32 as usize`` is ``usize::MAX`` — the classic silent
  ``-1``-as-index bug, regardless of width. Meanwhile float→integer
  **saturates** to the target's range with ``NaN`` mapping to ``0``
  (``300.0_f32 as u8`` is ``255``, ``-1.0_f32 as u8`` is ``0``). Separately,
  overflowing *arithmetic* on ``usize`` indices **panics in debug builds but
  wraps in release by default**
  (it tracks the ``overflow-checks`` profile flag) — so an index bug can stay
  hidden until the optimized build (Reference → Type cast expressions).

When reviewing a generated kernel, state the split explicitly: "in the safe
regions the compiler guarantees memory safety and data-race freedom (not
deadlocks, lock poisoning, atomic ordering, or logical races); inside
``unsafe`` / FFI you must audit those memory and data-race classes too;
**nowhere** does it guarantee the arithmetic or the concurrency logic — check
the indices, the reduction order, the casts, and the locking."
