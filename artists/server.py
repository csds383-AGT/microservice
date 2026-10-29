from google.protobuf import empty_pb2

import artists_pb2
import artists_pb2_grpc
import service
from common.server import field, invoke, serve, string_id


def to_artist(record):
    return artists_pb2.Artist(
        id=string_id(field(record, "id")),
        name=field(record, "name", ""),
        booking_contact=field(record, "booking_contact", ""),
        event_ids=[string_id(x) for x in (field(record, "event_ids", []) or [])],
    )


class ArtistService(artists_pb2_grpc.ArtistServiceServicer):
    def CreateArtist(self, request, context):
        result = invoke(
            context, service.create_artist,
            name=request.name,
            booking_contact=request.booking_contact,
            custom_id=request.custom_id or None,
            event_ids=list(request.event_ids),
        )
        return artists_pb2.IdResponse(id=string_id(result))

    def ShowArtists(self, request, context):
        records = invoke(context, service.find_artists, request.id or None)
        return artists_pb2.ShowArtistsResponse(artists=[to_artist(x) for x in records])

    def UpdateArtist(self, request, context):
        invoke(
            context, service.update_artist,
            artist_id=request.id,
            name=request.name if request.HasField("name") else None,
            booking_contact=request.booking_contact if request.HasField("booking_contact") else None,
            add_event_ids=list(request.add_event_ids),
            remove_event_ids=list(request.remove_event_ids),
        )
        return empty_pb2.Empty()

    def DeleteArtist(self, request, context):
        invoke(context, service.delete_artist, request.id)
        return empty_pb2.Empty()


if __name__ == "__main__":
    serve("artists", (artists_pb2_grpc.add_ArtistServiceServicer_to_server, ArtistService()))
