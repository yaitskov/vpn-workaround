import sys
import traceback
import asyncio
import time
from meta_stream import StreamMeta
import ssl

class TunnelState:
    def __init__(self):
        self.proxyWithoutFuture = set([])
        self.future2Proxy = {}
        self.sid2ProxyEndpoint = {}
        self.newProxyFuture = None
        self.nextStreamId = 1

        self.clientConnection = None

    def removeStream(self, streamMeta):
        del self.sid2ProxyEndpoint[streamMeta.streamId]
        streamMeta.close()

    def removeStreamIfExist(self, streamId):
        metaStream = self.sid2ProxyEndpoint.get(streamId)
        if metaStream is not None:
            self.removeStream(metaStream)


class Params:
    def __init__(self, clientHost, clientPort, proxyHost, proxyPort):
        self.clientHost = clientHost
        self.clientPort = clientPort
        self.proxyHost = proxyHost
        self.proxyPort = proxyPort

def initSsl():
    sslCtx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT) # ssl.PROTOCOL_TLSv1_2)
    sslCtx.options |= ssl.OP_NO_TLSv1
    sslCtx.options |= ssl.OP_NO_TLSv1_1
    # sslCtx.options |= ssl.OP_NO_TLSv1_2
    sslCtx.load_verify_locations(cafile='./root-ca.crt')
    sslCtx.check_hostname = False
    sslCtx.verify_mode = ssl.VerifyMode.CERT_NONE
    sslCtx.set_ciphers('ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384')
    # sslCtx.load_cert_chain(certfile="./root-ca.crt", keyfile="./root-ca.key")
    return sslCtx

class Connector:
    def __init__(self, params, state):
        self.params = params
        self.state = state

    async def run(self):
        await self.connectToClient()
        await asyncio.wait([self.pollClient(), self.pollProxy()])

    async def connectToClient(self):
        host, port = self.params.clientHost, self.params.clientPort
        reader, writer = await asyncio.open_connection(host, port, ssl=initSsl())
        self.state.clientConnection = StreamMeta(None, reader, writer)
        print('Connected to client [%s:%d]' % (host, port))

    async def pollClient(self):
        while True:
            try:
                client = self.state.clientConnection

                streamId = await client.readInt(8)

                packetSize = await client.readInt(2)

                data = await client.readExactly(packetSize)
                if packetSize > 0 and not data:
                    raise Exception("sink closed connection")

                if packetSize == 0:
                    self.state.removeStreamIfExist(streamId)
                    continue

                try:
                    streamMeta = await self.getToProxyStream(streamId)
                    print("send %d from sink %d" % (packetSize, streamId))
                    streamMeta.write(data)
                    await streamMeta.drain()
                except Exception as e:
                    self.state.removeStream(streamMeta)
            except KeyboardInterrupt:
                print("keyboard int1")
                sys.exit()
            except Exception as e:
                print(e)
                traceback.print_exc(file=sys.stdout)
                print("Reconnect to client")
                self.state.clientConnection.close()
                print("CLosed")
                try:
                    await asyncio.sleep(3)
                    await self.connectToClient()
                    print("Reconnected")
                except KeyboardInterrupt:
                    print("keyboard int2")
                    sys.exit()
                except Exception as e:
                    print("Failed to reconnect")
                    print(e)

    async def getToProxyStream(self, streamId):
        streamMeta = self.state.sid2ProxyEndpoint.get(streamId)

        if streamMeta is None:
            host, port = self.params.proxyHost, self.params.proxyPort
            reader, writer = await asyncio.open_connection(host, port)
            streamMeta = StreamMeta(streamId, reader, writer)
            self.state.sid2ProxyEndpoint[streamId] = streamMeta
            print('Connected to proxy [%s:%d] for stream %d'
                  % (host, port, streamId))
            self.state.proxyWithoutFuture.add(streamMeta)
            oldProxy = self.state.newProxyFuture
            self.state.newProxyFuture = asyncio.Future()
            oldProxy.set_result('new client')

        return streamMeta

    async def pollProxy(self):
        print("Poll proxy connections")
        pending = set([])
        while True:
            for proxy in list(self.state.proxyWithoutFuture):
                readTask = asyncio.create_task(self.readProxyStream(proxy))
                pending.add(readTask)
                self.state.future2Proxy[readTask] = proxy
                self.state.proxyWithoutFuture.remove(proxy)

            if self.state.newProxyFuture is None:
                self.state.newProxyFuture = asyncio.Future()
            pending.add(self.state.newProxyFuture)
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED)
            for doneFuture in done:
                proxy = self.state.future2Proxy.get(doneFuture)
                if proxy is None:  # new clien future
                    pass
                else:
                    del self.state.future2Proxy[doneFuture]
                    if proxy.isClosed():
                        print("Proxy %d is closed" % proxy.streamId)
                    else:
                        self.state.proxyWithoutFuture.add(proxy)

    async def readProxyStream(self, proxy):
        data = await proxy.reader.read(1000)
        print("Client %d read %s bytes at %f"
              % (proxy.streamId, len(data), time.time()))
        if not data:
            self.state.removeStreamIfExist(proxy.streamId)
        client = self.state.clientConnection
        client.writeInt(proxy.streamId, 8)
        client.writeInt(len(data), 2)
        client.write(data)
        await client.drain()


asyncio.run(Connector(
    Params(clientHost='127.0.0.1', clientPort=9012,
           proxyHost='127.0.0.1', proxyPort=9013),
    TunnelState()).run())
