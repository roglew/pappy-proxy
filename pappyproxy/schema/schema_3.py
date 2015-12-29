from pappyproxy import http
from twisted.internet import defer

"""
Schema v3

Description:
Adds tables to store tags associated with requests
"""

update_queries = [
    """
    CREATE TABLE tags (
        id       INTEGER   PRIMARY KEY  AUTOINCREMENT,
        tag      TEXT      NOT NULL
    );
    """,

    """
    CREATE TABLE tagged (
        reqid       INTEGER   REFERENCES requests(id),
        tagid       INTEGER   REFERENCES tags(id)
    );
    """,

    """
    UPDATE schema_meta SET version=3;
    """,
]

@defer.inlineCallbacks
def update(dbpool):
    for query in update_queries:
        yield dbpool.runQuery(query)
