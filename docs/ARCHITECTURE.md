# Architecture

## Layer diagram (ASCII)

```text
+---------------------------+
|        CLI Layer          |
| src/api/cli.py            |
| src/api/commands/*        |
+------------+--------------+
             |
             v
+---------------------------+
|       Core Services       |
| src/core/*                |
| (analysis, risk, batch)   |
+------------+--------------+
             |
             v
+---------------------------+
|     Data Access Layer     |
| src/data/database.py      |
| src/data/repositories/*   |
| src/data/schema.py        |
+------------+--------------+
             |
             v
+---------------------------+
| External/Infra Components |
| SQLite/Postgres, files,   |
| templates, workflows      |
+---------------------------+
```

## Design patterns used

- Dependency Injection: Core services receive repositories or engines as constructor parameters.
- Repository Pattern: Database operations are encapsulated in repository classes.
- Command Pattern: CLI command modules organize user actions into explicit command handlers.
- Factory/Builder style wiring: Command helpers build processing pipelines from reusable components.
- Context Manager pattern: Session lifecycle and transaction scope are guarded via `with` blocks.

## Module dependency map

```text
src/api/commands/*
  -> src/core/*
  -> src/data/database.py
  -> src/data/repositories/*
  -> src/utils/security.py
  -> src/utils/logger.py

src/core/*
  -> src/core/exceptions.py
  -> src/utils/logger.py
  -> src/ml/* (for compare workflows)

src/data/repositories/*
  -> src/data/schema.py
  -> sqlalchemy

src/ml/*
  -> numpy, scikit-learn, sentence-transformers
```
