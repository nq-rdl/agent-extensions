Conventional Commits Guidance
==============================

This document provides detailed guidelines based on the `Conventional Commits v1.0.0 specification <https://www.conventionalcommits.org/en/v1.0.0/>`_.

Core Rules
----------

1. Commits MUST be prefixed with a type (e.g., ``feat``, ``fix``), followed by the OPTIONAL scope, OPTIONAL ``!``, and REQUIRED terminal colon and space.
2. The type ``feat`` MUST be used when a commit adds a new feature.
3. The type ``fix`` MUST be used when a commit represents a bug fix.
4. A scope MAY be provided after a type. A scope MUST consist of a noun describing a section of the codebase surrounded by parenthesis, e.g., ``fix(parser):``.
5. A description MUST immediately follow the colon and space after the type/scope prefix. The description is a short summary of the code changes.
6. A longer commit body MAY be provided after the short description, providing additional contextual information about the code changes. The body MUST begin one blank line after the description.
7. A commit body is free-form and MAY consist of any number of newline separated paragraphs.
8. One or more footers MAY be provided one blank line after the body. Each footer MUST consist of a word token, followed by either a ``:<space>`` or ``<space>#`` separator, followed by a string value.
9. A footer's token MUST use ``-`` in place of whitespace characters, e.g., ``Acked-by``. An exception is made for ``BREAKING CHANGE``, which MAY also be used as a token.
10. A footer's value MAY contain spaces and newlines, and parsing MUST terminate when the next valid footer token/separator pair is observed.
11. Breaking changes MUST be indicated in the type/scope prefix of a commit, or as an entry in the footer.
12. If included as a footer, a breaking change MUST consist of the uppercase text ``BREAKING CHANGE``, followed by a colon, space, and description.
13. If included in the type/scope prefix, breaking changes MUST be indicated by a ``!`` immediately before the ``:``. If ``!`` is used, ``BREAKING CHANGE:`` MAY be omitted from the footer section.
14. Types other than ``feat`` and ``fix`` MAY be used (e.g., ``docs:``, ``chore:``, ``refactor:``).
15. The units of information that make up Conventional Commits MUST NOT be treated as case-sensitive by implementors, with the exception of ``BREAKING CHANGE`` which MUST be uppercase.
16. ``BREAKING-CHANGE`` MUST be synonymous with ``BREAKING CHANGE``, when used as a token in a footer.

Frequently Asked Questions
--------------------------

How does this relate to SemVer?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- ``fix`` type commits should be translated to PATCH releases.
- ``feat`` type commits should be translated to MINOR releases.
- Commits with ``BREAKING CHANGE`` in the commits, regardless of type, should be translated to MAJOR releases.

What do I do if the commit conforms to more than one of the commit types?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Go back and make multiple commits whenever possible. Conventional Commits drives us to make more organized commits and PRs.

Are the types in the commit title uppercase or lowercase?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Any casing may be used, but it's best to be consistent. Lowercase is the convention.

How does Conventional Commits handle revert commits?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Conventional Commits does not make an explicit effort to define revert behavior. A common recommendation is to use the ``revert`` type, and a footer that references the commit SHAs that are being reverted:

.. code-block:: text

   revert: let us never again speak of the noodle incident

   Refs: 676104e, a215868

What if I accidentally use the wrong commit type?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Prior to merging/releasing: Use ``git rebase -i`` to edit the commit history.
- After releasing: If the type is recognized by the spec but incorrect (e.g., ``fix`` instead of ``feat``), cleanup depends on tools. If a non-spec type is used (e.g., ``feet``), it will simply be missed by tools based on the spec.
