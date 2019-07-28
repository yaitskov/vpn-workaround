import virtualbox
import time

vbox = virtualbox.VirtualBox()
session = virtualbox.Session()
machine = vbox.find_machine("IE8 - Win7")

machine.lock_machine(session, virtualbox.library.LockType.shared)
console = session.console
keyboard = console.keyboard


def typeScanCodes(k, codes, delay=0.2):
    for cc in codes:
        k.put_scancodes(cc)
        time.sleep(delay)
        # k.release_keys()


typeScanCodes(keyboard, [[0x11], [0x91]], 0.001)

# typeScanCodes(keyboard, [[0x2A]], 0.001) # press shift

typeScanCodes(keyboard, [[0x2A, 0x1E], [0x9E, 0xAA]], 0.001)
typeScanCodes(keyboard, [[0x2A, 0x30], [0xB0, 0xAA]], 0.001)

# typeScanCodes(keyboard, [[0xAA]], 0.001) # release shift
typeScanCodes(keyboard, [[0x1C], [0x9C]], 0.001)  # enter

typeScanCodes(keyboard, [[0x1E], [0x9E]], 0.001)
typeScanCodes(keyboard, [[0x30], [0xB0]], 0.001)
