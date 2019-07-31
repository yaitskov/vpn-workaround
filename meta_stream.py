class StreamMeta:
    def __init__(self, streamId, reader, writer):
        self.streamId = streamId
        self.reader = reader
        self.writer = writer

    def close(self):
        self.writer.close()
        self.writer = None

    def isClosed(self):
        return self.writer is None

    def writeInt(self, number, width):
        self.write(int.to_bytes(number, length=width, byteorder='big'))

    def write(self, data):
        self.writer.write(data)

    async def drain(self):
        await self.writer.drain()

    async def readExactly(self, length):
        data = await self.reader.readexactly(length)
        return data

    async def readInt(self, length):
        return int.from_bytes(await self.readExactly(length), byteorder='big')
