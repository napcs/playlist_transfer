"""New modular playlist transfer script."""

import argparse
import getpass
from plex_reader import get_plex_account, read_plex_playlist_with_account
from plex_writer import write_plex_playlist_with_account


def transfer_plex_playlist(username, password, old_server_name, new_server_name, playlist_name):
    """Transfer a playlist between Plex servers using modular functions."""
    try:
        # Authenticate once
        account = get_plex_account(username, password)
        if not account:
            print("Failed to authenticate with Plex")
            return False
        
        # Read playlist from old server
        print(f"Reading playlist '{playlist_name}' from '{old_server_name}'...")
        items = read_plex_playlist_with_account(account, old_server_name, playlist_name)
        print(f"Read {len(items)} items from playlist")
        
        # Write playlist to new server
        print(f"Writing playlist '{playlist_name}' to '{new_server_name}'...")
        success = write_plex_playlist_with_account(account, new_server_name, playlist_name, items)
        
        return success
    
    except Exception as e:
        print(f"Error during transfer: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Transfer a Plex playlist between servers')
    parser.add_argument('--username', required=True, help='Plex username')
    parser.add_argument('--old-server', required=True, help='Name of the old Plex server')
    parser.add_argument('--new-server', required=True, help='Name of the new Plex server')
    parser.add_argument('--playlist', required=True, help='Name of the playlist to transfer')

    args = parser.parse_args()

    # Get password securely
    password = getpass.getpass("Enter your Plex password: ")

    transfer_plex_playlist(
        args.username,
        password,
        args.old_server,
        args.new_server,
        args.playlist
    )