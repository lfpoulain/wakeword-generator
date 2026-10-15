"""Local orchestration around the official openWakeWord training script.

Synthetic French WAV generation uses Piper; classification, augmentation and ONNX
export are performed by the pinned upstream openwakeword/train.py.
"""
from __future__ import annotations

import argparse
import os
import math
import re
import subprocess
import sys
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "training.yml"
UPSTREAM = Path(os.environ.get("OPENWAKEWORD_SOURCE", "/opt/openWakeWord"))
OFFICIAL_TRAIN = UPSTREAM / "openwakeword" / "train.py"


def config_file(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else HERE / path


def load_config(path: Path) -> dict:
    import yaml

    if not path.is_file():
        raise FileNotFoundError(path)
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Configuration openWakeWord invalide")
    for key in ("target_phrase", "custom_negative_phrases"):
        if (not isinstance(config.get(key), list) or not config[key] or
                not all(isinstance(value, str) and value.strip()
                        for value in config[key])):
            raise ValueError(f"{key} doit être une liste de phrases non vides")
    name = config.get("model_name")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name):
        raise ValueError("model_name doit être un nom de fichier simple, en minuscules ASCII")
    return config


def relative_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else HERE / path


def clip_dir(config: dict, kind: str, split: str) -> Path:
    return relative_path(config["output_dir"]) / config["model_name"] / f"{kind}_{split}"


def model_path(config: dict) -> Path:
    return relative_path(config["output_dir"]) / f"{config['model_name']}.onnx"


def verify_voice_files(voices: list[Path]) -> None:
    import json

    if not voices:
        raise ValueError("Aucune voix française dans data/voices. Voir README.")
    for path in voices:
        metadata_path = Path(str(path) + ".json")
        if not path.is_file() or not metadata_path.is_file():
            raise FileNotFoundError(f"Voix Piper incomplète : {path} et son .onnx.json sont requis")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not metadata.get("espeak", {}).get("voice", "").lower().startswith("fr"):
            raise ValueError(f"Voix Piper non française : {path}")


def speaker_pool(speaker_counts: list[int], split: str) -> list[tuple[int, int]]:
    """Give each speaker one slot; reserve the last fifth of large voices for test."""
    if split not in ("train", "test"):
        raise ValueError(f"Ensemble inconnu : {split}")
    pool = []
    for voice_index, count in enumerate(speaker_counts):
        if count < 1:
            raise ValueError("Une voix Piper doit avoir au moins un locuteur")
        boundary = int(count * 0.8) if count >= 20 else count
        speaker_ids = (range(boundary, count) if split == "test" and count >= 20
                       else range(boundary))
        pool.extend((voice_index, speaker_id) for speaker_id in speaker_ids)
    return pool


def sample_plan(index: int, pool: list[tuple[int, int]],
                variation_count: int, phrase_count: int) -> tuple[int, int, int, int]:
    """Balance speakers, then rotate variations and phrases independently by round."""
    slot = index % len(pool)
    cycle = index // len(pool)
    voice_index, speaker_id = pool[slot]
    return (voice_index, speaker_id, (cycle + slot) % variation_count,
            (cycle + slot) % phrase_count)


