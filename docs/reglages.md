# Les réglages de `training.yml`

Cette page décrit chaque clé de `training.yml`, le fichier qui dit au générateur quel mot apprendre et comment. Pour un premier modèle, seules les trois clés du mot sont à changer : voir [Entraîner un mot](entrainer.md#2-remplir-trainingyml).

Le générateur lit ce fichier pour produire les clips ; le script officiel d’openWakeWord le relit ensuite pour l’augmentation et l’entraînement. Les valeurs fournies sont celles du modèle « Cornelius ».

## Le mot

| Clé | Valeur fournie | Rôle |
|---|---|---|
| `model_name` | `cornelius` | Nom du modèle produit (`output/<model_name>.onnx`) et de son dossier de travail. Minuscules ASCII, chiffres, `_` ou `-`, 64 caractères au plus, en commençant par une lettre. |
| `target_phrase` | 4 graphies | Les façons d’écrire le mot pour que les voix le prononcent bien. Chaque graphie reçoit la même part des clips positifs. |
| `custom_negative_phrases` | 7 mots | Les mots proches qui ne doivent pas déclencher le modèle. Chacun reçoit la même part des clips négatifs. |

Un clip du mot doit durer entre 0,55 et 1,75 seconde. Plus court, il est refait avec une voix plus lente ; plus long, il est accéléré. Une expression longue à dire serait donc compressée : gardez-la sous deux secondes à l’oral.

## Le corpus

| Clé | Valeur fournie | Rôle |
|---|---|---|
| `n_samples` | `20000` | Nombre de clips pour l’entraînement, **pour chaque catégorie** : 20 000 du mot, 20 000 de mots proches. |
| `n_samples_val` | `2000` | Nombre de clips pour la validation, pour chaque catégorie. Ils ne servent pas à apprendre, seulement à mesurer. |
| `output_dir` | `"./output"` | Dossier des modèles et des dossiers de travail. |
| `piper_sample_generator_path` | `"/opt/piper-sample-generator"` | Chemin dans l’image Docker. À ne pas changer. |
| `tts_batch_size` | `50` | Lu seulement par la génération d’openWakeWord, que ce générateur remplace par la sienne. Sans effet ici. |

## L’augmentation

L’augmentation abîme volontairement les clips (sons de fond, réverbération d’une pièce, égaliseur…) pour qu’ils ressemblent à ce qu’entend un vrai micro, puis en calcule les caractéristiques, celles que le modèle apprend. Le détail est dans [Comment ça marche](fonctionnement.md#3-augment--bruit-réverbération-caractéristiques).

| Clé | Valeur fournie | Rôle |
|---|---|---|
| `rir_paths` | `./data/rir` | Dossiers de réponses de pièces (WAV), pour la réverbération. |
| `background_paths` | `./data/background` | Dossiers de sons de fond (WAV). |
| `background_paths_duplication_rate` | `1` | Combien de fois chaque dossier de sons de fond compte, dans l’ordre de `background_paths`. Pour donner plus de poids à un dossier ajouté. |
| `augmentation_rounds` | `1` | Nombre de versions bruitées de chaque clip. |
| `augmentation_batch_size` | `16` | Clips traités ensemble. À baisser si la mémoire manque. |

Pour ajouter vos propres bruits (votre cuisine, votre télévision…) : un dossier de WAV mono à 16 kHz, ajouté à `background_paths`, avec une ligne de plus dans `background_paths_duplication_rate`.

## L’entraînement

| Clé | Valeur fournie | Rôle |
|---|---|---|
| `model_type` | `dnn` | Architecture : `dnn` (couches entièrement connectées) ou `rnn` (LSTM). |
| `layer_size` | `32` | Taille des couches cachées, pour `dnn` seulement. Plus grand : plus de capacité, plus de calcul. |
| `steps` | `50000` | Pas de la première phase d’entraînement. Deux phases d’affinage suivent, de `steps / 10` pas chacune. |
| `max_negative_weight` | `1500` | Poids donné aux exemples négatifs, qui monte de 1 à cette valeur pendant l’entraînement. Plus haut : moins de faux déclenchements, mais plus d’appels manqués. |
| `target_false_positives_per_hour` | `0.2` | Nombre de faux déclenchements par heure visé sur les données de validation. Voir la remarque ci-dessous. |
| `batch_n_per_class` | 1 024 · 50 · 50 | Exemples de chaque source dans chaque lot : caractéristiques négatives générales (`ACAV100M_sample`), mots proches (`adversarial_negative`), mot (`positive`). |
| `feature_data_files` | `ACAV100M_sample` | Fichiers de caractéristiques négatives : 2 000 heures de sons et de paroles. |
| `false_positive_validation_data_path` | `validation_set_features.npy` | Environ 11 heures de sons et de paroles où le mot n’apparaît pas, pour compter les faux déclenchements. |

> [!NOTE]
> Dans la version d’openWakeWord utilisée, le poids des négatifs est doublé avant chaque phase d’affinage, quel que soit `target_false_positives_per_hour`. Changer cette valeur n’a donc pas d’effet visible ; `max_negative_weight` est le vrai levier.

## Quand un réglage change

Le générateur garde les clips et les caractéristiques déjà faits. Selon le réglage, il faut repartir plus ou moins loin :

| Réglage changé | À faire |
|---|---|
| `target_phrase` ou `custom_negative_phrases` | un nouveau `model_name` : le générateur refuse de mélanger les clips |
| `n_samples` ou `n_samples_val` à la hausse | rien : les clips manquants sont générés, l’augmentation refaite |
| `n_samples` ou `n_samples_val` à la baisse | un nouveau `model_name` |
| augmentation (`augmentation_rounds`, sons de fond, réponses de pièces) | supprimer les caractéristiques du dossier de travail : `docker run --rm -v wakeword-travail:/travail --entrypoint rm wakeword-fr-training -rf /travail/<model_name>/positive_features_train.npy` (et les trois autres `*_features_*.npy`) |
| entraînement (`model_type`, `layer_size`, `steps`, poids, lots) | renommer ou déplacer `output/<model_name>.onnx`, puis l’étape `train` |

## Voir aussi

- [Entraîner un mot](entrainer.md)
- [Comment ça marche](fonctionnement.md)
- [Le script d’entraînement d’openWakeWord](https://github.com/dscripka/openWakeWord/blob/main/openwakeword/train.py)
