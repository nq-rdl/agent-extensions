"""Installed prose links remain validated while executable examples stay literal."""

from pathlib import Path
import tempfile
import unittest

from scripts import codex_package as package
from tests.test_codex_package import fixture


class ProseAndLinks(unittest.TestCase):
    def test_subject_invocations_preserve_fences_and_inline_host_commands(self):
        examples = (
            '   ```json\n   {"command": "/sample:task"}\n   ```\n',
            '  ~~~~text\n/sample:task\n~~~\n/sample:task\n  ~~~~\n',
            '````markdown\n```text\n/sample:task\n```\n````\n',
            '    /sample:task\n    /sample:task arg\n',
        )
        for example in examples:
            with self.subTest(example=example):
                text = 'Use `/sample:task` and /sample:task.\n\n' + example + '\nUse ``/sample:task``. Keep `run /sample:task args` and ``echo `/sample:task` ``.\n'
                actual = package.prose_invocations(text, {"sample:task"})
                self.assertIn(example, actual)
                self.assertTrue(actual.startswith('Use `$sample:task` and $sample:task.'))
                self.assertIn('Use ``$sample:task``.', actual)
                self.assertIn('Keep `run /sample:task args` and ``echo `/sample:task` ``.', actual)

    def test_markdown_links_definitions_images_and_destination_syntax(self):
        text = '''[read](guide.rst#section) ![image](images/logo.svg)
[quoted](<files/with spaces.rst> "Title")
[paren](files/name(1).rst)
[escaped](files/name\\(2\\).rst)
[encoded](files/with%20spaces.rst?download=1)
[manual][ref]
[ref]: manual.rst "Title"
[next]:
  next.rst
[external](https://example.com/page) [anchor](#local) [email](mailto:test@example.com)
`[code](not-a-link.rst)` and ``[code](also-not-a-link.rst)``
\\[escaped](not-a-link.rst)
'''
        self.assertEqual(list(package.local_links(text)), [
            'guide.rst', 'images/logo.svg', 'files/with spaces.rst',
            'files/name(1).rst', 'files/name(2).rst', 'files/with spaces.rst',
            'manual.rst', 'next.rst',
        ])

    def test_rst_headings_anchors_and_inline_links(self):
        text = '''.. _intro:

Introduction
~~~~~~~~~~~~

Read `layout <layout.rst>`_ and `navigation <navigation.rst#nav>`__.

Details
~~~~~~~

.. _manual: manual.rst
.. _alias: intro_

Read [more](more.rst).
'''
        self.assertEqual(list(package.local_links(text, '.rst')), [
            'layout.rst', 'navigation.rst', 'manual.rst', 'more.rst',
        ])

    def test_admonitions_and_wrapped_rst_labels_are_prose(self):
        text = '''.. note::

   Read `the wrapped
   manual <manual.rst>`_.

.. admonition:: Further reading

   Read `details <details.rst>`__.

   Example::

      `fake <fake.rst>`_

.. warning::

   Read `warning <warning.rst>`_.
'''
        self.assertEqual(list(package.local_links(text, '.rst')), [
            'manual.rst', 'details.rst', 'warning.rst',
        ])

    def test_footnote_definitions_are_prose_not_link_destinations(self):
        text = 'A statement.[^note]\n\n[^note]: Explanation with [manual](manual.rst).\n'
        self.assertEqual(list(package.local_links(text)), ['manual.rst'])

    def test_loose_list_prose_and_nested_code_keep_distinct_scopes(self):
        text = '''- Resources:

    Invoke /sample:task and read [manual](manual.rst).

    - More resources:

      Read [details](details.rst).

          [fake](indented-example.rst) /sample:task

      ```markdown
      [fake](fenced-example.rst) /sample:task
      ```

    Use `/sample:task` again.

[outside](outside.rst)
'''
        self.assertEqual(list(package.local_links(text)), ['manual.rst', 'details.rst', 'outside.rst'])
        actual = package.prose_invocations(text, {'sample:task'})
        self.assertIn('Invoke $sample:task', actual)
        self.assertIn('Use `$sample:task` again.', actual)
        self.assertIn('[fake](indented-example.rst) /sample:task', actual)
        self.assertIn('[fake](fenced-example.rst) /sample:task', actual)

    def test_code_blocks_do_not_contribute_links(self):
        markdown = '''[before](before.rst)

   ```markdown
   [fake](fake1.rst)
   ```

  ~~~~markdown
[fake](fake2.rst)
~~~
[fake](fake3.rst)
  ~~~~

    [fake](fake4.rst)

[after](after.rst)
'''
        rst = '''Read `before <before.rst>`_.

.. code-block:: markdown
   :caption: Example

   [fake](fake1.rst)

Literal example::

    `fake <fake2.rst>`_

```markdown
[fake](fake3.rst)
```

Read `after <after.rst>`_.
'''
        for suffix, text in (('.md', markdown), ('.rst', rst)):
            with self.subTest(suffix=suffix):
                self.assertEqual(list(package.local_links(text, suffix)), ['before.rst', 'after.rst'])

    def test_fences_opening_on_list_marker_lines_preserve_code_and_following_prose(self):
        for marker in ('- ', '1. ', '  - '):
            with self.subTest(marker=marker):
                padding = ' ' * len(marker)
                example = (marker + '```markdown\n'
                           + padding + '[example](fake.rst) /sample:task\n'
                           + padding + '```\n')
                text = example + '\nRead [manual](manual.rst) and invoke /sample:task.\n'
                self.assertEqual(list(package.local_links(text)), ['manual.rst'])
                actual = package.prose_invocations(text, {'sample:task'})
                self.assertTrue(actual.startswith(example))
                self.assertIn('invoke $sample:task.', actual)

    def test_packaged_subject_list_fence_preserves_example_and_checks_following_link(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            fixture(repo)
            source = repo / 'skills/sample-task'
            source.rename(repo / 'skills/cc-hook')
            source = repo / 'skills/cc-hook'
            example = '- ```markdown\n  [example](fake.rst) /sample:task\n  ```\n'
            text = example + '\nInvoke /sample:task and read [manual](references/manual.rst).\n'
            (source / 'SKILL.md').write_text('---\nname: cc-hook\ndescription: Example task\n---\n' + text)
            (source / 'references/subagent.rst').unlink()
            (source / 'references/manual.rst').write_text('A bundled reference.\n')
            destination = repo / 'package/skills/task'
            package.skill_copy(repo, 'cc-hook', 'task', destination, {}, {'sample:task'})
            rendered = (destination / 'SKILL.md').read_text()
            self.assertIn(example, rendered)
            self.assertIn('Invoke $sample:task', rendered)
            self.assertEqual(list(package.local_links(rendered)), ['references/manual.rst'])
            self.assertTrue((destination / 'references/manual.rst').is_file())

    def test_packaged_reference_definitions_and_rst_sections_are_checked(self):
        for suffix, text in (
            ('.md', '[manual][ref]\n\n[ref]: missing.rst\n'),
            ('.md', '- Resources:\n\n    [manual](missing.rst)\n'),
            ('.md', '- ```markdown\n  [example](fake.rst)\n  ```\n\n[manual](missing.rst)\n'),
            ('.rst', 'First\n~~~~~\n\nRead `manual <missing.rst>`_.\n\nSecond\n~~~~~~\n'),
            ('.rst', '.. note::\n\n   Read `manual <missing.rst>`_.\n'),
            ('.rst', '.. admonition::\n\n   Read `manual <missing.rst>`_.\n'),
            ('.rst', 'Read `the wrapped\nmanual <missing.rst>`_.\n'),
        ):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as temp:
                repo = Path(temp)
                fixture(repo)
                (repo / f'skills/sample-task/references/guide{suffix}').write_text(text)
                package.sync(repo)
                errors = package.validate(repo)
                self.assertEqual(len(errors), 1, errors)
                self.assertIn('missing relative reference missing.rst', errors[0])
