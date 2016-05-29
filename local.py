#!/usr/bin/env python2
#-*- coding: UTF-8 -*-

import trollius
import socket, struct, logging, sys, zlib
from autobahn.asyncio.websocket import WebSocketClientProtocol, WebSocketClientFactory
#import hashlib

wsAddr, wsPort = '127.0.0.1', 5000
wsUrl  = 'ws://%s:%d' % (wsAddr, wsPort)

wsAddr = 'your.platform.com'
wsPort = 443
wsUrl  = 'wss://%s:%d' % (wsAddr, wsPort)


class LightSocks5Server(trollius.Protocol):
    class TunnelClientTransportProtocol(WebSocketClientProtocol):
        def __init__(self, addr='', port=-1):
            WebSocketClientProtocol.__init__(self)

            self.targetAddr = addr
            self.targetPort = port

            self.remoteAddr = ''
            self.remotePort = -1

            self.sendCallback = None

            self.waitingResponse = True

        def setTarget(self, addr, port):
            self.targetAddr = addr
            self.targetPort = port

        def setSendCallback(self, func, funcClose):
            self.sendCallback = func
            self.sendCloseCallback = funcClose

        def innerSend(self, data):
            self.sendMessage(payload=data, isBinary=True)

        def onConnect(self, response):
            pass

        def onOpen(self):
            if (self.targetAddr != '' and self.targetPort != -1):
                text = struct.pack('!H', self.targetPort) + self.targetAddr
                self.innerSend(text)
                #print 'Target sent to amazon'
            else:
                print 'open error!'

        def onMessageInner(self, data):
            if (self.waitingResponse):
                self.remotePort = struct.unpack('!H', data[0:2])[0]
                self.remoteAddr = data[2:]
                self.waitingResponse = False

                try:
                    reply = b"\x05\x00\x00\x01"
                    reply += socket.inet_aton(self.remoteAddr) + struct.pack("!H", self.remotePort)
                except:
                    reply = b"\x05\x00\x00\x03"
                    reply += chr(len(self.remoteAddr)) + self.remoteAddr + struct.pack("!H", self.remotePort)

                self.sendCallback(reply)
                print 'Replied from (%s, %d)' % (str(self.remoteAddr), self.remotePort)
            else:
                self.sendCallback(data)

        def onMessage(self, payload, isBinary):
            if (not isBinary):
                self.sendClose() #must be something wrong
            self.onMessageInner(payload)

        def onClose(self, wasClean, code, reason):
            #print 'local ws closing...', wasClean
            self.sendCloseCallback()
            pass

    class Stages:
        WaitingHandshake = 1
        WaitingRequest = 2
        Transferring = 3

    def connection_made(self, transport):
        self.transport = transport
        self.connectionStage = self.Stages.WaitingHandshake

    def connectionBuilt(self, args):
        self.remoteTransport, self.remoteProtocol = self.remoteSocket.result()

        self.remoteProtocol.setSendCallback(self.transport.write, self.cleanlyClose)
        #self.remoteProtocol.setTarget(self.targetAddr, self.targetPort)

        #print 'lets shake'
        #self.remoteProtocol.firstHandshake()
        
    def cleanlyClose(self):
        try:
            #print 'local ws closing, by server side...'
            if self.transport.can_write_eof():
                #print 'writing eof'
                self.transport.write_eof()
        except:
            pass
        
        try:
            self.transport.close()
        except:
            pass

    def data_received(self, data):
        if self.connectionStage == self.Stages.WaitingHandshake:
            reply = b'\x05\x00'
            self.connectionStage = self.Stages.WaitingRequest
            self.transport.write(reply)

        elif self.connectionStage == self.Stages.WaitingRequest:
            mode, addrtype = ord(data[1]), ord(data[3])
            data = data[4:]

            if addrtype == 1:       # IPv4
                addr = socket.inet_ntoa(data[0:4])
                data = data[4:]
            elif addrtype == 3:     # Domain name
                datalen = ord(data[0])
                addr = data[1:datalen+1]
                data = data[datalen+1:]
            else:
                print 'Not supported IP class'
                reply = b'\x05\x07\x00\x01' # Command not supported
                self.transport.write(reply)
                self.transport.close()
                return

            port = struct.unpack('!H', data[0:2])[0]

            if mode == 1:
                print 'Connecting to: (%s, %d)' % (str(addr), port)
                #reply = b"\x05\x00\x00\x01"

                #local = ('222.225.31.29', 24389)
                #reply += socket.inet_aton(local[0]) + struct.pack(">H", local[1])

                loop = trollius.get_event_loop()
                factory = WebSocketClientFactory(wsUrl, debug = False)

                factory.protocol = lambda: LightSocks5Server.TunnelClientTransportProtocol(addr, port)
                factory.setProtocolOptions(openHandshakeTimeout=60, closeHandshakeTimeout=15, version=13)

                if (wsUrl[0:3] == 'wss'):
                    coro = loop.create_connection(protocol_factory=factory, host=wsAddr, port=wsPort, ssl=True) #, server_hostname='*.rhcloud.com')
                    #TODO: Already found that there's no check of certificates
                else:
                    coro = loop.create_connection(protocol_factory=factory, host=wsAddr, port=wsPort)

                self.remoteSocket = trollius.async(coro)
                self.remoteSocket.add_done_callback(self.connectionBuilt);

                self.targetAddr = addr
                self.targetPort = port

                #self.reply = reply

                self.connectionStage = self.Stages.Transferring
            else: 
                print 'Not supported command'
                reply = b'\x05\x07\x00\x01' # Command not supported
                self.transport.close()
        else: #Transferring
            #print 'Writing:', hashlib.md5(data).hexdigest()
            self.remoteProtocol.innerSend(data)

    def eof_received(self):
        #print 'eof received'
        self.remoteProtocol.sendClose()
        self.transport.close()


loghdl = logging.StreamHandler(sys.stdout)
trollius.log.logger.addHandler(loghdl)
loop = trollius.get_event_loop()
#loop.set_debug(True)
# Each client connection will create a new protocol instance
coro = loop.create_server(LightSocks5Server, '127.0.0.1', 1081)
server = loop.run_until_complete(coro)

# Serve requests until CTRL+c is pressed
print('Server on {}'.format(server.sockets[0].getsockname()))

while True:
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        break
    except:
        pass

# Close the server
server.close()
loop.run_until_complete(server.wait_closed())
loop.close()
