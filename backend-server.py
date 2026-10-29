import sys
from pathlib import Path

from google.protobuf import empty_pb2

PROJECT_DIR = Path(__file__).resolve().parent
LOGIC_DIR = PROJECT_DIR / "logic"
if LOGIC_DIR.is_dir():
    sys.path.insert(0, str(LOGIC_DIR))

import services
import concerts_pb2
import concerts_pb2_grpc
import categories_pb2
import categories_pb2_grpc
import media_pb2
import media_pb2_grpc
from common.server import field, invoke, serve, string_id


def to_concert(record):
    return concerts_pb2.Concert(
        id=string_id(field(record, "id")),
        name=field(record, "name", ""),
        description=field(record, "description", ""),
        available_tickets=field(record, "available_tickets", 0),
        # The services/repository layer stores prices as integer cents.
        ticket_price_cents=field(record, "ticket_price", field(record, "ticket_price_cents", 0)),
        artist_ids=[string_id(x) for x in (field(record, "artist_ids", []) or [])],
        category_ids=[string_id(x) for x in (field(record, "category_ids", []) or [])],
        media_ids=[string_id(x) for x in (field(record, "media_ids", []) or [])],
    )


def to_category(record):
    return categories_pb2.Category(
        id=string_id(field(record, "id")),
        name=field(record, "name", ""),
        description=field(record, "description", ""),
        event_ids=[string_id(x) for x in (field(record, "event_ids", []) or [])],
    )


def to_media(record):
    return media_pb2.Media(
        id=string_id(field(record, "id")),
        event_id=string_id(field(record, "event_id")),
        image_url=field(record, "image_url", ""),
    )


class ConcertService(concerts_pb2_grpc.ConcertServiceServicer):
    def CreateConcert(self, request, context):
        result = invoke(
            context, services.create_concert,
            name=request.name,
            description=request.description,
            available_tickets=request.available_tickets,
            ticket_price=request.ticket_price,
            custom_id=request.custom_id or None,
            artist_ids=list(request.artist_ids),
            category_ids=list(request.category_ids),
            media_ids=list(request.media_ids),
        )
        return concerts_pb2.IdResponse(id=string_id(result))

    def ShowConcerts(self, request, context):
        records = invoke(context, services.find_concerts, request.id or None)
        return concerts_pb2.ShowConcertsResponse(concerts=[to_concert(x) for x in records])

    def UpdateConcert(self, request, context):
        invoke(
            context, services.update_concert,
            event_id=request.id,
            name=request.name if request.HasField("name") else None,
            description=request.description if request.HasField("description") else None,
            available_tickets=request.available_tickets if request.HasField("available_tickets") else None,
            ticket_price=request.ticket_price if request.HasField("ticket_price") else None,
            add_artist_ids=list(request.add_artist_ids),
            remove_artist_ids=list(request.remove_artist_ids),
            add_category_ids=list(request.add_category_ids),
            remove_category_ids=list(request.remove_category_ids),
            add_media_ids=list(request.add_media_ids),
            remove_media_ids=list(request.remove_media_ids),
        )
        return empty_pb2.Empty()

    def DeleteConcert(self, request, context):
        media_ids, category_ids = invoke(context, services.delete_concert, request.id)
        return concerts_pb2.DeleteConcertResponse(
            deleted_media_ids=[string_id(x) for x in media_ids],
            deleted_category_ids=[string_id(x) for x in category_ids],
        )


class BookingService(concerts_pb2_grpc.BookingServiceServicer):
    def BookArtist(self, request, context):
        invoke(context, services.add_booking, request.event_id, request.artist_id)
        return empty_pb2.Empty()

    def UnbookArtist(self, request, context):
        invoke(context, services.unbook_artist, request.event_id, request.artist_id)
        return empty_pb2.Empty()

    def ListBookings(self, request, context):
        records = invoke(context, services.find_bookings, list(request.artist_ids))
        return concerts_pb2.ListBookingsResponse(bookings=[
            concerts_pb2.Booking(event_id=string_id(x.event_id), artist_id=string_id(x.artist_id)) for x in records
        ])

    def ForgetArtist(self, request, context):
        invoke(context, services.forget_artist, request.artist_id)
        return empty_pb2.Empty()


class CategoryService(categories_pb2_grpc.CategoryServiceServicer):
    def CreateCategory(self, request, context):
        result = invoke(
            context, services.create_category,
            name=request.name,
            description=request.description,
            custom_id=request.custom_id or None,
            event_ids=list(request.event_ids),
        )
        return categories_pb2.IdResponse(id=string_id(result))

    def ShowCategories(self, request, context):
        records = invoke(context, services.find_categories, request.id or None)
        return categories_pb2.ShowCategoriesResponse(categories=[to_category(x) for x in records])

    def UpdateCategory(self, request, context):
        invoke(
            context, services.update_category,
            category_id=request.id,
            name=request.name if request.HasField("name") else None,
            description=request.description if request.HasField("description") else None,
            add_event_ids=list(request.add_event_ids),
            remove_event_ids=list(request.remove_event_ids),
        )
        return empty_pb2.Empty()

    def DeleteCategory(self, request, context):
        invoke(context, services.delete_category, request.id)
        return empty_pb2.Empty()


class MediaService(media_pb2_grpc.MediaServiceServicer):
    def CreateMedia(self, request, context):
        result = invoke(
            context, services.create_media,
            event_id=request.event_id,
            image_url=request.image_url,
            custom_id=request.custom_id or None,
        )
        return media_pb2.IdResponse(id=string_id(result))

    def ShowMedia(self, request, context):
        records = invoke(context, services.find_media, request.id or None)
        return media_pb2.ShowMediaResponse(media=[to_media(x) for x in records])

    def UpdateMedia(self, request, context):
        invoke(
            context, services.update_media,
            media_id=request.id,
            event_id=request.event_id if request.HasField("event_id") else None,
            image_url=request.image_url if request.HasField("image_url") else None,
        )
        return empty_pb2.Empty()

    def DeleteMedia(self, request, context):
        invoke(context, services.delete_media, request.id)
        return empty_pb2.Empty()


if __name__ == "__main__":
    serve(
        "logic",
        (concerts_pb2_grpc.add_ConcertServiceServicer_to_server, ConcertService()),
        (concerts_pb2_grpc.add_BookingServiceServicer_to_server, BookingService()),
        (categories_pb2_grpc.add_CategoryServiceServicer_to_server, CategoryService()),
        (media_pb2_grpc.add_MediaServiceServicer_to_server, MediaService()),
    )
