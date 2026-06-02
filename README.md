# Plex / Jellyfin Playlist Transfer

Transfer video playlists between Plex servers, Jellyfin, and M3U files.

> [!WARNING]
> Claude wrote most of this code. I designed the app, and it works for me. But I don't know Python and there are probably bugs.

## Installation

You need `uv` for this.

```bash
uv sync
```

## Commands

### Plex → Plex

```bash
uv run python transfer_playlist.py transfer \
  --username YOUR_USERNAME \
  --source "Old Server" \
  --dest "New Server" \
  --playlist "Playlist Name"
```

### Plex → M3U

```bash
uv run python transfer_playlist.py export \
  --username YOUR_USERNAME \
  --server "Server Name" \
  --playlist "Playlist Name" \
  --output playlist.m3u
```

`--playlist` is repeatable — pass it multiple times to export several playlists in one go (one Plex connection, output files named after each playlist). Add `--analyze-only` to inspect detected path prefixes without writing a file.

### M3U → Plex

```bash
uv run python transfer_playlist.py import \
  --username YOUR_USERNAME \
  --server "Server Name" \
  --input playlist.m3u \
  --input another.m3u
```

`--input` is repeatable — multiple files are imported with one Plex authentication.

### Plex → Jellyfin

```bash
uv run python transfer_playlist.py plex-to-jellyfin \
  --username YOUR_USERNAME \
  --plex-server "My Plex" \
  --playlist "Playlist Name" \
  --playlist "Another Playlist" \
  --server-url http://localhost:8096 \
  --api-key YOUR_API_KEY \
  --path-map /plex/media/=/jellyfin/media/
```

Plex authenticates once and the Jellyfin library is scanned once regardless of how many playlists you transfer.

### Jellyfin → Plex

```bash
uv run python transfer_playlist.py jellyfin-to-plex \
  --input "/jellyfin/data/playlists/Playlist Name/playlist.xml" \
  --username YOUR_USERNAME \
  --plex-server "My Plex" \
  --path-map /jellyfin/media/=/plex/media/
```

### M3U → Jellyfin

```bash
uv run python transfer_playlist.py jellyfin-import \
  --input playlist.m3u \
  --server-url http://localhost:8096 \
  --api-key YOUR_API_KEY \
  --path-map "\\\\oldserver\\share\\=/jellyfin/media/"
```

### Jellyfin → Jellyfin

```bash
uv run python transfer_playlist.py jellyfin-to-jellyfin \
  --src-server-url http://source:8096 \
  --src-api-key SOURCE_KEY \
  --playlist "Playlist Name" \
  --dest-server-url http://dest:8096 \
  --dest-api-key DEST_KEY
```

### Jellyfin → M3U

```bash
uv run python transfer_playlist.py jellyfin-export \
  --input "/jellyfin/data/playlists/Playlist Name/playlist.xml" \
  --output playlist.m3u
```

## Jellyfin

**Writing** to Jellyfin always uses the REST API. The tool scans your entire Jellyfin library once to build a path index, then matches each playlist item by path (exact, then case-insensitive, then unique filename). You'll need:
- `--server-url` — e.g. `http://jellyfin.local:8096`
- `--api-key` — generate one in **Jellyfin Dashboard → API Keys**
- `--user-id` — UUID of the playlist owner; if omitted the tool lists users and prompts you

**Reading** from Jellyfin (for `jellyfin-export` and `jellyfin-to-plex`) can use a `playlist.xml` file directly with `--input` (no auth needed), or the API with `--server-url`, `--api-key`, and `--playlist`.

## Path mapping

Plex and Jellyfin often mount media at different paths. Use `--path-map OLD=NEW` (repeatable) to translate prefixes:

```bash
--path-map /Volumes/Media/=/mnt/media/ \
--path-map /Volumes/TV/=/mnt/tv/
```

On export commands, if no `--path-map` is provided the tool will detect path prefixes and prompt interactively.

## Authentication

Plex commands prompt for your password at runtime. 2FA is supported — you'll be prompted for the code if needed.

## LICENSE

MIT. Use at your own risk though.
