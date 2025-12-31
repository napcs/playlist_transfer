"""Write playlists to Plex servers."""

from typing import List
from plexapi.myplex import MyPlexAccount
from playlist_types import PlaylistItem
from plex_reader import get_plex_account


def write_plex_playlist(username: str, password: str, server_name: str, playlist_name: str, items: List[PlaylistItem]) -> bool:
    """Write a playlist to a Plex server from universal playlist items."""
    account = get_plex_account(username, password)
    if not account:
        print("Failed to authenticate with Plex")
        return False
    
    return write_plex_playlist_with_account(account, server_name, playlist_name, items)


def write_plex_playlist_with_account(account: MyPlexAccount, server_name: str, playlist_name: str, items: List[PlaylistItem]) -> bool:
    """Write a playlist to a Plex server using an existing account."""
    # Connect to server
    print(f"Connecting to server '{server_name}'...")
    plex = account.resource(server_name).connect()
    print(f"Connected to server: {plex.friendlyName}")

    # Check if playlist already exists
    existing_playlists = plex.playlists()
    for playlist in existing_playlists:
        if playlist.title == playlist_name and playlist.playlistType == 'video':
            print(f"Found playlist: {playlist.title} with {len(playlist.items())} items on server. Stopping.")
            return False

    print(f"No video playlist named '{playlist_name}' found on server. We can proceed")

    # Find matching items on the server
    libraries = plex.library.sections()
    plex_items = []
    missing_items = []

    # Cache for show lookups to avoid repeated searches
    show_cache = {}

    for item in items:
        print(f"Looking for: {item}")
        found_item = _find_plex_item(item, libraries, show_cache)

        if found_item:
            plex_items.append(found_item)
        else:
            missing_items.append(str(item))
            print(f"  Not found")

    # Report missing items
    if missing_items:
        print(f"Items not found: {len(missing_items)}")
        print("The following items were not found on the server and won't be added to the playlist:")
        for item in missing_items:
            print(f"- {item}")

    # Ask user confirmation
    answer = input('Do you want to continue and make the playlist? ')
    if answer.lower().startswith("y"):
        new_playlist = plex.createPlaylist(playlist_name, items=plex_items)
        print(f"Created new playlist '{new_playlist.title}' with {len(plex_items)} items")
        print(f"Total items in original playlist: {len(items)}")
        print(f"Items found and added to new playlist: {len(plex_items)}")
        return True
    elif answer.lower().startswith("n"):
        print("sayonara, Robocop")
        return False

    return True


def _find_plex_item(item: PlaylistItem, libraries, show_cache: dict = None):
    """Find a universal PlaylistItem on the Plex server."""
    if show_cache is None:
        show_cache = {}

    # Try title-based matching first
    found_item = _find_by_title(item, libraries, show_cache)
    if found_item:
        return found_item

    # Try file path matching
    if item.file_path:
        found_item = _find_by_file_path(item, libraries)
        if found_item:
            return found_item

    return None


def _find_by_title(item: PlaylistItem, libraries, show_cache: dict = None):
    """Find item by title matching."""
    if show_cache is None:
        show_cache = {}

    for library in libraries:
        if library.type in ['movie', 'show', 'video']:
            try:
                # For TV episodes - only search in 'show' type libraries
                if item.media_type == 'episode' and item.show_title:
                    if library.type == 'show':
                        found_item = _find_episode(item, library, show_cache)
                        if found_item:
                            return found_item

                # For movies
                elif item.media_type == 'movie':
                    found_item = _find_movie(item, library)
                    if found_item:
                        return found_item

                # For other videos
                else:
                    found_item = _find_other_video(item, library)
                    if found_item:
                        return found_item

            except Exception as e:
                print(f"  Search error: {e}")

    return None


def _find_episode(item: PlaylistItem, library, show_cache: dict = None):
    """Find TV episode by show title, season, and episode number."""
    if show_cache is None:
        show_cache = {}

    # Create a cache key using library key and show title
    cache_key = (library.key, item.show_title)

    # Check if we've already looked up this show's episodes
    if cache_key not in show_cache:
        # Search for the show and cache all its episodes
        show_results = library.search(title=item.show_title)
        episode_dict = {}

        for show in show_results:
            if hasattr(show, 'episodes'):
                try:
                    # Fetch all episodes at once and build lookup dict
                    print(f"  Caching all episodes for '{show.title}'...")
                    all_episodes = show.episodes()
                    for ep in all_episodes:
                        season_num = getattr(ep, 'parentIndex', None)
                        episode_num = getattr(ep, 'index', None)
                        if season_num is not None and episode_num is not None:
                            episode_dict[(season_num, episode_num)] = ep
                    break
                except Exception as e:
                    print(f"  Error fetching episodes: {e}")

        show_cache[cache_key] = episode_dict

    # Look up the specific episode from cache
    episode_dict = show_cache[cache_key]
    if item.season and item.episode:
        episode_key = (item.season, item.episode)
        if episode_key in episode_dict:
            matching_episode = episode_dict[episode_key]
            print(f"  Found match using show/season/episode: {matching_episode.title}")
            return matching_episode

    return None


def _find_movie(item: PlaylistItem, library):
    """Find movie by exact title match."""
    results = library.search(title=item.title)
    for result in results:
        if result.type == 'movie' and result.title == item.title:
            print(f"  Found movie match: {result.title}")
            return result
    
    return None


def _find_other_video(item: PlaylistItem, library):
    """Find other video types by title match."""
    results = library.search(title=item.title)
    for result in results:
        if result.title == item.title:
            print(f"  Found match by title: {result.title}")
            return result
    
    return None


def _find_by_file_path(item: PlaylistItem, libraries):
    """Find item by matching file path."""
    if not item.file_path:
        return None
    
    try:
        print(f"  Searching by file path: {item.file_path}")
        
        for library in libraries:
            if library.type in ['movie', 'show', 'video']:
                for potential_match in library.all():
                    try:
                        if _has_matching_file_path(potential_match, item.file_path):
                            print(f"  Found match by file path: {potential_match.title}")
                            return potential_match
                    except Exception:
                        pass
    
    except Exception as e:
        print(f"  Path search error: {e}")
    
    return None


def _has_matching_file_path(potential_match, target_path):
    """Check if potential match has the target file path."""
    if not (hasattr(potential_match, 'media') and potential_match.media):
        return False
    
    for media in potential_match.media:
        for part in media.parts:
            if part.file == target_path:
                return True
    
    return False