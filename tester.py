"""Fenêtre locale pour essayer un modèle openWakeWord au microphone."""
from __future__ import annotations

import argparse
import hashlib
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.request import urlopen

import numpy as np
import sounddevice as sd

from pipeline import config_file, load_config, model_path

HERE = Path(__file__).resolve().parent
FEATURES = HERE / "data" / "preprocess"
BASE_URL = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/"
FEATURE_HASHES = {
    "melspectrogram.onnx": "ba2b0e0f8b7b875369a2c89cb13360ff53bac436f2895cced9f479fa65eb176f",
    "embedding_model.onnx": "70d164290c1d095d1d4ee149bc5e00543250a7316b59f31d056cff7bd3075c1f",
}
SAMPLE_RATE = 16_000
FRAME_SAMPLES = 1_280
FRAME_BYTES = FRAME_SAMPLES * 2
IDLE_COLOR = "#64748b"
DETECTED_COLOR = "#22c55e"


def prepare_features() -> None:
    """Télécharge et vérifie les deux modèles de caractéristiques partagés."""
    FEATURES.mkdir(parents=True, exist_ok=True)
    for name, expected_hash in FEATURE_HASHES.items():
        target = FEATURES / name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected_hash:
            print(f"{name} : prêt")
            continue
        temporary = FEATURES / f"{name}.part"
        try:
            digest = hashlib.sha256()
            received = 0
            with urlopen(BASE_URL + name, timeout=60) as response, temporary.open("wb") as output:
                while chunk := response.read(64 * 1024):
                    received += len(chunk)
                    if received > 30_000_000:
                        raise ValueError(f"Fichier trop volumineux : {name}")
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest() != expected_hash:
                raise ValueError(f"Empreinte SHA-256 incorrecte : {name}")
            temporary.replace(target)
            print(f"{name} : installé")
        finally:
            temporary.unlink(missing_ok=True)


class Detector:
    def __init__(self, path: Path) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"Modèle absent : {path}")
        missing = [str(FEATURES / name) for name in FEATURE_HASHES
                   if not (FEATURES / name).is_file()]
        if missing:
            raise FileNotFoundError("Prétraitement absent : lancez tester.py --prepare")
        from openwakeword.model import Model

        self.model = Model(
            wakeword_models=[str(path)],
            inference_framework="onnx",
            melspec_model_path=str(FEATURES / "melspectrogram.onnx"),
            embedding_model_path=str(FEATURES / "embedding_model.onnx"),
        )
        self.key = next(iter(self.model.models))

    def reset(self) -> None:
        self.model.reset()

    def score(self, pcm: bytes) -> float:
        if len(pcm) != FRAME_BYTES:
            raise ValueError(f"Trame audio incorrecte : {len(pcm)} octets")
        return float(self.model.predict(np.frombuffer(pcm, dtype="<i2"))[self.key])


