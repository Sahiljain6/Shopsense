import os
import sys
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure backend root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.db.session import Base
from app import models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=get_settings().database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection", None)

    def do_run_migrations(connection):
        # Self-healing: if database has an unknown or orphaned revision, heal it so migrations never crash loop
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(connection)
            if "alembic_version" in inspector.get_table_names():
                script = context.script
                known_revisions = {rev.revision for rev in script.walk_revisions()}
                rows = connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()
                for row in rows:
                    v = row[0]
                    if v and v not in known_revisions:
                        print(f"[ALEMBIC RECOVERY] Found orphaned revision '{v}' in database. Resetting to baseline '0001_add_sku'...")
                        connection.execute(text("UPDATE alembic_version SET version_num = '0001_add_sku' WHERE version_num = :bad_v"), {"bad_v": v})
                        try:
                            connection.commit()
                        except Exception:
                            pass
        except Exception as e:
            print(f"[ALEMBIC NOTICE] Revision recovery pre-check notice: {e}")

        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    if connectable is not None:
        do_run_migrations(connectable)
    else:
        engine = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        with engine.connect() as connection:
            do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
