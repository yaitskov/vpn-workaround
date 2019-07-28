import virtualbox
import time

vbox = virtualbox.VirtualBox()
session = virtualbox.Session()
machine = vbox.find_machine("IE8 - Win7")

machine.lock_machine(session, virtualbox.library.LockType.shared)
console = session.console
guest = console.guest

guestSesssion = guest.create_session("IEUser", "Passw0rd!", "", "s1")

igp = guestSesssion.process_create(
    "C:\\Windows\\notepad.exe", [], [], [], 20000)

print("status %s" % igp.status)
