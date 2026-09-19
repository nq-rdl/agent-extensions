---
description: Rewrite a small Go type whose identifiers break the naming conventions the naming skill covers
tags: [naming]
# The type-stutter rename is near a coin flip without the skill; 3 runs misread it.
runs: 5
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Can you clean up the naming in this Go code so it's idiomatic? Keep the behaviour the same and show me the full rewritten file in a single go code block.

```go
package account

type AccountHttpClient struct {
	base_url string
	ownerId  string
}

func NewAccountHttpClient(base_url string, ownerId string) *AccountHttpClient {
	return &AccountHttpClient{base_url: base_url, ownerId: ownerId}
}

func (this *AccountHttpClient) GetOwnerId() string {
	return this.ownerId
}

func (this *AccountHttpClient) GetBaseUrl() string {
	return this.base_url
}
```
