"""Local orchestration around the official openWakeWord training script.

Synthetic French WAV generation uses Piper; classification, augmentation and ONNX
export are performed by the pinned upstream openwakeword/train.py.
"""
from __future__ import annotations

import argparse
import multiprocessing
import os
import math
import re
import shutil
import subprocess
import sys
import time
import wave
from concurrent.futures import ProcessPoolExecutor
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


def work_root(config: dict) -> Path:
    """Où vivent clips et caractéristiques : WAKEWORD_WORK (un volume Docker) ou output_dir.

    À travers le dossier partagé entre Windows et Docker, ouvrir un fichier coûte environ
    10 ms : les 44 000 clips d'un mot passent bien plus vite dans un volume Docker.
    Le modèle ONNX, lui, arrive toujours dans output_dir.
    """
    work = os.environ.get("WAKEWORD_WORK")
    return Path(work) if work else relative_path(config["output_dir"])


def work_dir(config: dict) -> Path:
    return work_root(config) / config["model_name"]


def clip_dir(config: dict, kind: str, split: str) -> Path:
    return work_dir(config) / f"{kind}_{split}"


def model_path(config: dict) -> Path:
    return relative_path(config["output_dir"]) / f"{config['model_name']}.onnx"


def verify_voice_files(voices: list[Path]) -> None:
    import json

    if not voices:
        raise ValueError("Aucune voix française dans data/voices : lancez l’étape prepare")
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
    verify_voice_files(voices)
    targets = [str(value).strip() for value in config["target_phrase"]]
    negatives = [str(value).strip() for value in config["custom_negative_phrases"]]
    if not negatives or any(not value for value in targets + negatives):
        raise ValueError("Renseignez des expressions négatives françaises dans training.yml")
    if set(x.casefold() for x in targets) & set(x.casefold() for x in negatives):
        raise ValueError("Une expression négative est identique au mot d'appel")
    import json

    import_previous_work(config)
    manifest_path = work_dir(config) / "generation.json"
    manifest = {"generation_version": 4, "speaker_schedule": "balanced_per_speaker",
                "target_phrase": targets, "negative_phrases": negatives,
                "voices": [{"file": path.name, "bytes": path.stat().st_size} for path in voices]}
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if manifest_path.is_file():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        if previous != manifest:
            raise ValueError("La recette de génération, les phrases ou les voix ont changé ; "
                             "choisissez un autre model_name pour ne pas mélanger les clips")
    else:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    speaker_counts = [int(json.loads(Path(str(path) + ".json").read_text(encoding="utf-8"))
                          .get("num_speakers", 1)) for path in voices]
    variations = (
        (0.78, 0.52, 0.6), (0.9, 0.667, 0.8), (1.0, 0.8, 0.9),
        (1.12, 0.667, 1.0), (1.28, 0.9, 0.7),
    )
    workers, threads = generation_workers(config)
    print(f"Génération : {workers} processus × {threads} threads", flush=True)
    # « spawn » : chaque processus charge ses voix, sans hériter de l’état du parent
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(workers, mp_context=context, initializer=_load_voices,
                             initargs=([str(path) for path in voices], threads)) as executor:
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
                    raise ValueError(f"{folder} contient plus de clips que demandé ; "
                                     "choisissez un autre model_name pour ce réglage")
                for path in existing:
                    normalize_wav(path)
                missing = [index for index in range(count) if index not in existing_ids]
                print(f"{kind}_{split}: {len(existing)}/{count}, génération de {len(missing)}", flush=True)
                tasks = []
                for index in missing:
                    voice_index, speaker_id, variation_index, phrase_index = sample_plan(
                        index, pool, len(variations), len(phrases))
                    same_voice = [candidate for model, candidate in pool
                                  if model == voice_index]
                    position = same_voice.index(speaker_id)
                    candidates = [same_voice[(position + step) % len(same_voice)]
                                  for step in range(min(3, len(same_voice)))]
                    tasks.append((str(folder), kind, index, voice_index, candidates,
                                  variations[variation_index], phrases[phrase_index]))
                started = time.monotonic()
                for offset, (index, speaker_id, actual_speaker) in enumerate(
                        executor.map(_generate_clip, tasks, chunksize=8)):
                    if actual_speaker != speaker_id:
                        print(f"  {kind}_{split} {index}: locuteur {speaker_id} "
                              f"remplacé par {actual_speaker} après clips trop courts",
                              flush=True)
                    if (offset + 1) % 1000 == 0 or offset + 1 == len(tasks):
                        rate = (offset + 1) / max(time.monotonic() - started, 1e-6)
                        print(f"  {offset + 1}/{len(tasks)} ({rate:.0f} clips/s)", flush=True)


