---
description: A cheap getter should drop Get; a getter that does I/O and returns a collection should become List/Fetch
tags: [naming]
runs: 5
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Can you clean up the naming in this Go code so it's idiomatic? Keep the behaviour the same and show me the full rewritten file in a single go code block.

```go
package inventory

import (
	"context"
	"database/sql"
)

type Product struct {
	SKU string
}

type Store struct {
	db   *sql.DB
	name string
}

func (s *Store) GetName() string {
	return s.name
}

func (s *Store) GetProducts(ctx context.Context) ([]Product, error) {
	rows, err := s.db.QueryContext(ctx, "SELECT sku FROM products")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var products []Product
	for rows.Next() {
		var p Product
		if err := rows.Scan(&p.SKU); err != nil {
			return nil, err
		}
		products = append(products, p)
	}
	return products, rows.Err()
}
```
