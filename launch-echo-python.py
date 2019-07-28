import virtualbox
import time
import sys

vbox = virtualbox.VirtualBox()
session = virtualbox.Session()
machine = vbox.find_machine("IE8 - Win7")

machine.lock_machine(session, virtualbox.library.LockType.shared)
console = session.console
guest = console.guest
guestSesssion = guest.create_session("IEUser", "Passw0rd!", "", "s1")
igp = guestSesssion.process_create(
    "C:\\Users\\IEUser\\AppData\\Local\\Programs\\Python\\Python37-32\\python.exe",
    ["C:\\Users\\IEUser\\echo.py"],
    [],
    [], 20000)

while True:
    if igp.status == virtualbox.library.ProcessStatus.started:
        break
    print("Wait for started but %s" % igp.status)
    time.sleep(1)

#print("Wait for started")
#igp.waitForOperationCompletion(1, 10000)
# waitFor(virtualbox.library.ProcessWaitForFlag.start, 10000)

# print("Wait for stdin ready")
# igp.waitFor(virtualbox.library.ProcessWaitForFlag.std_in, 10000)

while True:
    print("Enter line:")
    line = sys.stdin.readline()
    if line == "\n":
        break
    lineBytes = line.encode()
    igp.write(0, 0,
              int.to_bytes(len(lineBytes),
                           length=1,
                           byteorder='big'),
              11111)
    igp.write(0, 0, lineBytes, 11111)
    toRead = int.from_bytes(igp.read(1, 1, 11111), byteorder='big')
    print("Read:\n%s" % igp.read(1, toRead, 1111))
