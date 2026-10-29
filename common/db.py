import os
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

from psycopg.rows import namedtuple_row
from psycopg.sql import SQL, Identifier, Placeholder
from psycopg.types.string import TextLoader
from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://festhub:festhub@localhost:5433/festhub")
POOL_SIZE = int(os.getenv("GRPC_WORKERS", "10"))


def configure(connection):
    connection.adapters.register_loader("uuid", TextLoader)


pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=POOL_SIZE, open=True, configure=configure,
                      kwargs={"autocommit": True, "row_factory": namedtuple_row})
current = ContextVar("current_connection", default=None)


@contextmanager
def connection():
    if (conn := current.get()) is not None:
        yield conn
        return
    with pool.connection() as conn:
        token = current.set(conn)
        try:
            yield conn
        finally:
            current.reset(token)


@contextmanager
def transaction():
    # commits when the block finishes and rolls back if it raises, so a failed command changes nothing
    with connection() as conn, conn.transaction():
        yield


def fetchone(query, params=None, row_factory=None):
    with connection() as conn:
        return conn.cursor(row_factory=row_factory).execute(query, params).fetchone()


def fetchall(query, params=None, row_factory=None):
    with connection() as conn:
        return conn.cursor(row_factory=row_factory).execute(query, params).fetchall()


def rowcount(query, params=None):
    with connection() as conn:
        return conn.execute(query, params).rowcount


def to_uuid(record_id):
    # an id that isn't a valid UUID can't match any row, so send NULL instead of letting Postgres raise
    try:
        return UUID(record_id)
    except (TypeError, ValueError):
        return None


def get(table, record_id):
    query = SQL("SELECT * FROM {} WHERE id = %s").format(Identifier(table))
    return fetchone(query, [to_uuid(record_id)])


def find(table, record_id, order_by):
    if record_id is not None:
        row = get(table, record_id)
        return [row] if row else []
    query = SQL("SELECT * FROM {} ORDER BY {}, id").format(Identifier(table), Identifier(order_by))
    return fetchall(query)


def insert(table, custom_id, record):
    # returns None when the custom id is already taken
    values = vars(record)
    query = SQL(
        "INSERT INTO {} (id, {}) VALUES (COALESCE(%(id)s, uuidv7()), {}) ON CONFLICT (id) DO NOTHING RETURNING id"
    ).format(Identifier(table), SQL(", ").join(map(Identifier, values)), SQL(", ").join(map(Placeholder, values)))
    row = fetchone(query, dict(values, id=custom_id))
    return None if row is None else row.id


def update(table, record_id, changes):
    # values left as None keep the column's current value
    values = vars(changes)
    assignments = SQL(", ").join(
        SQL("{0} = COALESCE({1}, {0})").format(Identifier(column), Placeholder(column)) for column in values
    )
    query = SQL("UPDATE {} SET {} WHERE id = %(id)s RETURNING *").format(Identifier(table), assignments)
    return fetchone(query, dict(values, id=to_uuid(record_id)))


def delete(table, record_id):
    query = SQL("DELETE FROM {} WHERE id = %s").format(Identifier(table))
    return rowcount(query, [to_uuid(record_id)]) > 0


def link(table, event_id, other_id):
    # returns False when the two are already linked
    query = SQL("INSERT INTO {} VALUES (%s, %s) ON CONFLICT DO NOTHING").format(Identifier(table))
    return rowcount(query, [to_uuid(event_id), to_uuid(other_id)]) > 0


def unlink(table, column, event_id, other_id):
    query = SQL("DELETE FROM {} WHERE event_id = %s AND {} = %s").format(Identifier(table), Identifier(column))
    return rowcount(query, [to_uuid(event_id), to_uuid(other_id)]) > 0
