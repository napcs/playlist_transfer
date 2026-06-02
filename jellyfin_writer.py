"""Write playlists to Jellyfin via the REST API."""

import os
import urllib.request
import urllib.parse
import json
from typing import List, Dict, Optional, Callable
from playlist_types import PlaylistItem


def build_jellyfin_path_index(server_url: str, api_key: str) -> Dict[str, str]:
    """Scan the Jellyfin library and return a path → item ID index.

    Call this once when importing multiple playlists so the scan only happens once.
    Pass the result as path_index= to write_jellyfin_api_playlist.
    """
    get = _make_get(server_url, api_key)
    print("Scanning Jellyfin library to build path index...")
    index = _build_path_index(get)
    print(f"Indexed {len(index)} files\n")
    return index


def write_jellyfin_api_playlist(
    server_url: str,
    api_key: str,
    user_id: str,
    playlist_name: str,
    items: List[PlaylistItem],
    path_mappings: Dict[str, str] = None,
    path_index: Dict[str, str] = None,
    overwrite: bool = False,
) -> bool:
    """Create a Jellyfin playlist via the REST API.

    Resolves each playlist item to a Jellyfin item ID using path_index.
    If path_index is not provided, the library is scanned automatically.
    For multiple playlists, build the index once with build_jellyfin_path_index()
    and pass it here to avoid rescanning.
    """
    if path_mappings is None:
        path_mappings = {}

    get = _make_get(server_url, api_key)

    def post(path, body=None):
        data = json.dumps(body or {}).encode()
        req = urllib.request.Request(
            f"{server_url.rstrip('/')}{path}", data=data,
            headers={
                'X-Emby-Token': api_key,
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())

    # Check for an existing playlist with the same name
    existing_id = _find_playlist_id(get, playlist_name)
    if existing_id:
        if overwrite:
            print(f"Deleting existing playlist '{playlist_name}'...")
            _delete_item(server_url, api_key, existing_id)
        else:
            print(f"Playlist '{playlist_name}' already exists. Use --overwrite to replace it.")
            return False

    if path_index is None:
        print("Scanning Jellyfin library to build path index...")
        path_index = _build_path_index(get)
        print(f"Indexed {len(path_index)} files\n")

    item_ids = []
    missing = []

    for item in items:
        print(f"Looking up: {item}")
        mapped_path = _map_path(item.file_path, path_mappings) if item.file_path else None
        item_id = _resolve_id(path_index, item, mapped_path)
        if item_id:
            item_ids.append(item_id)
        else:
            missing.append(str(item))
            print(f"  Not found")

    if missing:
        print(f"\nItems not found ({len(missing)}):")
        for m in missing:
            print(f"  - {m}")

    answer = input(f"\nCreate playlist '{playlist_name}' with {len(item_ids)} items? [y/n] ")
    if not answer.lower().startswith('y'):
        return False

    result = post('/Playlists', {
        'Name': playlist_name,
        'Ids': item_ids,
        'UserId': user_id,
    })
    playlist_id = result.get('Id') or result.get('id')
    print(f"Created playlist '{playlist_name}' (id={playlist_id}) with {len(item_ids)} items")
    return True


def _find_playlist_id(get_fn: Callable, playlist_name: str) -> Optional[str]:
    """Return the ID of an existing Jellyfin playlist with the given name, or None."""
    try:
        data = get_fn('/Playlists')
        for p in data.get('Items', []):
            if p.get('Name', '').lower() == playlist_name.lower():
                return p['Id']
    except Exception:
        pass
    return None


def _delete_item(server_url: str, api_key: str, item_id: str):
    """Delete a Jellyfin item by ID."""
    req = urllib.request.Request(
        f"{server_url.rstrip('/')}/Items/{item_id}",
        headers={'X-Emby-Token': api_key},
        method='DELETE',
    )
    urllib.request.urlopen(req).close()


def _make_get(server_url: str, api_key: str) -> Callable:
    """Return a simple GET function for the given Jellyfin server."""
    base = server_url.rstrip('/')
    headers = {'X-Emby-Token': api_key, 'Accept': 'application/json'}

    def get(path):
        req = urllib.request.Request(f"{base}{path}", headers=headers)
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())

    return get


def _build_path_index(get_fn: Callable) -> Dict[str, str]:
    """Scan all Jellyfin media items and return a path → item ID dict.

    Indexes both the raw path and a normalized (lowercase, forward-slash) form
    so lookups work case-insensitively across platforms.
    """
    index = {}
    limit = 5000
    start = 0

    while True:
        data = get_fn(
            f'/Items?Recursive=true'
            f'&IncludeItemTypes=Movie,Episode,Video'
            f'&Fields=Path,MediaSources'
            f'&Limit={limit}&StartIndex={start}'
        )
        batch = data.get('Items', [])
        total = data.get('TotalRecordCount', 0)

        for entry in batch:
            item_id = entry.get('Id')
            if not item_id:
                continue
            # MediaSources carries the actual file path (handles multi-version items)
            for src in (entry.get('MediaSources') or []):
                _add_to_index(index, src.get('Path'), item_id)
            # Top-level Path as fallback
            _add_to_index(index, entry.get('Path'), item_id)

        start += len(batch)
        print(f"  Scanned {min(start, total)}/{total} items...", end='\r')
        if start >= total or not batch:
            break

    print()
    return index


def _add_to_index(index: Dict[str, str], path: Optional[str], item_id: str):
    if not path:
        return
    index[path] = item_id
    index[_normalize(path)] = item_id


def _resolve_id(
    path_index: Dict[str, str],
    item: PlaylistItem,
    mapped_path: Optional[str],
) -> Optional[str]:
    """Resolve a Jellyfin item ID from the path index."""

    if mapped_path:
        # Exact match
        if mapped_path in path_index:
            print(f"  Found by exact path")
            return path_index[mapped_path]

        # Normalized (case-insensitive) match
        norm = _normalize(mapped_path)
        if norm in path_index:
            print(f"  Found by normalized path")
            return path_index[norm]

        # Unique filename match — handles minor mount-point differences
        filename_norm = os.path.basename(norm)
        candidates = {
            iid for path, iid in path_index.items()
            if os.path.basename(path) == filename_norm
        }
        if len(candidates) == 1:
            print(f"  Found by unique filename")
            return next(iter(candidates))
        elif len(candidates) > 1:
            print(f"  Filename is ambiguous ({len(candidates)} matches) — skipping")

    print(f"  Not found")
    return None


def _normalize(path: str) -> str:
    return path.replace('\\', '/').lower()


def _map_path(original_path: str, path_mappings: Dict[str, str]) -> str:
    if not path_mappings:
        return original_path
    for src in sorted(path_mappings.keys(), key=len, reverse=True):
        if original_path.startswith(src):
            return path_mappings[src] + original_path[len(src):]
    return original_path
