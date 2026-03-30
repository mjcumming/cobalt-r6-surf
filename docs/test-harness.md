# Local CAN Test Harness (No Boat Required)

This harness uses Linux `vcan` and `can-utils` to simulate bus traffic offline.

## Prerequisites

Install `can-utils`:

```bash
sudo apt-get update
sudo apt-get install -y can-utils
```

## 1. Create virtual CAN interface

```bash
sudo ./scripts/setup_vcan.sh vcan0
```

## 2. Run platform against `vcan0`

In one terminal:

```bash
. .venv/bin/activate
export COBALT_CAN_INTERFACE=vcan0
export COBALT_DECODER_BACKEND=basic
export COBALT_ALLOW_BASIC_DECODER_INSECURE=true
cobalt-boat-api
```

Open debug console:

- `http://127.0.0.1/debug`

## 3. Generate synthetic traffic

In another terminal:

```bash
./scripts/generate_vcan_traffic.sh vcan0 200
```

You should see catalog/events/log updates in `/debug`.

## 4. Replay captured candump logs

```bash
./scripts/replay_candump.sh vcan0 ./path/to/candump.log
```

## Notes

- This harness is for local testing only.
- Never run traffic generators (`cangen`, `cansend`) on the real boat NMEA bus.
- For production, set decoder back to CANboat and disable insecure basic mode.
