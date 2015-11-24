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

    """
    UPDATE schema_meta SET version=2;
    """,
]

@defer.inlineCallbacks
def update(dbpool):
    for query in update_queries:
        yield dbpool.runQuery(query)

    # Load each request and save them again for any request that specified a port
    # or protocol in the host header.
    http.init(dbpool)
    reqs = yield http.Request.load_from_filters([])
    for req in reqs:
        yield req.deep_save()
