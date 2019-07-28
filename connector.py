import asyncio
from dataclasses import dataclass


@dataclass
class StreamMeta:
    streamId = None
    reader = None
    writer = None

    def close(self):
        self.reader.close()
        self.writer.close()


class TunnelState:
    def __init__(self):
        self.sinkConnection = None
        self.nextStreamId = 1
        self.streams = {} # stream Id => (reader, writer)?

    def findById(self, streamId):
        streamMeta = self.streams.get(streamId)
        newStream = streaMeta is None
        if streamMeta is None:
            reader, writer = await asyncio.open_connection('127.0.0.1', 9011)
            self.streams[streamId] = StreamMeta(streamId, reader, writer)
            streamMeta = self.streams[streamId]

        return streamMeta, newStream

    def removeClient(self, streamMeta):
        del self.streams[streamMeta.streamId]
        streamMeta.close()
        if self.sinkConnection:
            self.sinkConnection.write(int.to_bytes(streamMeta.streamId, length=8, byteorder='big'))
            self.sinkConnection.write(int.to_bytes(0, length=2, byteorder='big'))
            self.sinkConnection.drain()


@dataclass
class SinkConn:
    reader = None
    writer = None

class SecondSink(Exception):
    pass

tunnelState: TunnelState = TunnelState()

async def backTunnelConnector():
    reader, writer = await asyncio.open_connection('127.0.0.1', 9016)
    tunnelState.sinkConnection = SinkConn(reader, writer)
    try:
        print('Connected')
        while True:
            streamId = int.from_bytes(await reader.readexactly(8), byteorder='big')
            streamMeta, newStream = tunnelState.findById(streamId)
            packetSize = int.from_bytes(await reader.readexactly(2), byteorder='big')
            if packetSize > 0:
                data = await reader.readexactly(packetSize)
                if not data:
                    raise Exception("back tunnel connection ended");
                print('Received: %d from %d' % (packetSize, streamId))
                try:
                    streamMeta.writer.write(data)
                    await streamMeta.writer.drain()
                except:
                    print("Failed client")
                    tunnelState.closeClient(streamMeta, notifyBackTunnel=True)
            elif not newStream:
                tunnelState.closeClient(streamMeta)
    finally:
        print('Close the connection')
        writer.close()
        await writer.wait_closed()

async def sinkConnectionHanlder(reader, writer):
    try:
        if tunnelState.sinkConnection is None:
            print("sink connection is active")
            tunnelState.sinkConnection = SinkConn(reader,  writer)
        else:
            raise SecondSink("reject second sink connection")

        while True:
            streamId = int.from_bytes(await reader.readexactly(8), byteorder='big')
            streamMeta = tunnelState.streams.get(streamId)
            if streamMeta is None:
                raise Exception("bad streamId %d from sink" % (streamId,))
            packetSize = int.from_bytes(await reader.readexactly(2), byteorder='big')

            data = await reader.readexactly(packetSize)
            if packetSize > 0 and not data:
                raise Exception("sink closed connection")
            try:
                if packetSize == 0:
                    raise Exception("remote connection for stream %d is closed" % (packetSize, streamId))
                print("send %d from sink %d" % (packetSize, streamId))
                streamMeta.writer.write(data)
                await streamMeta.writer.drain()
            except Exception as e:
                print("Delivery to stream %d failed %s" % (streamId, e))
                del tunnelState.streams[streamId]
                streamMeta.close()

    except SecondSink as e:
        print(e)
        reader.close()
    except Exception as e:
        print(e)
        reader.close()
        print("Sink is deactivated")
        tunnelState.sinkConnection = None
    finally:
        writer.close()


async def clientConnectionHanlder(reader, writer):
    streamMeta = tunnelState.registerClient(reader, writer)
    try:
        while True:
            data = await reader.read(1000)
            if not data:
                raise Exception("Client %s closed connection" % (streamMeta.streamId,))
            else:
                if tunnelState.sinkConnection is None:
                    raise Exception("No active sink connection")
                sink = tunnelState.sinkConnection
                print("Send to sink %d from %d" % (len(data), streamMeta.streamId))
                sink.write(int.to_bytes(streamMeta.streamId, length=8, byteorder='big'))
                sink.write(int.to_bytes(len(data), length=2, byteorder='big'))
                sink.write(data)
                await sink.drain()  # Flow control, see later
    finally:
        tunnelState.removeClient(streamMeta)

# async def pollProxy():
#     for streamMeta in tunnelState.streams.values():
#         streamMeta.read

async def main():
    await asyncio.wait([backTunnelConnector()])

asyncio.run(main())
