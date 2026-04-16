---
name: zod
license: MIT
description: >-
  Use this skill when defining, validating, or inferring types from data schemas using the Zod library. Useful for input validation, API response checking, and generating TypeScript types from runtime schemas.
metadata:
  repo: https://github.com/nq-rdl/agent-skills
  docs: https://zod.dev/
---

# zod — TypeScript-first schema validation

Zod is a TypeScript-first schema declaration and validation library. It allows you to create schemas that guarantee runtime data structure and automatically infer static TypeScript types.

---

## When to use Zod

Use Zod when:
- Validating untrusted input (e.g., API requests, form data, file parsing)
- Ensuring external API responses match expected formats
- Reducing duplication between runtime validation and static types (single source of truth)
- Generating detailed, typed error messages for invalid data

---

## Basic Pattern

The standard Zod workflow involves defining a schema, inferring its type, and parsing data.

### 1. Define the Schema

Create a schema using `z.object()`, `z.string()`, `z.number()`, etc.

```typescript
import { z } from "zod";

const UserSchema = z.object({
  id: z.string().uuid(),
  username: z.string().min(3).max(20),
  email: z.string().email(),
  age: z.number().int().positive().optional(),
  role: z.enum(["admin", "user", "guest"]).default("user"),
  isActive: z.boolean(),
});
```

### 2. Infer the TypeScript Type

Extract the static type from the schema so you don't have to write it twice.

```typescript
type User = z.infer<typeof UserSchema>;
// Equivalent to:
// type User = {
//   id: string;
//   username: string;
//   email: string;
//   age?: number | undefined;
//   role: "admin" | "user" | "guest";
//   isActive: boolean;
// }
```

### 3. Parse Data

Use `.parse()` (throws on error) or `.safeParse()` (returns success/error object) to validate data.

#### Using `parse` (Strict)

```typescript
try {
  const validUser = UserSchema.parse(unknownData);
  // validUser is fully typed as User
  console.log(validUser.username);
} catch (error) {
  if (error instanceof z.ZodError) {
    console.error("Validation failed:", error.issues);
  }
}
```

#### Using `safeParse` (Safe)

```typescript
const result = UserSchema.safeParse(unknownData);

if (result.success) {
  // result.data is typed as User
  console.log("Valid user:", result.data);
} else {
  // result.error is a ZodError
  console.error("Invalid data:", result.error.format());
}
```

---

## Common Schema Types

- **Primitives**: `z.string()`, `z.number()`, `z.boolean()`, `z.date()`
- **Empty types**: `z.undefined()`, `z.null()`, `z.void()`
- **Catch-all**: `z.any()`, `z.unknown()`
- **Complex**: `z.array(z.string())`, `z.object({ ... })`, `z.tuple([z.string(), z.number()])`
- **Unions/Intersections**: `z.union([z.string(), z.number()])`, `z.intersection(A, B)`

---

## Refinements and Custom Validation

You can add custom validation logic using `.refine()` or `.superRefine()`.

```typescript
const PasswordSchema = z.string().refine((val) => val.length >= 8, {
  message: "Password must be at least 8 characters long",
});

const DateRangeSchema = z.object({
  start: z.date(),
  end: z.date(),
}).refine((data) => data.end > data.start, {
  message: "End date must be after start date",
  path: ["end"], // attach the error to the `end` field
});
```

---

## Error Handling

When using `safeParse()`, you can format errors in different ways:

```typescript
const result = UserSchema.safeParse(badData);

if (!result.success) {
  // Array of ZodIssue objects
  console.log(result.error.issues);

  // Formatted object matching the schema shape
  console.log(result.error.format());

  // Flat array of string messages
  console.log(result.error.flatten().fieldErrors);
}
```

---

## Integration Patterns

### API Endpoints (Express example)

```typescript
import { Request, Response } from 'express';
import { z } from 'zod';

const CreateUserSchema = z.object({
  body: z.object({
    email: z.string().email(),
    password: z.string().min(8)
  })
});

app.post('/users', (req: Request, res: Response) => {
  const result = CreateUserSchema.safeParse({ body: req.body });

  if (!result.success) {
    return res.status(400).json({ errors: result.error.flatten().fieldErrors });
  }

  // Create user with valid data
  const { email, password } = result.data.body;
  // ...
});
```

### Environment Variables

Validate `process.env` at startup to fail fast on misconfiguration.

```typescript
const EnvSchema = z.object({
  PORT: z.string().transform(Number).default("3000"),
  DATABASE_URL: z.string().url(),
  NODE_ENV: z.enum(["development", "production", "test"]).default("development"),
});

const env = EnvSchema.parse(process.env);
// env.PORT is now a number!
```
