from uuid import UUID

from common import db


class FestHubError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def parse_id(custom_id):
    if custom_id is None:
        return None
    try:
        return str(UUID(custom_id))
    except ValueError:
        raise FestHubError("custom ID must be a valid UUID")


def check_lengths(name, description=""):
    if len(name) > 2000:
        raise FestHubError("name must be 2000 characters or fewer")
    if len(description) > 10000:
        raise FestHubError("description must be 10000 characters or fewer")


def require(table, record_id, label):
    record = db.get(table, record_id)
    if record is None:
        raise FestHubError(f"no {label} with id {record_id}")
    return record


def find_records(table, record_id, label, order_by="name"):
    rows = db.find(table, record_id, order_by)
    if record_id and not rows:
        raise FestHubError(f"no {label} with id {record_id}")
    return rows


def insert(table, custom_id, record, duplicate_message):
    record_id = db.insert(table, custom_id, record)
    if record_id is None:
        raise FestHubError(duplicate_message)
    return record_id


def update(table, record_id, label, changes):
    record = db.update(table, record_id, changes)
    if record is None:
        raise FestHubError(f"no {label} with id {record_id}")
    return record


def delete_record(table, record_id, label):
    with db.transaction():
        if not db.delete(table, record_id):
            raise FestHubError(f"no {label} with id {record_id}")
