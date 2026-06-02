"""Plex playlist transfer tool - transfer, export, and import playlists."""

import argparse
import getpass
from plex_reader import get_plex_account, read_plex_playlist_with_account
from plex_writer import write_plex_playlist_with_account
from m3u_writer import write_m3u_playlist_from_plex, print_path_analysis, analyze_playlist_paths
from m3u_reader import read_m3u_playlist, apply_path_mappings
from jellyfin_reader import read_jellyfin_xml_playlist, read_jellyfin_api_playlist
from jellyfin_writer import write_jellyfin_api_playlist, build_jellyfin_path_index


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
        success = write_plex_playlist_with_account(account, args.dest, args.playlist, items, overwrite=args.overwrite)

        return success

    except Exception as e:
        print(f"Error during transfer: {e}")
        return False


def cmd_export(args, password):
    """Export one or more Plex playlists to M3U format."""
    try:
        account = get_plex_account(args.username, password)
        if not account:
            print("Failed to authenticate with Plex")
            return False

        plex = account.resource(args.server).connect()
        success = True

        for playlist_name in args.playlist:
            print(f"\nReading playlist '{playlist_name}' from server '{args.server}'...")
            items = read_plex_playlist_with_account(account, args.server, playlist_name)
            print(f"Found {len(items)} items in playlist")

            if args.analyze_only:
                print_path_analysis(items)
                continue

            # Use --output only when a single playlist is given; otherwise derive from name
            output = args.output if len(args.playlist) == 1 else f"{playlist_name}.m3u"
            print(f"Generating M3U file: {output}")
            ok = write_m3u_playlist_from_plex(playlist_name, items, output, plex)
            if ok:
                print(f"M3U file created successfully: {output}")
            else:
                print(f"Failed to create M3U file for '{playlist_name}'")
                success = False

        return success

    except Exception as e:
        print(f"Error during export: {e}")
        return False


def cmd_import(args, password):
    """Import one or more M3U playlists to a Plex server."""
    try:
        account = get_plex_account(args.username, password)
        if not account:
            print("Failed to authenticate with Plex")
            return False

        success = True
        for input_file in args.input:
            print(f"\nReading M3U file: {input_file}")
            detected_name, items = read_m3u_playlist(input_file)

            if not items:
                print("No items found in the M3U file.")
                success = False
                continue

            playlist_name = args.playlist_name if len(args.input) == 1 else detected_name
            playlist_name = playlist_name or detected_name
            print(f"Found {len(items)} items in playlist '{playlist_name}'")

            path_mappings = _get_import_path_mappings(items)
            if path_mappings:
                print("Applying path mappings...")
                items = apply_path_mappings(items, path_mappings)

            print(f"Writing playlist '{playlist_name}' to server '{args.server}'...")
            ok = write_plex_playlist_with_account(account, args.server, playlist_name, items, overwrite=args.overwrite)
            if not ok:
                success = False

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


def cmd_jellyfin_import(args):
    """Import one or more M3U playlists into Jellyfin via API."""
    try:
        path_mappings = _parse_path_maps(args.path_map)
        user_id = args.user_id or _prompt_jellyfin_user_id(args.server_url, args.api_key)
        path_index = build_jellyfin_path_index(args.server_url, args.api_key)

        success = True
        for input_file in args.input:
            print(f"\nReading M3U file: {input_file}")
            detected_name, items = read_m3u_playlist(input_file)

            if not items:
                print("No items found.")
                success = False
                continue

            playlist_name = args.playlist_name if len(args.input) == 1 else detected_name
            playlist_name = playlist_name or detected_name
            print(f"Found {len(items)} items in playlist '{playlist_name}'")

            ok = write_jellyfin_api_playlist(
                args.server_url, args.api_key, user_id, playlist_name, items,
                path_mappings, path_index=path_index, overwrite=args.overwrite
            )
            if not ok:
                success = False

        return success

    except Exception as e:
        print(f"Error during jellyfin-import: {e}")
        return False


def cmd_jellyfin_export(args):
    """Export a Jellyfin playlist to M3U format."""
    try:
        if args.api_key:
            print(f"Reading playlist '{args.playlist}' from Jellyfin via API...")
            playlist_name, items = read_jellyfin_api_playlist(
                args.server_url, args.api_key, args.playlist
            )
        else:
            print(f"Reading Jellyfin XML: {args.input}")
            playlist_name, items = read_jellyfin_xml_playlist(args.input)

        print(f"Found {len(items)} items in playlist '{playlist_name}'")

        path_mappings = _parse_path_maps(args.path_map)

        from m3u_writer import write_m3u_playlist
        output = args.output or f"{playlist_name}.m3u"
        return write_m3u_playlist(playlist_name, items, output, path_mappings, auto_detect_paths=not path_mappings)

    except Exception as e:
        print(f"Error during jellyfin-export: {e}")
        return False


