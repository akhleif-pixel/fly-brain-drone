# Wiring

Pin numbers follow the common ESP32-S3 CAM map. Checked on 2026-10-26 against the labels printed on our board (photo of the ESP32-S3 WROOM CAM board): every pin used below is on its headers.

Its two 20-pin rows, read with the antenna at the top (the front of the drone):

| Left row | 3V3, EN, 4, 5, 6, 7, 15, 16, 17, 18, 8, 3, 46, 9, 10, 11, 12, 13, 14, 5V |
| --- | --- |
| Right row | TX, RX, 1, 2, 42, 41, 40, 39, 38, 37, 36, 35, 0, 45, 48, 47, 21, 20, 19, GND |

GPIO 48 drives the board's RGB LED.

## Power

```
Battery (+) ──┬──► motor (+) ×4
              ├──► TPS63020 VIN ──► VOUT 3.3 V ──► ESP32 3V3 pin ──► MPU6050 VCC
              └──► 100 µF capacitor (+)
Battery (−) ──► common ground: MOSFET sources, TPS63020 GND, ESP32 GND, capacitor (−, striped side)
```

- Never put the battery on the 3V3 pin directly. Use the 3V3 pin, not 5V, from the buck-boost.
- Unplug the battery while USB is connected.

## Camera (OV2640, 24-pin DVP connector, fixed)

| Signal | GPIO |
| --- | --- |
| XCLK | 15 |
| SIOD / SIOC | 4 / 5 |
| D0–D7 | 11, 9, 8, 10, 12, 18, 17, 16 |
| VSYNC / HREF / PCLK | 6 / 7 / 13 |

Don't reuse these, the PSRAM pins (35–37), USB (19/20) or strapping pins (0, 3, 45, 46).

## MPU6050

| MPU6050 | ESP32-S3 |
| --- | --- |
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO 41 |
| SCL | GPIO 42 |
| INT | GPIO 40 |

## Motors (×4, each the same)

```
Battery (+) ──► motor (+)
motor (−)   ──► IRLB8721 drain
IRLB8721 source ──► GND
ESP32 PWM pin ──► IRLB8721 gate, with 10 kΩ from gate to GND
1N5819 across the motor: striped end to battery (+), other end to motor (−)
```

| Motor | Position | Spin | GPIO |
| --- | --- | --- | --- |
| M1 | front right | CCW | 21 |
| M2 | rear right | CW | 47 |
| M3 | rear left | CCW | 14 |
| M4 | front left | CW | 38 |

Diagonal motors spin the same way. PWM about 20 kHz, 8-bit.

## Driver board layout

The full hole-by-hole layout (16 × 14 perfboard), a 23-step build guide, the wiring diagram and the wire list are in the 3D model: `docs/drone-3d/index.html`, published at https://claude.ai/artifact/NjziEZUPGjHmvTMsy9SgBu. Holes are named [column row]: columns A–P, rows 1–14, read on the parts side with the front of the drone at the top.

- Ground bus: row 14, [P14] to [B14]. Battery plus: row 1 and column A.
- Battery: plus to [A13], minus to [E14], through a plug so you can disconnect it.
- Buck-boost: VIN from [P1], GND from [P14], EN bridged to VIN. Output to ESP32 J1 3V3 and J1 GND.
- MPU6050: VCC to J1 3V3, GND to J3 GND, SCL 42, SDA 41, INT 40 (soldered into the ESP32 holes from below).
