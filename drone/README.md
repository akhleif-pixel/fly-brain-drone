# Drone firmware

ESP32-S3 firmware built with VS Code + PlatformIO. Start from Espressif's ESP-Drone (Crazyflie-based) and remap pins to `docs/wiring.md`.

## platformio.ini must enable PSRAM

```ini
[env:esp32s3cam]
platform = espressif32
board = esp32-s3-devkitc-1
framework = arduino
board_build.arduino.memory_type = qio_opi
board_build.flash_size = 16MB
build_flags = -DBOARD_HAS_PSRAM
monitor_speed = 115200
```

## Bring-up tests, one at a time

1. MPU6050 roll/pitch over serial
2. One motor at a time, slow PWM ramp, **props off** (use a spare 716 motor first)
3. Camera MJPEG stream over WiFi, 160×120 or QVGA, ESP32 as access point
4. Receive UDP commands (throttle, roll, pitch, yaw) from the laptop

A first draft of these four tests exists in the Tinkered project "WiFi ESP32-S3 Drone Quadrotor"; its compile check failed on Tinkered's side, so build it here.
