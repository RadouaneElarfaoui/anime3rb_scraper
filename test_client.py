import asyncio
from anime3rb_client import Anime3rbClient, Anime3rbError, NotFoundError

async def main():
    async with Anime3rbClient() as client:
        print("Testing list_anime...")
        try:
            pagination = await client.list_anime(page=1)
            print(f"Found {len(pagination.items)} animes on page 1.")
            if pagination.items:
                first_anime = pagination.items[0]
                print(f"First anime: {first_anime.title} ({first_anime.url})")

                print(f"Testing get_anime for {first_anime.title}...")
                full_anime = await client.get_anime(first_anime.url)
                print(f"Full anime details for {full_anime.title}:")
                print(f"  Synopsis: {full_anime.synopsis[:100]}...")
                print(f"  Genres: {', '.join(full_anime.genres)}")
                print(f"  Status: {full_anime.status}")
                print(f"  Rating: {full_anime.rating}")
                print(f"  Year: {full_anime.year}")
            else:
                print("No animes found on page 1.")

        except Anime3rbError as e:
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())


