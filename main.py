import os
import spotipy
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib3.util.retry import Retry
from spotipy.oauth2 import SpotifyOAuth
from requests.adapters import HTTPAdapter


load_dotenv()
client_id = os.getenv("SPOTIPY_CLIENT_ID")
client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
redirect_uri = os.getenv("SPOTIPY_REDIRECT_URI")


# Get valid year input
while True:
    try:
        year = int(input("Which year you want to travel to?(YYYY): "))
        now = datetime.now()
        if 1958 <= year <= now.year:
            break
        print(f"Please enter a year between 1958 and {now.year}")
    except ValueError:
        print("Invalid input. Please enter a 4-digit year.")


# Configure Billboard URL
date_obj = datetime.strptime(f"{year}-{now.month}-{now.day}", "%Y-%m-%d")
date = date_obj.strftime("%Y-%m-%d")
url = f"https://www.billboard.com/charts/hot-100/{date}/"


# Enhanced headers
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Referer": "https://www.billboard.com/",
}


def get_billboard_songs(url):
    # Setup session with retries
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))

    try:
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        songs = soup.select("h3.c-title.a-no-trucate")
        if not songs:
            # Fallback selector
            songs = soup.select("div > ul > li.lrv-u-width-100p > ul > li h3.c-title")

        titles = [song.get_text(strip=True) for song in songs]

        if not titles:
            print("No songs found. Saving HTML for debugging...")
            with open("billboard_debug.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            return None

        return titles[:100]

    except requests.exceptions.RequestException as e:
        print(f"Error accessing Billboard: {e}")
        return None



# Get songs from Billboard
songs_name = get_billboard_songs(url)
if not songs_name:
    print("Failed to retrieve songs from Billboard. Exiting.")
    exit(1)



# Spotify authentication
try:
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            scope="playlist-modify-private",
            redirect_uri=redirect_uri,
            client_id=client_id,
            client_secret=client_secret,
            show_dialog=True,
            cache_path="token.txt"
        )
    )
    user_id = sp.current_user()["id"]
except Exception as e:
    print(f"Spotify authentication failed: {e}")
    exit(1)



# Search for songs on Spotify
song_uris = []
missing_songs = []

for song in songs_name:
    try:
        result = sp.search(q=f"track:{song} year:{year}", type="track", limit=1)
        if not result["tracks"]["items"]:
            # Fallback without year filter
            result = sp.search(q=f"track:{song}", type="track", limit=1)

        if result["tracks"]["items"]:
            uri = result["tracks"]["items"][0]["uri"]
            song_uris.append(uri)
        else:
            missing_songs.append(song)
    except Exception as e:
        print(f"Error searching for {song}: {e}")
        missing_songs.append(song)

if missing_songs:
    print(f"\nCouldn't find {len(missing_songs)} songs on Spotify:")
    for song in missing_songs[:5]:
        print(f"- {song}")
    if len(missing_songs) > 5:
        print(f"... and {len(missing_songs) - 5} more")

if not song_uris:
    print("No songs found on Spotify to create playlist.")
    exit(1)



# Create playlist
try:
    playlist_name = f"{date} Billboard Top 100"
    playlist = sp.user_playlist_create(
        user=user_id,
        name=playlist_name,
        public=False,
        description=f"Top 100 songs from Billboard on {date}"
    )
    # Add songs in batches (Spotify limit is 100 per request)
    for i in range(0, len(song_uris), 100):
        batch = song_uris[i:i + 100]
        sp.playlist_add_items(playlist_id=playlist["id"], items=batch)

    print(f"\nSuccessfully created playlist: {playlist_name}")
    print(f"Playlist URL: {playlist['external_urls']['spotify']}")
    print(f"Added {len(song_uris)} songs to the playlist.")

except Exception as e:
    print(f"Error creating playlist: {e}")