def cmd_plex_to_jellyfin(args, password):
    """Transfer one or more Plex playlists to Jellyfin via API."""
    try:
        account = get_plex_account(args.username, password)
        if not account:
            print("Failed to authenticate with Plex")
            return False

        path_mappings = _parse_path_maps(args.path_map)
        user_id = args.user_id or _prompt_jellyfin_user_id(args.server_url, args.api_key)
        path_index = build_jellyfin_path_index(args.server_url, args.api_key)

        success = True
        for playlist_name in args.playlist:
            print(f"\nReading playlist '{playlist_name}' from Plex server '{args.plex_server}'...")
            items = read_plex_playlist_with_account(account, args.plex_server, playlist_name)
            print(f"Read {len(items)} items from playlist")

            ok = write_jellyfin_api_playlist(
                args.server_url, args.api_key, user_id, playlist_name, items,
                path_mappings, path_index=path_index, overwrite=args.overwrite
            )
            if not ok:
                success = False

        return success

    except Exception as e:
        print(f"Error during plex-to-jellyfin: {e}")
        return False


def cmd_jellyfin_to_jellyfin(args):
    """Transfer a playlist from one Jellyfin server to another."""
    try:
        if args.src_api_key:
            print(f"Reading playlist '{args.playlist}' from source Jellyfin via API...")
            playlist_name, items = read_jellyfin_api_playlist(
                args.src_server_url, args.src_api_key, args.playlist
            )
        else:
            print(f"Reading Jellyfin XML: {args.input}")
            playlist_name, items = read_jellyfin_xml_playlist(args.input)

        print(f"Found {len(items)} items in playlist '{playlist_name}'")

        path_mappings = _parse_path_maps(args.path_map)
        playlist_name = args.playlist_name or playlist_name
        user_id = args.user_id or _prompt_jellyfin_user_id(args.dest_server_url, args.dest_api_key)
        return write_jellyfin_api_playlist(
            args.dest_server_url, args.dest_api_key, user_id, playlist_name, items,
            path_mappings, overwrite=args.overwrite
        )

    except Exception as e:
        print(f"Error during jellyfin-to-jellyfin: {e}")
        return False


def cmd_jellyfin_to_plex(args, password):
    """Transfer a Jellyfin playlist to Plex."""
    try:
        if args.api_key:
            print(f"Reading playlist '{args.playlist}' from Jellyfin via API...")
            playlist_name, items = read_jellyfin_api_playlist(
                args.server_url, args.api_key, args.playlist
            )
        else:
            print(f"Reading Jellyfin XML: {args.input}")
            playlist_name, items = read_jellyfin_xml_playlist(args.input)

        print(f"Found {len(items)} items in playlist '{playlist_name}'")

        path_mappings = _parse_path_maps(args.path_map)
        if path_mappings:
            from m3u_reader import apply_path_mappings
            items = apply_path_mappings(items, path_mappings)

        playlist_name = args.playlist_name or playlist_name

        account = get_plex_account(args.username, password)
        if not account:
            print("Failed to authenticate with Plex")
            return False

        print(f"Writing playlist '{playlist_name}' to Plex server '{args.plex_server}'...")
        return write_plex_playlist_with_account(account, args.plex_server, playlist_name, items, overwrite=args.overwrite)

    except Exception as e:
        print(f"Error during jellyfin-to-plex: {e}")
        return False


def _parse_path_maps(path_map_list):
    """Parse a list of 'OLD=NEW' strings into a dict."""
    if not path_map_list:
        return {}
    mappings = {}
    for entry in path_map_list:
        if '=' not in entry:
            print(f"Warning: ignoring malformed --path-map '{entry}' (expected OLD=NEW)")
            continue
        src, _, dst = entry.partition('=')
        mappings[src] = dst
    return mappings


