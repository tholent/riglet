# Virtual Device Passthrough

Riglet bridges the gap between a remote radio and desktop applications by
exposing virtual devices on the client machine. This lets programs like
WSJT-X, fldigi, and similar software connect to the remote radio as though
it were locally attached.

Two independent passthrough mechanisms are documented here:

1. **Virtual serial port** — maps the radio's rigctld TCP port to a local
   serial device so desktop applications can open `/dev/ttyV0` (or a Windows
   COM port) and issue standard CAT commands.

2. **Virtual audio device** — presents Riglet's audio WebSocket as a local
   audio input/output device so applications can record and play through the
   remote radio without any special network configuration.

---

## 1. Virtual Serial Port (rigctld TCP → local serial device)

### Overview

Riglet runs one `rigctld` daemon per radio on the Raspberry Pi, each
listening on a dedicated TCP port (default 4532, incremented for additional
radios). The `socat` utility on the client machine creates a pair of linked
pseudo-terminals and bridges one end to that TCP port.

```
Desktop app (WSJT-X, fldigi, ...)
  |
  v  opens /dev/pts/N  (or COM5 on Windows)
socat PTY ↔ TCP
  |
  v  TCP connection to Pi port 4532
rigctld (on Pi)
  |
  v  USB serial CAT
Radio hardware
```

### Prerequisites

- `socat` installed on the client machine (`apt install socat`, `brew install socat`, or equivalent).
- The Raspberry Pi is reachable at a known hostname or IP (e.g. `riglet.local` via mDNS).
- The radio's rigctld port is accessible (default: TCP 4532).

### Setup on Linux / macOS

1. Start the virtual serial bridge in a terminal (or as a background service):

   ```bash
   socat \
     PTY,link=/tmp/riglet-radio1,rawer,waitslave \
     TCP:riglet.local:4532,retry,interval=2
   ```

   - `PTY,link=/tmp/riglet-radio1` — creates a pseudo-terminal and places a
     symlink at `/tmp/riglet-radio1` pointing to the actual `/dev/pts/N` node.
   - `rawer` — disables all PTY line discipline processing (required for
     binary CAT protocols).
   - `waitslave` — waits for the application to open the slave end before
     forwarding data.
   - `TCP:riglet.local:4532` — connects to rigctld on the Pi.
   - `retry,interval=2` — automatically reconnects if the Pi is restarted.

2. Configure your desktop application to use `/tmp/riglet-radio1` as its
   CAT/Hamlib serial port. Set the baud rate to match the radio's configured
   baud rate (default 19200; irrelevant for TCP, but applications may require
   it to be set).

3. For a second radio (rigctld on port 4533):

   ```bash
   socat \
     PTY,link=/tmp/riglet-radio2,rawer,waitslave \
     TCP:riglet.local:4533,retry,interval=2
   ```

### Setup on Windows

Windows does not have a native `socat`. Options:

**Option A — WSL2 with socat**

1. Install socat in WSL2: `sudo apt install socat`.
2. Run the socat command from WSL2 as above.  Use a path under `/tmp`.
3. In Windows, the WSL2 serial device is not directly visible to Win32
   applications.  Use the `com0com` null-modem emulator to bridge the WSL2
   PTY into a COM pair (advanced; see com0com documentation).

**Option B — hub4com / com0com**

