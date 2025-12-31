"""Read playlists from Plex servers."""

from typing import List, Optional
from plexapi.myplex import MyPlexAccount
from playlist_types import PlaylistItem


def get_plex_account(username: str, password: str) -> Optional[MyPlexAccount]:
    """Get authenticated Plex account with 2FA support."""
    try:
        # Try basic auth first
        account = MyPlexAccount(username, password)
        print("Successfully authenticated with Plex.")
        return account
    except:
        # If that fails, prompt for 2FA code
        code = input("Enter your 2FA code: ")
        try:
            # Try with the 2FA code
            account = MyPlexAccount(username, password, code=code)
            print("Successfully authenticated with Plex.")
            return account
        except Exception as e:
            print(f"Authentication failed: {e}")
            return None


def get_plex_auth_token(username: str, password: str) -> Optional[str]:
    """Get auth token interactively with 2FA support."""
    try:
        # Try basic auth first
        account = MyPlexAccount(username, password)
        return account.authenticationToken
    except:
        # If that fails, prompt for 2FA code
        code = input("Enter your 2FA code: ")
        try:
            # Try with the 2FA code
            account = MyPlexAccount(username, password, code=code)
            return account.authenticationToken
        except Exception as e:
            print(f"Authentication failed: {e}")
            return None


def read_plex_playlist(username: str, password: str, server_name: str, playlist_name: str) -> List[PlaylistItem]:
    """Read a playlist from a Plex server and return universal playlist items."""
    account = get_plex_account(username, password)
    return read_plex_playlist_with_account(account, server_name, playlist_name)


def read_plex_playlist_with_account(account: MyPlexAccount, server_name: str, playlist_name: str) -> List[PlaylistItem]:
    """Read a playlist from a Plex server using an existing account."""

    # Connect to server
    print(f"Connecting to server '{server_name}'...")
    plex = account.resource(server_name).connect()
    print(f"Connected to server: {plex.friendlyName}")

    # Find the playlist
    playlists = plex.playlists()
    target_playlist = None

    for playlist in playlists:
        if playlist.title == playlist_name and playlist.playlistType == 'video':
            target_playlist = playlist
            break

    if not target_playlist:
        raise Exception(f"No video playlist named '{playlist_name}' found on server")

    print(f"Found playlist: {target_playlist.title} with {len(target_playlist.items())} items")

    # Convert Plex items to universal format
    items = []
    for plex_item in target_playlist.items():
        item = _convert_plex_item_to_universal(plex_item, plex)
        items.append(item)

    return items


def _convert_plex_item_to_universal(plex_item, plex_server) -> PlaylistItem:
    """Convert a Plex item to universal PlaylistItem format."""
    # Get basic info
    title = plex_item.title
    media_type = getattr(plex_item, 'type', 'unknown')
    year = getattr(plex_item, 'year', None)
    duration = getattr(plex_item, 'duration', None)
    
    # Get file path if available (same logic as original script)
    file_path = None
    try:
        if hasattr(plex_item, 'media') and plex_item.media and len(plex_item.media) > 0:
            if hasattr(plex_item.media[0], 'parts') and len(plex_item.media[0].parts) > 0:
                file_path = plex_item.media[0].parts[0].file
    except Exception:
        file_path = None

    # Handle TV episodes
    show_title = None
    season = None
    episode = None
    if media_type == 'episode' and hasattr(plex_item, 'grandparentTitle'):
        show_title = plex_item.grandparentTitle
        season = getattr(plex_item, 'parentIndex', None)
        episode = getattr(plex_item, 'index', None)

    return PlaylistItem(
        title=title,
        file_path=file_path,
        year=year,
        duration=duration,
        show_title=show_title,
        season=season,
        episode=episode,
        media_type=media_type
    )