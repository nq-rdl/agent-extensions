---
type: regex
pattern: ^(?:[\s\S]*\n)? {0,3}`{3,}ya?ml[ \t]*(?=\n)(?![\s\S]*\n {0,3}`{3,}ya?ml)(?=(?:(?!\n
  {0,3}```)[\s\S])*?\n {0,3}```)(?=(?:(?!\n {0,3}```)[\s\S])*?\ndestination:[ \t]*["']?(?:pr-comment)["']?[
  \t]*(?:#[^\n]*)?\n)(?!(?:(?!\n {0,3}```)[\s\S])*?\ndestination:(?![ \t]*["']?(?:pr-comment)["']?[
  \t]*(?:#[^\n]*)?\n))
target: last_message
---