class WakeTester:
    def __init__(self, window: tk.Tk, detector: Detector, label: str) -> None:
        self.window = window
        self.detector = detector
        self.label = label
        self.window.title(f"Tester {label}")
        self.window.geometry("580x310")
        self.window.minsize(520, 300)
        self.window.configure(bg="#111827")
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=64)
        self.ui_queue: queue.SimpleQueue[tuple[int, str, object]] = queue.SimpleQueue()
        self.stop_event = threading.Event()
        self.audio_thread: threading.Thread | None = None
        self.stream: sd.RawInputStream | None = None
        self.running = False
        self.closed = False
        self.run_id = 0
        self.last_detection = 0.0
        self.highlight_until = 0.0
        self.detections = 0
        self.devices: dict[str, int] = {}
        self.microphone = tk.StringVar()
        self.threshold = tk.StringVar(value="0.5")
        self.status = tk.StringVar(value="Choisissez un micro, puis démarrez l'écoute.")
        self.result = tk.StringVar(value="Détections : 0")
        self.score_value = tk.StringVar(value="Score : 0,000")
        self._build_ui()
        self.refresh_devices()
        self.window.after(50, self._poll)

    def _build_ui(self) -> None:
        tk.Label(self.window, text="Test du mot d'appel", bg="#111827", fg="#e5e7eb",
                 font=("Segoe UI", 14, "bold")).pack(pady=(18, 0))
        self.word = tk.Label(self.window, text=self.label, bg="#111827", fg=IDLE_COLOR,
                             font=("Segoe UI", 40, "bold"))
        self.word.pack(pady=(4, 4))
        tk.Label(self.window, textvariable=self.score_value, bg="#111827", fg="#cbd5e1").pack()
        tk.Label(self.window, textvariable=self.result, bg="#111827", fg="#cbd5e1").pack()

        controls = tk.Frame(self.window, bg="#111827")
        controls.pack(fill="x", padx=22, pady=(15, 5))
        tk.Label(controls, text="Micro", bg="#111827", fg="#e5e7eb").grid(row=0, column=0)
        self.device_box = ttk.Combobox(controls, textvariable=self.microphone, state="readonly")
        self.device_box.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self.refresh_button = ttk.Button(controls, text="↻", width=3, command=self.refresh_devices)
        self.refresh_button.grid(row=0, column=2)
        tk.Label(controls, text="Seuil", bg="#111827", fg="#e5e7eb").grid(
            row=0, column=3, padx=(18, 5))
        self.threshold_entry = ttk.Entry(controls, textvariable=self.threshold, width=6)
        self.threshold_entry.grid(row=0, column=4)
        controls.columnconfigure(1, weight=1)

        buttons = tk.Frame(self.window, bg="#111827")
        buttons.pack(pady=(8, 4))
        self.start_button = ttk.Button(buttons, text="Démarrer", command=self.start)
        self.start_button.pack(side="left", padx=5)
        self.stop_button = ttk.Button(buttons, text="Arrêter", command=self.stop, state="disabled")
        self.stop_button.pack(side="left", padx=5)
        tk.Label(self.window, textvariable=self.status, bg="#111827", fg="#94a3b8",
                 wraplength=540).pack(padx=18, pady=(5, 0))

    def refresh_devices(self) -> None:
        try:
            inputs = [(index, device["name"]) for index, device in enumerate(sd.query_devices())
                      if device["max_input_channels"] > 0]
        except Exception as error:
            self.status.set(f"Impossible de lister les micros : {error}")
            self.start_button.configure(state="disabled")
            return
        self.devices = {f"{index} · {name}": index for index, name in inputs}
        self.device_box.configure(values=list(self.devices))
        default = sd.default.device[0]
        selection = next((label for label, index in self.devices.items() if index == default), None)
        if self.microphone.get() not in self.devices:
            self.microphone.set(selection or next(iter(self.devices), ""))
        self.start_button.configure(state="normal" if self.devices else "disabled")
        if not self.devices:
            self.status.set("Aucun microphone détecté.")

    def start(self) -> None:
        if self.running:
            return
        device = self.devices.get(self.microphone.get())
        if device is None:
            messagebox.showerror("Microphone", "Choisissez un microphone.")
            return
        try:
            threshold = float(self.threshold.get().replace(",", "."))
            if not 0 < threshold < 1:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Seuil", "Entrez un seuil entre 0 et 1, par exemple 0,5.")
            return
        self.audio_queue = queue.Queue(maxsize=64)
        self.stop_event.clear()
        self.run_id += 1
        try:
            sd.check_input_settings(device=device, samplerate=SAMPLE_RATE, channels=1, dtype="int16")
            self.stream = sd.RawInputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                                            blocksize=FRAME_SAMPLES, device=device,
                                            callback=self._audio_callback)
            self.stream.start()
        except Exception as error:
            self.stop_event.set()
            if self.stream is not None:
                self.stream.close()
                self.stream = None
            messagebox.showerror("Microphone", f"Impossible de démarrer ce micro : {error}")
            return
        self.running = True
        self.last_detection = 0.0
        self.highlight_until = 0.0
        self.detections = 0
        self.word.configure(fg=IDLE_COLOR)
        self.score_value.set("Score : 0,000")
        self.result.set("Détections : 0")
        self.audio_thread = threading.Thread(target=self._process_audio,
                                             args=(self.run_id, threshold), daemon=True)
        self.audio_thread.start()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.device_box.configure(state="disabled")
        self.refresh_button.configure(state="disabled")
        self.threshold_entry.configure(state="disabled")
        self.status.set(f"Écoute locale en cours. Dites « {self.label} ».")

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if self.stop_event.is_set():
            return
        if status:
            self.ui_queue.put((self.run_id, "status", f"Micro : {status}"))
        try:
            self.audio_queue.put_nowait(bytes(indata))
        except queue.Full:
            self.ui_queue.put((self.run_id, "error", "Traitement trop lent ; écoute arrêtée."))
            self.stop_event.set()

    def _process_audio(self, run_id: int, threshold: float) -> None:
        pending = bytearray()
        try:
            self.detector.reset()
            while not self.stop_event.is_set():
                try:
                    pending.extend(self.audio_queue.get(timeout=0.2))
                except queue.Empty:
                    continue
                while len(pending) >= FRAME_BYTES and not self.stop_event.is_set():
                    frame = bytes(pending[:FRAME_BYTES])
                    del pending[:FRAME_BYTES]
                    score = self.detector.score(frame)
                    now = time.monotonic()
                    detected = score >= threshold and now - self.last_detection >= 2.0
                    if detected:
                        self.last_detection = now
                    self.ui_queue.put((run_id, "score", (score, detected)))
        except Exception as error:
            self.ui_queue.put((run_id, "error", f"Détection interrompue : {error}"))

    def _poll(self) -> None:
        try:
            while True:
                run_id, kind, value = self.ui_queue.get_nowait()
                if run_id != self.run_id:
                    continue
                if kind == "score" and self.running:
                    score, detected = value
                    self.score_value.set(f"Score : {score:.3f}".replace(".", ","))
                    if detected:
                        self.detections += 1
                        self.result.set(f"Détections : {self.detections}")
                        self.word.configure(fg=DETECTED_COLOR)
                        self.highlight_until = time.monotonic() + 2.0
                elif kind == "error":
                    self.stop()
                    self.status.set(str(value))
                elif kind == "status" and self.running:
                    self.status.set(str(value))
        except queue.Empty:
            pass
        if self.highlight_until and time.monotonic() >= self.highlight_until:
            self.highlight_until = 0.0
            self.word.configure(fg=IDLE_COLOR)
        if not self.closed:
            self.window.after(50, self._poll)

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        self.stop_event.set()
        if self.stream is not None:
            try:
                self.stream.stop()
            except Exception:
                pass
            try:
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        if self.audio_thread is not None:
            self.audio_thread.join(timeout=2.0)
            self.audio_thread = None
        self.word.configure(fg=IDLE_COLOR)
        self.start_button.configure(state="normal" if self.devices else "disabled")
        self.stop_button.configure(state="disabled")
        self.device_box.configure(state="readonly")
        self.refresh_button.configure(state="normal")
        self.threshold_entry.configure(state="normal")
        self.status.set("Écoute arrêtée.")

    def close(self) -> None:
        self.stop()
        self.closed = True
        self.window.destroy()


