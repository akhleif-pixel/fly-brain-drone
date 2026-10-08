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

**Ayham** works with Claude. **Ahmed** works in KiCad 10 on the PCB frame.

Ahmed, to get the files:
1. Accept the GitHub invite (email or github.com/notifications).
2. Install [GitHub Desktop](https://desktop.github.com), sign in, choose **File → Clone repository**, and pick `akhleif-pixel/fly-brain-drone`.
3. Open `pcb/kicad/fly-drone.kicad_pro` in KiCad. Start with [pcb/README.md](pcb/README.md).
4. When you've changed something: in GitHub Desktop, write a short summary, click **Commit**, then **Push origin**. Click **Fetch / Pull** before you start work to get Ayham's changes.

Both of you: pull before you start, and push when you're done. Don't edit the same file at the same time; Git will flag a conflict if you do.

When a decision changes, update `CLAUDE.md` so Claude knows.
