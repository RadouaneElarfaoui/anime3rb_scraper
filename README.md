# Anime3rb Downloader

This project provides a Python utility for scraping anime information and downloading episodes from anime3rb.com. It includes both a command-line interface (CLI) and a Gradio-based graphical user interface (GUI).

## Features

*   **Anime Search**: Search for anime titles on anime3rb.com.
*   **Episode Listing**: Get a list of episodes for a selected anime.
*   **Direct Download Links**: Scrape direct video download URLs, prioritizing higher quality (1080p, 720p, 480p).
*   **Video Downloader**: Download anime episodes to your local `output/` directory.
*   **Facebook Upload (GUI only)**: Upload downloaded videos to a configured Facebook Page.
*   **Error Handling**: Robust error management and Cloudflare bypass using `cloudscraper`.

## Installation

1.  **Clone the repository**:

    ```bash
    git clone https://github.com/RadouaneElarfaoui/anime3rb_scraper.git
    cd anime3rb_scraper
    ```

2.  **Ensure you have Python 3.7 or later installed.**

3.  **Install the required dependencies**:

    ```bash
    pip install -e .
    ```

    This will install all necessary packages, including `cloudscraper`, `BeautifulSoup4`, `requests`, `tqdm`, and `gradio`.

## Usage

The project offers two main ways to interact: a command-line interface and a web-based GUI.

### Command-Line Interface (CLI)

You can use the `anime3rb_dl` command directly after installation.

```bash
# Example: Download an anime by URL
anime3rb_dl "https://anime3rb.com/titles/naruto"

# For more options, run:
anime3rb_dl --help
```

### Graphical User Interface (GUI)

Run the Gradio application to access a user-friendly web interface.

```bash
python src/anime3rb_downloader/gui_app.py
```

Then, open your web browser and navigate to the address provided by Gradio (usually `http://127.0.0.1:7860`).

## Project Structure

*   `src/anime3rb_downloader/cli_downloader.py`: Core CLI scraper and downloader logic.
*   `src/anime3rb_downloader/gui_app.py`: Gradio-based GUI application.
*   `src/notebooks/anime3rb_gui_colab.ipynb`: Jupyter Notebook for Google Colab integration.
*   `output/`: Directory where downloaded video files are stored.
*   `setup.py`: Package distribution configuration.
*   `requirements.txt`: Project dependencies.
*   `CONTRIBUTING.md`: Guidelines for contributing to the project.
*   `CODE_OF_CONDUCT.md`: Code of conduct for community participation.
*   `LICENSE`: Project license.

## Contributing

We welcome contributions! Please see `CONTRIBUTING.md` for guidelines on how to contribute to this project.

## Code of Conduct

Please review our `CODE_OF_CONDUCT.md` to understand the expected behavior in our community.

## Legal Disclaimer

This script is provided for educational and research purposes only. It is designed to interact respectfully with the website by adhering to delays and `robots.txt` policies. Any abusive use or use not in compliance with applicable laws is strictly prohibited. The author cannot be held responsible for any inappropriate use of this script.