def main() -> int:
    parser = argparse.ArgumentParser(description="Essayer un mot d'appel openWakeWord au microphone")
    parser.add_argument("--config", default="training.yml", help="Configuration du modèle")
    parser.add_argument("--model", help="Chemin ONNX à tester (par défaut : celui de la configuration)")
    parser.add_argument("--label", help="Texte affiché dans la fenêtre")
    parser.add_argument("--prepare", action="store_true", help="Télécharger les deux modèles de prétraitement")
    parser.add_argument("--check", action="store_true", help="Vérifier le modèle et les micros")
    args = parser.parse_args()
    try:
        if args.prepare:
            prepare_features()
            return 0
        config = load_config(config_file(args.config))
        source = Path(args.model) if args.model else model_path(config)
        if not source.is_absolute():
            source = HERE / source
        detector = Detector(source)
        label = args.label or config["model_name"].replace("_", " ").title()
        if args.check:
            inputs = [device for device in sd.query_devices() if device["max_input_channels"] > 0]
            print(f"Modèle prêt : {source}")
            print(f"Micros détectés : {len(inputs)}")
            return 0 if inputs else 1
        window = tk.Tk()
        WakeTester(window, detector, label)
        window.mainloop()
        return 0
    except Exception as error:
        print(f"Testeur indisponible : {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
