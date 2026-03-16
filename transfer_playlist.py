"""Plex playlist transfer tool - transfer, export, and import playlists."""

import argparse
import getpass
from plex_reader import get_plex_account, read_plex_playlist_with_account
from plex_writer import write_plex_playlist_with_account
from m3u_writer import write_m3u_playlist_from_plex, print_path_analysis, analyze_playlist_paths
from m3u_reader import read_m3u_playlist, apply_path_mappings


def cmd_transfer(args, password):
    """Transfer a playlist between Plex servers."""
    try:
        account = get_plex_account(args.username, password)
        if not account:
            print("Failed to authenticate with Plex")
            return False

        # Read playlist from source server
        print(f"Reading playlist '{args.playlist}' from '{args.source}'...")
        items = read_plex_playlist_with_account(account, args.source, args.playlist)
        print(f"Read {len(items)} items from playlist")

        # Write playlist to destination server
        print(f"Writing playlist '{args.playlist}' to '{args.dest}'...")
        success = write_plex_playlist_with_account(account, args.dest, args.playlist, items)

        return success

    except Exception as e:
        print(f"Error during transfer: {e}")
        return False


def cmd_export(args, password):
    """Export a Plex playlist to M3U format."""
    try:
        account = get_plex_account(args.username, password)
        if not account:
            print("Failed to authenticate with Plex")
            return False

        # Read playlist from Plex server
        print(f"Reading playlist '{args.playlist}' from server '{args.server}'...")
        items = read_plex_playlist_with_account(account, args.server, args.playlist)
        print(f"Found {len(items)} items in playlist")

        if args.analyze_only:
            print_path_analysis(items)
            return True

        # Generate M3U file
        print(f"\nGenerating M3U file: {args.output}")
        plex = account.resource(args.server).connect()
        success = write_m3u_playlist_from_plex(args.playlist, items, args.output, plex)

        if success:
            print(f"\nM3U file created successfully: {args.output}")
        else:
            print("Failed to create M3U file")

        return success

    except Exception as e:
        print(f"Error during export: {e}")
        return False


def cmd_import(args, password):
    """Import an M3U playlist to a Plex server."""
    try:
        # Read the M3U file
        print(f"Reading M3U file: {args.input}")
        detected_name, items = read_m3u_playlist(args.input)

        if not items:
            print("No items found in the M3U file.")
            return False

        # Use provided playlist name or the one from the file
        playlist_name = args.playlist_name or detected_name
        print(f"Found {len(items)} items in playlist '{playlist_name}'")

        # Get path mappings interactively
        path_mappings = _get_import_path_mappings(items)

        # Apply path mappings
        if path_mappings:
            print("\nApplying path mappings...")
            items = apply_path_mappings(items, path_mappings)

        # Authenticate with Plex
        print("\nAuthenticating with Plex...")
        account = get_plex_account(args.username, password)
        if not account:
            print("Failed to authenticate with Plex")
            return False

        # Write playlist to Plex server
        print(f"\nWriting playlist '{playlist_name}' to server '{args.server}'...")
        success = write_plex_playlist_with_account(account, args.server, playlist_name, items)

        return success

    except Exception as e:
        print(f"Error during import: {e}")
        return False


def _get_import_path_mappings(items):
    """Interactively get path mappings from user for import."""
    path_groups = analyze_playlist_paths(items)

    if not path_groups:
        print("No file paths detected in playlist.")
        return {}

    print_path_analysis(items)
    print("\nPath Mapping Configuration:")
    print("Map M3U paths to your Plex server paths.")
    print("-" * 50)

    mappings = {}
    for base_path in path_groups.keys():
        print(f"\nM3U path: {base_path}")

        user_input = input("Map to Plex server path (or press Enter to keep as-is): ").strip()

        if user_input:
            # Ensure trailing slash/backslash for consistency
            if not user_input.endswith('/') and not user_input.endswith('\\'):
                user_input += '/'
            mappings[base_path] = user_input

    return mappings


def main():
    parser = argparse.ArgumentParser(
        description='Plex playlist transfer tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Transfer between servers:
    %(prog)s transfer --username USER --source "Old Server" --dest "New Server" --playlist "My Playlist"

  Export to M3U:
    %(prog)s export --username USER --server "Server" --playlist "My Playlist" --output playlist.m3u

  Import from M3U:
    %(prog)s import --username USER --server "Server" --input playlist.m3u
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Transfer subcommand
    transfer_parser = subparsers.add_parser('transfer', help='Transfer playlist between Plex servers')
    transfer_parser.add_argument('--username', required=True, help='Plex username')
    transfer_parser.add_argument('--source', required=True, help='Source Plex server name')
    transfer_parser.add_argument('--dest', required=True, help='Destination Plex server name')
    transfer_parser.add_argument('--playlist', required=True, help='Name of the playlist to transfer')

    # Export subcommand
    export_parser = subparsers.add_parser('export', help='Export Plex playlist to M3U file')
    export_parser.add_argument('--username', required=True, help='Plex username')
    export_parser.add_argument('--server', required=True, help='Plex server name')
    export_parser.add_argument('--playlist', required=True, help='Name of the playlist to export')
    export_parser.add_argument('--output', default='playlist.m3u', help='Output M3U file path')
    export_parser.add_argument('--analyze-only', action='store_true', help='Only analyze paths, do not create M3U')

    # Import subcommand
    import_parser = subparsers.add_parser('import', help='Import M3U playlist to Plex server')
    import_parser.add_argument('--username', required=True, help='Plex username')
    import_parser.add_argument('--server', required=True, help='Plex server name')
    import_parser.add_argument('--input', required=True, help='Input M3U file path')
    import_parser.add_argument('--playlist-name', help='Custom playlist name (default: derived from filename)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Get password securely
    password = getpass.getpass("Enter your Plex password: ")

    # Dispatch to appropriate command
    if args.command == 'transfer':
        success = cmd_transfer(args, password)
    elif args.command == 'export':
        success = cmd_export(args, password)
    elif args.command == 'import':
        success = cmd_import(args, password)
    else:
        parser.print_help()
        return

    if success:
        print("\nOperation completed successfully!")
    else:
        print("\nOperation failed.")


if __name__ == "__main__":
    main()
