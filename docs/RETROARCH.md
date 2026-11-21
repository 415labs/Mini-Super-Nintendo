# RetroArch / RetroPie setup

After `bash install.sh`, the daemon creates one virtual gamepad per pad: **"SNES GPIO Pad 1"** and **"SNES GPIO Pad 2"**. They look like ordinary USB gamepads to RetroArch, EmulationStation and anything else that reads `/dev/input`.

## 1. Check that the daemon sees your buttons

```bash
sudo python3 software/snes_test.py --evdev -n 2
```

Press every button on each pad. Each one should light up on the first press. Use `-n 1` if only one pad is connected.

If a pad is missing or the buttons misbehave, see [Troubleshooting](TROUBLESHOOTING.md).

## 2. RetroPie / EmulationStation

On the EmulationStation screen, press a button on the pad when asked and run the input configuration. This lets you navigate the menus with the pad. RetroPie then applies the mapping to its emulators.

## 3. RetroArch

1. Open **Settings → Input → Port 1 Controls**.
2. Set **Device Index** to **SNES GPIO Pad 1**.
3. Choose **Set All Controls** and press each button when prompted.
4. For a second pad, repeat with **Port 2 Controls** and **SNES GPIO Pad 2**.

The D-pad is reported as the X and Y axes. The face buttons map to the standard gamepad buttons (B, Y, A, X, L, R, Select, Start).

## 4. Settings that cut latency

| Setting | Where | Value |
|---|---|---|
| Poll Type Behavior | Settings → Input | **Late** (reads the pad as late as possible in each frame) |
| Run-Ahead | Settings → Latency | 1 frame, if the game runs full speed with it |
| Frame Delay | Settings → Latency | Try 4 to 8 ms, if your Pi keeps up |

Run-ahead and frame delay both depend on how fast the emulator core runs on your Pi, so test each game. Poll Type Behavior = Late is safe for everything.

## 5. Where the rest of the latency lives

This adapter adds roughly 0.1 to 0.7 ms between the pad and RetroArch ([details](LATENCY.md)). The display, the emulator frame time and the video output setup usually cost far more. A display in game mode helps most.