def normalize_wav(path: Path) -> None:
    """Official augmentation requires mono 16 kHz PCM16 clips."""
    import math

    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import resample_poly

    rate, audio = wavfile.read(path)
    if rate == 16000 and audio.dtype == np.int16 and audio.ndim == 1:
        return
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    if audio.dtype != np.int16:
        if np.issubdtype(audio.dtype, np.integer):
            audio = audio.astype(np.float32) / max(abs(np.iinfo(audio.dtype).min), 1)
        else:
            audio = audio.astype(np.float32)
        audio = np.clip(audio * 32767, -32768, 32767)
    if rate != 16000:
        divisor = math.gcd(rate, 16000)
        audio = resample_poly(audio.astype(np.float32),
                              16000 // divisor, rate // divisor)
    temporary = path.with_suffix(".16k.wav")
    try:
        wavfile.write(temporary, 16000,
                      np.clip(audio, -32768, 32767).astype(np.int16))
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def fit_positive_duration(path: Path, limit_seconds: float = 1.75) -> None:
    """Keep the entire positive phrase inside upstream's minimum 2 s window."""
    with wave.open(str(path), "rb") as stream:
        duration = stream.getnframes() / stream.getframerate()
    if duration <= limit_seconds:
        return
    tempo = duration / limit_seconds
    filters = f"atempo={math.sqrt(tempo):.6f},atempo={math.sqrt(tempo):.6f}"
    accelerated = path.with_suffix(".fast.wav")
    try:
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
             "-i", str(path), "-filter:a", filters, "-ac", "1", "-c:a",
             "pcm_s16le", str(accelerated)],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with wave.open(str(accelerated), "rb") as stream:
            if stream.getnframes() / stream.getframerate() > 1.9:
                raise RuntimeError(f"Accélération audio insuffisante : {path}")
        accelerated.replace(path)
    finally:
        accelerated.unlink(missing_ok=True)


def synthesize_valid_wav(voice, phrase: str, target: Path,
                         speaker_ids: list[int], speed: float, noise: float,
                         noise_w: float, minimum_seconds: float) -> int:
    """Retry short Piper output at slower speeds, then within the same split."""
    from piper import SynthesisConfig

    for speaker_id in speaker_ids:
        for attempt in range(6):
            settings = SynthesisConfig(
                speaker_id=speaker_id,
                length_scale=speed + 0.2 * attempt,
                noise_scale=noise,
                noise_w_scale=noise_w,
            )
            with wave.open(str(target), "wb") as stream:
                voice.synthesize_wav(phrase, wav_file=stream, syn_config=settings)
            with wave.open(str(target), "rb") as stream:
                duration = stream.getnframes() / stream.getframerate()
            if duration >= minimum_seconds:
                return speaker_id
    raise RuntimeError(
        f"Clip Piper trop court après {len(speaker_ids) * 6} essais : "
        f"{phrase} ({target.name}, locuteurs {speaker_ids})")


