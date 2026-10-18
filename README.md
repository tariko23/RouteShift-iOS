🗺️ RouteShift lets you simulate a different location on your iPhone from your Mac. Pick a start and destination, and it can simulate the journey along real roads rather than instantly jumping between two points. This is useful for testing things like Maps, location-based apps and how simulated location behaves across iOS services such as Find My.



# 🗺️ RouteShift

### 🚗 Road-aware iOS location simulation for development & testing

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-macOS-lightgrey)
![iOS](https://img.shields.io/badge/iOS-17%2B-black)
![License](https://img.shields.io/badge/License-MIT-green)

RouteShift is a macOS Python GUI that turns two coordinates into a road-following, timed GPX journey and plays it on a physical iPhone using `pymobiledevice3`.

## ✨ Highlights

- 🛣️ **Real road routing** — Driving geometry provided by OSRM
- ⏱️ **Timed GPX journeys** — Configurable journey duration
- ⏳ **Scheduled departure** — Optional wait period before starting
- 📱 **Physical iPhone testing** — Uses Apple's developer location services
- 🚗 **Live journey progress** — Progress, ETA and activity logging
- 📌 **Destination hold** — Remains at the destination after arrival
- 🔄 **Restore real GPS** — Return to genuine device location in one click
- 🔐 **Privacy conscious** — No personal coordinates embedded in the repository

## Architecture

```text
Start + destination coordinates
            |
            v
      OSRM road routing
            |
            v
     Route resampling
            |
            v
      Timed GPX file
            |
            v
     pymobiledevice3
            |
            v
      Physical iPhone
```

## Requirements

- macOS
- Python 3.11+ recommended
- `pymobiledevice3`
- A physical iPhone paired/trusted with the Mac
- Developer Mode enabled on the iPhone
- Internet access while obtaining the OSRM road route

> iOS developer-service behavior can change between iOS and `pymobiledevice3` releases. RouteShift has no affiliation with Apple, OSRM, or the `pymobiledevice3` project.

## Installation

Clone the repository and install the dependency:

```bash
git clone https://github.com/YOUR-USERNAME/RouteShift-iOS.git
cd RouteShift-iOS
python3 -m pip install -r requirements.txt
```

Run RouteShift:

```bash
python3 src/routeshift.py
```

## iPhone setup

1. Connect and trust the iPhone on the Mac.
2. Enable **Developer Mode** on the iPhone.
3. Unlock the iPhone when initially establishing the developer connection.
4. Close other location-simulation tools before starting RouteShift.
5. Enter start/destination coordinates and choose **Test Start**, **Start Scheduled Journey**, or **Start Journey Now**.
6. Use **Stop + Restore Real GPS** when finished.

## How the journey works

RouteShift requests a driving route from OSRM, resamples that road geometry, assigns timestamps across the requested duration, writes a GPX 1.1 track, and launches `pymobiledevice3 developer dvt simulate-location play`.

After GPX playback finishes, RouteShift holds the destination using the developer location service until the simulation is cleared.

### Choosing a realistic duration

The Activity log displays OSRM's estimated driving time. For realistic test movement, set **Journey duration** close to that estimate. Deliberately choosing a much shorter duration causes the simulated position to traverse the same route faster.

## Troubleshooting

### `CERTIFICATE_VERIFY_FAILED`

If you installed Python from python.org on macOS, run the bundled **Install Certificates.command** and restart RouteShift. Do not work around this by disabling TLS certificate verification.

### iPhone not detected / developer command fails

Confirm the iPhone is connected, trusted, initially unlocked, and Developer Mode is enabled. Current iOS releases may require `pymobiledevice3` to establish an iOS developer tunnel automatically.

### Location remains simulated after testing

Use **Stop + Restore Real GPS**. If RouteShift was force-closed, reconnect the phone and run:

```bash
pymobiledevice3 developer dvt simulate-location clear
```

## Privacy

RouteShift does not ship with or intentionally store personal start/destination coordinates. Coordinates are sent to the configured OSRM routing endpoint to obtain road geometry. The generated GPX is stored locally in `~/Downloads/RouteShift_route.gpx` and may contain the coordinates you entered. Delete that file after testing if it contains sensitive locations.

## Responsible use

RouteShift is intended for software development, QA, demonstrations, and testing on devices you control or are authorized to test. Do not use location simulation to misrepresent your location for fraud, evade platform rules, bypass access controls, or deceive other people.

## Project structure

```text
RouteShift-iOS/
├── src/
│   └── routeshift.py
├── docs/
│   └── DEVELOPMENT.md
├── examples/
│   └── README.md
├── .gitignore
├── CONTRIBUTING.md
├── LICENSE
├── requirements.txt
├── pyproject.toml
├── SECURITY.md
└── README.md
```

## Roadmap

- Optional wireless developer connection where supported
- Saved test presets without storing sensitive coordinates by default
- Route preview before playback
- Automatic use of routing-estimated duration
- Packaged macOS application
- Automated tests for GPX generation and route resampling

## License

MIT. See `LICENSE`.
