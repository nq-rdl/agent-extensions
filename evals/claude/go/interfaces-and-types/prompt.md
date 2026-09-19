---
description: Interfaces named with an I prefix or Interface suffix, and variables that embed their type
# Baseline already scores 1.00 on sonnet-5 (delta 0): a regression guard, not a signal.
tags: [naming, saturated]
runs: 5
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Can you clean up the naming in this Go code so it's idiomatic? Keep the behaviour the same and show me the full rewritten file in a single go code block.

```go
package ingest

type Record struct {
	Fields map[string]string
}

type IValidator interface {
	Validate(r Record) error
}

type RecordReaderInterface interface {
	ReadRecord() (Record, error)
}

func CountValid(recordSlice []Record, v IValidator) int {
	validCount := 0
	for _, recordItem := range recordSlice {
		if v.Validate(recordItem) == nil {
			validCount++
		}
	}
	return validCount
}
```
