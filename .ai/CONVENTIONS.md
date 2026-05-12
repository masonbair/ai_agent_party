# ai_agent_party - Development Conventions

**Purpose:** Coding standards and development practices for this project
**Last Updated:** 2026-05-12

---

## Core Development Principles

### 1. Test-Driven Development (Fail-to-Succeed Pipeline)

**CRITICAL:** All new features and bug fixes must follow this workflow:

1. **Write the test FIRST** - before any implementation code
2. **Run the test - it MUST fail** - this proves the test is actually testing something
3. **Write minimal code to make it pass** - no more, no less
4. **Run the test - it MUST pass** - this proves the implementation works
5. **Refactor if needed** - while keeping tests green

**Why this matters:** A test that passes on the first run without any implementation might be faulty or testing the wrong thing. The fail-first approach ensures tests are valid.

**Example workflow:**
```bash
# 1. Write test
# 2. Run tests - should see NEW failure
cargo test  # or npm test, pytest, etc.
# 3. Implement feature
# 4. Run tests - should see the failure turn green
cargo test
```

### 2. Simplicity First

**Keep code minimal and simple:**
- Write the simplest solution that works
- Avoid premature optimization
- Avoid premature abstraction
- Three similar lines of code is better than a premature abstraction
- Don't add features "for the future" - build what's needed now
- Prefer clear, obvious code over clever code

**Anti-patterns to avoid:**
- Complex class hierarchies when a simple function would work
- Generic solutions for specific problems
- "Just in case" code that isn't currently needed

### 3. Leverage External Libraries

**Don't reinvent the wheel:**
- Use well-maintained external libraries for common tasks
- Prefer battle-tested libraries over custom implementations
- Examples: date handling, HTTP clients, parsing, data structures
- Exception: Only write custom code if the library adds too much dependency weight

**When choosing libraries:**
- Check maintenance status (recent commits, active maintainers)
- Check community adoption (downloads, stars)
- Prefer libraries with minimal dependencies

### 4. File Organization - Keep Files Short

**Split files when they grow:**
- **Rule of thumb:** If a file exceeds ~200-300 lines, consider splitting
- **Immediate split:** If a file has two distinct responsibilities, split it now
- Each file should have a single, clear purpose
- File names should clearly indicate their purpose

**Example split patterns:**
- `user.rs` → `user/model.rs`, `user/service.rs`, `user/validation.rs`
- `api.py` → `api/routes.py`, `api/handlers.py`, `api/middleware.py`
- `app.ts` → `app/config.ts`, `app/server.ts`, `app/routes.ts`

**Benefits:**
- Easier to navigate
- Easier to test
- Easier to understand
- Reduces merge conflicts

---

## Testing Standards

### Test Coverage
- All public functions/methods require tests
- Critical paths require integration tests
- Edge cases must be tested

### Test Organization
- Tests live close to the code they test
- One test file per source file (e.g., `user.rs` → `user_test.rs` or `user.test.ts`)
- Test names should describe what they verify: `test_user_creation_fails_with_invalid_email`

### What to Test
- Happy paths (normal operation)
- Edge cases (boundary conditions)
- Error paths (invalid input, failure scenarios)
- Integration points (external services, databases)

---

## Code Style


### html

{PLACEHOLDER: Add html-specific linting rules, formatting standards}

- Use language standard formatter (rustfmt, prettier, black, gofmt)
- Follow language idioms and conventions
- Use linter to catch common issues


### css

{PLACEHOLDER: Add css-specific linting rules, formatting standards}

- Use language standard formatter (rustfmt, prettier, black, gofmt)
- Follow language idioms and conventions
- Use linter to catch common issues


### typescript

{PLACEHOLDER: Add typescript-specific linting rules, formatting standards}

- Use language standard formatter (rustfmt, prettier, black, gofmt)
- Follow language idioms and conventions
- Use linter to catch common issues


### python

{PLACEHOLDER: Add python-specific linting rules, formatting standards}

- Use language standard formatter (rustfmt, prettier, black, gofmt)
- Follow language idioms and conventions
- Use linter to catch common issues



---

## Documentation

**Keep it minimal but useful:**
- Document WHY, not WHAT (code shows what)
- Complex algorithms need explanation
- Public APIs need usage examples
- Avoid obvious comments like `// increment counter` above `counter++`

---

## Git Workflow

{PLACEHOLDER: Define branching strategy, commit message format}

**Commit messages should:**
- Start with a verb (Add, Fix, Update, Refactor)
- Be concise (50 chars for subject line)
- Explain why if not obvious

---

## For AI Agents: Development Checklist

When implementing ANY feature or fix:

- [ ] Write test FIRST (it should fail)
- [ ] Run tests to confirm failure
- [ ] Implement minimal solution
- [ ] Run tests to confirm they pass
- [ ] Check if any files exceed 200-300 lines (split if needed)
- [ ] Verify external libraries are used for common functionality
- [ ] Ensure code is simple and clear
- [ ] Add necessary documentation (WHY, not WHAT)

**Remember:** Simple, tested, modular code is better than complex, untested, monolithic code.
