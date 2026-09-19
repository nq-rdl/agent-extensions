---
description: Rewrite a small Go type whose identifiers break the naming conventions the naming skill covers
tags: [naming]
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Can you clean up the naming in this Go code so it's idiomatic? Keep the behaviour the same and show me the full rewritten file.

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
