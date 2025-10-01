# Database Migrations

Use Alembic to manage database schema revisions. Configure the target database URL in
`alembic.ini` or via the `sqlalchemy.url` override, then run:

```bash
alembic upgrade head
```
