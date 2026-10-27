# Historique des changements

Cette page retrace les changements du générateur, du plus récent au plus ancien. Quand la recette de génération change, sa version (`generation_version`, enregistrée dans `generation.json`) change aussi : les clips d’une ancienne recette ne sont jamais mélangés aux nouveaux.

## Non publié

### 2026-10-27 : plus rapide, et d’autres mots

**Ajouté**

- `build.ps1 -Config lumos.yml` et `./build.sh --config=lumos.yml` : entraîner une autre recette que `training.yml`. Première recette fournie : « Lumos » (`lumos.yml`).
- Réglages facultatifs `generation_workers` et `generation_threads` : processus et threads de Piper pendant la génération.
- Étape `ecoute` : copie 12 clips de chaque dossier dans `output/<model_name>-ecoute/`, pour les écouter.

**Modifié**

- La génération tourne en parallèle : 16 processus de 2 threads par défaut, environ 55 clips/s au lieu de 12 sur un processeur de 32 threads. Piper reste sur le processeur, quatre fois plus rapide que sur le GPU pour des phrases si courtes.
- Clips et caractéristiques vivent dans le volume Docker `wakeword-travail` (`/travail/<model_name>/`) au lieu de `output/<model_name>/` : ouvrir un fichier à travers le dossier partagé avec Windows coûte environ 10 ms. Sur 4 400 clips : génération 93 → 60 s, augmentation 66 → 44 s. Le modèle arrive toujours dans `output/`. Un ancien dossier `output/<model_name>/` est recopié une fois dans le volume.
- L’augmentation reste sur le processeur, après essai sur GPU : le modèle d’embedding y donne des valeurs différentes de celles du processeur (0,66 d’écart moyen pour une amplitude de 13), pour 5 s gagnées sur 4 400 clips ; et PyTorch 1.13 en CUDA 11.7 ne sait pas faire de FFT sur les RTX 40.

### 2026-10-20 : documentation et vitrine du dépôt

**Ajouté**

- Documentation complète dans `docs/` : [préparer la machine](docs/installer.md), [entraîner un mot](docs/entrainer.md), [tester au micro](docs/tester.md), [utiliser le modèle](docs/utiliser.md), [les réglages](docs/reglages.md), [comment ça marche](docs/fonctionnement.md), [dépannage](docs/depannage.md).
- Bannière, README refait, [guide de contribution](CONTRIBUTING.md) et cet historique.
- `build.ps1` et `build.sh` lancent une seule étape en la nommant : `doctor`, `prepare`, `generate`, `augment` ou `train` (`build` par défaut). Seules `build` et `train` demandent le GPU.

**Modifié**

- Les messages d’erreur conseillent de changer `model_name`, et non plus `output_dir`, quand la recette ou le nombre de clips a changé.
- `tester.bat` et `tester.sh` renvoient vers la page [Tester au micro](docs/tester.md) quand le testeur n’est pas installé.

### 2026-10-15 : projet autonome

**Ajouté**

- Le générateur quitte le dépôt de Cornelius et devient ce dépôt, avec sa licence (PolyForm Noncommercial 1.0.0), ses [notices des tiers](THIRD_PARTY_NOTICES.md) et une vérification automatique à chaque envoi (tests et `shellcheck`).

### Premières versions, dans le dépôt de Cornelius

**Ajouté**

- Génération des clips par quatre locuteurs français de Piper (Siwis, Jessica et Pierre d’UPMC, Tom), avec cinq variations de débit et d’intonation, répartis à parts égales entre locuteurs, graphies et variations (recette 4).
- Clips du mot gardés entre 0,55 et 1,75 seconde : refaits plus lentement s’ils sont trop courts, accélérés s’ils sont trop longs.
- Augmentation et entraînement par le script officiel d’openWakeWord, dans une image Docker aux versions figées, sur GPU NVIDIA ou sur processeur.
- Téléchargements qui reprennent après une coupure, voix et fragment AudioSet vérifiés par empreinte SHA-256.
- Testeur au micro pour Windows et Linux (Python 3.12).
- Le modèle « Cornelius » (SHA-256 `9c8adc85…`), livré avec Cornelius sous CC BY-NC-SA 4.0.
