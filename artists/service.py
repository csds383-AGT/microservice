from contextlib import suppress
from types import SimpleNamespace

from email_validator import EmailNotValidError, validate_email

import concerts_pb2
import concerts_pb2_grpc
from common import db, peers
from common.records import FestHubError, check_lengths, find_records, insert, parse_id, require, update

concerts = peers.stub(concerts_pb2_grpc.BookingServiceStub, "CONCERTS")


def check_artist(artist):
    check_lengths(artist.name)
    try:
        validate_email(artist.booking_contact, check_deliverability=False)
    except EmailNotValidError:
        raise FestHubError("booking contact must be a valid email address")


def change_bookings(artist_id, add_event_ids=(), remove_event_ids=()):
    done = []
    try:
        for change, undo, event_ids in [
            (concerts.BookArtist, concerts.UnbookArtist, add_event_ids),
            (concerts.UnbookArtist, concerts.BookArtist, remove_event_ids),
        ]:
            for event_id in event_ids:
                booking = concerts_pb2.BookingRequest(event_id=event_id, artist_id=artist_id)
                peers.call(change, booking)
                done.append((undo, booking))
    except FestHubError:
        for undo, booking in reversed(done):
            with suppress(FestHubError):
                peers.call(undo, booking)
        raise


def create_artist(name, booking_contact, custom_id=None, event_ids=()):
    with db.transaction():
        custom_id = parse_id(custom_id)
        artist = SimpleNamespace(name=name, booking_contact=booking_contact)
        check_artist(artist)
        artist_id = insert("artists", custom_id, artist, "an artist with that ID already exists")
        change_bookings(artist_id, add_event_ids=event_ids)
        return artist_id


def find_artists(artist_id=None):
    artists = find_records("artists", artist_id, "artist")
    if not artists:
        return []
    response = peers.call(concerts.ListBookings, concerts_pb2.ListBookingsRequest(artist_ids=[a.id for a in artists]))
    event_ids = {}
    for booking in response.bookings:
        event_ids.setdefault(booking.artist_id, []).append(booking.event_id)
    return [SimpleNamespace(**artist._asdict(), event_ids=event_ids.get(artist.id, [])) for artist in artists]


def update_artist(artist_id, name=None, booking_contact=None, add_event_ids=(), remove_event_ids=()):
    with db.transaction():
        changes = SimpleNamespace(name=name, booking_contact=booking_contact)
        check_artist(update("artists", artist_id, "artist", changes))
        change_bookings(artist_id, add_event_ids, remove_event_ids)


def delete_artist(artist_id):
    with db.transaction():
        require("artists", artist_id, "artist")
        peers.call(concerts.ForgetArtist, concerts_pb2.ForgetArtistRequest(artist_id=artist_id))
        db.delete("artists", artist_id)
