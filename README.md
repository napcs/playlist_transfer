# Plex Transfer

Transfer Plex playlists between servers and export to various formats.

## Installation

```bash
uv sync
```

## Usage

```bash
uv run python transfer_playlist.py --username YOUR_USERNAME --old-server "Old Server" --new-server "New Server" --playlist "Playlist Name"
```

The script will prompt for your Plex password and handle 2FA if needed.