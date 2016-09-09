#!/usr/bin/env python
# tinybitcoinpeer.py
#
# A toy bitcoin node in Python. Connects to a random testnet
# node, shakes hands, reacts to pings, and asks for pongs.
# - Andrew Miller https://soc1024.com/
#
# Thanks to Peter Todd, Jeff Garzik, Ethan Heilman
#
# Dependencies: 
# - gevent
# - https://github.com/petertodd/python-bitcoinlib
# 
# This file is intended to be useful as a starting point 
# for building your own Bitcoin network tools. Rather than
# choosing one way to do things, it illustrates several 
# different ways... feel free to pick and choose.
# 
# - The msg_stream() function handily turns a stream of raw
#     Bitcoin p2p socket data into a stream of parsed messages.
#     Parsing is provided by the python-bitcoinlib dependency.
#
# - The handshake is performed with ordinary sequential code.
#    You can get a lot done without any concurrency, such as
#     connecting immediately to fetching blocks or addrs,
#     or sending payloads of data to a node.

# - The node first attempts to resolve the DNS name of a Bitcoin
#     seeder node. Bitcoin seeder speak the DNS protocol, but
#     actually respond with IP addresses for random nodes in the
#     network.
#
# - After the handshake, a "message handler" is installed as a 
#     background thread. This handler logs every message 
#     received, and responds to "Ping" challenges. It is easy 
#     to add more reactive behaviors too.
# 
# - This shows off a versatile way to use gevent threads, in
#     multiple ways at once. After forking off the handler 
#     thread, the main thread also keeps around a tee of the
#     stream, making it easy to write sequential schedules.
#     This code periodically sends ping messages, sleeping 
#     in between. Additional threads could be given their 
#     own tees too.
#
import gevent, gevent.socket as socket
from gevent.queue import Queue
import bitcoin
from bitcoin.messages import *
from bitcoin.net import CAddress
import time, sys, contextlib

PORT = 18333
bitcoin.SelectParams('testnet')

# Turn a raw stream of Bitcoin p2p socket data into a stream of 
# parsed messages.
def msg_stream(f):
    while True:
        yield MsgSerializable.stream_deserialize(f)

def tee_and_handle(sock, msgs):
    queue = Queue() # unbounded buffer
    def _run():
        for msg in msgs:
            sys.stdout.write('Received: %s\n' % type(msg))
            if msg.command == 'ping':
                print 'Handler: Sending pong'
                sock.send( msg_pong(nonce=msg.nonce).to_bytes() )
            queue.put(msg)
    t = gevent.Greenlet(_run)
    t.start()
    while True: yield(queue.get())

def version_pkt(my_ip, their_ip):
    msg = msg_version()
    msg.nVersion = 70002
    msg.addrTo.ip = their_ip
    msg.addrTo.port = PORT
    msg.addrFrom.ip = my_ip
    msg.addrFrom.port = PORT
    msg.strSubVer = "/tinybitcoinpeer.py/"
    return msg

def addr_pkt( str_addrs ):
    msg = msg_addr()
    addrs = []
    for i in str_addrs:
        addr = CAddress()
        addr.port = PORT
        addr.nTime = int(time.time())
        addr.ip = i
        addrs.append( addr )
    msg.addrs = addrs
    return msg

def main():
    with contextlib.closing(socket.socket()) as s, \
         contextlib.closing(s.makefile("r+b", bufsize=0)) as cf:

        # This will actually return a random testnet node
        their_ip = socket.gethostbyname("seed.tbtc.petertodd.org")
        print 'Connecting to:', their_ip

        my_ip = "127.0.0.1"

        s.connect( (their_ip,PORT) )
        stream = msg_stream(cf)

        # Send Version packet
        s.send( version_pkt(my_ip, their_ip).to_bytes() )
        print "Send version"

        # Receive their Version
        their_ver = stream.next()
        print 'Got', their_ver

        # Send Version acknolwedgement (Verack)
        s.send( msg_verack().to_bytes() )
        print 'Sent verack'

        # Fork off a handler, but keep a tee of the stream
        stream = tee_and_handle(s, stream)

        # Get Verack
        their_verack = stream.next()
        print 'Got', their_verack

        # Send a ping!
        try:
            while True:
                s.send( msg_ping().to_bytes() )
                print 'Sent ping'
                gevent.sleep(5)
        except KeyboardInterrupt: pass

try: __IPYTHON__
except NameError: main()
