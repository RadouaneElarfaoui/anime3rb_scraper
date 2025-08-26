import os
import time
import threading
import sys
from collections import deque
import cloudscraper
from bs4 import BeautifulSoup
import gradio as gr
import re # Import regex module
from tqdm import tqdm
import requests # Import requests module for Facebook API interaction

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
    Downloads a single video file with print statements instead of a progress callback.
    """
    response = scraper.get(url, headers=headers, stream=True)

    if response.status_code != 200:
        print(f"Failed to download video: {response.status_code}")
        return "Échec du téléchargement"

    total_size = int(response.headers.get('content-length', 0))
    os.makedirs("output", exist_ok=True)

    with open(f"output/{filename}", 'wb') as f:
        with tqdm(total=total_size, unit='B', unit_scale=True, desc=filename) as pbar:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)
                pbar.update(len(chunk))
    return "Téléchargement réussi"

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
            # Initialise un dictionnaire pour suivre la meilleure qualité trouvée et la balise <label> correspondante.
            # La qualité est initialisée à 0 pour s'assurer que toute qualité trouvée (480, 720, 1080) sera supérieure.
            best_link_tag_info = {'quality': 0, 'tag': None}

            # Parcourt toutes les balises <label> qui représentent les options de qualité de téléchargement.
            for label in labels:
                text = label.text.lower() # Convertit le texte de la balise en minuscules pour une comparaison insensible à la casse.
                
                # Skip HEVC links as they are not accessible in the free plan
                if "hevc" in text:
                    print(f"Skipping HEVC link for episode {ep_nbr}: {text}")
                    continue

                # Vérifie si "1080" est dans le texte et si c'est une meilleure qualité que celle actuellement stockée.
                if "1080" in text and best_link_tag_info['quality'] < 1080:
                    best_link_tag_info = {'quality': 1080, 'tag': label} # Met à jour avec 1080p comme meilleure qualité.
                # Sinon, vérifie si "720" est dans le texte et si c'est une meilleure qualité que celle actuellement stockée.
                # Cette condition n'est évaluée que si 1080p n'a pas été trouvé ou si la qualité actuelle est inférieure à 720p.
                elif "720" in text and best_link_tag_info['quality'] < 720:
                    best_link_tag_info = {'quality': 720, 'tag': label} # Met à jour avec 720p.
                # Sinon, vérifie si "480" est dans le texte et si c'est une meilleure qualité que celle actuellement stockée.
                # Cette condition n'est évaluée que si 1080p et 720p n'ont pas été trouvés ou si la qualité actuelle est inférieure à 480p.
                elif "480" in text and best_link_tag_info['quality'] < 480:
                    best_link_tag_info = {'quality': 480, 'tag': label} # Met à jour avec 480p.
            
            # Une fois toutes les balises <label> parcourues, 'best_label_tag' contient la balise correspondant à la plus haute qualité trouvée.
            best_label_tag = best_link_tag_info['tag']

            if best_label_tag:
                # Trouve le conteneur parent de la balise <label> pour localiser le lien de téléchargement réel.
                container = best_label_tag.parent
                # Cherche la balise <a> (lien) à l'intérieur de ce conteneur.
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


def start_download_process(url, selected_episodes_tuples, max_concurrent_downloads=3):
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

        print("Recherche des liens de téléchargement...")
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

        def download_worker(ep_num, link, result_list):
                    nonlocal active_downloads
                    try:
                        ep_name = f"{anime_name}-ep-{ep_num}.mp4"
                        status = download_video(link, ep_name, None) # Changed to download_video
                        result_list.append(status)
                        print(status)
                    finally:
                        with queue_lock:
                            active_downloads -= 1

        for i, (ep_num, link) in enumerate(items_to_process):
            # Wait if we've reached the maximum number of concurrent downloads
            while active_downloads >= max_concurrent_downloads:
                time.sleep(0.5)

            # Removed progress_tracker = gr.Progress()
            thread = threading.Thread(target=download_worker, args=(ep_num, link, results))
            download_threads.append(thread)
            with queue_lock:
                active_downloads += 1
            thread.start()
            time.sleep(0.1)

        for thread in download_threads:
            thread.join()

        return f"Processus terminé. {len([s for s in results if 'réussi' in s])}/{num_to_download} épisodes téléchargés.\n" + "\n".join(results)
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

def scrape_episode_list(url):
    """Scrapes the anime page to get a list of all available episodes."""
    if not url:
        return gr.update(choices=[], value=[], label="URL is missing.")
    print("Recherche de la page de l'anime...")
    try:
        page = scraper.get(url, headers=headers)
        page.raise_for_status()
        soup = BeautifulSoup(page.content, "html.parser")
        
        anime_id = url.rstrip('/').split('/')[-1]
        print(f"Anime ID: {anime_id}")
        print("Analyse des liens d'épisodes...")
        
        episode_tuples = get_episode_list(soup, anime_id)
        print(f"Found {len(episode_tuples)} episode links: {episode_tuples}")
        
        if episode_tuples:
            episode_choices = [f"🎬 Episode {ep_nbr} | 🔗 {ep_link}" for ep_nbr, ep_link in episode_tuples]
            return gr.update(choices=episode_choices, value=[], label=f"{len(episode_choices)} épisodes trouvés")
        else:
            return gr.update(choices=[], value=[], label="Impossible de trouver les liens des épisodes.")
    except Exception as e:
        return gr.update(choices=[], value=[], label=f"Error: {e}")

def list_existing_videos():
    """
    Lists all .mp4 files in the 'output' directory and updates the Gradio CheckboxGroup choices.
    """
    output_dir = "output"
    if not os.path.exists(output_dir):
        # Return an update to clear choices if directory doesn't exist
        return gr.update(choices=[], value=[])
    
    video_files = [f for f in os.listdir(output_dir) if f.endswith(".mp4")]
    # Update the choices of the CheckboxGroup and clear any selected values
    return gr.update(choices=video_files, value=[])

# --- Gradio UI ---
def create_gui():
    with gr.Blocks(theme=gr.themes.Soft()) as demo:
        gr.Markdown("# Anime3rb Downloader")
        selected_anime_state = gr.State({})
        anime_map_state = gr.State({})
        selected_episodes_state = gr.State([])
        selected_files_to_upload_state = gr.State([]) # New state for files to upload
        fb_config_state = gr.State({ # New state for FB API config
            "access_token": "",
            "page_id": ""
        })

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
                with gr.Row():
                    back_to_episodes_btn_from_download = gr.Button("Précédent")
                    proceed_to_existing_files_btn = gr.Button("Suivant")

            with gr.TabItem("Fichiers existants", id=4): # Nouveau Tab
                gr.Markdown("## Fichiers vidéo existants")
                list_files_btn = gr.Button("Actualiser la liste des fichiers")
                existing_files_checkbox_group = gr.CheckboxGroup(label="Fichiers trouvés dans 'output'", interactive=True)
                with gr.Row():
                    back_from_files_btn = gr.Button("Précédent")
                    proceed_to_upload_btn = gr.Button("Suivant", interactive=False) # Changed button name and interaction

            with gr.TabItem("Upload vers Facebook", id=5): # Nouveau Tab pour l'upload
                gr.Markdown("## Uploader les vidéos sélectionnées sur Facebook")
                upload_files_display = gr.Markdown("Aucun fichier sélectionné pour l'upload.")
                video_title_input = gr.Textbox(label="Titre de la vidéo (optionnel)", placeholder="Entrez un titre pour la vidéo...")
                video_description_input = gr.Textbox(label="Description de la vidéo (optionnel)", placeholder="Entrez une description pour la vidéo...", lines=3)
                upload_to_fb_button = gr.Button("Lancer l'upload vers Facebook", variant="primary")
                upload_output_text = gr.Textbox(label="Statut de l'upload", interactive=False, lines=5)
                with gr.Row():
                    back_from_upload_btn = gr.Button("Précédent")
                    proceed_to_fb_config_btn = gr.Button("Suivant") # New button to go to FB config

            with gr.TabItem("Configuration FB API", id=6): # Nouveau Tab pour la configuration FB API
                gr.Markdown("## Configuration de l'API Facebook")
                fb_access_token_input = gr.Textbox(label="Facebook Page Access Token", placeholder="Entrez votre Page Access Token")
                fb_page_id_input = gr.Textbox(label="Facebook Page ID", placeholder="Entrez l'ID de votre page Facebook")
                save_fb_config_button = gr.Button("Sauvegarder la configuration", variant="primary")
                fb_config_status_text = gr.Textbox(label="Statut de la configuration", interactive=False)
                with gr.Row():
                    back_from_fb_config_btn = gr.Button("Précédent")
                    proceed_to_faq_btn = gr.Button("Suivant") # New button to go to FAQ tab

            with gr.TabItem("FAQ", id=7): # Nouveau Tab pour les Questions Fréquentes
                gr.Markdown("## Questions Fréquentes (FAQ)")
                with gr.Accordion("Comment rechercher un anime ?", open=False):
                    gr.Markdown("Pour rechercher un anime, allez dans l'onglet **Recherche**, entrez le nom de l'anime dans le champ de texte et cliquez sur **Rechercher**. Les résultats apparaîtront en dessous.")
                with gr.Accordion("Comment télécharger des épisodes ?", open=False):
                    gr.Markdown("Après avoir recherché et sélectionné un anime, allez dans l'onglet **Détails**, puis **Épisodes**. Cliquez sur **Rechercher les épisodes**, sélectionnez ceux que vous voulez et cliquez sur **Lancer le téléchargement** dans l'onglet **Téléchargement**.")
                with gr.Accordion("Où sont sauvegardés les fichiers téléchargés ?", open=False):
                    gr.Markdown("Les fichiers vidéo téléchargés sont sauvegardés dans le dossier `output/` à la racine de votre projet.")
                with gr.Accordion("Comment uploader des vidéos sur Facebook ?", open=False):
                    gr.Markdown("Dans l'onglet **Fichiers existants**, actualisez la liste, sélectionnez les vidéos à uploader, puis allez dans l'onglet **Upload vers Facebook**. Remplissez le titre et la description (optionnel) et cliquez sur **Lancer l'upload vers Facebook**.")
                with gr.Accordion("Comment configurer l'API Facebook ?", open=False):
                    gr.Markdown("Allez dans l'onglet **Configuration FB API**. Entrez votre **Facebook Page Access Token** et l'**ID de votre page Facebook**, puis cliquez sur **Sauvegarder la configuration**.")
                with gr.Row():
                    back_from_faq_btn = gr.Button("Précédent")

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

        # Navigation pour l'onglet "Téléchargement"
        back_to_episodes_btn_from_download.click(lambda: gr.update(selected=2), None, tabs)
        proceed_to_existing_files_btn.click(lambda: gr.update(selected=4), None, tabs)

        # Écouteurs d'événements pour le nouvel onglet "Fichiers existants"
        list_files_btn.click(fn=list_existing_videos, outputs=existing_files_checkbox_group)
        existing_files_checkbox_group.change(
            fn=lambda s: gr.update(interactive=bool(s)), 
            inputs=existing_files_checkbox_group, 
            outputs=proceed_to_upload_btn # Update interaction for the new button
        )
        back_from_files_btn.click(lambda: gr.update(selected=3), None, tabs)
        
        def go_to_upload_tab(selected_files):
            if not selected_files:
                return gr.update(selected=4), [], "Veuillez sélectionner au moins un fichier à uploader."
            display_message = f"**Fichiers sélectionnés pour l'upload :** `{', '.join(selected_files)}`"
            return gr.update(selected=5), selected_files, display_message

        proceed_to_upload_btn.click(
            fn=go_to_upload_tab,
            inputs=existing_files_checkbox_group,
            outputs=[tabs, selected_files_to_upload_state, upload_files_display]
        )

        # Écouteurs d'événements pour le nouvel onglet "Upload vers Facebook"
        def upload_videos_to_facebook(files_to_upload, title, description, fb_config):
            if not files_to_upload:
                return "Aucun fichier sélectionné pour l'upload."
            if not fb_config.get("access_token") or not fb_config.get("page_id"):
                return "Erreur: La configuration de l'API Facebook est incomplète. Veuillez la remplir dans l'onglet 'Configuration FB API'."
            
            results = []
            for filename in files_to_upload:
                filepath = os.path.join("output", filename) # Ensure 'output' is the correct directory
                
                # Facebook Graph API endpoint for video uploads
                upload_url = f"https://graph.facebook.com/v18.0/{fb_config['page_id']}/videos"
                
                params = {
                    'access_token': fb_config['access_token'],
                    'title': title if title else filename, # Use provided title or filename
                    'description': description # Use provided description
                }
                
                try:
                    with open(filepath, 'rb') as video_file:
                        files = {'source': video_file}
                        response = requests.post(upload_url, params=params, files=files)
                        response.raise_for_status() # Raise an exception for HTTP errors
                        
                        results.append(f"✅ Upload de '{filename}' réussi. Réponse: {response.json()}")
                except requests.exceptions.RequestException as e:
                    results.append(f"❌ Échec de l'upload de '{filename}': {e}")
            return "\n".join(results)

        upload_to_fb_button.click(
            fn=upload_videos_to_facebook,
            inputs=[selected_files_to_upload_state, video_title_input, video_description_input, fb_config_state],
            outputs=upload_output_text
        )
        back_from_upload_btn.click(lambda: gr.update(selected=4), None, tabs)
        proceed_to_fb_config_btn.click(lambda: gr.update(selected=6), None, tabs) # Navigate to FB config tab

        # Écouteurs d'événements pour le nouvel onglet "Configuration FB API"
        def save_facebook_config(access_token, page_id):
            config = {
                "access_token": access_token,
                "page_id": page_id
            }
            # In a real application, you would save this securely (e.g., to a config file)
            # For this example, we just update the state and return a message.
            print(f"Facebook API Configuration Saved: {config}")
            return config, "Configuration sauvegardée avec succès!"

        save_fb_config_button.click(
            fn=save_facebook_config,
            inputs=[fb_access_token_input, fb_page_id_input],
            outputs=[fb_config_state, fb_config_status_text]
        )
        # Update config inputs when state changes (e.g., on initial load or if config is loaded from file)
        fb_config_state.change(
            fn=lambda cfg: (cfg.get("access_token", ""), cfg.get("page_id", "")),
            inputs=fb_config_state,
            outputs=[fb_access_token_input, fb_page_id_input]
        )
        back_from_fb_config_btn.click(lambda: gr.update(selected=5), None, tabs)
        proceed_to_faq_btn.click(lambda: gr.update(selected=7), None, tabs) # Navigate to FAQ tab

        # Écouteurs d'événements pour le nouvel onglet "FAQ"
        back_from_faq_btn.click(lambda: gr.update(selected=6), None, tabs)

    print("Lancement de l'interface Gradio...")
    demo.launch(debug=True,share=True)

if __name__ == "__main__":
    create_gui()