from psycopg.rows import scalar_row

from common.db import delete, fetchall, fetchone, link, rowcount, to_uuid, transaction, unlink


def artist_booking_summary(artist_id):
    return fetchone(
        "SELECT COUNT(*) - COUNT(DISTINCT e.name) AS duplicate_names, "
        "COALESCE(SUM(e.ticket_price), 0) AS total_price "
        "FROM event_artists ea JOIN concert_events e ON e.id = ea.event_id WHERE ea.artist_id = %s",
        [to_uuid(artist_id)],
    )


def bookings(artist_ids):
    return fetchall(
        "SELECT event_id, artist_id FROM event_artists WHERE artist_id = ANY(%s) ORDER BY artist_id, event_id",
        [[to_uuid(artist_id) for artist_id in artist_ids]],
    )


def forget_artist(artist_id):
    return rowcount("DELETE FROM event_artists WHERE artist_id = %s", [to_uuid(artist_id)])


def delete_unused_categories(category_ids):
    return fetchall(
        "WITH deleted AS (DELETE FROM categories c WHERE id = ANY(%s) "
        "AND NOT EXISTS (SELECT 1 FROM event_categories WHERE category_id = c.id) RETURNING id) "
        "SELECT id FROM deleted ORDER BY id",
        [category_ids],
        row_factory=scalar_row,
    )
