# CANboat Setup (Authoritative Decoder)

This project treats CANboat as the authoritative NMEA 2000 decoder.

## Safety posture

- `COBALT_DECODER_BACKEND=canboat` is the default.
- `COBALT_DECODER_REQUIRED=true` is the default.
- Startup fails if the decoder is unavailable.
- `basic` decoder is blocked unless explicitly enabled with `COBALT_ALLOW_BASIC_DECODER_INSECURE=true`.

## Reproducible install on Raspberry Pi OS

From the project root:

```bash
sudo ./scripts/install_canboat.sh
```

Defaults:

- CANboat repo: `https://github.com/canboat/canboat.git`
- Pinned version: `v6.1.6`
- Install prefix: `/usr/local`
- Wrapper installed to: `/usr/local/bin/cobalt-canboat-decoder`

Install metadata is recorded to:

- `/usr/local/share/cobalt/canboat-install.txt`

## Decoder wrapper

Canonical runtime command:

```bash
/usr/local/bin/cobalt-canboat-decoder
```

Self-check:

```bash
/usr/local/bin/cobalt-canboat-decoder --self-check
```

Optional version assertion:

```bash
export COBALT_CANBOAT_EXPECTED_VERSION=v6.1.6
/usr/local/bin/cobalt-canboat-decoder --self-check
```

The wrapper treats **`v6.1.6` and `6.1.6`** as compatible with analyzer output that reports `6.1.6`.

## Runtime environment

Recommended service env:

```bash
COBALT_DECODER_BACKEND=canboat
COBALT_CANBOAT_COMMAND=/usr/local/bin/cobalt-canboat-decoder
COBALT_DECODER_REQUIRED=true
COBALT_ALLOW_BASIC_DECODER_INSECURE=false
```
