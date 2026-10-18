# Development notes

## Data flow

1. Validate start and destination latitude/longitude.
2. Request driving geometry from the OSRM route endpoint.
3. Resample geometry by cumulative distance.
4. Generate timestamped GPX track points.
5. Start `pymobiledevice3` GPX playback as a persistent subprocess.
6. Report elapsed time and progress in the Tk event loop through a thread-safe queue.
7. Hold the final coordinate after playback completes.
8. Clear developer location simulation on request.

## Design choices

The UI runs on Tk's main thread. Network and device operations run in worker threads. UI updates are passed through a queue to avoid touching Tk widgets from background threads.

TLS verification remains enabled. Certificate errors are surfaced with remediation guidance rather than bypassed.

The public OSRM server is appropriate for light development/testing. A production or high-volume application should use an appropriate hosted or self-hosted routing service and respect its usage policy.
