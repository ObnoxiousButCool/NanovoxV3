# Migrations

Generate a revision after changing `infrastructure/persistence/tables.py`:

```bash
alembic revision --autogenerate -m "add employer, broker, member tables"
```

Review the generated file before committing — autogenerate proposes, it
doesn't decide. Apply migrations with:

```bash
alembic upgrade head
```

`alembic heads` must always print exactly one line; that's a gate (plan
§2A.7/§10).
