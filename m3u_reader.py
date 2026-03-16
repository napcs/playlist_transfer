"""Read playlists from M3U files."""

import os
import re
from typing import List, Tuple
from playlist_types import PlaylistItem


def read_m3u_playlist(file_path: str) -> Tuple[str, List[PlaylistItem]]:
    """Read an M3U playlist file and return playlist name and items.

    Args:
        file_path: Path to the M3U file

    Returns:
        Tuple of (playlist_name, list of PlaylistItem objects)
    """
    # Derive playlist name from filename
    playlist_name = os.path.splitext(os.path.basename(file_path))[0]

    items = []

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Parse the M3U file
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines and header
        if not line or line == '#EXTM3U':
            i += 1
            continue

        # Parse EXTINF line
        if line.startswith('#EXTINF:'):
            duration, title = _parse_extinf(line)

            # Next non-empty line should be the file path
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1

            if i < len(lines):
                file_path_entry = lines[i].strip()
                if not file_path_entry.startswith('#'):
                    item = PlaylistItem(
                        title=title,
                        file_path=file_path_entry,
                        duration=duration * 1000 if duration and duration > 0 else None,  # Convert to ms
                        media_type='video'
                    )
                    items.append(item)

        # Handle simple M3U (just file paths, no EXTINF)
        elif not line.startswith('#'):
            # This is a file path without EXTINF metadata
            title = _derive_title_from_path(line)
            item = PlaylistItem(
                title=title,
                file_path=line,
                media_type='video'
            )
            items.append(item)

        i += 1

    return playlist_name, items


def _parse_extinf(line: str) -> Tuple[int, str]:
    """Parse an EXTINF line and return duration and title.

    Format: #EXTINF:duration,title
    Examples:
        #EXTINF:1355, - Lisa's Wedding
        #EXTINF:1230,Simpsons - The Joy of Sect
        #EXTINF:-1,Unknown Title
    """
    # Remove the #EXTINF: prefix
    content = line[8:]

    # Split on first comma
    comma_idx = content.find(',')
    if comma_idx == -1:
        # No comma, try to parse as just duration
        try:
            return int(content.strip()), "Unknown"
        except ValueError:
            return -1, content.strip()

    duration_str = content[:comma_idx].strip()
    title = content[comma_idx + 1:].strip()

    # Parse duration
    try:
        duration = int(duration_str)
    except ValueError:
        duration = -1

    # Clean up title - remove leading " - " if present
    if title.startswith(' - '):
        title = title[3:]
    elif title.startswith('- '):
        title = title[2:]

    return duration, title


def _derive_title_from_path(file_path: str) -> str:
    """Derive a title from a file path when no EXTINF is available."""
    # Get the filename
    # Handle both Windows and Unix paths
    if '\\' in file_path:
        filename = file_path.split('\\')[-1]
    else:
        filename = os.path.basename(file_path)

    # Remove extension
    title = os.path.splitext(filename)[0]

    return title


def apply_path_mappings(items: List[PlaylistItem], path_mappings: dict) -> List[PlaylistItem]:
    """Apply path mappings to playlist items.

    Args:
        items: List of PlaylistItem objects
        path_mappings: Dict mapping source paths to destination paths

    Returns:
        List of PlaylistItem objects with mapped file paths
    """
    if not path_mappings:
        return items

    mapped_items = []
    for item in items:
        if item.file_path:
            mapped_path = _map_file_path(item.file_path, path_mappings)
            # Create a new item with the mapped path
            mapped_item = PlaylistItem(
                title=item.title,
                file_path=mapped_path,
                year=item.year,
                duration=item.duration,
                show_title=item.show_title,
                season=item.season,
                episode=item.episode,
                media_type=item.media_type
            )
            mapped_items.append(mapped_item)
        else:
            mapped_items.append(item)

    return mapped_items


def _map_file_path(original_path: str, path_mappings: dict) -> str:
    """Map a file path using the provided mappings."""
    if not path_mappings:
        return original_path

    # Find the longest matching prefix
    matching_prefix = None
    for source_path in sorted(path_mappings.keys(), key=len, reverse=True):
        if original_path.startswith(source_path):
            matching_prefix = source_path
            break

    if matching_prefix:
        # Replace the source path prefix with the mapped path
        relative_path = original_path[len(matching_prefix):]
        mapped_path = path_mappings[matching_prefix] + relative_path
        return mapped_path

    return original_path
