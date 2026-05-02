TDD Methodology Reference
=========================

The 4-Phase Cycle
-----------------

Test-Driven Development (TDD) structures development around a short,
repeating cycle:

::

   red      → write a failing test that specifies intended behaviour
   green    → write the minimum code to make the test pass
   refactor → improve the code without changing behaviour
   review   → verify quality and correctness

Each phase has a strict constraint: - **red phase**: write tests only.
The code does not exist or fails. - **green phase**: write the minimum
implementation. Tests pass. - **refactor phase**: improve quality. Tests
still pass. - **review phase**: act as a quality gate that either
approves or requests changes.

The discipline comes from never mixing phases. You don’t refactor while
red. You don’t add features while green.

Why Tests First?
----------------

Writing tests before code forces you to think about the interface and
behaviour before the implementation. This produces:

1. **Better APIs** — you use the API before writing it; awkward APIs
   become obvious immediately
2. **Minimal implementations** — you implement exactly what is tested,
   reducing dead code
3. **Living documentation** — tests document intended behaviour in
   executable form
4. **Confidence** — a full suite of green tests lets you refactor
   fearlessly

The Three Laws (Robert C. Martin)
---------------------------------

1. You may not write production code unless it is to make a failing test
   pass.
2. You may not write more of a unit test than is sufficient to fail, and
   not compiling is failing.
3. You may not write more production code than is sufficient to pass the
   currently failing test.

Test Quality
------------

Good tests are: - **Fast** — run in milliseconds - **Isolated** — don’t
depend on other tests or shared state - **Repeatable** — same result
every run - **Self-checking** — assert a specific expected outcome -
**Timely** — written just before the code

Bad tests: - Test implementation details (not behaviour) - Are trivially
true - Have multiple unrelated assertions - Depend on external services
without mocking

Naming Tests
------------

Test names should read as specifications:

.. code:: python

   # Bad
   def test_fizzbuzz():
       ...

   # Good
   def test_multiples_of_3_return_fizz():
       ...

   def test_multiples_of_15_return_fizzbuzz_not_fizz_or_buzz():
       ...

Triangulation
-------------

When multiple tests are needed to drive out the correct algorithm, use
triangulation:

1. First test: hardcode the return value
2. Second test: hardcode a second case
3. Third test: generalise (the duplication forces you to write the real
   algorithm)

.. code:: python

   # Test 1: hardcoding passes
   def fizzbuzz(n):
       return "Fizz"  # passes test_multiples_of_3_return_fizz

   # Test 2: the second test breaks hardcoding
   def test_multiples_of_5_return_buzz():
       assert fizzbuzz(5) == "Buzz"  # fails — forces real logic

   # Now implement:
   def fizzbuzz(n):
       if n % 3 == 0: return "Fizz"
       if n % 5 == 0: return "Buzz"
       return str(n)

Common Mistakes
---------------

**Mistake 1: Writing too many tests at once** Write ONE failing test,
make it green, then write the next. The cycle should be minutes long,
not hours.

**Mistake 2: Refactoring while red** Never refactor when tests are
failing. Revert to green first.

**Mistake 3: Testing implementation, not behaviour** Tests should verify
outputs for given inputs, not inspect internal state or call order.

**Mistake 4: Skipping the refactor phase** The refactor phase is where
you pay back the debt incurred by writing minimum green code. Don’t skip
it.

**Mistake 5: Making tests pass by deleting them** If a test is hard to
make pass, that’s information — the design may need rethinking.

The Review Phase
----------------

The review phase is not an afterthought, but a core part of the TDD
cycle. The reviewer acts as a quality gate that checks: 1. Did the tests
actually specify the feature? (red discipline) 2. Is the implementation
minimal? (green discipline) 3. Is the code clean and readable? (refactor
discipline) 4. Are all tests passing? (cycle complete)

The reviewer issues an ``APPROVED|review`` token when all four criteria
are met, or issues a ``REQUEST_CHANGES|review|<reason>`` token with a
specific actionable reason to start a new cycle.

Orchestration and Dispatch
--------------------------

In our automated workflow, the **orchestrator** manages the 4-phase
cycle by dispatching specialized **phase agents** to configured
backends. The orchestrator never writes code directly.

At the end of their work, each phase agent produces a standardized
status token to communicate with the orchestrator: - ``DONE|<phase>``:
The phase agent completed its work successfully. - ``APPROVED|review``:
The reviewer agent approved the cycle. -
``REQUEST_CHANGES|review|<reason>``: The reviewer agent found issues.
This triggers a new cycle starting back at the red phase. -
``ERROR|<phase>|<reason>``: The phase failed unexpectedly.

To enforce progress and prevent infinite cycles, the orchestrator uses a
cycle cap (default 3 cycles). If the reviewer requests changes but the
maximum cycle count is reached, the process halts to avoid endless
rework.

References
----------

- Kent Beck, *Test-Driven Development: By Example* (2002)
- Robert C. Martin, *Clean Code* (2008), Chapter 9: Unit Tests
- Martin Fowler, “Test-Driven Development”
  (martinfowler.com/bliki/TestDrivenDevelopment.html)
