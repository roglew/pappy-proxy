import gc
import shlex
import code
import crochet
import os
import resource
import random
import datetime
from pappyproxy.http import Request, post_request
from pappyproxy.util import PappyException
from pappyproxy.requestcache import RequestCache
from pappyproxy.util import print_requests
from pappyproxy.pappy import heapstats, session
from pappyproxy.plugin import require_modules
from twisted.internet import defer

def cache_info(line):
    c = Request.cache
    print 'Cache has %d/%d slots filled' % (len(c._cached_reqs), c._cache_size)
    print 'Hit score: {0:.2f} ({1}/{2})'.format(c.hit_ratio, c.hits, c.hits+c.misses)
    print ''
    if line != 'q':
        rl = [v for k, v in Request.cache._cached_reqs.iteritems()]
        rs = sorted(rl, key=lambda r: Request.cache._last_used[r.reqid], reverse=True)
        print_requests(rs)
        
@require_modules('psutil')
def memory_info(line):
    import psutil
    proc = psutil.Process(os.getpid())
    mem = proc.memory_info().rss
    megabyte = (float(mem)/1024)/1024
    print 'Memory usage: {0:.2f} Mb ({1} bytes)'.format(megabyte, mem)

@require_modules('guppy')
def heap_info(line):
    size = heapstats.heap().size
    print 'Heap usage: {0:.2f} Mb'.format(size/(1024.0*1024.0))
    print heapstats.heap()
    
def limit_info(line):
    rsrc = resource.RLIMIT_AS
    soft, hard = resource.getrlimit(rsrc)
    print 'Soft limit starts as:', soft
    print 'Hard limit starts as:', hard
    if line:
        limit_mb = int(line)
        limit_kb = int(line)*1024
        print 'Setting limit to %s Mb' % limit_mb
        resource.setrlimit(rsrc, (limit_kb, hard)) #limit to one kilobyte
        soft, hard = resource.getrlimit(rsrc)
        print 'Soft limit is now:', soft
        print 'Hard limit is now:', hard
        
@require_modules('objgraph')
def graph_randobj(line):
    import objgraph
    args = shlex.split(line)
    if len(args) > 1:
        fname = args[1]
    else:
        fname = 'chain.png'
    print 'Getting random %s object...' % args[0]
    obj = random.choice(objgraph.by_type(args[0]))
    print 'Creating chain...'
    chain = objgraph.find_backref_chain(obj, objgraph.is_proper_module)
    print 'Saving chain...'
    objgraph.show_chain(chain, filename=fname)
        
    
def heapdo(line):
    if heapstats is None:
        raise PappyException('Command requires the guppy library')
    h = heapstats.heap()
    code.interact(local=locals())
    
def collect(line):
    gc.collect()
    
@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def loadblock(line):
    args = shlex.split(line)
    yield Request.cache.load(args[0], int(args[1]))

@crochet.wait_for(timeout=None)
@defer.inlineCallbacks
def big_fucking_data_file(line):
    print "Generating some giant fucking requests"
    for i in range(1000):
        if i % 20 == 0:
            print 'Generated %d' % i
        r = post_request('https://www.google.com')
        r.body = 'A'*(1024*1024)
        yield r.async_deep_save()
        
def time_cmd(line):
    print 'Timing `%s`...' % line
    start = datetime.datetime.now()
    session.cons.onecmd(line.strip())
    end = datetime.datetime.now()
    total_time = (end-start).total_seconds()
    print '`{0}` took {1:.3f} seconds'.format(line, total_time)

def cache_data(line):
    args = shlex.split(line)
    reqid = args[0]
    cached = reqid in Request.cache._cached_reqs
    if reqid in Request.cache._last_used:
        last_used = Request.cache._last_used[reqid]
    else:
        last_used = 'NOT IN _last_used'
    in_all = reqid in Request.cache.all_ids
    in_unmangled = reqid in Request.cache.unmangled_ids
    try:
        ordered_ids_pos = Request.cache.ordered_ids.index(reqid)
    except ValueError:
        ordered_ids_pos = 'Not in ordered_ids'
    in_inmem = reqid in Request.cache.inmem_reqs

    print ''
    print 'Cache data about request %s ----------' % reqid
    print 'Cahced: %s' % cached
    print 'Last used: %s' % last_used
    print 'In all_ids: %s' % in_all
    print 'In unmangled: %s' % in_unmangled
    print 'Ordered id pos: %s' % ordered_ids_pos
    print 'Is inmem: %s' % in_inmem
    print ''
    
        
def check_cache(line):
    Request.cache.assert_ids()

def load_cmds(cmd):
    cmd.set_cmds({
        'cacheinfo': (cache_info, None),
        'heapinfo': (heap_info, None),
        'memlimit': (limit_info, None),
        'heapdo': (heapdo, None),
        'gccollect': (collect, None),
        'graphobj': (graph_randobj, None),
        'meminfo': (memory_info, None),
        'genbigdata': (big_fucking_data_file, None),
        'checkcache': (check_cache, None),
        'loadblock': (loadblock, None),
        'time': (time_cmd, None),
        'cachedata': (cache_data, None),
    })
    cmd.add_aliases([
    ])
