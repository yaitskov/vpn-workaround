import sys
import traceback
import asyncio
from meta_stream import StreamMeta


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


async def clientsMain(host, port):
    print("Clients accepted on %s %d" % (host, port))
    server = await asyncio.start_server(clientConnectionHanlder, host, port)
    await server.serve_forever()


async def sinkMain(host, port):
    print("Sink accepted on %s %d" % (host, port))
    server = await asyncio.start_server(sinkConnectionHanlder, host, port)
    await server.serve_forever()


async def multi():
    await asyncio.wait([
        clientsMain('0.0.0.0', 9011),
        sinkMain('0.0.0.0', 9012)])

asyncio.run(multi())
