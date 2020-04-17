import sys
import traceback
import asyncio
from meta_stream import StreamMeta
import ssl


class TunnelState:
    def __init__(self):
        self.sinkConnection = None
        self.nextStreamId = 1
        self.streams = {}

    def closeSink(self):
        print("Sink is deactivated")
        self.sinkConnection = None
        for stream in self.streams.values():
            stream.close()

        self.streams = {}

    def registerClient(self, reader, writer):
        streamId = self.nextStreamId
        print("New client %d" % (streamId,))
        self.nextStreamId = streamId + 1
        self.streams[streamId] = StreamMeta(streamId, reader, writer)
        return self.streams[streamId]

    def closeClient(self, streamMeta):
        if streamMeta.streamId in self.streams:
            del self.streams[streamMeta.streamId]
            streamMeta.close()
        else:
            print("Stream %d is already closed" % streamMeta.streamId)

    async def removeClient(self, streamMeta):
        self.closeClient(streamMeta)
        if self.sinkConnection:
            sink = self.sinkConnection
            sink.writeInt(streamMeta.streamId, 8)
            sink.writeInt(0, 2)
            await sink.drain()


class SecondSink(Exception):
    pass


tunnelState = TunnelState()


async def sinkConnectionHanlder(reader, writer):
    if tunnelState.sinkConnection is None:
        print("sink connection is active")
        tunnelState.sinkConnection = StreamMeta(None, reader,  writer)
    else:
        print("reject second sink connection")
        writer.close()
        return

    sink = tunnelState.sinkConnection

    try:
        while True:
            streamId = await sink.readInt(8)
            streamMeta = tunnelState.streams.get(streamId)
            packetSize = await sink.readInt(2)
            data = await sink.readExactly(packetSize)

            if streamMeta is None:
                if packetSize:
                    print("bad streamId %d from sink" % streamId)
                else:
                    print("Zombi stream %d" % streamId)
                continue

            if packetSize > 0 and not data:
                raise Exception("sink closed connection")
            elif packetSize == 0:
                print("remote connection for stream %d is closed" % streamId)
                tunnelState.closeClient(streamMeta)
                continue

            try:
                print("send %d from sink %d" % (packetSize, streamId))
                streamMeta.write(data)
                await streamMeta.drain()
            except Exception as e:
                print("Delivery to stream %d failed %s" % (streamId, e))
                tunnelState.closeClient(streamMeta)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        tunnelState.closeSink()


async def clientConnectionHanlder(reader, writer):
    streamMeta = tunnelState.registerClient(reader, writer)
    try:
        while True:
            data = await reader.read(4000)
            if not data:
                raise Exception("Client %s closed connection"
                                % streamMeta.streamId)
            else:
                if tunnelState.sinkConnection is None:
                    raise Exception("No active sink connection")
                sink = tunnelState.sinkConnection
                print("Send to sink %d %d bytes"
                      % (streamMeta.streamId, len(data)))
                sink.writeInt(streamMeta.streamId, 8)
                sink.writeInt(len(data), 2)
                sink.write(data)
                await sink.drain()  # Flow control, see later
    except Exception as e:
        print(e)
    finally:
        await tunnelState.removeClient(streamMeta)

def initSsl():
    sslCtx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER) # ssl.PROTOCOL_TLSv1_2)
    sslCtx.options |= ssl.OP_NO_TLSv1
    sslCtx.options |= ssl.OP_NO_TLSv1_1
    sslCtx.options |= ssl.OP_SINGLE_DH_USE
    sslCtx.options |= ssl.OP_SINGLE_ECDH_USE
    # sslCtx.load_verify_locations(cafile='./root-ca.crt')
    sslCtx.check_hostname = False
    sslCtx.verify_mode = ssl.VerifyMode.CERT_NONE
    sslCtx.set_ciphers('ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384')
    sslCtx.load_cert_chain(certfile="./cloud-sport.pl.crt", keyfile="./cloud-sport.pl.key")
    return sslCtx

async def startServer(label, handler, host, port, ssl):
    print("%s accepted on %s %d" % (label, host, port))
    server = await asyncio.start_server(
        handler, host, port, ssl=ssl)
    await server.serve_forever()

async def clientsMain(host, port):
    await startServer("Clients", clientConnectionHanlder, host, port, None)

async def sinkMain(host, port):
    await startServer("Sink", sinkConnectionHanlder, host, port, initSsl())

async def multi():
    await asyncio.wait([
        clientsMain('0.0.0.0', 9011),
        sinkMain('0.0.0.0', 9012)])

asyncio.run(multi())