def generation_workers(config: dict) -> tuple[int, int]:
    """Processus et threads par processus pour Piper.

    Piper sur GPU est plus lent que sur processeur pour des phrases de deux mots (mesuré
    sur RTX 4090 : 48 clips/s en 8 processus, contre 183 sur 16 processus × 2 threads) :
    la génération reste donc sur le processeur, mais en parallèle.
    """
    cpus = os.cpu_count() or 1
    threads = int(config.get("generation_threads", 2))
    workers = int(config.get("generation_workers", 0)) or max(1, min(16, cpus // threads))
    return workers, threads


_VOICES: list = []


def _load_voices(paths: list[str], threads: int) -> None:
    """Dans chaque processus : les voix Piper, sur processeur, avec peu de threads."""
    import json

    import onnxruntime
    from piper import PiperVoice
    from piper.config import PiperConfig

    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    for path in paths:
        session = onnxruntime.InferenceSession(path, sess_options=options,
                                               providers=["CPUExecutionProvider"])
        config = PiperConfig.from_dict(json.loads(Path(path + ".json").read_text(encoding="utf-8")))
        _VOICES.append(PiperVoice(session=session, config=config))


def _generate_clip(task) -> tuple[int, int, int]:
    folder, kind, index, voice_index, candidates, variation, phrase = task
    speed, noise, noise_w = variation
    target = Path(folder) / f"{index:08d}.wav"
    temporary = Path(folder) / f"{index:08d}.part.wav"
    try:
        minimum_seconds = 0.55 if kind == "positive" else 0.2
        actual_speaker = synthesize_valid_wav(
            _VOICES[voice_index], phrase, temporary, candidates, speed, noise,
            noise_w, minimum_seconds)
        normalize_wav(temporary)
        if kind == "positive":
            fit_positive_duration(temporary)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return index, candidates[0], actual_speaker


def run_official(config_path: Path, stage: str, overwrite: bool = False) -> None:
    if not OFFICIAL_TRAIN.is_file():
        raise FileNotFoundError(f"Script officiel introuvable : {OFFICIAL_TRAIN}")
    config = load_config(config_path)
    if stage == "train" and model_path(config).exists():
        raise FileExistsError(f"Modèle déjà présent : {model_path(config)} ; choisissez un autre model_name")
    import json

    import_previous_work(config)
    manifest_path = work_dir(config) / "generation.json"
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
        features = work_dir(config)
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
    if os.environ.get("WAKEWORD_WORK"):
        # Le script officiel lit output_dir : il reçoit une copie de la recette qui pointe
        # vers le dossier de travail, et y écrit le modèle, recopié ensuite dans output_dir.
        import yaml

        derived = dict(config, output_dir=str(work_root(config)))
        config_path = work_dir(config) / "recette.yml"
        config_path.write_text(yaml.safe_dump(derived, allow_unicode=True), encoding="utf-8")
        (work_root(config) / f"{config['model_name']}.onnx").unlink(missing_ok=True)
    command = [sys.executable, str(OFFICIAL_TRAIN),
               "--training_config", str(config_path), flag]
    if overwrite and stage == "augment":
        command.append("--overwrite")
    environment = os.environ.copy()
    if stage == "augment":
        # Caractéristiques sur processeur, comme à l'usage. Essayé sur GPU (onnxruntime-gpu,
        # RTX 4090) : le modèle d'embedding y donne des valeurs différentes (0,66 d'écart
        # moyen pour une amplitude de 13), pour seulement 5 s gagnées sur 4 400 clips. Et le
        # PyTorch de l'image (1.13, CUDA 11.7) ne sait pas faire de FFT sur les RTX 40,
        # nécessaire aux altérations.
        environment["CUDA_VISIBLE_DEVICES"] = ""
    subprocess.run(command, cwd=HERE, env=environment, check=True)
    trained = work_root(config) / f"{config['model_name']}.onnx"
    if stage == "train" and trained != model_path(config) and trained.is_file():
        model_path(config).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(trained, model_path(config))


def import_previous_work(config: dict) -> None:
    """Reprend dans le volume un dossier output/<model_name> fait avant le volume."""
    previous = relative_path(config["output_dir"]) / config["model_name"]
    if work_dir(config) == previous or work_dir(config).exists() or not previous.is_dir():
        return
    print(f"Copie de {previous} dans le dossier de travail (une seule fois)", flush=True)
    shutil.copytree(previous, work_dir(config))


def export_clips(config: dict, count: int = 12) -> None:
    """Copie quelques clips de chaque dossier dans output/<model_name>-ecoute/, pour les écouter."""
    import_previous_work(config)
    target = relative_path(config["output_dir"]) / f"{config['model_name']}-ecoute"
    total = 0
    for kind in ("positive", "negative"):
        for split in ("train", "test"):
            folder = clip_dir(config, kind, split)
            clips = sorted(p for p in folder.glob("*.wav") if p.stem.isdigit())[:count]
            if clips:
                (target / folder.name).mkdir(parents=True, exist_ok=True)
            for clip in clips:
                shutil.copyfile(clip, target / folder.name / clip.name)
                total += 1
    print(f"{total} clips à écouter dans {target}", flush=True)


def augmented_features_ready(config: dict) -> bool:
    """Resume the official pipeline only when all generated feature arrays are complete."""
    import numpy as np

    folder = work_dir(config)
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
    print(f"Dossier de travail : {work_dir(config)}")
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
    commands.add_parser("ecoute")
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
        elif args.command == "ecoute":
            export_clips(config)
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








