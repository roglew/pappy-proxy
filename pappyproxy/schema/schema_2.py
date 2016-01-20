from pappyproxy import http
from twisted.internet import defer

"""
Schema v2

Description:
Adds support for specifying the port of a request and specify its port. This
lets requests that have the port/ssl settings specified in the CONNECT request
maintain that information.
"""

update_queries = [
    """
    ALTER TABLE requests ADD COLUMN port INTEGER;
    """,

    """
    ALTER TABLE requests ADD COLUMN is_ssl INTEGER;
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

    # Create an object and get its port/is_ssl
    for reqrow in reqrows:
        reqid = reqrow[0]
        fullreq = reqrow[1]
        r = http.Request(fullreq)
        port = r.port
        is_ssl = r.is_ssl
        yield dbpool.runQuery(
            """
            UPDATE requests SET port=?,is_ssl=? WHERE id=?;
            """,
            (port, is_ssl, reqid)
        )

    yield dbpool.runQuery(
        """
        UPDATE schema_meta SET version=2;
        """
    )
