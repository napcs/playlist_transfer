# Plex Transfer

Transfer Plex playlists between servers and export to various formats.

## Installation

```bash
uv sync
```

## Usage

The script will prompt for your Plex password and handle 2FA if needed.

### Transfer between Plex servers

```bash
uv run python transfer_playlist.py transfer --username YOUR_USERNAME --source "Old Server" --dest "New Server" --playlist "Playlist Name"
```

### Export to M3U

```bash
uv run python transfer_playlist.py export --username YOUR_USERNAME --server "Server Name" --playlist "Playlist Name" --output playlist.m3u
```

### Import from M3U

```bash
uv run python transfer_playlist.py import --username YOUR_USERNAME --server "Server Name" --input playlist.m3u
```