def _prompt_jellyfin_user_id(server_url, api_key):
    """Fetch Jellyfin users and return the appropriate user ID."""
    import urllib.request
    import json

    server_url = server_url.rstrip('/')
    req = urllib.request.Request(
        f"{server_url}/Users",
        headers={'X-Emby-Token': api_key, 'Accept': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            users = json.loads(resp.read().decode())
    except Exception as e:
        print(f"Could not fetch Jellyfin users: {e}")
        return input("Enter Jellyfin user UUID: ").strip()

    if len(users) == 1:
        u = users[0]
        print(f"Using Jellyfin user: {u['Name']} ({u['Id']})")
        return u['Id']

    print("Available Jellyfin users:")
    for i, u in enumerate(users):
        print(f"  {i + 1}) {u['Name']}  —  {u['Id']}")
    choice = input("Enter number or UUID: ").strip()
    if choice.isdigit():
        return users[int(choice) - 1]['Id']
    return choice


def main():
    parser = argparse.ArgumentParser(
        description='Plex / Jellyfin playlist transfer tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Transfer between Plex servers:
    %(prog)s transfer --username USER --source "Old Server" --dest "New Server" --playlist "My Playlist"

  Export Plex playlist to M3U:
    %(prog)s export --username USER --server "Server" --playlist "My Playlist" --output playlist.m3u

  Import M3U to Plex:
    %(prog)s import --username USER --server "Server" --input playlist.m3u

  Import M3U to Jellyfin (XML file):
    %(prog)s jellyfin-import --input playlist.m3u --output "My Playlist/playlist.xml"

  Import M3U to Jellyfin (API):
    %(prog)s jellyfin-import --input playlist.m3u --server-url http://localhost:8096 --api-key KEY

  Export Jellyfin playlist to M3U (XML file):
    %(prog)s jellyfin-export --input playlist.xml --output playlist.m3u

  Export Jellyfin playlist to M3U (API):
    %(prog)s jellyfin-export --server-url http://localhost:8096 --api-key KEY --playlist "My Playlist" --output out.m3u

  Transfer Plex playlist to Jellyfin (XML):
    %(prog)s plex-to-jellyfin --username USER --plex-server "My Plex" --playlist "My Playlist" --output "My Playlist/playlist.xml" --path-map /plex/media/=/jellyfin/media/

  Transfer Jellyfin playlist to Plex (XML):
    %(prog)s jellyfin-to-plex --input playlist.xml --username USER --plex-server "My Plex" --path-map /jellyfin/media/=/plex/media/
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # ── Plex-only commands ─────────────────────────────────────────────────────

    transfer_parser = subparsers.add_parser('transfer', help='Transfer playlist between Plex servers')
    transfer_parser.add_argument('--username', required=True)
    transfer_parser.add_argument('--source', required=True, help='Source Plex server name')
    transfer_parser.add_argument('--dest', required=True, help='Destination Plex server name')
    transfer_parser.add_argument('--playlist', required=True)
    transfer_parser.add_argument('--overwrite', action='store_true', help='Replace existing playlist')

    export_parser = subparsers.add_parser('export', help='Export Plex playlist(s) to M3U')
    export_parser.add_argument('--username', required=True)
    export_parser.add_argument('--server', required=True, help='Plex server name')
    export_parser.add_argument('--playlist', required=True, action='append',
                               help='Playlist name (repeatable)')
    export_parser.add_argument('--output', help='Output M3U path (single playlist only; default: <name>.m3u)')
    export_parser.add_argument('--analyze-only', action='store_true')

    import_parser = subparsers.add_parser('import', help='Import M3U playlist(s) to Plex')
    import_parser.add_argument('--username', required=True)
    import_parser.add_argument('--server', required=True, help='Plex server name')
    import_parser.add_argument('--input', required=True, action='append',
                               help='Input M3U file (repeatable)')
    import_parser.add_argument('--playlist-name', help='Override name (single file only)')
    import_parser.add_argument('--overwrite', action='store_true', help='Replace existing playlist')

    # ── Jellyfin commands ──────────────────────────────────────────────────────

    def _add_jellyfin_write_args(p):
        """Attach required Jellyfin API write arguments."""
        g = p.add_argument_group('Jellyfin API')
        g.add_argument('--server-url', required=True, help='Jellyfin server URL, e.g. http://localhost:8096')
        g.add_argument('--api-key', required=True, help='Jellyfin API key')
        g.add_argument('--user-id', help='Jellyfin user ID (UUID); prompted if omitted')
        p.add_argument(
            '--path-map',
            metavar='OLD=NEW',
            action='append',
            help='Path prefix mapping (repeatable), e.g. /plex/media/=/jellyfin/media/',
        )
        p.add_argument('--overwrite', action='store_true', help='Replace existing playlist')

    def _add_jellyfin_read_args(p, need_playlist=False):
        """Attach Jellyfin read arguments (XML or API)."""
        g = p.add_argument_group('Jellyfin API (optional — omit to use XML file mode)')
        g.add_argument('--server-url', help='Jellyfin server URL, e.g. http://localhost:8096')
        g.add_argument('--api-key', help='Jellyfin API key')
        if need_playlist:
            g.add_argument('--playlist', help='Jellyfin playlist name (required for API mode)')
        p.add_argument(
            '--path-map',
            metavar='OLD=NEW',
            action='append',
            help='Path prefix mapping (repeatable), e.g. /jellyfin/media/=/plex/media/',
        )

    ji = subparsers.add_parser('jellyfin-import', help='Import M3U playlist(s) into Jellyfin')
    ji.add_argument('--input', required=True, action='append', help='Input M3U file (repeatable)')
    ji.add_argument('--playlist-name', help='Override playlist name (single file only)')
    _add_jellyfin_write_args(ji)

    je = subparsers.add_parser('jellyfin-export', help='Export Jellyfin playlist to M3U')
    je.add_argument('--input', help='Input Jellyfin playlist.xml (XML mode)')
    je.add_argument('--output', help='Output M3U file path')
    _add_jellyfin_read_args(je, need_playlist=True)

    p2j = subparsers.add_parser('plex-to-jellyfin', help='Transfer Plex playlist(s) to Jellyfin')
    p2j.add_argument('--username', required=True, help='Plex username')
    p2j.add_argument('--plex-server', required=True, help='Plex server name')
    p2j.add_argument('--playlist', required=True, action='append', help='Playlist name (repeatable)')
    _add_jellyfin_write_args(p2j)

    j2j = subparsers.add_parser('jellyfin-to-jellyfin', help='Transfer playlist between Jellyfin servers')
    j2j.add_argument('--input', help='Source Jellyfin playlist.xml (XML mode)')
    j2j.add_argument('--playlist', help='Source playlist name (API mode)')
    j2j.add_argument('--playlist-name', help='Override playlist name on destination')
    sg = j2j.add_argument_group('Source Jellyfin (optional — omit to use XML file mode)')
    sg.add_argument('--src-server-url', help='Source Jellyfin server URL')
    sg.add_argument('--src-api-key', help='Source Jellyfin API key')
    dg = j2j.add_argument_group('Destination Jellyfin')
    dg.add_argument('--dest-server-url', required=True, help='Destination Jellyfin server URL')
    dg.add_argument('--dest-api-key', required=True, help='Destination Jellyfin API key')
    dg.add_argument('--user-id', help='Destination Jellyfin user ID (UUID); prompted if omitted')
    j2j.add_argument('--path-map', metavar='OLD=NEW', action='append',
                     help='Path prefix mapping (repeatable)')
    j2j.add_argument('--overwrite', action='store_true', help='Replace existing playlist')

    j2p = subparsers.add_parser('jellyfin-to-plex', help='Transfer Jellyfin playlist to Plex')
    j2p.add_argument('--username', required=True, help='Plex username')
    j2p.add_argument('--plex-server', required=True, help='Plex server name')
    j2p.add_argument('--input', help='Input Jellyfin playlist.xml (XML mode)')
    j2p.add_argument('--playlist-name', help='Override playlist name in Plex')
    j2p.add_argument('--overwrite', action='store_true', help='Replace existing playlist')
    _add_jellyfin_read_args(j2p, need_playlist=True)

    # ──────────────────────────────────────────────────────────────────────────

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    needs_plex_password = args.command in ('transfer', 'export', 'import', 'plex-to-jellyfin', 'jellyfin-to-plex')
    password = getpass.getpass("Enter your Plex password: ") if needs_plex_password else None

    if args.command == 'transfer':
        success = cmd_transfer(args, password)
    elif args.command == 'export':
        success = cmd_export(args, password)
    elif args.command == 'import':
        success = cmd_import(args, password)
    elif args.command == 'jellyfin-import':
        success = cmd_jellyfin_import(args)
    elif args.command == 'jellyfin-export':
        success = cmd_jellyfin_export(args)
    elif args.command == 'plex-to-jellyfin':
        success = cmd_plex_to_jellyfin(args, password)
    elif args.command == 'jellyfin-to-jellyfin':
        success = cmd_jellyfin_to_jellyfin(args)
    elif args.command == 'jellyfin-to-plex':
        success = cmd_jellyfin_to_plex(args, password)
    else:
        parser.print_help()
        return

    if success:
        print("\nOperation completed successfully!")
    else:
        print("\nOperation failed.")


if __name__ == "__main__":
    main()
