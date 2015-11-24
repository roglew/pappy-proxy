import pappy

from twisted.internet import reactor

if __name__ == '__main__':
    reactor.callWhenRunning(pappy.main)
    reactor.run()
