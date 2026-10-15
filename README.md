# wakeword-generator

Générateur de mots d’appel en français pour [openWakeWord](https://github.com/dscripka/openWakeWord) : il fabrique un modèle ONNX pour un mot ou une courte expression, à partir de voix françaises de synthèse, puis permet de l’essayer au micro.

Tout se passe sur votre machine, après le téléchargement des ressources. Aucun enregistrement de votre voix n’est nécessaire pour construire le corpus.

Ce générateur a été écrit pour le mot « Cornelius » du miroir [Cornelius](https://github.com/lfpoulain/Cornelius), qui embarque le modèle obtenu. La configuration fournie, `training.yml`, vise toujours ce mot ; il suffit de la modifier pour en entraîner un autre.

## Sommaire

- [Ce qu’il faut](#ce-quil-faut)
- [Préparer un nouveau mot](#préparer-un-nouveau-mot)
- [Entraîner le modèle](#entraîner-le-modèle)
- [Tester au micro](#tester-au-micro)
- [Utiliser le modèle avec Cornelius](#utiliser-le-modèle-avec-cornelius)
- [Développer](#développer)
- [Licences](#licences)

## Ce qu’il faut

- **Pour entraîner** : Docker avec des conteneurs Linux, environ 40 Go d’espace libre et une connexion pour les téléchargements initiaux. Un GPU NVIDIA accessible à Docker accélère beaucoup l’entraînement ; le mode processeur fonctionne mais il est plus lent.
- **Pour tester au micro** : Python 3.12 avec Tkinter, et un micro capable de fournir du son mono à 16 kHz.

Les ressources téléchargées (`data/`) et les modèles produits (`output/`) restent dans le dossier et sont exclus de Git. Elles sont conservées pour les mots suivants.

## Préparer un nouveau mot

Dans `training.yml`, renseignez :

- **model_name** : nom court du fichier ONNX, en minuscules ASCII, par exemple `mon_assistant` ;
- **target_phrase** : une ou plusieurs graphies que les voix françaises prononcent comme le mot voulu ;
- **custom_negative_phrases** : des mots proches qui ne doivent pas déclencher le modèle.

Gardez un nom de modèle différent pour chaque mot. La construction ne remplace jamais un fichier ONNX existant et refuse de mélanger des phrases ou des voix différentes avec un corpus existant sous le même nom. Écoutez et testez les différentes graphies : une variation écrite ne garantit pas la prononciation attendue.

La recette génère 20 000 clips positifs et 20 000 négatifs pour l’entraînement, puis 2 000 de chaque pour la validation. Elle répartit les exemples sur quatre locuteurs français : Siwis, Jessica et Pierre d’UPMC, et Tom. Piper fait varier la vitesse et le rendu de chaque voix ; le script officiel d’openWakeWord ajoute du bruit et de la réverbération, entraîne le classifieur et exporte l’ONNX.

## Entraîner le modèle

Le script construit l’image Docker si elle manque, télécharge les voix et les données, génère les WAV, lance l’augmentation puis l’entraînement. Une exécution interrompue peut être relancée : les clips déjà générés et valides sont conservés.

### Windows (PowerShell)

Depuis ce dossier :

```powershell
.\build.ps1
```

Sans GPU NVIDIA :

```powershell
.\build.ps1 -Cpu
```

### Linux

Depuis ce dossier :

```sh
./build.sh
# ou, sans GPU NVIDIA :
./build.sh --cpu
```

Le script équivaut à :

```sh
docker build -t wakeword-fr-training .
docker run --rm --gpus all --shm-size=8g -v "$(pwd):/workspace" -w /workspace wakeword-fr-training --config training.yml build
```

Pour le mode processeur, retirez `--gpus all` de la seconde commande.

Le modèle final est `output/<model_name>.onnx`. Les WAV et les matrices d’entraînement se trouvent dans `output/<model_name>/`.

## Tester au micro

Le testeur ouvre une fenêtre locale avec le modèle indiqué par `training.yml`. Il n’enregistre pas le son. Il montre le score en direct et colore le mot en vert pendant deux secondes à chaque détection.

### Windows

Installez Python 3.12, puis depuis ce dossier :

```powershell
py -3.12 -m venv .venv-test
.\.venv-test\Scripts\python.exe -m pip install -r tester-requirements.txt
.\.venv-test\Scripts\python.exe -m pip install --no-deps openwakeword==0.6.0
.\tester.bat
```

Les lancements suivants se font par double-clic sur `tester.bat`. Le premier télécharge les deux modèles de prétraitement d’openWakeWord, vérifiés par SHA-256. Choisissez le micro dans la fenêtre, gardez le seuil à **0,5** pour commencer, puis cliquez sur **Démarrer**.

### Linux

Installez Python 3.12 avec Tkinter et PortAudio (Debian et Ubuntu : `sudo apt install python3-tk libportaudio2` ; Arch : `sudo pacman -S tk portaudio`), puis depuis ce dossier :

```sh
python3.12 -m venv .venv-test
.venv-test/bin/python -m pip install -r tester-requirements.txt
.venv-test/bin/python -m pip install --no-deps openwakeword==0.6.0
./tester.sh
```

`./tester.sh` prépare les modèles de prétraitement puis ouvre la fenêtre ; il accepte les options de `tester.py`.

### Options du testeur

- `tester.py --model chemin/vers/modele.onnx --label "Mon mot"` : essayer un autre ONNX sans changer `training.yml` ;
- `tester.py --check` : vérifier le chargement du modèle et la présence d’un micro, sans ouvrir la fenêtre.

Répétez les essais avec plusieurs personnes, distances et bruits, puis essayez les mots proches. Le score d’entraînement ne remplace pas ces essais réels.

## Utiliser le modèle avec Cornelius

Cornelius cherche son modèle dans `models/cornelius.onnx`, à la racine de son dépôt. Pour remplacer celui qui est fourni par votre version, copiez le fichier produit :

```sh
cp output/cornelius.onnx ../Cornelius/models/cornelius.onnx
```

```powershell
Copy-Item output\cornelius.onnx ..\Cornelius\models\cornelius.onnx
```

Adaptez `../Cornelius` à l’emplacement de votre copie de Cornelius, ou indiquez un autre fichier avec la variable `CORNELIUS_WAKE_MODEL` de son `.env`. Relancez ensuite Cornelius. Le détail est dans [la page « Mot d’appel » de Cornelius](https://github.com/lfpoulain/Cornelius/blob/main/docs/fonctionnalites/mot-d-appel.md).

Tout autre programme qui utilise openWakeWord avec l’inférence ONNX peut charger le modèle de la même façon.

## Développer

| Fichier | Rôle |
| --- | --- |
| `training.yml` | mot visé, mots proches et réglages de l’entraînement |
| `pipeline.py` | génération des clips, augmentation et entraînement (dans Docker) |
| `download_assets.py` | téléchargement des voix Piper et des données d’openWakeWord |
| `Dockerfile` | environnement d’entraînement figé (CUDA 11.7, PyTorch 1.13, openWakeWord à un commit précis) |
| `build.ps1`, `build.sh` | construction de l’image et lancement de l’entraînement |
| `tester.py`, `tester.bat`, `tester.sh` | testeur au micro |
| `tests/` | tests de la répartition des voix et des phrases |

Les tests se lancent avec pytest :

```sh
python -m pip install pytest pyyaml requests
python -m pytest tests -q
```

## Licences

Le code de ce dépôt est distribué sous la [PolyForm Noncommercial License 1.0.0](LICENSE) : usage, partage et modification permis pour un usage non commercial, en gardant la ligne `Required Notice` du fichier `LICENSE`. Ce n’est pas une licence « open source » au sens de l’OSI, puisqu’elle exclut l’usage commercial.

Le dépôt ne contient aucun poids, aucune voix ni aucun corpus : ils sont téléchargés sur votre machine, chacun avec sa licence. Ces licences pèsent sur les modèles que vous entraînez ; lisez [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) avant de diffuser un modèle ou d’en faire un usage commercial.
