# Fly-Brain Drone

A small ESP32-S3 camera quadcopter steered by a simulated fruit fly brain (FlyWire connectome, Shiu et al. 2024 model) running on a laptop.

- **Plan, phases and tasks:** https://claude.ai/artifact/NuM1vron4UPJLkWDwymUnH
- **Parts with photos and links:** https://claude.ai/artifact/14MLLZMBsPiJeyRGL1XqSZ
- **Project context for Claude:** [CLAUDE.md](CLAUDE.md)

## Folders

| Folder | What goes there | Owner |
| --- | --- | --- |
| `brain/` | Brain model setup and the laptop control loop | Person A |
| `drone/` | ESP32-S3 firmware (PlatformIO) | Person B |
| `frame/` | 3D-print files | Person B |
| `docs/` | Parts, wiring, notes | Both |

## Working together

1. Pull before you start: `git pull`
2. Work on your part, then commit and push: `git add -A`, `git commit -m "what changed"`, `git push`
3. When a decision changes, update `CLAUDE.md` so both Claudes know.
