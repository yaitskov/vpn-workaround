import asyncio
import random
import time

MAX_NEW_CLIENT_DELAY=3
MAX_MEW_MSG_DELAY=3

class StreamMeta:
    def __init__(self, streamId, reader, writer):
        self.streamId = streamId
        self.reader = reader
        self.writer = writer

    def close(self):
        if (self.writer):
            self.writer.close()


class TunnelState:
    def __init__(self):
        self.clientWithoutFuture = set([])
        self.future2Client = {}
        self.sid2EndpointOnServer = {}
        self.newClientFuture = None
        self.nextStreamId = 1

    def registerClient(self, reader, writer):
        ms = StreamMeta(self.nextStreamId, reader, writer)
        self.sid2EndpointOnServer[ms.streamId] = ms
        print("Client %d connected on server" % ms.streamId)
        self.nextStreamId += 1

tunnelState: TunnelState = TunnelState()

async def clientConnectionHanlder(reader, writer):
    streamMeta = tunnelState.registerClient(reader, writer)
    while True:
        await asyncio.sleep(30)

async def generateMessages():
    print("generate new message started")
    msgId = 1
    while True:
        delay = random.randint(0, MAX_MEW_MSG_DELAY)
        print("GEN msg in %d sec" % delay)
        await asyncio.sleep(delay)
        if len(tunnelState.sid2EndpointOnServer) > 0:
            streamIdx = random.randint(1, len(tunnelState.sid2EndpointOnServer))
            print("GEN for %d" % (streamIdx))
            metaStream = next(ms for ms in  tunnelState.sid2EndpointOnServer.values()
                              if ms.streamId == streamIdx)
            msg = "for client %d msg #%d at %f" % (streamIdx, msgId, time.time())
            msg = msg.encode()
            metaStream.writer.write(int.to_bytes(len(msg), length=2, byteorder='big'))
            metaStream.writer.write(msg)
            msgId += 1
        else:
            print("SKIP no clients")

async def readClientStream(client):
    toRead = int.from_bytes(await client.reader.read(2), byteorder='big')
    data = await client.reader.read(toRead)
    print("Client %d read [%s] at %f" % (client.streamId, data, time.time()))
    return data

async def pollNewMessages():
    print("Poll new Messages")
    pending = set([])
    while True:
        for client in list(tunnelState.clientWithoutFuture):
            readTask = asyncio.create_task(readClientStream(client))
            pending.add(readTask)
            tunnelState.future2Client[readTask] = client
            tunnelState.clientWithoutFuture.remove(client)

        if tunnelState.newClientFuture is None:
            tunnelState.newClientFuture = asyncio.Future()
        pending.add(tunnelState.newClientFuture)
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for doneFuture in done:
            client = tunnelState.future2Client.get(doneFuture)
            if client is None: # new clien future
                pass
            else:
                del tunnelState.future2Client[doneFuture]
                tunnelState.clientWithoutFuture.add(client)

async def generateNewClients(port):
    print("client generator")
    clientId = 0
    if tunnelState.newClientFuture is None:
        tunnelState.newClientFuture = asyncio.Future()
    while True:
        if clientId >= tunnelState.nextStreamId:
            print("increment clientId")
            clientId += 1
        else:
            clientId = tunnelState.nextStreamId

        delay = random.randint(1, MAX_NEW_CLIENT_DELAY)
        print("New client %d in %d seconds" % (clientId, delay))
        await asyncio.sleep(delay)

        reader, writer = await asyncio.open_connection('127.0.0.1', port)

        tunnelState.clientWithoutFuture.add(StreamMeta(clientId, reader, writer))
        tunnelState.newClientFuture.set_result("new client %d" % clientId)
        tunnelState.newClientFuture = asyncio.Future()

async def serveClients(host, port):
    print("Clients are accepted on %s %d" % (host, port))
    server = await asyncio.start_server(clientConnectionHanlder, host, port)
    await server.serve_forever()

async def multi(port):
    await asyncio.gather(serveClients('0.0.0.0', port),
                         pollNewMessages(),
                         generateNewClients(port),
                         generateMessages())

print("START")
asyncio.run(multi(9020))
