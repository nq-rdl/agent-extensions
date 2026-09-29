---
type: regex
# Hand-written; fixtures in tests/test_eval_prompting_graders.py.
# max_tokens is resized because thinking counts toward it.
pattern: '[Tt]hinking[^\n]{0,60}(?:counts?|is counted|is included|consumes?|uses?|comes out of|eats into)[^\n]{0,80}max_tokens|max_tokens[^\n]{0,160}(?:room|headroom|space|includ|cover)[^\n]{0,80}[Tt]hinking'
target: last_message
---
