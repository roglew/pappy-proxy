from pappyproxy import http
from twisted.internet import defer

"""
Schema v4

Description:
Adds additional metadata to the database for requests. Mainly it stores the host
that a request was sent to so that pappy doesn't have to guess from the host
header.
"""

update_queries = [
    """
    ALTER TABLE requests ADD COLUMN host TEXT;
    """,
]

@defer.inlineCallbacks
def update(dbpool):
    for query in update_queries:
        yield dbpool.runQuery(query)

    # Update metadata for each request
    reqrows = yield dbpool.runQuery(
        """
        SELECT id, full_request
        FROM requests;
        """,
        )

    # Create an object that will parse the host from the request
    for reqrow in reqrows:
        reqid = reqrow[0]
        fullreq = reqrow[1]
        r = http.Request(fullreq)
        host = r.host
        if r.host:
            yield dbpool.runQuery(
                """
                UPDATE requests SET host=? WHERE id=?;
                """,
                (host, reqid)
            )

    yield dbpool.runQuery(
        """
        UPDATE schema_meta SET version=4;
        """
    )
