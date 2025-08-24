import json
import time
import cloudscraper
from bs4 import BeautifulSoup
import os

def test_search_anime():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }
    
    scraper = cloudscraper.create_scraper()
    search_query = "naruto"
    search_url = f"https://anime3rb.com/search?q={search_query}"
    
    print(f"Recherche de: {search_query}")
    print(f"URL: {search_url}")
    
    try:
        page = scraper.get(search_url, headers=headers)
        page.raise_for_status()
        
        print(f"Status code: {page.status_code}")
        time.sleep(2)
    except Exception as e:
        print(f"Erreur lors de la requête: {e}")
        return
    
    #save page content
    with open("search_results.html", "w", encoding="utf-8") as f:
        f.write(page.text)

    # Analyse locale du fichier HTML sauvegardé
    html_path = "search_results.html"
    if not os.path.exists(html_path):
        print(f"Fichier {html_path} introuvable.")
        return
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    soup = BeautifulSoup(html, "html.parser")

    # Trouver la liste des titres
    titles_list = soup.find("div", class_="search-results")
    if not titles_list:
        # fallback: chercher tous les <a> avec la classe simple-title-card
        anime_cards = soup.find_all("a", class_=lambda x: x and "simple-title-card" in x)
    else:
        anime_cards = titles_list.find_all("a", class_=lambda x: x and "simple-title-card" in x)

    results = []
    for card in anime_cards:
        url = card.get("href")
        img = card.find("img")
        image_url = img.get("src") if img else None
        details = card.find("div", class_="details")
        title = details.find("h4").text.strip() if details and details.find("h4") else None
        subtitle = details.find("h5").text.strip() if details and details.find("h5") else None
        badges = details.find_all("span", class_="badge") if details else []
        score = badges[0].text.strip() if len(badges) > 0 else None
        episodes = badges[1].text.strip() if len(badges) > 1 else None
        season = badges[2].text.strip() if len(badges) > 2 else None
        results.append({
            "title": title,
            "subtitle": subtitle,
            "url": url,
            "image": image_url,
            "score": score,
            "episodes": episodes,
            "season": season
        })
    # Sauvegarder les résultats dans un fichier pour analyse
    with open("search_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nNombre de résultats d'anime trouvés: {len(results)}")
    print("Les résultats ont été sauvegardés dans search_results.json")
    if results:
        print("\nExemple de résultat:")
        first = results[0]
        print(f"Titre: {first['title']}")
        print(f"URL: {first['url']}")
        print(f"Image: {first['image']}")
        print(f"Score: {first['score']}")
        print(f"Episodes: {first['episodes']}")
        print(f"Saison: {first['season']}")

def get_episode_cnt(soup):
    try:
        cnt = soup.find_all('p', class_="text-lg leading-relaxed")[1].text.strip()
        return int(cnt)
    except (IndexError, ValueError, AttributeError):
        print("Failed to retrieve episode count.")
        return None

def get_episode_links(url, episodes):
    res = []
    i = url.index("titles")
    base_url = url[:i] + "episode" + url[i + 6:]
    for episode in range(1, episodes + 1):
        res.append(f"{base_url}/{episode}")
    return res

def get_download_link(episode_url, scraper, headers):
    page = scraper.get(episode_url, headers=headers)
    soup = BeautifulSoup(page.content, "html.parser")
    holder = soup.find("div", class_="flex-grow flex flex-wrap gap-4 justify-center")
    if not holder:
        return None
    labels = holder.find_all("label")
    desired = [None, None]
    for link in labels:
        if "480" in link.text:
            desired = [480, link]
        elif "720" in link.text and desired[0] != 1080:
            desired = [720, link]
        elif not desired[1]:
            desired = [1080, link]
    if desired[1]:
        a_tag = desired[1].parent.find("a")
        if a_tag and a_tag.has_attr("href"):
            return a_tag["href"]
    return None

def test_scrape_anime_page():
    url = input("Entrez l'URL de l'anime (ex: https://anime3rb.com/titles/naruto): ").strip()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }
    scraper = cloudscraper.create_scraper()
    page = scraper.get(url, headers=headers)
    soup = BeautifulSoup(page.content, "html.parser")
    anime_name = url[url.index("titles") + 7:]
    episodes_cnt = get_episode_cnt(soup)
    if not episodes_cnt:
        print("Impossible de déterminer le nombre d'épisodes.")
        return
    episode_links = get_episode_links(url, episodes_cnt)
    print(f"{anime_name} a {episodes_cnt} épisodes.")
    data = {
        "anime_name": anime_name,
        "episodes_count": episodes_cnt,
        "episodes": []
    }
    for idx, ep_url in enumerate(episode_links, 1):
        print(f"Scraping épisode {idx}/{episodes_cnt}...", end='\r')
        dl_link = get_download_link(ep_url, scraper, headers)
        data["episodes"].append({
            "episode": idx,
            "page_url": ep_url,
            "download_link": dl_link
        })
    with open("episodes_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("\nDonnées sauvegardées dans episodes_data.json")

if __name__ == "__main__":
    print("1. Test recherche anime (search)")
    print("2. Test extraction page anime et liens de téléchargement (scrape)")
    choix = input("Choisissez le test à exécuter (1 ou 2): ").strip()
    if choix == "1":
        test_search_anime()
    elif choix == "2":
        test_scrape_anime_page()
    else:
        print("Choix invalide.")
