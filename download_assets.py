"""Public assets used by the single French openWakeWord training pipeline."""
from __future__ import annotations

import hashlib
import json
import subprocess
import wave
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
VOICE_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/fr/fr_FR"
VOICES = {
    "siwis": ("siwis/medium", "fr_FR-siwis-medium"),
    "upmc": ("upmc/medium", "fr_FR-upmc-medium"),
    "tom": ("tom/medium", "fr_FR-tom-medium"),
}
DEFAULT_VOICES = ("siwis", "upmc", "tom")
VOICE_SHA256 = {
    "siwis": "641d1ab097da2b81128c076810edb052b385decc8be3381814802a64a73baf99",
    "upmc": "9abb3800c199148897a9ed64e100d224f3de83579f100044174ad19418f1786f",
    "tom": "bf65074ccdeeeeaa832e75edb1c0a513c01c9a972bdf085ff8a6e71ea234fd41",
}
FEATURE_BASE = "https://huggingface.co/datasets/davidscripka/openwakeword_features/resolve/main"
AUDIOSET_REVISION = "0c609e8302cf139307f639c57652032af0a88041"
AUDIOSET_SHA256 = "b433e7bcf3bbdfb0488791fceae1eb7100711d13093d22e2253f15d2dcabc084"
AUDIOSET_SIZE = 687636067


