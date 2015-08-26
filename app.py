#!/usr/bin/python
#-*- coding: UTF-8 -*-

import os
   
from autobahn.asyncio.websocket import WebSocketServerProtocol, WebSocketServerFactory
import trollius
import struct, zlib, logging, sys, time
#import hashlib

class TunnelServerTransportProtocol(WebSocketServerProtocol): 
    class SocketMirrorProtocol(trollius.Protocol):
        def connection_made(self, transport):
            self.transport = transport
            
        def setSendCallback(self, func, funcClose):
            self.sendCallback = func
            self.sendCloseCallback = funcClose
            
        def data_received(self, data):
            #print 'sending from tunnel'
            self.sendCallback(data)
            
        def eof_received(self):
            self.sendCloseCallback()
            

    def __init__(self):
        WebSocketServerProtocol.__init__(self)
        
        self.waitingStage = 0
        self.remoteAddr, self.remotePort = '', -1
        self.localAddr , self.localPort  = '', -1
        
        self.connectionClosed = False 
   
    def connectionBuilt(self, args):
        self.remoteTransport, self.remoteProtocol = self.remoteSocket.result()
        
        self.remoteProtocol.setSendCallback( lambda x:self.sendMessage(payload=x, isBinary=True), self.sendClose )
        
        self.localAddr, self.localPort = self.remoteTransport.get_extra_info('sockname')
        self.sendMessage( payload= struct.pack('!H', self.localPort) + self.localAddr, isBinary=True )
        
        #print 'replied handshake'

    
    def onMessageInner(self, data):
        if (self.waitingStage == 0):
            self.waitingStage = 1
                
            self.remotePort = struct.unpack('!H', data[0:2])[0]
            self.remoteAddr = data[2:]
            
            loop = trollius.get_event_loop()
            coro = loop.create_connection(TunnelServerTransportProtocol.SocketMirrorProtocol, self.remoteAddr, self.remotePort)
            
            self.remoteSocket = trollius.async(coro)
            self.remoteSocket.add_done_callback(self.connectionBuilt)
            
        else:
            #print 'Writing:', hashlib.md5(data).hexdigest()
            self.remoteTransport.write( data )
    
    def onMessage(self, payload, isBinary):   
        if not isBinary:
            return
            #self.sendClose() must be something wrong
        self.onMessageInner(payload)
        
    def onClose(self, wasClean, code, reason):
        try:
            #print 'app ws closing...', wasClean
            if self.remoteTransport.can_write_eof():
                #print 'writing eof'
                self.remoteTransport.write_eof()
        except:
            pass
        
        try:
            self.remoteTransport.close()
        except:
            pass
        
ip, port = '0.0.0.0', os.environ.get('PORT', 5000)
   
factory = WebSocketServerFactory('ws://{0}:{1}'.format(ip, port), debug = False)
factory.protocol = TunnelServerTransportProtocol

loghdl = logging.StreamHandler(sys.stdout)
trollius.log.logger.addHandler(loghdl)

loop = trollius.get_event_loop()
coro = loop.create_server(factory, ip, port)
server = loop.run_until_complete(coro)

try:
    #print 'serving....'
    loop.run_forever()
except:
    pass
 
server.close()
loop.run_until_complete(server.wait_closed())
loop.close()