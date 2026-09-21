---
description: Sentinel errors, error types and constants that break the ErrFoo / FooError / MixedCaps conventions
tags: [naming]
runs: 5
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Can you clean up the naming in this Go code so it's idiomatic? Keep the behaviour the same and show me the full rewritten file in a single go code block.

```go
package jobs

import "errors"

const MAX_RETRY_COUNT = 5

var TimeoutError = errors.New("job timed out")
var ErrorNotFound = errors.New("job not found")

type ErrInvalidPayload struct {
	Field string
}

func (e ErrInvalidPayload) Error() string {
	return "invalid payload: " + e.Field
}

func Retryable(err error) bool {
	return errors.Is(err, TimeoutError)
}
```
