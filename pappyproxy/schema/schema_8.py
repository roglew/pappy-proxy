from twisted.internet import defer

"""
Schema v8

Creates a table for saved contexts and for web socket messages. Saved contexts
are saved as a json list of filter strings.
"""

update_queries = [
    """
    CREATE TABLE saved_contexts (
        id                INTEGER   PRIMARY KEY  AUTOINCREMENT,
        context_name      TEXT      UNIQUE,
        filter_strings    TEXT
    );
    """,

    """
    CREATE TABLE websocket_messages (
        id                INTEGER   PRIMARY KEY  AUTOINCREMENT,
        parent_request    INTEGER   REFERENCES requests(id),
        unmangled_id      INTEGER   REFERENCES websocket_messages(id),
        is_binary         INTEGER,
        direction         INTEGER,
        time_sent         REAL,
        contents          BLOB
    );
    """,

    """
    UPDATE schema_meta SET version=8;
    """
]

@defer.inlineCallbacks
def update(dbpool):
    for query in update_queries:
        yield dbpool.runQuery(query)
