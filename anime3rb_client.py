# anime3rb_client.py

# Ce fichier contiendra le module Python pour le web scraping du site anime3rb.com.
# Un README bref sera inclus en commentaire en tête de fichier.
# Les modèles de données (dataclasses) et la classe Anime3rbClient seront définis ici.
# Des exemples d'utilisation et un bloc de tests rapides seront également inclus.




"""
README:

Ce module Python permet d'extraire des informations du site anime3rb.com.

Installation:
Assurez-vous d'avoir Python 3.10+ installé.
Installez les dépendances nécessaires avec pip:
`pip install httpx beautifulsoup4 selectolax python-dotenv`

Utilisation:
Voir les exemples d'utilisation à la fin de ce fichier (dans `if __name__ == "__main__":`).

Avertissements légaux:
Ce script est fourni à des fins éducatives et de recherche uniquement. Il est conçu pour interagir de manière respectueuse avec le site web en respectant les délais et les politiques de `robots.txt`. Toute utilisation abusive ou non conforme aux lois applicables est strictement interdite. L'auteur ne peut être tenu responsable de toute utilisation inappropriée de ce script.
"""




import httpx
from dataclasses import dataclass
from typing import Optional, List, TypeVar, Generic

T = TypeVar("T")

@dataclass
class Anime:
    title: str
    url: str
    slug: str
    alt_titles: list[str]
    synopsis: str
    cover_url: str
    status: Optional[str]
    genres: list[str]
    rating: Optional[float]
    year: Optional[int]

@dataclass
class Episode:
    title: str
    url: str
    number: Optional[float]
    season: Optional[int]
    air_date: Optional[str]

@dataclass
class EpisodeLink:
    server: str
    kind: str  # "stream" | "download"
    url: str

@dataclass
class Pagination(Generic[T]):
    items: List[T]
    page: int
    has_next: bool
    total_estimated: Optional[int]





import time
import logging
from urllib.parse import urljoin
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class Anime3rbError(Exception):
    """Base exception for Anime3rbClient errors."""
    pass

class NotFoundError(Anime3rbError):
    """Exception raised when a requested resource is not found."""
    pass

