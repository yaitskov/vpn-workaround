import asyncio
import random

listOfFutures = []
theAlarm = []

async def www(n):
    sleepForSec = random.randint(1, 10)
    await asyncio.sleep(sleepForSec)
    return [n, sleepForSec]

async def waitMany():
    for i in range(10):
        listOfFutures.append(asyncio.create_task(www(i)))
    done, pending = await asyncio.wait(set([theAlarm[0]] + listOfFutures), return_when=asyncio.FIRST_COMPLETED)
    for d in done:
        if id(d) == id(theAlarm[0]):
            print("Alarm oFF %s" % (d.result(), ))
        else:
            print("Other Coro complete %s" % (d.result(), ))

async def alarmFuture(sleep):
    await asyncio.sleep(sleep)
    print("SEND alarm")
    theAlarm[0].set_result([-10, sleep])

async def multi():
    theAlarm.append(asyncio.Future()) # create_future()
    await asyncio.gather(waitMany(), alarmFuture(3))
    print("Ta tam!")


print("START")
asyncio.run(multi())
