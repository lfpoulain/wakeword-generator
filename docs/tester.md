# Tester au micro

Cette page installe le testeur, puis explique comment juger un modèle et choisir son seuil. Le testeur ouvre une petite fenêtre : on parle, il affiche le score du modèle en direct et colore le mot en vert à chaque détection.

Il tourne sur votre ordinateur, hors de Docker. Le son du micro est analysé à la volée, **jamais enregistré**.

## Installer le testeur

Une seule fois, depuis le dossier du dépôt.

### Windows

Installez [Python 3.12](https://www.python.org/downloads/windows/) (Tkinter est inclus), puis dans PowerShell :

```powershell
py -3.12 -m venv .venv-test
.\.venv-test\Scripts\python.exe -m pip install -r tester-requirements.txt
.\.venv-test\Scripts\python.exe -m pip install --no-deps openwakeword==0.6.0
```

### Linux

Installez Python 3.12 avec Tkinter et PortAudio :

- Debian, Ubuntu : `sudo apt install python3-tk libportaudio2`
- Arch : `sudo pacman -S tk portaudio`

Puis :

```sh
python3.12 -m venv .venv-test
.venv-test/bin/python -m pip install -r tester-requirements.txt
.venv-test/bin/python -m pip install --no-deps openwakeword==0.6.0
```

openWakeWord est installé avec `--no-deps` : sa version publiée réclame un composant (TFLite) dont le testeur n’a pas besoin. Les composants vraiment nécessaires sont dans `tester-requirements.txt`.

## Lancer le testeur

| Système | Commande |
|---|---|
| Windows | double-clic sur `tester.bat`, ou `.\tester.bat` dans PowerShell |
| Linux | `./tester.sh` |

Le premier lancement télécharge les deux modèles de prétraitement d’openWakeWord (2,4 Mo, dans `data/preprocess/`), vérifiés par leur empreinte SHA-256. Le testeur charge ensuite le modèle désigné par `training.yml` : `output/<model_name>.onnx`.

Dans la fenêtre :

1. choisissez le **micro** (↻ rafraîchit la liste) ;
2. gardez le **seuil** à 0,5 pour commencer ;
3. cliquez sur **Démarrer**, puis dites le mot.

Le score suit chaque trame de 80 ms. Quand il atteint le seuil, le mot passe au vert pendant deux secondes et le compteur de détections avance. Deux détections sont séparées d’au moins deux secondes.

## Les options

`tester.bat` et `tester.sh` transmettent leurs options à `tester.py` :

| Option | Effet |
|---|---|
| `--model chemin/vers/modele.onnx` | essaie un autre modèle, sans toucher à `training.yml` |
| `--label "Mon mot"` | change le mot affiché (par défaut : `model_name`, avec majuscules) |
| `--config autre.yml` | lit une autre configuration |
| `--check` | vérifie le modèle et la présence d’un micro, sans ouvrir la fenêtre |

Par exemple, pour essayer le modèle livré avec Cornelius :

```powershell
.\tester.bat --model ..\cornelius\models\cornelius.onnx --label Cornelius
```

## Juger un modèle

Le score obtenu pendant l’entraînement ne dit pas comment le modèle se comporte dans votre maison. Faites deux séries d’essais, et notez les résultats.

**Il entend quand on l’appelle.** Dites le mot une vingtaine de fois :

- avec plusieurs personnes : voix graves et aiguës, enfants ;
- de près, puis de l’autre bout de la pièce ;
- à voix normale, puis plus bas ;
- avec du bruit : musique, télévision, lave-vaisselle.

**Il se tait quand on ne l’appelle pas.** Laissez tourner le testeur :

- en disant les mots proches de `custom_negative_phrases`, et les prénoms de la maison ;
- pendant une conversation ordinaire ;
- pendant une heure de radio ou de télévision.

Un bon modèle répond presque à chaque appel et ne se déclenche presque jamais tout seul.

## Choisir le seuil

| Constat | Réglage |
|---|---|
| Il manque des appels, les scores plafonnent un peu sous le seuil | baissez le seuil (0,4, puis 0,3) |
| Il se déclenche tout seul, ou sur un mot proche | montez le seuil (0,6, puis 0,7) |
| Les deux à la fois | le seuil n’y peut rien : réentraînez avec d’autres graphies ou plus de mots proches |

Le seuil retenu se reporte dans le programme qui utilise le modèle : pour Cornelius, la variable `CORNELIUS_WAKE_THRESHOLD` (voir [Utiliser le modèle](utiliser.md#avec-cornelius)).

## Voir aussi

- [Entraîner un mot](entrainer.md)
- [Utiliser le modèle](utiliser.md)
- [Dépannage](depannage.md#le-testeur)
