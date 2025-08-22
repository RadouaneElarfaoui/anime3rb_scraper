# Anime3rb Scraper

Ce projet fournit un module Python pour le web scraping du site anime3rb.com. Il permet de récupérer des informations sur les animes, leurs épisodes, les liens de streaming/téléchargement, et d'effectuer des recherches.

## Fonctionnalités

- Lister les animes par page et par genre.
- Obtenir les détails complets d'un anime.
- Lister les épisodes d'un anime donné.
- Récupérer les liens de streaming/téléchargement pour un épisode.
- Rechercher des animes.
- Lister les genres disponibles.
- Gestion des erreurs et résilience (tentative de contournement de Cloudflare via Playwright).

## Installation

1.  **Cloner le dépôt (si applicable) ou télécharger les fichiers :**

    ```bash
    git clone <URL_DU_DEPOT>
    cd anime3rb_scraper
    ```

2.  **Assurez-vous d'avoir Python 3.10 ou une version ultérieure installée.**

3.  **Installez les dépendances requises :**

    ```bash
    pip install httpx beautifulsoup4 selectolax python-dotenv playwright
    playwright install
    ```

## Utilisation

Le module principal est `anime3rb_client.py`. Vous pouvez l'importer dans vos propres scripts ou exécuter le fichier directement pour voir des exemples d'utilisation.

### Exemples d'utilisation (voir `anime3rb_client.py` pour le code complet)

```python
import asyncio
from anime3rb_client import Anime3rbClient, Anime3rbError, NotFoundError

async def main():
    async with Anime3rbClient() as client:
        # Lister les animes
        print("--- Listing Animes ---")
        try:
            pagination = await client.list_anime(page=1)
            print(f"Found {len(pagination.items)} animes on page 1.")
            if pagination.items:
                first_anime = pagination.items[0]
                print(f"First anime: {first_anime.title} ({first_anime.url})")

                # Obtenir les détails d'un anime
                print(f"\n--- Getting Anime Details for {first_anime.title} ---")
                full_anime = await client.get_anime(first_anime.url)
                print(f"  Synopsis: {full_anime.synopsis[:100]}...")
                print(f"  Genres: {\", \".join(full_anime.genres)}")

                # Lister les épisodes
                print(f"\n--- Listing Episodes for {full_anime.title} ---")
                episodes = await client.list_episodes(full_anime.slug)
                print(f"Found {len(episodes)} episodes.")
                if episodes:
                    first_episode = episodes[0]
                    print(f"  First episode: {first_episode.title}")

                    # Obtenir les liens d'épisode
                    print(f"\n--- Getting Episode Links for {first_episode.title} ---")
                    episode_links = await client.get_episode_links(first_episode.url)
                    for link in episode_links:
                        print(f"  Server: {link.server}, Kind: {link.kind}, URL: {link.url}")

        except Anime3rbError as e:
            print(f"An error occurred: {e}")

        # Rechercher des animes
        print("\n--- Searching for \'naruto\' ---")
        try:
            search_results = await client.search("naruto")
            print(f"Found {len(search_results.items)} search results.")
        except Anime3rbError as e:
            print(f"An error occurred during search: {e}")

        # Lister les genres
        print("\n--- Listing Genres ---")
        try:
            genres = await client.list_genres()
            print(f"Found {len(genres)} genres.")
        except Anime3rbError as e:
            print(f"An error occurred during genre listing: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

## Avertissements légaux

Ce script est fourni à des fins éducatives et de recherche uniquement. Il est conçu pour interagir de manière respectueuse avec le site web en respectant les délais et les politiques de `robots.txt`. Toute utilisation abusive ou non conforme aux lois applicables est strictement interdite. L'auteur ne peut être tenu responsable de toute utilisation inappropriée de ce script.