def download(url: str, target: Path, minimum_bytes: int) -> None:
    """Resume a requested download and publish only a complete file."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and target.stat().st_size >= minimum_bytes:
        return
    partial = Path(str(target) + ".part")
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    with requests.get(url, headers=headers, stream=True, timeout=(20, 120)) as response:
        response.raise_for_status()
        if offset and response.status_code == 206:
            content_range = response.headers.get("Content-Range", "")
            if not content_range.startswith(f"bytes {offset}-"):
                raise RuntimeError(f"Reprise HTTP incohérente pour {target}: {content_range}")
            mode = "ab"
        else:
            offset = 0
            mode = "wb"
        total = int(response.headers.get("Content-Length", 0)) + offset
        with partial.open(mode) as stream:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    stream.write(chunk)
                    if stream.tell() // (256 * 1024 * 1024) != (
                        stream.tell() - len(chunk)) // (256 * 1024 * 1024):
                        print(f"{target.name}: {stream.tell() / 1024**3:.2f} Gio", flush=True)
    size = partial.stat().st_size
    if size < minimum_bytes or (total and size != total):
        raise RuntimeError(f"Téléchargement incomplet : {target} ({size} octets)")
    partial.replace(target)
    print(f"Téléchargé : {target} ({size / 1024**2:.1f} Mio)", flush=True)


def voice(name: str) -> None:
    directory, basename = VOICES[name]
    target = HERE / "data" / "voices" / f"{basename}.onnx"
    download(f"{VOICE_BASE}/{directory}/{basename}.onnx?download=true", target, 1024 * 1024)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if digest != VOICE_SHA256[name]:
        raise ValueError(f"SHA-256 de voix Piper inattendu : {target} ({digest})")
    config = Path(str(target) + ".json")
    download(f"{VOICE_BASE}/{directory}/{basename}.onnx.json?download=true", config, 100)
    metadata = json.loads(config.read_text(encoding="utf-8"))
    if not metadata.get("espeak", {}).get("voice", "").lower().startswith("fr"):
        raise ValueError(f"Voix non française : {config}")
    download(f"{VOICE_BASE}/{directory}/MODEL_CARD?download=true",
             HERE / "data" / "voices" / f"{basename}.MODEL_CARD", 50)


def features() -> None:
    folder = HERE / "data" / "features"
    for filename, minimum in (
        ("openwakeword_features_ACAV100M_2000_hrs_16bit.npy", 16 * 1024**3),
        ("validation_set_features.npy", 100 * 1024**2),
    ):
        download(f"{FEATURE_BASE}/{filename}?download=true",
                 folder / filename, minimum)


def rir() -> None:
    """Download the 16 kHz MIT room responses referenced by the official notebook."""
    folder = HERE / "data" / "rir"
    cached = list(folder.glob("*.wav"))
    if len(cached) == 270 and all(path.stat().st_size > 100 for path in cached):
        print("Réponses de pièce prêtes : 270 WAV", flush=True)
        return
    api = ("https://huggingface.co/api/datasets/"
           "davidscripka/MIT_environmental_impulse_responses/"
           "tree/main/16khz?recursive=true&limit=1000")
    response = requests.get(api, timeout=(20, 60))
    response.raise_for_status()
    files = [entry for entry in response.json()
             if entry.get("type") == "file" and entry.get("path", "").endswith(".wav")]
    if not files:
        raise RuntimeError("Aucune réponse impulsionnelle WAV trouvée")
    for entry in files:
        source = entry["path"]
        target = HERE / "data" / "rir" / Path(source).name
        download("https://huggingface.co/datasets/"
                 "davidscripka/MIT_environmental_impulse_responses/"
                 f"resolve/main/{source}?download=true", target, 100)
    print(f"Réponses de pièce prêtes : {len(files)} WAV", flush=True)


def background() -> None:
    """Extract one pinned, 500-clip AudioSet shard to mono 16 kHz WAV files."""
    import pyarrow.parquet as pq

    directory = HERE / "data" / "background"
    existing = sorted(directory.glob("audioset-*.wav"))
    if len(existing) == 500:
        try:
            def valid(path: Path) -> bool:
                with wave.open(str(path), "rb") as stream:
                    return (stream.getframerate() == 16000
                            and stream.getnchannels() == 1
                            and stream.getsampwidth() == 2
                            and stream.getnframes() >= 16000)
            if all(valid(path) for path in existing):
                print("Fonds AudioSet prêts : 500 WAV", flush=True)
                return
        except (EOFError, wave.Error):
            pass
    cache = HERE / "data" / "cache" / "audioset-bal-train-00.parquet"
    url = ("https://huggingface.co/datasets/agkphysics/AudioSet/resolve/"
           f"{AUDIOSET_REVISION}/data/bal_train/00.parquet?download=true")
    download(url, cache, AUDIOSET_SIZE)
    if cache.stat().st_size != AUDIOSET_SIZE:
        raise RuntimeError(f"Taille AudioSet inattendue : {cache}")
    digest = hashlib.sha256()
    with cache.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != AUDIOSET_SHA256:
        raise RuntimeError(f"Empreinte AudioSet invalide : {cache}")

    parquet = pq.ParquetFile(cache)
    if parquet.metadata.num_rows != 500:
        raise RuntimeError("Le fragment AudioSet attendu doit contenir 500 clips")
    directory = HERE / "data" / "background"
    directory.mkdir(parents=True, exist_ok=True)
    index = 0
    for batch in parquet.iter_batches(batch_size=8, columns=["audio"]):
        for row in batch.to_pylist():
            target = directory / f"audioset-{index:04d}.wav"
            if target.is_file():
                try:
                    with wave.open(str(target), "rb") as stream:
                        valid = (stream.getframerate() == 16000 and
                                 stream.getnchannels() == 1 and
                                 stream.getsampwidth() == 2 and
                                 stream.getnframes() >= 16000)
                    if valid:
                        index += 1
                        continue
                except (EOFError, wave.Error):
                    pass
            temporary = target.with_suffix(".part.wav")
            try:
                audio = row["audio"]["bytes"]
                if not audio:
                    raise RuntimeError(f"Clip AudioSet vide : {index}")
                subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                     "-y", "-f", "flac", "-i", "pipe:0", "-ac", "1", "-ar",
                     "16000", "-c:a", "pcm_s16le", str(temporary)],
                    input=audio, check=True, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE)
                with wave.open(str(temporary), "rb") as stream:
                    if stream.getnframes() < 16000:
                        raise RuntimeError(f"Clip AudioSet trop court : {index}")
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            index += 1
            if index % 50 == 0:
                print(f"Fonds AudioSet : {index}/500", flush=True)
    print(f"Fonds AudioSet prêts : {index} WAV dans {directory}", flush=True)
    cache.unlink(missing_ok=True)


def prepare() -> None:
    print("Voix françaises Piper...", flush=True)
    for name in DEFAULT_VOICES:
        voice(name)
    print("Réponses de pièce MIT...", flush=True)
    rir()
    print("Fonds sonores AudioSet...", flush=True)
    background()
    print("Caractéristiques négatives openWakeWord...", flush=True)
    features()
    print("Données prêtes", flush=True)
