import os
import glob
import imp

from twisted.internet import reactor
from twisted.enterprise import adbapi
from twisted.internet import defer

@defer.inlineCallbacks
def get_schema_version(dbpool):
    schema_exists = yield dbpool.runQuery("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta';")
    if not schema_exists:
        # If we get an empty list, we have no schema
        defer.returnValue(0)
    else:
        schema_version_result = yield dbpool.runQuery("SELECT version FROM schema_meta;")

        # There should only be one row in the meta table
        assert(len(schema_version_result) == 1)

        # Return the retrieved version
        version = schema_version_result[0][0]
        defer.returnValue(version)

def add_schema_files(schemas):
    # Finds and imports all schema_*.py files into the list
    module_files = glob.glob(os.path.dirname(os.path.abspath(__file__)) + "/schema_*.py")
    for mod in module_files:
        module_name = os.path.basename(os.path.splitext(mod)[0])
        newmod = imp.load_source('%s'%module_name, mod)
        schemas.append( (module_name, newmod) )

@defer.inlineCallbacks
def update_schema(dbpool):
    # Update the database schema to the latest version
    schema_version = yield get_schema_version(dbpool)
    schemas = []
    add_schema_files(schemas)
    schemas = sorted(schemas, key=lambda tup: tup[0])
    for i in range(schema_version, len(schemas)):
        # schemas[0] is v1, schemas[1] is v2, etc
        print "Updating datafaile schema to version %d" % (i+1)
        yield schemas[i][1].update(dbpool)
    
@defer.inlineCallbacks
def main():
    dbpool = adbapi.ConnectionPool("sqlite3", "data.db", check_same_thread=False)
    yield update_schema(dbpool)
    reactor.stop()
        
if __name__ == '__main__':
    reactor.callWhenRunning(main)
    reactor.run()
