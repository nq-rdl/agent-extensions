---
type: regex
# Hand-written; fixtures in tests/test_eval_data_request_graders.py.
# diagnosis_codes is exactly the requested I71.3 and I71.4, not the concept.
pattern: '^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\ndiagnosis_codes:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:I71\.3))(?=(?:(?!\n {0,3}```)[\s\S])*?\ndiagnosis_codes:(?:(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*?(?:I71\.4))(?=(?:(?!\n {0,3}```)[\s\S])*?\ndiagnosis_codes:(?:(?!I71(?!\.[34]\b)|[Aa]ortic|[Aa]neurysm|[Cc]oncept)(?!\n[^ \t\n-])(?!\n {0,3}```)[\s\S])*(?:\n[^ \t\n-]|\n {0,3}```))'
target: last_message
---
