Rust Reading Vocabulary
=======================

The fixed pattern set behind most "I can't read this." For a reader who already
programs: each entry is **what it does** + **why it's there**, oriented toward
*reading* code, not writing it. Explain on Rust's own terms; reach for a C++ or
Python analogy only when it truly clarifies.

Ownership & Borrowing
---------------------

``T`` owns its value; ``&T`` borrows it (shared, read-only); ``&mut T`` borrows
it exclusively (read-write). Assigning or passing an owned non-``Copy`` value
*moves* it — the source is *invalidated* and can no longer be used.

.. code:: rust

   let s = String::from("grid");
   let t = s;            // value MOVES from s to t
   // println!("{s}");   // would not compile: s no longer owns anything
   println!("{t}");      // t is the owner now

*Why it's there:* ownership frees memory without a garbage collector and prevents
use-after-free at compile time. Reading rule: a bare ``T`` in a signature takes
ownership (the caller gives it up); ``&T`` / ``&mut T`` borrows (the caller keeps
it).

Lifetimes
---------

A lifetime like ``'a`` names *how long a reference is valid*. You mostly read
them in signatures: ``fn first<'a>(xs: &'a [f64]) -> &'a f64`` says "the returned
reference lives as long as the slice you passed in." Most lifetimes are *elided*
(inferred); you only see explicit ones when the compiler cannot guess the
relationship.

*Why it's there:* lifetimes let the borrow checker prove a reference never
outlives the data it points to — no dangling pointers. Reading rule: ``'a`` is
not a value, it is a constraint; read which inputs and outputs share a lifetime
and ignore the rest of the noise.

Error Flow
----------

``Result<T, E>`` is "either a ``T`` (``Ok``) or an error ``E`` (``Err``)";
``Option<T>`` is "either a ``T`` (``Some``) or nothing (``None``)". The ``?``
operator means "unwrap the ``Ok`` / ``Some``, or return the ``Err`` / ``None``
from this function early."

.. code:: rust

   fn load(path: &str) -> Result<String, std::io::Error> {
       let text = std::fs::read_to_string(path)?;  // ? returns early on Err
       Ok(text)
   }

``.unwrap()`` and ``.expect("msg")`` extract the value but **panic** on ``Err`` /
``None`` — a crash point. Flag them in code meant to be robust.

*Why it's there:* errors are ordinary values, so the type system forces you to
handle (or explicitly defer with ``?``) every failure. Reading rule: ``?`` is a
propagation shortcut; ``.unwrap()`` is a "trust me, cannot fail here" — and a
place bugs hide.

Traits & Generics
-----------------

A trait is a shared interface (close to a C++ concept or a Python protocol).
Generics with ``where`` bounds say "any type that implements this trait."

.. code:: rust

   // signature sketch — `Float` comes from the num_traits crate
   fn norm<T>(xs: &[T]) -> T
   where
       T: num_traits::Float,
   {
       xs.iter().fold(T::zero(), |a, &x| a + x * x).sqrt()
   }

- ``impl Trait`` in argument position = "some type implementing Trait", resolved
  at compile time (*monomorphized* — one specialized copy per concrete type, zero
  runtime cost).
- ``dyn Trait`` (a *trait object*, usually ``Box<dyn Trait>`` or ``&dyn Trait``)
  = dynamic dispatch through a vtable (one copy of the code, runtime
  indirection).

*Why it's there:* traits give polymorphism with a choice of cost model. Reading
rule: ``impl`` / generic = compile-time, fast, larger binary; ``dyn`` = runtime
dispatch, smaller binary, slight overhead.

Pattern Matching
----------------

``match`` destructures a value against patterns, *exhaustively* (every case must
be handled). ``if let`` and ``let ... else`` are shorthands for matching a single
pattern.

.. code:: rust

   match result {
       Ok(v) => use_it(v),
       Err(e) => report(e),
   }

   let Some(x) = maybe else {
       return;            // bail out if None
   };

*Why it's there:* exhaustiveness means adding a new enum variant forces you to
update every match — the compiler finds the gaps. Reading rule: arms are tried
top-to-bottom; ``_`` is the catch-all.

