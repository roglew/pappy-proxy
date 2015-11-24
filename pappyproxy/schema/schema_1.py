from twisted.internet import defer

"""
Schema v1

Description:
The initial schema for the first version of the proxy. It includes the creation
of the schema_meta table and other data tables.
"""

update_queries = [
    """
    CREATE TABLE responses (
        id             INTEGER   PRIMARY KEY  AUTOINCREMENT,
        full_response  BLOB  NOT NULL,
        unmangled_id   INTEGER   REFERENCES responses(id)
    );
    """,

    """
    CREATE TABLE requests (
        id                INTEGER   PRIMARY KEY  AUTOINCREMENT,
        full_request      BLOB      NOT NULL,
        tag               TEXT,
        submitted         INTEGER   NOT NULL,
        response_id       INTEGER   REFERENCES responses(id),
        unmangled_id      INTEGER   REFERENCES requests(id),
        start_datetime    TEXT,
        end_datetime      TEXT
    );
    """,
    
    """
    CREATE TABLE schema_meta (
        version INTEGER NOT NULL
    );
    """,
    
    """
    CREATE TABLE scope (
        filter_order    INTEGER  NOT NULL,
        filter_string   TEXT  NOT NULL
    );
    """,

    """
    INSERT INTO schema_meta (version) VALUES (1);
    """,
]

@defer.inlineCallbacks
def update(dbpool):
    for query in update_queries:
        yield dbpool.runQuery(query)
