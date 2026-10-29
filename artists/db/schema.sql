CREATE TABLE artists
(
    id              UUID PRIMARY KEY DEFAULT uuidv7(),
    name            TEXT             NOT NULL,
    booking_contact TEXT             NOT NULL
);
