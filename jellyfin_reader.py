"""Read playlists from Jellyfin (XML files or API)."""

import os
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional
from playlist_types import PlaylistItem


def read_jellyfin_xml_playlist(xml_path: str) -> Tuple[str, List[PlaylistItem]]:
    """Read a Jellyfin playlist XML file and return playlist name and items.

    Args:
        xml_path: Path to the Jellyfin playlist.xml file

    Returns:
        Tuple of (playlist_name, list of PlaylistItem objects)
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Extract playlist name from LocalTitle element
    name_el = root.find('LocalTitle')
    if name_el is not None and name_el.text:
        playlist_name = name_el.text.strip()
    else:
        playlist_name = os.path.splitext(os.path.basename(xml_path))[0]

    items = []
    playlist_items_el = root.find('PlaylistItems')
    if playlist_items_el is not None:
        for pi_el in playlist_items_el.findall('PlaylistItem'):
            path_el = pi_el.find('Path')
            if path_el is not None and path_el.text:
                file_path = path_el.text.strip()
                title = _derive_title_from_path(file_path)
                item = PlaylistItem(
                    title=title,
                    file_path=file_path,
                    media_type='video',
                )
                items.append(item)

    return playlist_name, items


def read_jellyfin_api_playlist(
    server_url: str, api_key: str, playlist_name: str
) -> Tuple[str, List[PlaylistItem]]:
    """Read a Jellyfin playlist via the REST API.

    Args:
        server_url: Base URL of the Jellyfin server (e.g. http://localhost:8096)
        api_key:    Jellyfin API key
        playlist_name: Name of the playlist to read

    Returns:
        Tuple of (playlist_name, list of PlaylistItem objects)
    """
    import urllib.request
    import json

    server_url = server_url.rstrip('/')
    headers = {'X-Emby-Token': api_key, 'Accept': 'application/json'}

    def get(path):
        req = urllib.request.Request(f"{server_url}{path}", headers=headers)
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())

    # Find the playlist by name
    data = get('/Playlists?Fields=Path')
    playlists = data.get('Items', [])
    target = next(
        (p for p in playlists if p.get('Name', '').lower() == playlist_name.lower()),
        None,
    )
    if not target:
        raise ValueError(f"Playlist '{playlist_name}' not found on Jellyfin server")

    playlist_id = target['Id']
    found_name = target['Name']
    print(f"Found playlist: {found_name} (id={playlist_id})")

    # Fetch playlist items with MediaSources so we get file paths
    items_data = get(
        f'/Playlists/{playlist_id}/Items?Fields=MediaSources,Path'
    )
    items = []
    for entry in items_data.get('Items', []):
        file_path = _extract_path_from_api_item(entry)
        title = entry.get('Name', '')
        media_type = entry.get('Type', 'Video').lower()
        duration_ticks = entry.get('RunTimeTicks')
        duration_ms = int(duration_ticks / 10000) if duration_ticks else None

        show_title = entry.get('SeriesName') or None
        season = entry.get('ParentIndexNumber') or None
        episode = entry.get('IndexNumber') or None
        year = entry.get('ProductionYear') or None

        item = PlaylistItem(
            title=title,
            file_path=file_path,
            year=year,
            duration=duration_ms,
            show_title=show_title,
            season=season,
            episode=episode,
            media_type='episode' if show_title else ('movie' if media_type == 'movie' else 'video'),
        )
        items.append(item)

    return found_name, items


def _extract_path_from_api_item(entry: dict) -> Optional[str]:
    """Pull a file path out of a Jellyfin API item dict."""
    # MediaSources is the most reliable place
    for src in entry.get('MediaSources') or []:
        path = src.get('Path')
        if path:
            return path
    # Fallback: top-level Path field
    return entry.get('Path') or None


def _derive_title_from_path(file_path: str) -> str:
    """Derive a display title from a file path."""
    if '\\' in file_path:
        filename = file_path.split('\\')[-1]
    else:
        filename = os.path.basename(file_path)
    return os.path.splitext(filename)[0]
