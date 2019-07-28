
import virtualbox


vbox = virtualbox.VirtualBox()

for m in vbox.machines:
    print("Machine [%s]" % m.name)
