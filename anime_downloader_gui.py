import os
import time
import threading
import sys
from collections import deque
import cloudscraper
from bs4 import BeautifulSoup
import gradio as gr
import re # Import regex module

# --- Global Variables & Setup ---
queue = deque()
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}
queue_lock = threading.Lock()
# We keep a global scraper for non-threaded tasks like searching
scraper = cloudscraper.create_scraper()

# --- Core Logic Functions (Scraping & Downloading) ---

def download_video(url, filename, progress_callback, max_retries=3, retry_delay=5):
    """
    (ENHANCED VERSION) Downloads a single video file with progress reporting, error handling, and retry logic.
    This version handles intermediate download pages, is thread-safe, and includes advanced features.
    """
    for attempt in range(max_retries):
        try:
            # 1. Create a new scraper instance FOR EACH THREAD to ensure session isolation.
            thread_scraper = cloudscraper.create_scraper()

            print(f"[{filename}] Attempt {attempt + 1}/{max_retries}: Visiting intermediate page: {url}")

            # 2. Get the intermediate page with timeout handling.
            intermediate_page_response = thread_scraper.get(url, headers=headers, timeout=30)
            intermediate_page_response.raise_for_status()

            # 3. Parse the intermediate page to find the final, direct download link.
            soup = BeautifulSoup(intermediate_page_response.content, "html.parser")

            # Add more detailed logging to help diagnose the issue
            print(f"[{filename}] Intermediate page content: {intermediate_page_response.content[:500]}...")  # Log first 500 characters of the page content

            # Try to find the download link using the same logic as anime3rb_dl.py
            download_links_holder = soup.find("div", class_="flex-grow flex flex-wrap gap-4 justify-center")
            if not download_links_holder:
                print(f"[{filename}] Failed to find download links container in intermediate page")
                # Try alternative class names that might be used for the download links container
                download_links_holder = soup.find("div", class_="flex flex-wrap gap-4 justify-center")
                if not download_links_holder:
                    download_links_holder = soup.find("div", class_="flex-grow flex-wrap gap-4 justify-center")
                    if not download_links_holder:
                        print(f"[{filename}] Failed to find download links container with alternative class names")
                        if attempt == max_retries - 1:
                            return f"Échec pour {filename}: Impossible de trouver le conteneur de liens de téléchargement après {max_retries} tentatives."
                        else:
                            print(f"[{filename}] Conteneur de liens de téléchargement non trouvé. Réessai dans {retry_delay} secondes...")
                            time.sleep(retry_delay)
                            continue

            download_links = download_links_holder.find_all("label")
            desired = [None, None]

            for link in download_links:
                if "480" in link.text:
                    desired = [480, link]
                elif "720" in link.text and desired[0] != 1080:
                    desired = [720, link]
                elif not desired[1]:
                    desired = [1080, link]

            if desired[1]:
                final_link_tag = desired[1].parent.find("a")
                if final_link_tag and final_link_tag.has_attr('href'):
                    final_url = final_link_tag['href']
                    print(f"[{filename}] Lien de téléchargement final trouvé: {final_url}")
                else:
                    print(f"[{filename}] Failed to find associated <a> tag for the best quality link")
                    if attempt == max_retries - 1:
                        return f"Échec pour {filename}: Impossible de trouver le lien de téléchargement final après {max_retries} tentatives."
                    else:
                        print(f"[{filename}] Lien de téléchargement final non trouvé. Réessai dans {retry_delay} secondes...")
                        time.sleep(retry_delay)
                        continue
            else:
                print(f"[{filename}] No valid download link quality found in intermediate page")
                if attempt == max_retries - 1:
                    return f"Échec pour {filename}: Aucune qualité de lien de téléchargement valide trouvée après {max_retries} tentatives."
                else:
                    print(f"[{filename}] Aucune qualité de lien de téléchargement valide trouvée. Réessai dans {retry_delay} secondes...")
                    time.sleep(retry_delay)
                    continue

            # 4. Download the actual video file from the final URL with timeout and progress tracking.
            response = thread_scraper.get(final_url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()

            content_type = response.headers.get('content-type', '')
            if 'text/html' in content_type:
                if attempt == max_retries - 1:
                    return f"Échec pour {filename}: Le lien final était une page HTML, pas une vidéo après {max_retries} tentatives."
                else:
                    print(f"[{filename}] Le lien final était une page HTML. Réessai dans {retry_delay} secondes...")
                    time.sleep(retry_delay)
                    continue

            total_size = int(response.headers.get('content-length', 0))
            os.makedirs("output", exist_ok=True)

            from tqdm import tqdm

            downloaded_size = 0
            filepath = os.path.join("output", filename)
            start_time = time.time()
            last_update_time = start_time

            with open(filepath, 'wb') as f, tqdm(
                total=total_size,
                unit='B',
                unit_scale=True,
                desc=f"Téléchargement de {filename}"
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        pbar.update(len(chunk))
                        current_time = time.time()

                        # Update progress and speed every second
                        if current_time - last_update_time >= 1.0 or downloaded_size == total_size:
                            elapsed_time = current_time - start_time
                            speed = downloaded_size / (1024 * 1024 * elapsed_time) if elapsed_time > 0 else 0
                            progress = downloaded_size / total_size if total_size > 0 else 0
                            progress_callback(progress, f"Téléchargement de {filename}... {progress:.1%} | Vitesse: {speed:.2f} MB/s")
                            last_update_time = current_time

            # 5. Final verification of the downloaded file size.
            if os.path.getsize(filepath) < 100 * 1024: # Less than 100 KB
                os.remove(filepath) # Clean up the invalid file
                if attempt == max_retries - 1:
                    return f"Échec pour {filename}: Le fichier final est trop petit (erreur probable) après {max_retries} tentatives."
                else:
                    print(f"[{filename}] Fichier trop petit. Réessai dans {retry_delay} secondes...")
                    time.sleep(retry_delay)
                    continue

            return f"{filename} téléchargé avec succès!"
        except Exception as e:
            if attempt == max_retries - 1:
                return f"Échec du téléchargement de {filename} après {max_retries} tentatives: {str(e)}"
            else:
                print(f"[{filename}] Erreur: {str(e)}. Réessai dans {retry_delay} secondes...")
                time.sleep(retry_delay)
                continue

def get_episode_list(soup, anime_id):
    """
    Extracts episode numbers and links from the anime page soup.
    Returns a list of tuples: (ep_nbr, ep_link)
    """
    episodes = []
    try:
        episode_links = soup.find_all('a', href=re.compile(f"https://anime3rb.com/episode/{anime_id}/\\d+"))
        print(f"Found {len(episode_links)} episode links.")
        for link in episode_links:
            ep_link = link['href']
            ep_nbr = ep_link.split("/")[-1]
            episodes.append((ep_nbr, ep_link))
            print(f"Episode {ep_nbr}: {ep_link}")
        episodes.sort(key=lambda x: int(x[0]))
        return episodes
    except Exception as e:
        print(f"Failed to extract episode list: {e}")
        return []

def get_download_links(episode_tuples: list[tuple]):
    """
    Finds the best available download link by precisely replicating
    the working logic from 'anime3rb_dl.py'.
    """
    for ep_nbr, episode_url in episode_tuples:
        try:
            page = scraper.get(episode_url, headers=headers)
            page.raise_for_status()
            soup = BeautifulSoup(page.content, "html.parser")

            download_links_holder = soup.find("div", class_="flex-grow flex flex-wrap gap-4 justify-center")

            if not download_links_holder:
                print(f"No download links container found for episode {ep_nbr} at {episode_url}")
                continue

            print(f"Found download links holder for episode {ep_nbr} at {episode_url}")
            
            labels = download_links_holder.find_all("label")
            best_link_tag_info = {'quality': 0, 'tag': None}

            for label in labels:
                text = label.text.lower()
                if "1080" in text and best_link_tag_info['quality'] < 1080:
                    best_link_tag_info = {'quality': 1080, 'tag': label}
                elif "720" in text and best_link_tag_info['quality'] < 720:
                    best_link_tag_info = {'quality': 720, 'tag': label}
                elif "480" in text and best_link_tag_info['quality'] < 480:
                    best_link_tag_info = {'quality': 480, 'tag': label}
            
            best_label_tag = best_link_tag_info['tag']

            if best_label_tag:
                container = best_label_tag.parent
                link_tag = container.find('a') if container else None

                if link_tag and link_tag.has_attr('href'):
                    desired_link = link_tag['href']
                    with queue_lock:
                        queue.append((ep_nbr, desired_link))
                    print(f"✅ Added episode {ep_nbr} ({best_link_tag_info['quality']}p) to download queue.")
                else:
                    print(f"❌ Found label for episode {ep_nbr}, but failed to find associated <a> tag.")
            else:
                print(f"❌ No valid download link quality found for episode {ep_nbr} at {episode_url}")

        except Exception as e:
            print(f"Error processing episode {episode_url}: {e}")


def start_download_process(url, selected_episodes_tuples, progress=gr.Progress(), max_concurrent_downloads=3):
    """
    Main download process function with enhanced parallel download handling.
    """
    print("start_download_process called")
    if not url:
        return "L'URL de l'anime est manquante."
    if not selected_episodes_tuples:
        return "Aucun épisode sélectionné pour le téléchargement."

    try:
        anime_name = url.split("/")[-1]

        with queue_lock:
            queue.clear()

        progress(0, "Recherche des liens de téléchargement...")
        get_download_links(selected_episodes_tuples)

        download_threads = []
        results = []
        active_downloads = 0

        with queue_lock:
            num_to_download = len(queue)
            if num_to_download == 0:
                return "Impossible de trouver des liens de téléchargement pour les épisodes sélectionnés."

            items_to_process = list(queue)
            queue.clear()

        def download_worker(ep_num, link, progress_callback, result_list):
                    nonlocal active_downloads
                    try:
                        ep_name = f"{anime_name}-ep-{ep_num}.mp4"
                        status = download_video(link, ep_name, progress_callback)
                        result_list.append(status)
                        print(status)
                    finally:
                        with queue_lock:
                            active_downloads -= 1

        for i, (ep_num, link) in enumerate(items_to_process):
            # Wait if we've reached the maximum number of concurrent downloads
            while active_downloads >= max_concurrent_downloads:
                time.sleep(0.5)

            # Create a unique progress tracker for each download
            progress_tracker = gr.Progress(track_tqdm=True)
            thread = threading.Thread(target=download_worker, args=(ep_num, link, progress_tracker, results))
            download_threads.append(thread)
            with queue_lock:
                active_downloads += 1
            thread.start()
            time.sleep(0.1)

        for thread in download_threads:
            thread.join()

        return f"Processus terminé. {len([s for s in results if 'succès' in s])}/{num_to_download} épisodes téléchargés.\n" + "\n".join(results)
    except Exception as e:
        return f"Une erreur est survenue: {e}"

def search_anime(search_query):
    """Searches for an anime and returns a list of results."""
    if not search_query:
        return gr.update(choices=[], value=None), {}

    search_url = f"https://anime3rb.com/search?q={search_query.replace(' ', '+')}"
    try:
        page = scraper.get(search_url, headers=headers)
        page.raise_for_status()
    except Exception as e:
        print(f"Error fetching search results: {e}")
        return gr.update(choices=[("Error fetching results.", "")]), {}

    soup = BeautifulSoup(page.content, "html.parser")
    anime_cards = soup.find_all("a", class_=lambda x: x and "simple-title-card" in x)
    results = []
    anime_map = {}

    for card in anime_cards:
        url = card.get("href")
        details = card.find("div", class_="details")
        title = details.find("h4").text.strip() if details and details.find("h4") else "N/A"
        subtitle = details.find("h5").text.strip() if details and details.find("h5") else ""
        img = card.find("img")
        image_url = img.get("src") if img else None
        
        if title != "N/A" and url:
            label = f"{title} ({subtitle})"
            results.append(label)
            anime_map[label] = {"url": url, "title": title, "subtitle": subtitle, "image": image_url}
            
    if not results:
        return gr.update(choices=[("No results found.", "")], value=None), {}
    
    return gr.update(choices=results, value=None, interactive=True), anime_map

def scrape_episode_list(url, progress=gr.Progress()):
    """Scrapes the anime page to get a list of all available episodes."""
    if not url:
        return gr.update(choices=[], value=[], label="URL is missing.")
    progress(0, desc="Recherche de la page de l'anime...")
    try:
        page = scraper.get(url, headers=headers)
        page.raise_for_status()
        soup = BeautifulSoup(page.content, "html.parser")
        
        anime_id = url.rstrip('/').split('/')[-1]
        print(f"Anime ID: {anime_id}")
        progress(0.5, desc="Analyse des liens d'épisodes...")
        
        episode_tuples = get_episode_list(soup, anime_id)
        print(f"Found {len(episode_tuples)} episode links: {episode_tuples}")
        
        if episode_tuples:
            episode_choices = [f"🎬 Episode {ep_nbr} | 🔗 {ep_link}" for ep_nbr, ep_link in episode_tuples]
            return gr.update(choices=episode_choices, value=[], label=f"{len(episode_choices)} épisodes trouvés")
        else:
            return gr.update(choices=[], value=[], label="Impossible de trouver les liens des épisodes.")
    except Exception as e:
        return gr.update(choices=[], value=[], label=f"Error: {e}")

# --- Gradio UI ---
def create_gui():
    with gr.Blocks(theme=gr.themes.Soft()) as demo:
        gr.Markdown("# Anime3rb Downloader")
        selected_anime_state = gr.State({})
        anime_map_state = gr.State({})
        selected_episodes_state = gr.State([])

        with gr.Tabs() as tabs:
            with gr.TabItem("Recherche", id=0):
                with gr.Row():
                    search_input = gr.Textbox(label="Entrez le nom de l'anime à rechercher", scale=4)
                    search_button = gr.Button("Rechercher", scale=1)
                search_results_radio = gr.Radio(label="Résultats", choices=[], interactive=True)
                details_button = gr.Button("Voir les détails", interactive=False)

            with gr.TabItem("Détails", id=1):
                with gr.Row():
                    with gr.Column(scale=1):
                        anime_image = gr.Image(label="Couverture", height=300)
                    with gr.Column(scale=2):
                        anime_title = gr.Textbox(label="Titre", interactive=False)
                        anime_subtitle = gr.Textbox(label="Sous-titre", interactive=False)
                        anime_url_display = gr.Textbox(label="URL", interactive=False)
                with gr.Row():
                    back_to_search_btn = gr.Button("Précédent")
                    proceed_to_episodes_btn = gr.Button("Suivant", variant="primary")
            
            with gr.TabItem("Épisodes", id=2):
                gr.Markdown("## Sélection des épisodes")
                episodes_url_input = gr.Textbox(label="Anime URL", interactive=False)
                find_episodes_btn = gr.Button("Rechercher les épisodes", variant="primary")
                with gr.Row():
                    select_all_btn = gr.Button("Tout sélectionner")
                    deselect_all_btn = gr.Button("Tout désélectionner")
                episodes_checkbox_group = gr.CheckboxGroup(label="Épisodes trouvés", interactive=True)
                with gr.Row():
                    back_to_details_btn = gr.Button("Précédent")
                    proceed_to_download_config_btn = gr.Button("Suivant", interactive=False)
            
            with gr.TabItem("Téléchargement", id=3):
                gr.Markdown("## Lancement du téléchargement")
                download_url_input = gr.Textbox(label="Anime URL", placeholder="L'URL sera remplie automatiquement", interactive=False)
                selected_episodes_display = gr.Markdown("Aucun épisode sélectionné.")
                download_button = gr.Button("Lancer le téléchargement", variant="primary")
                output_text = gr.Textbox(label="Statut", interactive=False, lines=10)

        search_button.click(fn=search_anime, inputs=search_input, outputs=[search_results_radio, anime_map_state])
        search_results_radio.change(fn=lambda s: gr.update(interactive=bool(s)), inputs=search_results_radio, outputs=details_button)
        
        def go_to_details(selected_label, anime_map):
            selected_anime_data = anime_map.get(selected_label, {})
            return gr.update(selected=1), selected_anime_data
        details_button.click(fn=go_to_details, inputs=[search_results_radio, anime_map_state], outputs=[tabs, selected_anime_state])

        def update_details_view(anime_data):
            if not anime_data: return None, "", "", ""
            return anime_data.get('image'), anime_data.get('title'), anime_data.get('subtitle'), anime_data.get('url')
        selected_anime_state.change(fn=update_details_view, inputs=selected_anime_state, outputs=[anime_image, anime_title, anime_subtitle, anime_url_display])
        
        back_to_search_btn.click(lambda: gr.update(selected=0), None, tabs)

        def go_to_episodes(anime_data):
            return gr.update(selected=2), anime_data.get('url', '')
        proceed_to_episodes_btn.click(fn=go_to_episodes, inputs=selected_anime_state, outputs=[tabs, episodes_url_input])

        find_episodes_btn.click(fn=scrape_episode_list, inputs=episodes_url_input, outputs=episodes_checkbox_group)
        select_all_btn.click(lambda choices: gr.update(value=choices), inputs=episodes_checkbox_group, outputs=episodes_checkbox_group)
        deselect_all_btn.click(lambda: gr.update(value=[]), None, outputs=episodes_checkbox_group)
        episodes_checkbox_group.change(fn=lambda s: gr.update(interactive=bool(s)), inputs=episodes_checkbox_group, outputs=proceed_to_download_config_btn)
        
        back_to_details_btn.click(lambda: gr.update(selected=1), None, tabs)
        
        def go_to_download_config(url, selected_episodes_text):
            if not selected_episodes_text:
                return gr.update(selected=2), url, [], "Veuillez sélectionner au moins un épisode."
            episode_tuples = []
            for ep_text in selected_episodes_text:
                match = re.search(r'Episode (\d+) \| 🔗 (.+)', ep_text)
                if match:
                    ep_nbr, ep_link = match.group(1), match.group(2)
                    episode_tuples.append((ep_nbr, ep_link))
                    print(f"Episode {ep_nbr}: {ep_link}")
            ep_numbers_str = ", ".join([t[0] for t in episode_tuples])
            display_message = f"**Épisodes sélectionnés pour le téléchargement :** `{ep_numbers_str}`"
            return gr.update(selected=3), url, episode_tuples, display_message
            
        proceed_to_download_config_btn.click(
            fn=go_to_download_config, 
            inputs=[episodes_url_input, episodes_checkbox_group], 
            outputs=[tabs, download_url_input, selected_episodes_state, selected_episodes_display]
        )
        download_button.click(
            fn=start_download_process, 
            inputs=[download_url_input, selected_episodes_state], 
            outputs=output_text
        )
    print("Lancement de l'interface Gradio...")
    demo.launch(debug=True)

if __name__ == "__main__":
    create_gui()