def generate(config: dict, voices: list[Path]) -> None:
    from piper import PiperVoice

    verify_voice_files(voices)
    targets = [str(value).strip() for value in config["target_phrase"]]
    negatives = [str(value).strip() for value in config["custom_negative_phrases"]]
    if not negatives or any(not value for value in targets + negatives):
        raise ValueError("Renseigne des expressions négatives françaises dans training.yml")
    if set(x.casefold() for x in targets) & set(x.casefold() for x in negatives):
        raise ValueError("Une expression négative est identique au mot d'appel")
    import json

    manifest_path = relative_path(config["output_dir"]) / config["model_name"] / "generation.json"
    manifest = {"generation_version": 4, "speaker_schedule": "balanced_per_speaker",
                "target_phrase": targets, "negative_phrases": negatives,
                "voices": [{"file": path.name, "bytes": path.stat().st_size} for path in voices]}
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if manifest_path.is_file():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous != manifest:
            raise ValueError("La recette de génération, les phrases ou les voix ont changé ; "
                             "utilise un nouveau output_dir pour éviter de mélanger les clips")
    else:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    loaded = [PiperVoice.load(str(path)) for path in voices]
    speaker_counts = [int(voice.config.num_speakers) for voice in loaded]
    variations = (
        (0.78, 0.52, 0.6), (0.9, 0.667, 0.8), (1.0, 0.8, 0.9),
        (1.12, 0.667, 1.0), (1.28, 0.9, 0.7),
    )
    for split, count in (("train", int(config["n_samples"])),
                         ("test", int(config["n_samples_val"]))):
        pool = speaker_pool(speaker_counts, split)
        print(f"{split}: {len(pool)} locuteurs, {count} clips par catégorie", flush=True)
        for kind, phrases in (("positive", targets), ("negative", negatives)):
            folder = clip_dir(config, kind, split)
            folder.mkdir(parents=True, exist_ok=True)
            existing = sorted(p for p in folder.glob("*.wav") if p.stem.isdigit())
            existing_ids = {int(path.stem) for path in existing}
            if any(index >= count for index in existing_ids):
                raise ValueError(f"{folder} contient des indices hors limite ; "
                                 "utilise un output_dir vide pour ce réglage")
            for path in existing:
                normalize_wav(path)
            missing = [index for index in range(count) if index not in existing_ids]
            print(f"{kind}_{split}: {len(existing)}/{count}, génération de {len(missing)}", flush=True)
            for offset, index in enumerate(missing):
                voice_index, speaker_id, variation_index, phrase_index = sample_plan(
                    index, pool, len(variations), len(phrases))
                voice = loaded[voice_index]
                speed, noise, noise_w = variations[variation_index]
                phrase = phrases[phrase_index]
                target = folder / f"{index:08d}.wav"
                temporary = folder / f"{index:08d}.part.wav"
                try:
                    same_voice = [candidate for model, candidate in pool
                                  if model == voice_index]
                    position = same_voice.index(speaker_id)
                    candidates = [same_voice[(position + step) % len(same_voice)]
                                  for step in range(min(3, len(same_voice)))]
                    minimum_seconds = 0.55 if kind == "positive" else 0.2
                    actual_speaker = synthesize_valid_wav(
                        voice, phrase, temporary, candidates, speed, noise,
                        noise_w, minimum_seconds)
                    if actual_speaker != speaker_id:
                        print(f"  {kind}_{split} {index}: locuteur {speaker_id} "
                              f"remplacé par {actual_speaker} après clips trop courts",
                              flush=True)
                    normalize_wav(temporary)
                    if kind == "positive":
                        fit_positive_duration(temporary)
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
                if (offset + 1) % 100 == 0:
                    print(f"  {offset + 1}/{len(missing)}", flush=True)


def run_official(config_path: Path, stage: str, overwrite: bool = False) -> None:
    if not OFFICIAL_TRAIN.is_file():
        raise FileNotFoundError(f"Script officiel introuvable : {OFFICIAL_TRAIN}")
    config = load_config(config_path)
    if stage == "train" and model_path(config).exists():
        raise FileExistsError(f"Modèle déjà présent : {model_path(config)} ; choisissez un autre model_name")
    import json

    manifest_path = relative_path(config["output_dir"]) / config["model_name"] / "generation.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Provenance des clips absente : {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("generation_version") != 4 or
            manifest.get("speaker_schedule") != "balanced_per_speaker" or
            manifest["target_phrase"] != config["target_phrase"] or
            manifest["negative_phrases"] != config["custom_negative_phrases"]):
        raise ValueError("La recette a changé depuis la génération des clips")
    for kind in ("positive", "negative"):
        for split, expected in (("train", int(config["n_samples"])),
                                ("test", int(config["n_samples_val"]))):
            folder = clip_dir(config, kind, split)
            count = sum(1 for path in folder.glob("*.wav") if path.stem.isdigit())
            if count < expected:
                raise FileNotFoundError(f"Clips incomplets : {folder} ({count}/{expected})")
    if stage == "train":
        features = relative_path(config["output_dir"]) / config["model_name"]
        for name in ("positive_features_train.npy", "negative_features_train.npy",
                     "positive_features_test.npy", "negative_features_test.npy"):
            if not (features / name).is_file():
                raise FileNotFoundError(features / name)
        required = list(config["feature_data_files"].values())
        required.append(config["false_positive_validation_data_path"])
        for item in required:
            if not relative_path(item).is_file():
                raise FileNotFoundError(relative_path(item))
    else:
        for key in ("rir_paths", "background_paths"):
            for item in config[key]:
                path = relative_path(item)
                if not path.is_dir() or not any(path.glob("*.wav")):
                    raise FileNotFoundError(f"Corpus WAV manquant : {path}")
    flag = "--augment_clips" if stage == "augment" else "--train_model"
    command = [sys.executable, str(OFFICIAL_TRAIN),
               "--training_config", str(config_path), flag]
    if overwrite and stage == "augment":
        command.append("--overwrite")
    environment = os.environ.copy()
    if stage == "augment":
        environment["CUDA_VISIBLE_DEVICES"] = ""
    subprocess.run(command, cwd=HERE, env=environment, check=True)


