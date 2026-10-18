#!/usr/bin/env python3
"""RouteShift — macOS GUI for timed iOS location simulation using road-route GPX playback."""
from __future__ import annotations

import json
import math
import os
import queue
import shutil
import signal
import ssl
import subprocess
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import messagebox, ttk

APP_NAME = "RouteShift"
VERSION = "3.0.0"
OSRM_URL = "https://router.project-osrm.org"


class RouteShiftApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("980x840")
        self.minsize(850, 720)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.active_proc: subprocess.Popen[str] | None = None
        self.worker: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.route_file = Path.home() / "Downloads" / "RouteShift_route.gpx"
        self._build_ui()
        self.after(120, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        ttk.Label(self, text="RouteShift", font=("Helvetica", 28, "bold")).pack(pady=(18, 2))
        ttk.Label(self, text="Road-aware iOS location simulation for development and testing").pack(pady=(0, 14))

        form = ttk.LabelFrame(self, text="Journey")
        form.pack(fill="x", padx=24, pady=6)
        self.vars = {
            "start_lat": tk.StringVar(), "start_lon": tk.StringVar(),
            "end_lat": tk.StringVar(), "end_lon": tk.StringVar(),
            "stay": tk.StringVar(value="0"), "drive": tk.StringVar(value="10"),
            "points": tk.StringVar(value="120"),
        }
        rows = [
            ("Start latitude", "start_lat"), ("Start longitude", "start_lon"),
            ("Destination latitude", "end_lat"), ("Destination longitude", "end_lon"),
            ("Wait at start (minutes)", "stay"), ("Journey duration (minutes)", "drive"),
            ("Route detail points", "points"),
        ]
        for row, (label, key) in enumerate(rows):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=6)
            ttk.Entry(form, textvariable=self.vars[key]).grid(row=row, column=1, sticky="ew", padx=10, pady=6)
        form.columnconfigure(1, weight=1)

        note = ("Requires a paired iPhone with Developer Mode enabled and pymobiledevice3 installed. "
                "RouteShift requests road geometry from the public OSRM demo service and creates a timed GPX track locally.")
        ttk.Label(self, text=note, wraplength=900, justify="left").pack(padx=30, pady=(8, 6))

        buttons = ttk.Frame(self); buttons.pack(pady=7)
        ttk.Button(buttons, text="Test Start", command=self.test_start).grid(row=0, column=0, padx=5)
        ttk.Button(buttons, text="Start Scheduled Journey", command=lambda: self.start_journey(False)).grid(row=0, column=1, padx=5)
        ttk.Button(buttons, text="Start Journey Now", command=lambda: self.start_journey(True)).grid(row=0, column=2, padx=5)
        ttk.Button(buttons, text="Stop + Restore Real GPS", command=self.stop_and_clear).grid(row=0, column=3, padx=5)

        self.status = tk.StringVar(value="Ready")
        self.detail = tk.StringVar(value="Enter start and destination coordinates, then choose an action.")
        ttk.Label(self, textvariable=self.status, font=("Helvetica", 15, "bold")).pack(pady=(10, 2))
        ttk.Label(self, textvariable=self.detail).pack(pady=(0, 5))
        self.progress = ttk.Progressbar(self, maximum=100, mode="determinate")
        self.progress.pack(fill="x", padx=28, pady=6)

        log_frame = ttk.LabelFrame(self, text="Activity log")
        log_frame.pack(fill="both", expand=True, padx=24, pady=(8, 18))
        self.log_box = tk.Text(log_frame, height=12, state="disabled", font=("Menlo", 10), wrap="word")
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=scroll.set)
        self.log_box.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _drain_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.log_box.config(state="normal")
                    self.log_box.insert("end", str(value) + "\n")
                    self.log_box.see("end")
                    self.log_box.config(state="disabled")
                elif kind == "status": self.status.set(str(value))
                elif kind == "detail": self.detail.set(str(value))
                elif kind == "progress": self.progress["value"] = float(value)
        except queue.Empty:
            pass
        self.after(120, self._drain_events)

    def log(self, message: str) -> None:
        self.events.put(("log", message))

    def pymobiledevice3(self) -> str:
        executable = shutil.which("pymobiledevice3")
        if not executable:
            raise RuntimeError("pymobiledevice3 was not found. Install it with: python3 -m pip install -U pymobiledevice3")
        return executable

    def coordinates(self) -> tuple[tuple[float, float], tuple[float, float]]:
        try:
            start = (float(self.vars["start_lat"].get()), float(self.vars["start_lon"].get()))
            end = (float(self.vars["end_lat"].get()), float(self.vars["end_lon"].get()))
        except ValueError as exc:
            raise RuntimeError("Enter valid numeric latitude/longitude values.") from exc
        for lat, lon in (start, end):
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise RuntimeError("Coordinates are outside valid latitude/longitude ranges.")
        return start, end

    def kill_active(self) -> None:
        proc = self.active_proc
        if proc and proc.poll() is None:
            try:
                proc.send_signal(signal.SIGINT); proc.wait(timeout=5)
            except Exception:
                try: proc.terminate(); proc.wait(timeout=3)
                except Exception:
                    try: proc.kill()
                    except Exception: pass
        self.active_proc = None

    def persistent_set(self, lat: float, lon: float) -> None:
        self.kill_active()
        cmd = [self.pymobiledevice3(), "developer", "dvt", "simulate-location", "set", "--", str(lat), str(lon)]
        self.log("$ " + " ".join(cmd))
        self.active_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        time.sleep(3)
        if self.active_proc.poll() is not None:
            output = self.active_proc.stdout.read() if self.active_proc.stdout else ""
            raise RuntimeError(output.strip() or "Location command exited unexpectedly.")

    def clear_location(self) -> None:
        self.kill_active()
        cmd = [self.pymobiledevice3(), "developer", "dvt", "simulate-location", "clear"]
        self.log("$ " + " ".join(cmd))
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Clear timed out. Reconnect/unlock the iPhone and try again.") from exc
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "Clear failed").strip())

    def test_start(self) -> None:
        def work() -> None:
            try:
                start, _ = self.coordinates()
                self.events.put(("status", "Connecting…"))
                self.persistent_set(*start)
                self.events.put(("status", "Start location active"))
                self.events.put(("detail", "Check your test app/Apple Maps. Use Stop to restore real GPS."))
            except Exception as exc:
                self.events.put(("status", "Error")); self.log("ERROR: " + str(exc))
        threading.Thread(target=work, daemon=True).start()

    def fetch_route(self, start: tuple[float, float], end: tuple[float, float]):
        url = (f"{OSRM_URL}/route/v1/driving/{start[1]},{start[0]};{end[1]},{end[0]}"
               "?overview=full&geometries=geojson&steps=false")
        self.log("Fetching road route from OSRM…")
        request = urllib.request.Request(url, headers={"User-Agent": f"RouteShift/{VERSION} (development tool)"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, ssl.SSLCertVerificationError):
                raise RuntimeError("TLS certificate verification failed. On python.org macOS Python, run 'Install Certificates.command', then retry.") from exc
            raise RuntimeError(f"Could not reach routing service: {exc.reason}") from exc
        if data.get("code") != "Ok" or not data.get("routes"):
            raise RuntimeError("OSRM did not return a driving route for these coordinates.")
        route = data["routes"][0]
        coords = [(lat, lon) for lon, lat in route["geometry"]["coordinates"]]
        return coords, float(route.get("distance", 0)), float(route.get("duration", 0))

    @staticmethod
    def distance(a, b) -> float:
        lat1, lon1 = map(math.radians, a); lat2, lon2 = map(math.radians, b)
        dlat, dlon = lat2-lat1, lon2-lon1
        h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))

    def resample(self, points, count: int):
        if len(points) < 2: return points
        segments = [self.distance(points[i], points[i+1]) for i in range(len(points)-1)]
        total = sum(segments)
        if total <= 0: return [points[0]] * count
        cumulative = [0.0]
        for d in segments: cumulative.append(cumulative[-1] + d)
        result, j = [], 0
        for k in range(count):
            target = total * k / (count - 1)
            while j < len(segments)-1 and cumulative[j+1] < target: j += 1
            ratio = (target-cumulative[j]) / max(segments[j], 1e-9)
            result.append((points[j][0] + (points[j+1][0]-points[j][0])*ratio,
                           points[j][1] + (points[j+1][1]-points[j][1])*ratio))
        return result

    def write_gpx(self, route, wait_minutes: float, drive_minutes: float) -> Path:
        now = datetime.now(timezone.utc) + timedelta(seconds=3)
        drive_start = now + timedelta(minutes=wait_minutes)
        timed = [(route[0][0], route[0][1], now)]
        if wait_minutes > 0: timed.append((route[0][0], route[0][1], drive_start))
        for i, (lat, lon) in enumerate(route):
            fraction = i / max(1, len(route)-1)
            timed.append((lat, lon, drive_start + timedelta(seconds=drive_minutes*60*fraction)))
        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<gpx version="1.1" creator="RouteShift" xmlns="http://www.topografix.com/GPX/1/1">',
                 '<trk><name>RouteShift Journey</name><trkseg>']
        for lat, lon, stamp in timed:
            lines.append(f'<trkpt lat="{lat:.8f}" lon="{lon:.8f}"><time>{stamp.isoformat().replace("+00:00", "Z")}</time></trkpt>')
        lines += ['</trkseg></trk></gpx>']
        self.route_file.write_text("\n".join(lines), encoding="utf-8")
        return self.route_file

    def start_journey(self, now: bool) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Journey running", "Stop the current journey before starting another."); return
        try:
            start, end = self.coordinates()
            wait = 0.0 if now else float(self.vars["stay"].get())
            drive = float(self.vars["drive"].get()); points = int(self.vars["points"].get())
            if wait < 0 or drive <= 0 or not 20 <= points <= 500: raise ValueError
        except Exception:
            messagebox.showerror("Check settings", "Check coordinates. Wait must be 0+, duration must be positive, and route points must be 20–500."); return
        self.stop_event.clear()
        self.worker = threading.Thread(target=self.run_journey, args=(start, end, wait, drive, points), daemon=True)
        self.worker.start()

    def run_journey(self, start, end, wait, drive, points) -> None:
        try:
            self.events.put(("status", "Calculating road route…")); self.events.put(("progress", 0))
            raw, distance, estimate = self.fetch_route(start, end)
            route = self.resample(raw, points)
            gpx = self.write_gpx(route, wait, drive)
            self.log(f"Road route: {distance/1000:.2f} km • OSRM estimate: {estimate/60:.1f} min")
            self.log(f"Requested simulation duration: {drive:.1f} min")
            self.log(f"Generated GPX: {gpx}")
            self.kill_active()
            cmd = [self.pymobiledevice3(), "developer", "dvt", "simulate-location", "play", str(gpx)]
            self.log("$ " + " ".join(cmd))
            self.active_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            started, total = time.time(), (wait + drive) * 60
            while True:
                if self.stop_event.is_set(): return
                rc = self.active_proc.poll(); elapsed = time.time() - started
                if rc is not None:
                    output = self.active_proc.stdout.read() if self.active_proc.stdout else ""
                    if rc != 0: raise RuntimeError(output.strip() or f"GPX playback exited with code {rc}")
                    break
                self.events.put(("progress", min(100, elapsed/max(total, 1)*100)))
                if elapsed < wait*60:
                    remaining = wait*60-elapsed
                    self.events.put(("status", "Waiting at start")); self.events.put(("detail", f"Departure in {int(remaining//60):02d}:{int(remaining%60):02d}"))
                else:
                    travelled = elapsed-wait*60; remaining = max(0, drive*60-travelled)
                    percent = min(100, int(travelled/(drive*60)*100))
                    self.events.put(("status", "Journey in progress")); self.events.put(("detail", f"ETA {int(remaining//60):02d}:{int(remaining%60):02d} • {percent}%"))
                time.sleep(0.5)
            self.events.put(("status", "Arrived")); self.events.put(("detail", "Destination is being held until Stop + Restore Real GPS.")); self.events.put(("progress", 100))
            self.persistent_set(*end)
            self.log("Journey complete. Holding destination location.")
        except Exception as exc:
            self.events.put(("status", "Error")); self.events.put(("detail", "See Activity log.")); self.log("ERROR: " + str(exc))

    def stop_and_clear(self) -> None:
        self.stop_event.set()
        def work() -> None:
            try:
                self.events.put(("status", "Stopping…")); self.clear_location()
                self.events.put(("status", "Real GPS restored")); self.events.put(("detail", "Location simulation cleared.")); self.events.put(("progress", 0))
                self.log("Simulation cleared.")
            except Exception as exc:
                self.events.put(("status", "Stop error")); self.log("ERROR clearing location: " + str(exc))
        threading.Thread(target=work, daemon=True).start()

    def on_close(self) -> None:
        if self.active_proc and self.active_proc.poll() is None:
            if not messagebox.askyesno("Close RouteShift?", "A simulated location is active. Close without restoring real GPS?"):
                return
            self.kill_active()
        self.destroy()


if __name__ == "__main__":
    RouteShiftApp().mainloop()
