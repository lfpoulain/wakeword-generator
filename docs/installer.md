# Préparer la machine

Cette page installe ce qu’il faut pour entraîner un mot d’appel, puis pour l’essayer au micro. Elle s’adresse à la personne qui fabrique le modèle, sous Windows ou sous Linux. L’entraînement lui-même est décrit dans [Entraîner un mot](entrainer.md).

## Ce qu’il faut

| | Pour entraîner | Pour tester au micro |
|---|---|---|
| **Logiciel** | Docker, avec des conteneurs Linux | Python 3.12 avec Tkinter |
| **Matériel** | un GPU NVIDIA de préférence ; le processeur seul suffit, en plus lent | un micro |
| **Disque** | environ 40 Go libres | environ 350 Mo |
| **Réseau** | pour les téléchargements du premier lancement | pour deux petits modèles au premier lancement |

Le modèle « Cornelius » a été entraîné sous Windows 11, avec Docker Desktop et une RTX 4090.

## Ce qui est téléchargé

Tout arrive dans le dossier `data/` du dépôt, exclu de Git. Rien n’est retéléchargé pour les mots suivants.

| Données | Taille | Dossier | Rôle |
|---|---|---|---|
| Caractéristiques négatives d’openWakeWord (2 000 heures de sons et de paroles) | 17 Go | `data/features/` | apprendre ce qui n’est **pas** le mot |
| Données de validation d’openWakeWord | 185 Mo | `data/features/` | compter les faux déclenchements pendant l’entraînement |
| Trois voix françaises Piper | 195 Mo | `data/voices/` | prononcer le mot et les mots proches |
| 500 sons de fond AudioSet | 150 Mo, plus 690 Mo le temps de les extraire | `data/background/` | mêler du bruit aux exemples |
| 270 réponses de pièces du MIT | 9 Mo | `data/rir/` | ajouter la réverbération d’une pièce |
| Deux modèles de prétraitement d’openWakeWord | 2,4 Mo | `data/preprocess/` | pour le testeur seulement |

S’y ajoutent l’image Docker (CUDA, PyTorch et les outils d’entraînement), puis, pour chaque mot, quelques Go de clips dans le volume Docker `wakeword-travail`. Un téléchargement interrompu reprend là où il s’était arrêté.

Les voix et le fragment AudioSet sont vérifiés par leur empreinte SHA-256 : un fichier modifié à la source est refusé.

## Docker sous Windows

1. Installez [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/), avec le moteur **WSL 2** (le choix par défaut).
2. Gardez les **conteneurs Linux** (le réglage par défaut).
3. Pour le GPU : un pilote NVIDIA à jour suffit. Docker Desktop transmet la carte aux conteneurs à travers WSL 2, sans autre installation.

Les commandes de la documentation se lancent dans **PowerShell**, depuis le dossier du dépôt.

> [!NOTE]
> Si PowerShell refuse de lancer `build.ps1` (« l’exécution de scripts est désactivée »), lancez-le ainsi : `powershell -ExecutionPolicy Bypass -File .\build.ps1`. Les options s’ajoutent à la suite.

## Docker sous Linux

1. Installez [Docker Engine](https://docs.docker.com/engine/install/) et ajoutez votre compte au groupe `docker` (ou lancez les scripts avec `sudo`).
2. Pour le GPU : installez le [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html), puis redémarrez Docker.

## Récupérer le dépôt

```sh
git clone https://github.com/lfpoulain/wakeword-generator.git
cd wakeword-generator
```

Il peut vivre n’importe où, par exemple à côté de Cornelius.

## Construire l’image Docker

Le premier lancement de `build.ps1` ou `build.sh` construit l’image `wakeword-fr-training` si elle manque. Pour la construire à l’avance :

```sh
docker build -t wakeword-fr-training .
```

Les versions qui comptent y sont figées : CUDA 11.7, PyTorch 1.13.1, openWakeWord et piper-sample-generator à un commit précis, Piper 1.3.0, ONNX Runtime 1.23.2.

> [!IMPORTANT]
> Les scripts ne reconstruisent l’image que si elle **manque**. Après une mise à jour du dépôt qui touche le `Dockerfile`, reconstruisez-la avec la commande ci-dessus.

## Vérifier le GPU

Une fois l’image construite :

```sh
docker run --rm --gpus all --entrypoint nvidia-smi wakeword-fr-training
```

Le tableau de `nvidia-smi` doit afficher la carte. Sinon, voir [Dépannage](depannage.md#le-gpu-nest-pas-vu). Sans GPU, tout fonctionne avec l’option `-Cpu` (Windows) ou `--cpu` (Linux), en plus lent.

> [!WARNING]
> CUDA 11.7 et PyTorch 1.13 ne connaissent pas les cartes les plus récentes (RTX 50, architecture Blackwell). Sur ces cartes, entraînez avec le processeur.

## Le testeur au micro

Il tourne hors de Docker, dans un petit environnement Python à part. Son installation est décrite dans [Tester au micro](tester.md#installer-le-testeur).

## Voir aussi

- [Entraîner un mot](entrainer.md)
- [Tester au micro](tester.md)
- [Dépannage](depannage.md)