class Anime3rbClient:
    BASE_URL = "https://anime3rb.com/"

    def __init__(self, timeout: int = 15, rate_limit_s: float = 1.0):
        self.timeout = timeout
        self.rate_limit_s = rate_limit_s
        self._last_request_time = 0
        self.client = httpx.Client(timeout=self.timeout)
        self.playwright_browser = None
        self.playwright_context = None

    def _throttle(self):
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit_s:
            sleep_time = self.rate_limit_s - elapsed
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    async def _start_playwright_browser(self):
        if not self.playwright_browser:
            from playwright.async_api import async_playwright
            self.playwright_instance = await async_playwright().start()
            self.playwright_browser = await self.playwright_instance.chromium.launch()
            self.playwright_context = await self.playwright_browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36")

    async def _close_playwright_browser(self):
        if self.playwright_browser:
            await self.playwright_browser.close()
            await self.playwright_instance.stop()
            self.playwright_browser = None
            self.playwright_context = None

    async def _get_playwright(self, url: str) -> str:
        await self._start_playwright_browser()
        page = await self.playwright_context.new_page()
        try:
            await page.goto(url)
            await page.wait_for_load_state('networkidle') # Attendre que le réseau soit inactif
            # await page.wait_for_selector("body:not(:has(#cf-spinner))") # Peut être retiré si networkidle suffit
            return await page.content()
        finally:
            await page.close()

    async def _get(self, url: str) -> str:
        self._throttle()
        try:
            response = self.client.get(url)
            response.raise_for_status()
            return response.text
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            logging.warning(f"HTTPX failed for {url}, trying Playwright: {exc}")
            try:
                return await self._get_playwright(url)
            except Exception as pw_exc:
                logging.error(f"Playwright also failed for {url}: {pw_exc}")
                raise Anime3rbError(f"Failed to retrieve {url} with both HTTPX and Playwright") from pw_exc

    def _abs(self, url: str) -> str:
        return urljoin(self.BASE_URL, url)

    def _parse_anime_card(self, node) -> Optional[Anime]:
        try:
            title = node.select_one("h3.anime-title a").text.strip()
            url = self._abs(node.select_one("h3.anime-title a")["href"])
            slug = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
            cover_url = self._abs(node.select_one("img.anime-cover")["src"])
            # Placeholder for other fields, will be refined after inspecting actual HTML
            return Anime(title=title, url=url, slug=slug, alt_titles=[], synopsis="", cover_url=cover_url, status=None, genres=[], rating=None, year=None)
        except Exception as e:
            logging.warning(f"Failed to parse anime card: {e}")
            return None

    def _parse_anime_detail(self, html: str) -> Optional[Anime]:
        soup = BeautifulSoup(html, "html.parser")
        try:
            title = soup.select_one("h1.anime-title").text.strip()
            url = soup.find("link", {"rel": "canonical"})["href"]
            slug = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
            cover_url = self._abs(soup.select_one("img.anime-cover")["src"])
            synopsis = soup.select_one("div.anime-synopsis p").text.strip()
            
            alt_titles = [li.text.strip() for li in soup.select("ul.anime-info li:contains(\"Alternative Titles\") span")]
            status = soup.select_one("ul.anime-info li:contains(\"Status\") span").text.strip()
            genres = [a.text.strip() for a in soup.select("ul.anime-info li:contains(\"Genres\") a")]
            rating_text = soup.select_one("span.anime-rating").text.strip()
            rating = float(rating_text) if rating_text else None
            year_text = soup.select_one("ul.anime-info li:contains(\"Released\") span").text.strip()
            year = int(year_text) if year_text and year_text.isdigit() else None

            return Anime(title=title, url=url, slug=slug, alt_titles=alt_titles, synopsis=synopsis, cover_url=cover_url, status=status, genres=genres, rating=rating, year=year)
        except Exception as e:
            logging.error(f"Failed to parse anime detail: {e}")
            return None

    async def list_anime(self, page: int = 1, genre: Optional[str] = None) -> Pagination[Anime]:
        url = self.BASE_URL
        if genre:
            url = self._abs(f"genre/{genre}/")
        if page > 1:
            url = self._abs(f"page/{page}/") if not genre else self._abs(f"genre/{genre}/page/{page}/")

        html = await self._get(url)
        soup = BeautifulSoup(html, "html.parser")

        anime_cards = soup.select("div.anime-card")
        animes = [self._parse_anime_card(card) for card in anime_cards if self._parse_anime_card(card) is not None]

        # Basic pagination detection (needs refinement based on actual site structure)
        next_page_link = soup.select_one("a.next-page")
        has_next = next_page_link is not None

        # total_estimated is hard to get without making extra requests, leaving as None for now
        return Pagination(items=animes, page=page, has_next=has_next, total_estimated=None)

    async def get_anime(self, slug_or_url: str) -> Anime:
        if slug_or_url.startswith(self.BASE_URL):
            url = slug_or_url
        else:
            url = self._abs(f"anime/{slug_or_url}/")

        html = await self._get(url)
        anime = self._parse_anime_detail(html)
        if not anime:
            raise NotFoundError(f"Anime not found or could not be parsed from {url}")
        return anime

    async def list_episodes(self, anime_slug_or_url: str) -> list[Episode]:
        if anime_slug_or_url.startswith(self.BASE_URL):
            url = anime_slug_or_url
        else:
            url = self._abs(f"anime/{anime_slug_or_url}/")

        html = await self._get(url)
        return self._parse_episode_list(html)

    async def get_episode_links(self, episode_slug_or_url: str) -> list[EpisodeLink]:
        if episode_slug_or_url.startswith(self.BASE_URL):
            url = episode_slug_or_url
        else:
            url = self._abs(f"episode/{episode_slug_or_url}/") # Assuming episode links are under /episode/

        html = await self._get(url)
        return self._parse_episode_links(html)

    async def search(self, query: str, page: int = 1) -> Pagination[Anime]:
        url = self._abs(f"?s={query}&page={page}")
        html = await self._get(url)
        soup = BeautifulSoup(html, "html.parser")

        anime_cards = soup.select("div.anime-card")
        animes = [self._parse_anime_card(card) for card in anime_cards if self._parse_anime_card(card) is not None]

        next_page_link = soup.select_one("a.next-page")
        has_next = next_page_link is not None

        return Pagination(items=animes, page=page, has_next=has_next, total_estimated=None)

    async def list_genres(self) -> list[str]:
        url = self.BASE_URL # Assuming genres are listed on the homepage or a specific page
        html = await self._get(url)
        soup = BeautifulSoup(html, "html.parser")

        genres = []
        # This selector needs to be adjusted based on the actual website structure
        for genre_node in soup.select("ul.genres-list li a"): # Placeholder selector
            genres.append(genre_node.text.strip())
        return genres




    async def close(self):
        await self._close_playwright_browser()




    async def __aenter__(self):
        await self._start_playwright_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_playwright_browser()


