from pappyproxy import http
from twisted.internet import defer

"""
Schema v5

Description:
Adds a column to the requests table which will store a dict that plugins can
use to store metadata about requests.
"""

update_queries = [
    """
    ALTER TABLE requests ADD COLUMN plugin_data TEXT;
    """,

    """
    UPDATE requests SET plugin_data="{}";
    """,

    """
    UPDATE schema_meta SET version=5;
    """
]

@defer.inlineCallbacks
def update(dbpool):
    for query in update_queries:
        yield dbpool.runQuery(query)
