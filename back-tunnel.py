import asyncio
from dataclasses import dataclass


# async def tcp_echo_client(message):
#     reader, writer = await asyncio.open_connection(
#         '127.0.0.1', 8888)

#     print(f'Send: {message!r}')
#     writer.write(message.encode())

#     data = await reader.read(100)
#     print(f'Received: {data.decode()!r}')

#     print('Close the connection')
#     writer.close()
#     await writer.wait_closed()

# asyncio.run(tcp_echo_client('Hello World!'))

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

    def registerClient(self, reader, writer):
        streamId = self.nextStreamId
        print("New client %d" % (streamId,))
        self.nextStreamId = streamId + 1
        self.streams[streamId] = StreamMeta(streamId, reader, writer)
        return self.streams[streamId]

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


async def clientsMain(host, port):
    print("Clients accepted on %s %d" % (host, port))
    server = await asyncio.start_server(clientConnectionHanlder, host, port)
    await server.serve_forever()

async def sinkMain(host, port):
    print("Sink accepted on %s %d" % (host, port))
    server = await asyncio.start_server(sinkConnectionHanlder, host, port)
    await server.serve_forever()


async def multi():
    await asyncio.wait([sinkMain('0.0.0.0', 9015), clientsMain('0.0.0.0', 9016)])

#asyncio.run(main('0.0.0.0', 9015))
asyncio.run(multi())
