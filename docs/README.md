# Documentation de wakeword-generator

Cette page est l’index de la documentation. Pour une présentation rapide du projet, voir le [README](../README.md) à la racine du dépôt.

## Par où commencer

1. [Préparer la machine](installer.md) : Docker, le GPU, l’espace disque.
2. [Entraîner un mot](entrainer.md) : du choix du mot au fichier ONNX.
3. [Tester au micro](tester.md) : juger le modèle et choisir son seuil.
4. [Utiliser le modèle](utiliser.md) : dans Cornelius ou ailleurs.

## Je veux…

| Je veux… | Page |
|---|---|
| reconstruire le modèle « Cornelius » | [Entraîner un mot](entrainer.md#3-lancer-lentraînement) |
| créer un mot d’appel à moi | [Entraîner un mot](entrainer.md) |
| savoir combien de place il faut | [Préparer la machine](installer.md#ce-qui-est-téléchargé) |
| entraîner sans carte graphique | [Préparer la machine](installer.md#vérifier-le-gpu) |
| savoir si mon modèle est bon | [Tester au micro](tester.md#juger-un-modèle) |
| installer mon modèle dans Cornelius | [Utiliser le modèle](utiliser.md#avec-cornelius) |
| partager mon modèle | [Utiliser le modèle](utiliser.md#partager-le-modèle) |
| comprendre un réglage de `training.yml` | [Les réglages](reglages.md) |
| comprendre ce que fait chaque étape | [Comment ça marche](fonctionnement.md) |
| comprendre un message d’erreur | [Dépannage](depannage.md) |
| proposer une modification | [Contribuer](../CONTRIBUTING.md) |

## Toutes les pages

- [Préparer la machine](installer.md) : Docker sous Windows et Linux, le GPU, ce qui est téléchargé.
- [Entraîner un mot](entrainer.md) : choisir le mot, remplir `training.yml`, lancer, écouter les premiers clips, reprendre.
- [Tester au micro](tester.md) : installer le testeur, juger un modèle, choisir le seuil.
- [Utiliser le modèle](utiliser.md) : avec Cornelius et ses satellites, avec un autre programme, avant de le partager.
- [Les réglages de `training.yml`](reglages.md) : chaque clé, et ce qu’il faut refaire quand elle change.
- [Comment ça marche](fonctionnement.md) : les voix, la répartition des clips, l’augmentation, l’entraînement.
- [Dépannage](depannage.md) : Docker, les messages du générateur, le testeur, un modèle qui se comporte mal.

## Ailleurs

- [Notices des composants tiers](../THIRD_PARTY_NOTICES.md) : les licences des voix, des données et des logiciels.
- [Historique des changements](../CHANGELOG.md).
- [Le mot d’appel dans Cornelius](https://github.com/lfpoulain/Cornelius/blob/main/docs/fonctionnalites/mot-d-appel.md).
