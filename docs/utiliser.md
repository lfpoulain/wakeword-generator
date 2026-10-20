# Utiliser le modèle

Cette page installe le modèle produit dans Cornelius ou dans un autre programme, puis dit quoi vérifier avant de le partager. Le modèle est le fichier `output/<model_name>.onnx`, d’environ 200 Ko.

## Avec Cornelius

Cornelius cherche son modèle dans `models/cornelius.onnx`, à la racine de son dépôt. Deux façons de le remplacer :

**Copier le fichier à sa place.** Depuis ce dépôt, avec Cornelius cloné à côté (adaptez `../cornelius` sinon) :

```sh
cp output/cornelius.onnx ../cornelius/models/cornelius.onnx
```

```powershell
Copy-Item output\cornelius.onnx ..\cornelius\models\cornelius.onnx
```

Votre version apparaît alors dans le `git status` de Cornelius. `git checkout models/cornelius.onnx`, dans Cornelius, rend celle d’origine.

**Ou indiquer son chemin**, dans le fichier `.env` de Cornelius, sans toucher au dépôt :

```ini
CORNELIUS_WAKE_MODEL=/chemin/vers/wakeword-generator/output/barnabe.onnx
```

Relancez ensuite Cornelius : `scripts/restart.sh` sous Linux, `powershell -ExecutionPolicy Bypass -File scripts\restart.ps1` sous Windows. La rubrique **Mise en route** de l’administration indique « Modèle local prêt. » quand il est chargé.

### Le seuil

Le seuil choisi avec le testeur se reporte dans le `.env` de Cornelius :

```ini
CORNELIUS_WAKE_THRESHOLD=0.5
```

Il doit être strictement compris entre 0 et 1 ; sinon, 0,5 est utilisé. Cornelius réagit comme le testeur : mêmes trames de 80 ms, même seuil, au moins deux secondes entre deux détections.

### Les satellites audio

Les satellites de Cornelius n’ont pas de modèle à eux : ils envoient le son de leur micro à l’ordinateur, qui y cherche le mot avec ce même modèle. Remplacer le modèle de Cornelius suffit donc pour toute la maison.

Le détail est dans la page [Le mot d’appel](https://github.com/lfpoulain/Cornelius/blob/main/docs/fonctionnalites/mot-d-appel.md) de Cornelius.

## Avec un autre programme

Le modèle suit le format d’openWakeWord : tout programme qui l’utilise avec l’inférence ONNX peut le charger. Il a besoin des deux modèles de prétraitement d’openWakeWord (`melspectrogram.onnx` et `embedding_model.onnx`, version v0.5.1), que le testeur a déjà téléchargés dans `data/preprocess/`.

```python
import numpy as np
from openwakeword.model import Model

model = Model(
    wakeword_models=["output/barnabe.onnx"],
    inference_framework="onnx",
    melspec_model_path="data/preprocess/melspectrogram.onnx",
    embedding_model_path="data/preprocess/embedding_model.onnx",
)

# Une trame : 1 280 échantillons de 16 bits, mono, à 16 kHz (80 ms).
score = model.predict(np.frombuffer(trame, dtype="<i2"))["barnabe"]
if score >= 0.5:
    print("Mot d’appel entendu")
```

Envoyez les trames les unes après les autres, sans trou : le modèle tient compte des précédentes.

Le modèle est au format ONNX seulement. Il ne convient pas aux outils qui attendent un fichier `.tflite`, ni à microWakeWord sur un microcontrôleur.

## Partager le modèle

Le code de ce dépôt est sous licence non commerciale, et les données d’entraînement ont leurs propres conditions. Elles s’appliquent au modèle que vous produisez. Avant de le publier :

1. **Diffusez-le sous [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.fr)**, pour un usage non commercial : c’est la condition des caractéristiques négatives d’openWakeWord.
2. **Joignez-lui ses attributions** : openWakeWord, openwakeword_features, les réponses de pièces du MIT, les trois voix Piper. Le fichier [`cornelius.onnx.LICENSE`](https://github.com/lfpoulain/Cornelius/blob/main/models/cornelius.onnx.LICENSE) de Cornelius sert de modèle : copiez-le à côté du vôtre sous le nom `<model_name>.onnx.LICENSE`, et changez le nom du mot et l’empreinte SHA-256.
3. **Ne publiez pas les clips ni les données** : ni les WAV, ni les `.npy`, ni le contenu de `data/`.
4. **Pour un usage commercial**, réentraînez avec des données dont les droits le permettent.

L’empreinte SHA-256 du modèle s’obtient avec `sha256sum output/barnabe.onnx` sous Linux, ou `Get-FileHash output\barnabe.onnx` dans PowerShell.

Le détail des licences, source par source, est dans [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Voir aussi

- [Tester au micro](tester.md)
- [Le mot d’appel](https://github.com/lfpoulain/Cornelius/blob/main/docs/fonctionnalites/mot-d-appel.md), dans Cornelius
- [Configuration de Cornelius](https://github.com/lfpoulain/Cornelius/blob/main/docs/reference/configuration.md)