1. Install [com0com](https://com0com.sourceforge.net/) to create a null-modem
   COM port pair, e.g. COM5 ↔ COM6.
2. Run [hub4com](https://sourceforge.net/projects/com0com/files/hub4com/) to
   bridge COM5 to the rigctld TCP port:

   ```
   hub4com --route=All:All \
     --create-filter=escparse,,EscapeChar=0 \
     \\.\COM5 \
     --use-driver=tcp riglet.local:4532
   ```

3. Point your desktop application at COM6.

**Option C — Windows `socat` port**

Precompiled socat binaries for Windows are available from third-party sources.
Search for "socat windows binary".  Once installed, the Linux commands above
work unchanged at a PowerShell or cmd prompt, substituting a Windows COM port
for the PTY:

```
socat COM5,raw,b19200 TCP:riglet.local:4532,retry
```

### Running as a systemd service (Linux client)

To start the bridge automatically when the client machine boots, create a
user service:

```ini
# ~/.config/systemd/user/riglet-vserial-radio1.service
[Unit]
Description=Riglet virtual serial port for radio1
After=network.target

[Service]
ExecStart=socat PTY,link=%h/riglet-radio1,rawer,waitslave TCP:riglet.local:4532,retry,interval=2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Enable and start:

```bash
systemctl --user daemon-reload
systemctl --user enable --now riglet-vserial-radio1.service
```

### Connecting WSJT-X

1. Open WSJT-X → File → Settings → Radio.
2. Set **Rig** to the Hamlib model matching your radio (e.g. IC-706MkIIG = 3009).
3. Set **Serial Port** to `/tmp/riglet-radio1` (Linux/macOS) or the COM port
   (Windows).
4. Set **Baud Rate** to 19200 (or whatever the radio uses).
5. Set **PTT Method** to CAT (or whichever PTT method you configured in Riglet).
6. Click **Test CAT** — WSJT-X should report the current frequency.

### Connecting fldigi

1. Open fldigi → Configure → Rig Control → Hamlib.
2. Select the Hamlib model for your radio.
3. Set **Device** to `/tmp/riglet-radio1`.
4. Set the baud rate and RTS/DTR options to match your radio.
5. Check **Initialize Rig Control** and click **Initialize**.

---

## 2. Virtual Audio Device (PipeWire/JACK ↔ Riglet Audio WebSocket)

### Overview

Riglet streams audio over a binary WebSocket as raw PCM (s16le, mono, 16 kHz).
A client-side bridge utility presents this stream as a standard audio device,
allowing desktop apps to record (RX audio from the radio) and play back (TX
audio to the radio) through the remote hardware.

```
Desktop app (WSJT-X, fldigi, ...)
  |
  v  ALSA / PulseAudio / PipeWire device
Audio bridge daemon (client machine)
  |
  v  WebSocket ws://riglet.local:8080/api/radio/{id}/ws/audio
FastAPI backend (Pi)
  |
  v  PipeWire capture/playback
Radio USB audio interface
```

### Using PipeWire with virtual sinks/sources (Linux)

PipeWire's `pw-loopback` module creates virtual loopback devices that can be
bridged to the WebSocket.

#### Prerequisites

- PipeWire installed and running on the client: `pipewire`, `pipewire-pulse`,
  `wireplumber`.
- `websocat` or a custom bridge script for the WebSocket side.
- `ffmpeg` (optional) for format conversion if sample rates differ.

#### Approach: websocat + ffmpeg + PipeWire loopback

This approach uses `websocat` to forward PCM between the WebSocket and a
FIFO, and `ffmpeg` to feed that FIFO into a PipeWire virtual device.

1. Create a PipeWire loopback sink (appears as a playback device to apps):

   ```bash
   pactl load-module module-null-sink \
     sink_name=riglet_rx \
     sink_properties=device.description="Riglet\ RX\ (radio1)"
   ```

2. Start the RX bridge (WebSocket → PipeWire):

   ```bash
   # Receive PCM from Riglet and play into the PipeWire loopback sink
   websocat -b ws://riglet.local:8080/api/radio/radio1/ws/audio - |
     ffmpeg -f s16le -ar 16000 -ac 1 -i pipe:0 \
            -f pulse -ar 16000 -ac 1 riglet_rx
   ```

3. Configure your application to record from the **monitor** of `riglet_rx`
   (this is the loopback source — what the sink plays back).

4. Create a virtual source for TX (application → WebSocket):

   ```bash
   pactl load-module module-null-sink \
     sink_name=riglet_tx \
     sink_properties=device.description="Riglet\ TX\ (radio1)"
   ```

5. Start the TX bridge (PipeWire → WebSocket):

   ```bash
   # Capture from the riglet_tx monitor and forward to Riglet
   ffmpeg -f pulse -i riglet_tx.monitor \
          -ar 16000 -ac 1 -f s16le pipe:1 |
     websocat -b - ws://riglet.local:8080/api/radio/radio1/ws/audio
   ```

6. Configure your application to play (TX) to `riglet_tx`.

> **Note**: TX audio sent while PTT is not active is silently dropped by the
> Riglet backend.  Use Riglet's PTT control to key the radio before starting
> a transmission.

#### Installing websocat

```bash
# Debian/Ubuntu
apt install websocat

# macOS via Homebrew
brew install websocat

# Or download a binary from https://github.com/vi/websocat/releases
```

### Using JACK (Linux/macOS)

For lower latency or DAW integration, JACK can be used in place of
PipeWire/PulseAudio.  The principle is the same: create JACK ports bridged to
the audio WebSocket via a small helper script.

A minimal Python bridge using `websockets` and `sounddevice`:

```python
#!/usr/bin/env python3
"""
riglet-audio-bridge.py -- Bridge Riglet audio WebSocket to a local JACK/ALSA device.

Usage:
  python3 riglet-audio-bridge.py --host riglet.local --radio radio1 \
      --rx-device default --tx-device default
"""
import argparse
import asyncio
import struct
import numpy as np
import sounddevice as sd
import websockets

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 320  # 20 ms at 16 kHz

async def run(host: str, radio: str, rx_device: str, tx_device: str) -> None:
    url = f"ws://{host}:8080/api/radio/{radio}/ws/audio"
    async with websockets.connect(url) as ws:
        print(f"Connected to {url}")

        # RX: receive PCM from server, play locally
        rx_stream = sd.OutputStream(
            device=rx_device,
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='int16',
        )
        rx_stream.start()

        # TX: capture from mic, send to server
        tx_queue: asyncio.Queue[bytes] = asyncio.Queue()

        def tx_callback(indata: np.ndarray, frames: int, time, status) -> None:
            asyncio.get_event_loop().call_soon_threadsafe(
                tx_queue.put_nowait, indata.tobytes()
            )

        tx_stream = sd.InputStream(
            device=tx_device,
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='int16',
            blocksize=CHUNK_SAMPLES,
            callback=tx_callback,
        )
        tx_stream.start()

        async def recv_loop() -> None:
            async for msg in ws:
                if isinstance(msg, bytes):
                    samples = np.frombuffer(msg, dtype='int16')
                    rx_stream.write(samples)

        async def send_loop() -> None:
            while True:
                data = await tx_queue.get()
                await ws.send(data)

        await asyncio.gather(recv_loop(), send_loop())

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='riglet.local')
    ap.add_argument('--radio', default='radio1')
    ap.add_argument('--rx-device', default='default')
    ap.add_argument('--tx-device', default='default')
    args = ap.parse_args()
    asyncio.run(run(args.host, args.radio, args.rx_device, args.tx_device))
```

Install dependencies:

```bash
pip install websockets sounddevice numpy
```

### macOS (BlackHole / Soundflower)

On macOS, virtual audio devices can be created with
[BlackHole](https://github.com/ExistentialAudio/BlackHole) (free) or the
commercial Loopback app.

1. Install BlackHole (2ch version is sufficient).
2. Use the Python bridge script above with `--rx-device BlackHole\ 2ch`
   and `--tx-device BlackHole\ 2ch`.
3. In your desktop application, select **BlackHole 2ch** as the audio input
   and output device.

---

## Troubleshooting

### No audio received from the WebSocket

- Check that Riglet's audio WebSocket is active: open the Riglet UI and verify
  the radio is online with audio enabled.
- Verify network connectivity: `curl -v http://riglet.local:8080/api/status`
- Check that the radio's audio source is correctly mapped in the Riglet setup
  wizard.

### socat disconnects repeatedly

- Confirm rigctld is running on the Pi: `systemctl status rigctld@radio1`
- Increase retry interval: `socat ... TCP:riglet.local:4532,retry,interval=5`
- Check firewall rules if Pi is behind a router.

### WSJT-X reports "Rig not responding"

- Verify the Hamlib model number matches the radio.  Check the
  [Hamlib supported radios list](https://hamlib.github.io/Hamlib/index.html).
- Ensure the baud rate matches the radio's CAT settings.
- Try the **Test CAT** button in Riglet's setup wizard to verify basic CAT
  communication works end-to-end.

### Audio latency is too high

- The raw PCM format (s16le, 16 kHz, 20 ms chunks) is designed for low
  latency.  If you observe high latency, check for buffer bloat in your
  PipeWire/ALSA configuration.
- Reduce the PipeWire quantum: add
  `pulse.min.req = 128/16000` to `/etc/pipewire/pipewire.conf.d/latency.conf`.
- If LAN latency is the bottleneck, ensure the Riglet Pi and the client
  machine are on the same subnet without routing hops.
