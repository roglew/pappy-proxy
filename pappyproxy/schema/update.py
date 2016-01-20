import os
import glob
import imp
import random

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
        
def copy_file(a, b):
    a_bytes = a.read(1024)
    while a_bytes:
        b.write(a_bytes)
        a_bytes = a.read(1024)

def create_backup(filename):
    backup = filename + '.bak'
    while os.path.isfile(backup):
        backup = '%s.%d' % (backup, random.randint(0, 9999999999))
    # Make sure backup file has secure permissions
    with os.fdopen(os.open(backup, os.O_CREAT, 0o0600), 'r') as f:
        pass
    # Copy the datafile
    with open(filename, 'r') as a:
        with open(backup, 'w') as b:
            copy_file(a, b)
    return backup
        
@defer.inlineCallbacks
def update_schema(dbpool, filename):
    # Update the database schema to the latest version
    schema_version = yield get_schema_version(dbpool)
    if schema_version == 0:
        verbose_update = False
    else:
        verbose_update = True
    schemas = []
    add_schema_files(schemas)
    schemas = sorted(schemas, key=lambda tup: tup[0])
    to_run = range(schema_version, len(schemas))
    if len(to_run) > 0:
        # Back up data file
        if verbose_update:
            print 'Backing up data file'
        backup = create_backup(filename)
        if verbose_update:
            print 'Backed up to %s' % backup
        try:
            for i in to_run:
                # schemas[0] is v1, schemas[1] is v2, etc
                if verbose_update:
                    print "Updating datafaile schema to version %d" % (i+1)
                yield schemas[i][1].update(dbpool)
            # Delete backup
            os.remove(backup)
            if verbose_update:
                print 'Update successful! Deleted backup'
        except Exception as e:
            # restore the backup
            print 'Update failed, restoring backup'
            with open(filename, 'w') as a:
                with open(backup, 'r') as b:
                    copy_file(b, a)
            os.remove(backup)
            raise e
    
@defer.inlineCallbacks
def main():
    dbpool = adbapi.ConnectionPool("sqlite3", "data.db", check_same_thread=False)
    yield update_schema(dbpool)
    reactor.stop()
        
if __name__ == '__main__':
    reactor.callWhenRunning(main)
    reactor.run()
