---
name: Bug report
about: A pad misbehaves, a button is missing, or the daemon will not start
---

**What happens?**

**Setup**
- Raspberry Pi model and OS:
- Number of pads (`-n`):
- Daemon options (`systemctl cat snes-pad | grep ExecStart`):
- Original Nintendo pad or clone?

**Output of these commands**
```
pgrep -a snes_pad
systemctl status snes-pad
sudo systemctl stop snes-pad && sudo python3 software/snes_test.py --raw -n 1
```

**Wiring**
Photo of the hub and the cord colours you identified, if possible.
