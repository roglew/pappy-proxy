from twisted.internet import defer

"""
Schema v7

Creates an index for requests on start time in the data file. This will make
iterating through history a bit faster.
"""

update_queries = [
    """
    CREATE INDEX ind_start_time ON requests(start_datetime);
    """,

    """
    UPDATE schema_meta SET version=7;
    """
]

@defer.inlineCallbacks
def update(dbpool):
    for query in update_queries:
        yield dbpool.runQuery(query)
