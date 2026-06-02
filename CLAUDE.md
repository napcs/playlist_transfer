# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Transfer playlist between Plex servers
uv run python transfer_playlist.py transfer --username USER --source "Old Server" --dest "New Server" --playlist "Playlist Name"

# Export Plex playlist to M3U file
uv run python transfer_playlist.py export --username USER --server "Server" --playlist "Playlist Name" --output playlist.m3u

# Analyze playlist paths only (no export)
uv run python transfer_playlist.py export --username USER --server "Server" --playlist "Playlist Name" --analyze-only

# Import M3U playlist to Plex server
uv run python transfer_playlist.py import --username USER --server "Server" --input playlist.m3u

# Import M3U into Jellyfin (via API)
uv run python transfer_playlist.py jellyfin-import --input playlist.m3u --server-url http://localhost:8096 --api-key KEY

# Export Jellyfin playlist to M3U (from XML file)
uv run python transfer_playlist.py jellyfin-export --input "/jellyfin/data/playlists/My Playlist/playlist.xml" --output playlist.m3u

# Export Jellyfin playlist to M3U (via API)
uv run python transfer_playlist.py jellyfin-export --server-url http://localhost:8096 --api-key KEY --playlist "My Playlist" --output playlist.m3u

# Transfer Plex playlists to Jellyfin (via API) — --playlist is repeatable, index built once
uv run python transfer_playlist.py plex-to-jellyfin --username USER --plex-server "My Plex" --playlist "Playlist 1" --playlist "Playlist 2" --server-url http://localhost:8096 --api-key KEY

# Transfer Jellyfin playlist to Jellyfin (via API)
uv run python transfer_playlist.py jellyfin-to-jellyfin --src-server-url http://source:8096 --src-api-key KEY --playlist "My Playlist" --dest-server-url http://dest:8096 --dest-api-key KEY

# Transfer Jellyfin playlist to Plex (from XML, with path mapping)
uv run python transfer_playlist.py jellyfin-to-plex --input playlist.xml --username USER --plex-server "My Plex" --path-map /jellyfin/media/=/plex/media/

# Run tests
uv run pytest

# Format code
uv run black .

# Lint code
uv run ruff check .
```

## Architecture

The codebase transfers video playlists between Plex servers using a universal `PlaylistItem` dataclass as an intermediate format.

**Data flow:**
1. `plex_reader.py` - Authenticates with Plex (with 2FA support) and reads playlists into `PlaylistItem` objects
2. `plex_writer.py` - Matches items on destination server and creates the playlist
3. `m3u_writer.py` - Exports playlists to M3U format with path mapping
4. `m3u_reader.py` - Reads M3U files into `PlaylistItem` objects (supports Windows UNC and Unix paths)
5. `jellyfin_reader.py` - Reads Jellyfin playlist XML files or via REST API into `PlaylistItem` objects
6. `jellyfin_writer.py` - Creates Jellyfin playlists via REST API (builds a full path index of the library upfront, then resolves items by path); `--user-id` is auto-resolved from the API if omitted

**Key modules:**
- `playlist_types.py` - Defines `PlaylistItem` dataclass (the universal format)
- `plex_utils.py` - Shared utilities for populating file paths from Plex libraries
- `transfer_playlist.py` - Unified CLI with subcommands: transfer, export, import, jellyfin-import, jellyfin-export, plex-to-jellyfin, jellyfin-to-jellyfin, jellyfin-to-plex

**Jellyfin write strategy in jellyfin_writer.py:**
Writing to Jellyfin requires a server URL and API key. The writer scans the entire Jellyfin library once to build a path → item ID index, then resolves each playlist item with:
1. Exact path match
2. Normalized path match (case-insensitive, slash-unified)
3. Unique filename match (handles minor mount-point differences)

Reading from Jellyfin can use a `playlist.xml` file directly (no auth) or the API.

**Item matching strategy in plex_writer.py:**
1. For TV episodes: matches by show title + season + episode number (caches all episodes per show for efficiency)
2. For movies: exact title match
3. Fallback: file path matching (slower, iterates all library items)