if __name__ == "__main__":
    async def main():
        async with Anime3rbClient() as client:
            print("\n--- Testing list_anime ---")
            try:
                pagination = await client.list_anime(page=1)
                print(f"Found {len(pagination.items)} animes on page 1.")
                if pagination.items:
                    first_anime = pagination.items[0]
                    print(f"First anime: {first_anime.title} ({first_anime.url})")

                    print(f"\n--- Testing get_anime for {first_anime.title} ---")
                    full_anime = await client.get_anime(first_anime.url)
                    print(f"Full anime details for {full_anime.title}:")
                    print(f"  Synopsis: {full_anime.synopsis[:100]}...")
                    print(f"  Genres: {', '.join(full_anime.genres)}")
                    print(f"  Status: {full_anime.status}")
                    print(f"  Rating: {full_anime.rating}")
                    print(f"  Year: {full_anime.year}")

                    print(f"\n--- Testing list_episodes for {full_anime.title} ---")
                    episodes = await client.list_episodes(full_anime.slug)
                    print(f"Found {len(episodes)} episodes for {full_anime.title}.")
                    if episodes:
                        first_episode = episodes[0]
                        print(f"First episode: {first_episode.title} ({first_episode.url})")

                        print(f"\n--- Testing get_episode_links for {first_episode.title} ---")
                        episode_links = await client.get_episode_links(first_episode.url)
                        print(f"Found {len(episode_links)} links for {first_episode.title}.")
                        for link in episode_links:
                            print(f"  Server: {link.server}, Kind: {link.kind}, URL: {link.url}")
                    else:
                        print(f"No episodes found for {full_anime.title}.")
                else:
                    print("No animes found on page 1.")

            except Anime3rbError as e:
                print(f"An error occurred during anime listing/detail: {e}")

            print("\n--- Testing search (query: 'naruto') ---")
            try:
                search_results = await client.search("naruto")
                print(f"Found {len(search_results.items)} search results for 'naruto'.")
                if search_results.items:
                    for anime in search_results.items[:3]: # Print first 3 results
                        print(f"  - {anime.title} ({anime.url})")
            except Anime3rbError as e:
                print(f"An error occurred during search: {e}")

            print("\n--- Testing list_genres ---")
            try:
                genres = await client.list_genres()
                print(f"Found {len(genres)} genres.")
                print(f"Genres: {', '.join(genres[:10])}...") # Print first 10 genres
            except Anime3rbError as e:
                print(f"An error occurred during genre listing: {e}")

    import asyncio
    asyncio.run(main())