Smart Pointers & Combinations
-----------------------------

- ``Box<T>`` — owned value on the heap (one owner).
- ``Rc<T>`` / ``Arc<T>`` — shared ownership by reference counting (``Arc`` is the
  thread-safe, atomic version).
- ``Weak<T>`` — a *non-owning* ``Rc`` / ``Arc`` handle (from ``Rc::downgrade`` /
  ``Arc::downgrade``). It does **not** keep the value alive; you call
  ``.upgrade()`` to get an ``Option<Rc<T>>`` (or ``Option<Arc<T>>`` on the
  ``Arc`` side) and find out whether it still exists. Its purpose is to
  **break reference cycles** (see below).
- ``RefCell<T>`` / ``Mutex<T>`` — interior mutability: mutate through a shared
  reference, with the borrow rule enforced at *runtime* (``RefCell``, single
  thread) or via a lock (``Mutex``, across threads).

Read combinations inside-out. ``Arc<Mutex<T>>`` = "a ``T`` that several threads
share (``Arc``) and take turns mutating under a lock (``Mutex``)" — the canonical
shared-mutable-state-across-threads shape.

*Why it's there:* these recover patterns that ownership alone forbids — sharing,
back-references, mutate-through-shared — each naming its exact cost. One caveat
worth flagging when you see it: ``Rc`` / ``Arc`` do **not** manage *cycles* — a
cycle of strong references never reaches refcount 0 and leaks, and ``Weak<T>``
is precisely how correct code breaks it (Book §15.6, via
``references/canonical-sources.rst``). Reading rule: the outer wrapper is the
sharing model, the inner one is the data, and a ``Weak`` is a deliberately
non-owning edge.

Closures & Iterators
--------------------

A closure ``|x| x * x`` is an anonymous function that can capture variables. The
trait it implements says how it can be *called*: ``Fn`` (via ``&self`` — only
reads its captures, so callable repeatedly), ``FnMut`` (via ``&mut self`` — may
mutate captures), ``FnOnce`` (via ``self`` — may move captures out, so callable
once). ``move`` is separate: it forces the closure to *capture by value* (take
ownership), common when spawning threads — a ``move`` closure can still be
``Fn`` if its body only reads what it captured.

Iterator chains are **lazy**: ``.iter().map(...).filter(...)`` builds a pipeline
that does nothing until a *consumer* (``.collect()``, ``.sum()``, a ``for`` loop)
drives it.

.. code:: rust

   let squares: Vec<f64> = xs.iter().map(|x| x * x).collect();
   let total: f64 = squares.iter().sum();

*Why it's there:* laziness lets chains fuse into a single pass with no
intermediate allocations — the *zero-cost-abstraction* intent is that they
optimize down to roughly what a hand-written loop emits (an optimizer outcome,
not a language guarantee). Reading rule: find the consumer at the end of the
chain; that is what actually runs the work.

Macros
------

A trailing ``!`` marks a macro invocation, not a function call: ``println!``,
``vec!``, ``assert_eq!``. Macros run at compile time and accept "syntax" a
function cannot (format strings, variadic arguments). ``#[derive(Debug, Clone)]``
is a *derive macro* that generates trait implementations for you.

*Why it's there:* macros remove boilerplate the type system cannot. Reading rule:
treat ``name!(...)`` as "expands to some code"; when you must see what, use
``cargo expand`` (see ``references/tooling.rst``).

Modules, Visibility & Turbofish
-------------------------------

``mod`` defines a module; ``pub`` exposes an item; ``use`` brings a path into
scope. Paths use ``::`` (``std::sync::Arc``). The **turbofish** ``::<>`` pins a
generic type the compiler cannot infer:

.. code:: rust

   let v = "42".parse::<i32>().unwrap();      // ::<i32> tells parse what to make
   let xs = (0..n).map(|i| i as f64).collect::<Vec<f64>>();  // ::<Vec<f64>> picks the container

*Why it's there:* explicit paths and visibility keep the module graph auditable.
Reading rule: a turbofish always answers "what type?" for the call immediately
before it.
