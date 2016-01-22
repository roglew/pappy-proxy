import pytest

from pappyproxy.requestcache import RequestCache, RequestCacheIterator
from pappyproxy.http import Request, Response, get_request
from pappyproxy.util import PappyException

def gen_reqs(n):
    ret = []
    for i in range(1, n+1):
        r = get_request('https://www.kdjasdasdi.sadfasdf')
        r.headers['Test-Id'] = i
        r.reqid = str(i)
        ret.append(r)
    return ret

@pytest.inlineCallbacks
def test_cache_simple():
    reqs = gen_reqs(5)
    cache = RequestCache(5)
    cache.add(reqs[0])
    g = yield cache.get('1')
    assert g == reqs[0]
    
def test_cache_evict():
    reqs = gen_reqs(5)
    cache = RequestCache(3)
    cache.add(reqs[0])
    cache.add(reqs[1])
    cache.add(reqs[2])
    cache.add(reqs[3])
    assert not cache.check(reqs[0].reqid)
    assert cache.check(reqs[1].reqid)
    assert cache.check(reqs[2].reqid)
    assert cache.check(reqs[3].reqid)
    
    # Testing the implementation
    assert reqs[0].reqid not in cache._cached_reqs
    assert reqs[1].reqid in cache._cached_reqs
    assert reqs[2].reqid in cache._cached_reqs
    assert reqs[3].reqid in cache._cached_reqs

@pytest.inlineCallbacks
def test_cache_lru():
    reqs = gen_reqs(5)
    cache = RequestCache(3)
    cache.add(reqs[0])
    cache.add(reqs[1])
    cache.add(reqs[2])
    yield cache.get(reqs[0].reqid)
    cache.add(reqs[3])
    assert cache.check(reqs[0].reqid)
    assert not cache.check(reqs[1].reqid)
    assert cache.check(reqs[2].reqid)
    assert cache.check(reqs[3].reqid)
    
    # Testing the implementation
    assert reqs[0].reqid in cache._cached_reqs
    assert reqs[1].reqid not in cache._cached_reqs
    assert reqs[2].reqid in cache._cached_reqs
    assert reqs[3].reqid in cache._cached_reqs

@pytest.inlineCallbacks
def test_cache_lru_add():
    reqs = gen_reqs(5)
    cache = RequestCache(3)
    cache.add(reqs[0])
    cache.add(reqs[1])
    cache.add(reqs[2])
    yield cache.add(reqs[0])
    cache.add(reqs[3])
    assert cache.check(reqs[0].reqid)
    assert not cache.check(reqs[1].reqid)
    assert cache.check(reqs[2].reqid)
    assert cache.check(reqs[3].reqid)
    
    # Testing the implementation
    assert reqs[0].reqid in cache._cached_reqs
    assert reqs[1].reqid not in cache._cached_reqs
    assert reqs[2].reqid in cache._cached_reqs
    assert reqs[3].reqid in cache._cached_reqs

@pytest.inlineCallbacks
def test_cache_inmem_simple():
    cache = RequestCache(3)
    req = gen_reqs(1)[0]
    req.reqid = None
    cache.add(req)
    assert req.reqid[0] == 'm'
    g = yield cache.get(req.reqid)
    assert req == g

def test_cache_inmem_evict():
    reqs = gen_reqs(5)
    cache = RequestCache(3)
    reqs[0].reqid = None
    reqs[1].reqid = None
    reqs[2].reqid = None
    reqs[3].reqid = None
    cache.add(reqs[0])
    cache.add(reqs[1])
    cache.add(reqs[2])
    cache.add(reqs[3])
    assert not cache.check(reqs[0].reqid)
    assert cache.check(reqs[1].reqid)
    assert cache.check(reqs[2].reqid)
    assert cache.check(reqs[3].reqid)
    
    # Testing the implementation
    assert reqs[0] in RequestCache.inmem_reqs
    assert reqs[1] in RequestCache.inmem_reqs
    assert reqs[2] in RequestCache.inmem_reqs
    assert reqs[3] in RequestCache.inmem_reqs
