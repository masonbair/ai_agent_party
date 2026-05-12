# Available Tools

0/4 installed


## CodeSummarizer
❌ Not installed

Generates hierarchical context maps of the codebase for AI agents

```bash
code-summarizer --project-root . --output .ai/context/
```

## ContextQuery
❌ Not installed

Structure-aware code search combining text, AST patterns, and graph traversal

```bash
context-query --pattern "async function.*database" --type structural
```

## CodeIndex
❌ Not installed

Persistent semantic cache for AI agents - indexes codebases with tree-sitter for fast symbol lookup, dependency analysis, and code intelligence

```bash
code-index daemon start
```

## ContextPacker
❌ Not installed

Smart context window packing - assembles relevant code within token budget

```bash
context-packer --query "implement feature" --budget 8000 --format claude
```


Run `<tool> --help` for full documentation.
