# Build / install helpers. Most people should just run bash install.sh
CC     ?= gcc
CFLAGS ?= -O2 -Wall -Wextra

all: snes_pad

snes_pad: software/snes_pad.c
	$(CC) $(CFLAGS) -o $@ $<

install: snes_pad
	sudo install -m 755 snes_pad /usr/local/bin/snes_pad

clean:
	rm -f snes_pad

diagrams:
	python3 hardware/diagrams/src/make_schematic.py docs/images/snes_pi_wiring.svg
	python3 hardware/diagrams/src/make_hub.py docs/images/snes_hub_perfboard.svg

.PHONY: all install clean diagrams