def augmented_features_ready(config: dict) -> bool:
    """Resume the official pipeline only when all generated feature arrays are complete."""
    import numpy as np

    folder = relative_path(config["output_dir"]) / config["model_name"]
    for split, count in (("train", int(config["n_samples"])),
                         ("test", int(config["n_samples_val"]))):
        for kind in ("positive", "negative"):
            path = folder / f"{kind}_features_{split}.npy"
            if not path.is_file():
                return False
            try:
                features = np.load(path, mmap_mode="r")
                if (features.ndim != 3 or features.shape[0] < count or
                        features.shape[1] < 16 or features.shape[2] != 96):
                    return False
            except (OSError, ValueError):
                return False
    return True


def default_voices() -> list[Path]:
    from download_assets import DEFAULT_VOICES, VOICES

    return [HERE / "data" / "voices" / f"{VOICES[name][1]}.onnx"
            for name in DEFAULT_VOICES]


def build(config_path: Path, config: dict) -> None:
    from download_assets import prepare

    if model_path(config).exists():
        raise FileExistsError(f"Modèle déjà présent : {model_path(config)} ; choisissez un autre model_name")
    prepare()
    generate(config, default_voices())
    if augmented_features_ready(config):
        print("Caractéristiques augmentées déjà prêtes", flush=True)
    else:
        run_official(config_path, "augment", overwrite=True)
    run_official(config_path, "train")
    if not model_path(config).is_file():
        raise FileNotFoundError("Entraînement terminé sans fichier ONNX")
    print(f"Modèle prêt : {model_path(config)}", flush=True)


def doctor(config: dict) -> None:
    print(f"Python : {sys.version.split()[0]}")
    print(f"Script officiel : {OFFICIAL_TRAIN} ({'OK' if OFFICIAL_TRAIN.is_file() else 'absent'})")
    for split, count in (("train", config["n_samples"]), ("test", config["n_samples_val"])):
        for kind in ("positive", "negative"):
            folder = clip_dir(config, kind, split)
            print(f"{kind}_{split}: {len(list(folder.glob('*.wav')))}/{count}")
    for key in ("rir_paths", "background_paths"):
        for item in config[key]:
            path = relative_path(item)
            print(f"{key}: {path} ({len(list(path.glob('*.wav')))} WAV)")
    for item in (*config["feature_data_files"].values(),
                 config["false_positive_validation_data_path"]):
        path = relative_path(item)
        print(f"Features: {path} ({path.stat().st_size if path.is_file() else 'absent'})")
    path = model_path(config)
    print(f"Modèle: {path} ({'présent' if path.is_file() else 'absent'})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline local openWakeWord officiel")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    commands.add_parser("prepare")
    commands.add_parser("build")
    commands.add_parser("generate")
    augmented = commands.add_parser("augment")
    augmented.add_argument("--overwrite", action="store_true")
    commands.add_parser("train")
    args = parser.parse_args(argv)
    try:
        config_path = config_file(args.config)
        config = load_config(config_path)
        if args.command == "doctor":
            doctor(config)
        elif args.command == "prepare":
            from download_assets import prepare
            prepare()
        elif args.command == "build":
            build(config_path, config)
        elif args.command == "generate":
            generate(config, default_voices())
        elif args.command in ("augment", "train"):
            run_official(config_path, args.command,
                         getattr(args, "overwrite", False))
    except (FileNotFoundError, FileExistsError, ValueError, RuntimeError,
            subprocess.CalledProcessError, ImportError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())








