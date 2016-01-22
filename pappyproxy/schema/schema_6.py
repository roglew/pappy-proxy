import time
import datetime
from pappyproxy import http
from twisted.internet import defer

"""
Schema v6

Description:
Replaces the string representation of times with unix times so that we can select
by most recent first. Also deletes old tag column.
"""

update_queries = [
    """
    CREATE TABLE requests_new (
        id                INTEGER   PRIMARY KEY  AUTOINCREMENT,
        full_request      BLOB      NOT NULL,
        submitted         INTEGER   NOT NULL,
        response_id       INTEGER   REFERENCES responses(id),
        unmangled_id      INTEGER   REFERENCES requests(id),
        port              INTEGER,
        is_ssl            INTEGER,
        host              TEXT,
        plugin_data       TEXT,
        start_datetime    REAL,
        end_datetime      REAL
    );
    """,

    """
    INSERT INTO requests_new (id, full_request, submitted, response_id, unmangled_id, port, is_ssl, host, plugin_data) SELECT id, full_request, submitted, response_id, unmangled_id, port, is_ssl, host, plugin_data FROM requests;
    """,
]

drop_queries = [
    """
    DROP TABLE requests;
    """,

    """
    ALTER TABLE requests_new RENAME TO requests;
    """
]

@defer.inlineCallbacks
def update(dbpool):
    for query in update_queries:
        yield dbpool.runQuery(query)
    reqrows = yield dbpool.runQuery(
        """
        SELECT id, start_datetime, end_datetime
        FROM requests;
        """,
        )

    new_times = []
    
    for row in reqrows:
        reqid = row[0]
        if row[1]:
            start_datetime = datetime.datetime.strptime(row[1], "%Y-%m-%dT%H:%M:%S.%f")
            start_unix_time = time.mktime(start_datetime.timetuple())
        else:
            start_unix_time = None
        if row[2]:
            end_datetime = datetime.datetime.strptime(row[2], "%Y-%m-%dT%H:%M:%S.%f")
            end_unix_time = time.mktime(end_datetime.timetuple())
        else:
            end_unix_time = None
        new_times.append((reqid, start_unix_time, end_unix_time))

    for reqid, start_unix_time, end_unix_time in new_times:
        yield dbpool.runQuery(
            """
            UPDATE requests_new SET start_datetime=?, end_datetime=? WHERE id=?;
            """, (start_unix_time, end_unix_time, reqid)
        )

    for query in drop_queries:
        yield dbpool.runQuery(query)

    yield dbpool.runQuery(
        """
        UPDATE schema_meta SET version=6;
        """
    )
