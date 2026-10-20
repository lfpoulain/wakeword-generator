# Notices et attributions

wakeword-generator s’appuie sur le travail d’autres projets. Ce fichier les cite avec leur licence. Il accompagne toute copie du dépôt, avec le fichier [`LICENSE`](LICENSE).

> Required Notice: Copyright (c) 2026 Entremakers SAS, Les Frères Poulain (https://github.com/lfpoulain/wakeword-generator)

Chaque projet ci-dessous garde sa propre licence : celle de wakeword-generator ne s’applique pas à eux. Ce fichier résume les conditions annoncées par chaque source, sans trancher de question juridique.

## Logiciels utilisés pendant l’entraînement

Ils sont installés dans l’image Docker, pas copiés dans le dépôt.

| Élément | Licence | Remarque |
| --- | --- | --- |
| [openWakeWord](https://github.com/dscripka/openWakeWord), David Scripka | Apache 2.0 | Script d’entraînement et architecture du modèle. |
| [piper-sample-generator](https://github.com/dscripka/piper-sample-generator), David Scripka | MIT | Chargé par le script officiel ; les clips sont générés directement avec Piper. |
| Moteur de synthèse [Piper](https://github.com/OHF-Voice/piper1-gpl) et [espeak-ng](https://github.com/espeak-ng/espeak-ng) | GPL 3.0 | Si vous distribuez l’image Docker construite, respectez la GPL pour elle. Cela ne change pas la licence du code de ce dépôt. |
| PyTorch, torchaudio, ONNX, ONNX Runtime, NumPy, SciPy, scikit-learn, speechbrain, audiomentations… | BSD, MIT ou Apache 2.0 | Versions fixées dans le `Dockerfile` et `tester-requirements.txt`. |

## Données et modèles téléchargés

Ils sont téléchargés dans `data/` par `download_assets.py` et le `Dockerfile`, jamais inclus dans le dépôt.

| Élément | Licence annoncée | Ce qu’il faut savoir |
| --- | --- | --- |
| Caractéristiques négatives [openwakeword_features](https://huggingface.co/datasets/davidscripka/openwakeword_features) | CC BY-NC-SA 4.0 | Usage non commercial et partage dans les mêmes conditions : un modèle entraîné avec elles est, par prudence, à diffuser sous CC BY-NC-SA 4.0. |
| Réponses impulsionnelles [MIT environmental impulse responses](https://huggingface.co/datasets/davidscripka/MIT_environmental_impulse_responses) | inconnue | À éclaircir, ou à remplacer par des enregistrements à licence explicite, avant de distribuer un corpus ou un modèle. |
| Bruits de fond (AudioSet et autres) | variable | Les droits des vidéos d’origine [peuvent varier](https://github.com/dscripka/openWakeWord/discussions/174) : à vérifier un à un avant de publier un corpus audio. |
| Voix Piper [Siwis](https://huggingface.co/rhasspy/piper-voices/blob/main/fr/fr_FR/siwis/medium/MODEL_CARD) | CC BY 4.0 | Garder l’attribution. |
| Voix Piper [UPMC](https://huggingface.co/rhasspy/piper-voices/blob/main/fr/fr_FR/upmc/medium/MODEL_CARD) | CC BY-SA 4.0 | Garder l’attribution, partage dans les mêmes conditions. |
| Voix Piper [Tom](https://huggingface.co/rhasspy/piper-voices/blob/main/fr/fr_FR/tom/medium/MODEL_CARD) | AGPL v3 | Garder l’attribution. |
| Modèles de prétraitement d’openWakeWord v0.5.1 (`melspectrogram.onnx`, `embedding_model.onnx`) | à clarifier | Leur licence fait l’objet d’une [demande de clarification](https://github.com/dscripka/openWakeWord/issues/338). Vérifiés par SHA-256 au téléchargement. |

Les cartes des voix décrivent les données des voix ; elles ne disent pas, à elles seules, le statut des sons générés ni du modèle entraîné.

## Diffuser un modèle entraîné

Avant de publier un modèle produit avec ce générateur :

1. diffusez-le pour un usage non commercial, sous CC BY-NC-SA 4.0, à cause des caractéristiques négatives ;
2. joignez-lui les attributions ci-dessus (openWakeWord, openwakeword_features, voix Piper) ;
3. ne publiez pas les WAV, NPY ou corpus téléchargés ou générés ;
4. pour un usage commercial, réentraînez avec des données aux droits explicites.

Le modèle « Cornelius » diffusé avec [Cornelius](https://github.com/lfpoulain/Cornelius) suit ces règles : voir son fichier `models/cornelius.onnx.LICENSE`.
