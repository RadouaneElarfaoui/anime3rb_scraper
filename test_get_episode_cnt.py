from bs4 import BeautifulSoup
import cloudscraper
import re

def get_episode(soup, id):
    try:
        # Cherche les tag a qui contient un lien de https://anime3rb.com/episode/[id]/[nombre]
        episode_link = soup.find_all('a', href=re.compile(f"https://anime3rb.com/episode/{id}/\d+"))
        print(episode_link)
        episodes = []
        if episode_link:
            for link in episode_link:
                # Cherche le numéro d'épisode dans le texte du span (ex: 'الحلقة 1', 'الحلقة 12 الأخيرة')
                span = link.find('span')
                if span:
                    match = re.search(r'(\d+)', span.text)
                    if match:
                        
                        ep_link = link['href']
                        # extrait ep_nbr de eps de ep_link
                        ep_nbr = ep_link.split("/")[-1]

                        episodes.append((ep_nbr, ep_link))
                        print(f"Found episode: {ep_nbr} - {ep_link}")
            return episodes if episodes else None
    except (IndexError, ValueError, AttributeError):
        print("Failed to retrieve episode count.")
        return None

# --- TEST ---
def test_get_episode():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }

    resp = cloudscraper.create_scraper().get("https://anime3rb.com/titles/kaijuu-8-gou", headers=headers).text

    #save html file
    with open("test.html", "w", encoding="utf-8") as f:
        f.write(resp)
    soup = BeautifulSoup(resp, "html.parser")
    eps = get_episode(soup, id="kaijuu-8-gou")
    print(eps)

if __name__ == "__main__":
    test_get_episode()
