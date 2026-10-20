# Contribuer à wakeword-generator

Merci de vouloir améliorer le générateur. Cette page explique comment proposer une modification et ce qu’il faut vérifier avant de l’envoyer. Le fonctionnement interne est décrit dans [Comment ça marche](docs/fonctionnement.md).

## Proposer une modification

1. Ouvrez d’abord un ticket qui décrit le problème ou le besoin. Pour un souci d’entraînement, joignez la sortie de `doctor` et le message d’erreur (voir [Dépannage](docs/depannage.md#demander-de-laide)).
2. Créez une branche à partir de `main`, avec un sujet par branche.
3. Ouvrez une demande de fusion qui explique ce qui change et comment vous l’avez vérifié : tests automatiques, et, si la génération ou l’entraînement change, un entraînement complet et un essai au testeur.

Ne joignez jamais de clips, d’enregistrement de voix, de fichier de `data/` ou de `output/`.

## Avant d’envoyer

```sh
python -m pip install pytest pyyaml requests shellcheck-py==0.11.0.1
python -m pytest tests -q
shellcheck -x *.sh
```

Les mêmes vérifications tournent à chaque envoi (`.github/workflows/check.yml`).

## Changer la recette de génération

La recette, ce sont les voix, les variations, la répartition des clips et leurs durées (`pipeline.py`, `download_assets.py`). Un corpus déjà généré doit rester cohérent avec elle. Si vous la changez :

- augmentez `generation_version` dans `pipeline.py`, aux deux endroits où elle apparaît : les anciens corpus seront refusés au lieu d’être mélangés ;
- adaptez les tests de `tests/test_distribution.py` ;
- mettez à jour [Comment ça marche](docs/fonctionnement.md) ;
- pour une nouvelle voix, ajoutez son empreinte SHA-256, et sa licence dans [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Changer l’image Docker

- Fixez la version de chaque composant ajouté.
- Entraînez un modèle complet avec la nouvelle image, au moins sur GPU, et notez la carte utilisée dans la demande de fusion.
- Reportez les versions qui comptent dans [Préparer la machine](docs/installer.md#construire-limage-docker).

## Conventions

- `pipeline.py` et `download_assets.py` tournent dans Docker, avec Python 3.10 ; le testeur tourne avec Python 3.12. Gardez-les compatibles avec leur version.
- Textes en français (messages, fenêtre du testeur, documentation), au vouvoiement, en phrases courtes, sans tiret long.
- Un message d’erreur dit quoi faire, pas seulement ce qui ne va pas.
- Tout changement visible a sa ligne dans le [CHANGELOG](CHANGELOG.md), et sa place dans la documentation de `docs/`.

## Licence des contributions

Ce dépôt est sous [PolyForm Noncommercial License 1.0.0](LICENSE), comme Cornelius. En proposant un changement, vous confirmez en être l’auteur ou avoir le droit de le proposer, et vous acceptez qu’il soit distribué sous cette licence. Vous autorisez aussi les auteurs de wakeword-generator à le distribuer sous d’autres conditions, notamment dans une licence commerciale accordée par écrit.
