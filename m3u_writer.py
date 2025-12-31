"""Write playlists to M3U format with path mapping support."""

import os
from typing import List, Dict, Set
from playlist_types import PlaylistItem
from plex_utils import populate_file_paths


def analyze_playlist_paths(items: List[PlaylistItem]) -> Dict[str, List[str]]:
    """Analyze playlist file paths to identify common base directories.
    
    Returns a dict mapping detected base paths to the files that use them.
    """
    if not items:
        return {}
    
    # Get all file paths that exist
    file_paths = [item.file_path for item in items if item.file_path]
    if not file_paths:
        return {}
    
    # Find common directory prefixes
    common_prefixes = _find_common_prefixes(file_paths)
    
    # Group files by their base directory
    path_groups = {}
    for prefix in common_prefixes:
        matching_files = [path for path in file_paths if path.startswith(prefix)]
        if matching_files:
            path_groups[prefix] = matching_files
    
    return path_groups


def _find_common_prefixes(file_paths: List[str]) -> List[str]:
    """Find common directory prefixes from a list of file paths."""
    if not file_paths:
        return []
    
    # Get all possible directory prefixes
    all_prefixes = set()
    for path in file_paths:
        # Handle Windows UNC paths manually since os.path.dirname doesn't work on Unix
        if path.startswith('\\\\'):
            # Windows UNC path - split manually
            parts = path.split('\\')
            # Rebuild path incrementally: \\server\share\folder1\folder2\...
            for i in range(3, len(parts)):  # Start after \\server\share
                prefix = '\\'.join(parts[:i]) + '\\'
                all_prefixes.add(prefix)
        else:
            # Unix-style path
            dir_path = os.path.dirname(path)
            while dir_path and dir_path != '/':
                all_prefixes.add(dir_path + '/')
                dir_path = os.path.dirname(dir_path)
    
    # Find prefixes that are used by multiple files or are significant
    significant_prefixes = []
    for prefix in all_prefixes:
        matching_files = [path for path in file_paths if path.startswith(prefix)]
        
        # Include if used by multiple files OR is a deep directory structure
        if len(matching_files) > 1 or prefix.count('/') >= 3:
            significant_prefixes.append(prefix)
    
    # Sort by length (longer prefixes first) to prioritize more specific paths
    significant_prefixes.sort(key=len, reverse=True)
    
    # Remove redundant prefixes (if a longer prefix covers the same files)
    filtered_prefixes = []
    for prefix in significant_prefixes:
        prefix_files = set(path for path in file_paths if path.startswith(prefix))
        
        # Check if any existing filtered prefix already covers these files
        is_redundant = False
        for existing_prefix in filtered_prefixes:
            existing_files = set(path for path in file_paths if path.startswith(existing_prefix))
            if prefix_files.issubset(existing_files):
                is_redundant = True
                break
        
        if not is_redundant:
            filtered_prefixes.append(prefix)
    
    return filtered_prefixes


def print_path_analysis(items: List[PlaylistItem]):
    """Print analysis of playlist paths for user review."""
    path_groups = analyze_playlist_paths(items)
    
    if not path_groups:
        print("No file paths found in playlist items.")
        return
    
    print("Detected base directories in playlist:")
    print("=" * 50)
    
    for base_path, files in path_groups.items():
        print(f"\nBase path: {base_path}")
        print(f"Files using this path: {len(files)}")
        
        # Show first few examples
        for i, file_path in enumerate(files[:3]):
            relative_path = file_path[len(base_path):]
            print(f"  Example: .../{relative_path}")
        
        if len(files) > 3:
            print(f"  ... and {len(files) - 3} more files")
    
    print("\n" + "=" * 50)
    print("You can map these base paths to your desired output format.")


def write_m3u_playlist_from_plex(playlist_name: str, items: List[PlaylistItem], 
                                output_path: str, plex_server, 
                                path_mappings: Dict[str, str] = None,
                                auto_detect_paths: bool = True) -> bool:
    """Write M3U playlist from Plex items, populating file paths as needed."""
    # Populate file paths from Plex server
    print("Populating file paths from Plex server...")
    items_with_paths = populate_file_paths(items.copy(), plex_server)
    
    # Use the standard M3U writer
    return write_m3u_playlist(playlist_name, items_with_paths, output_path, 
                             path_mappings, auto_detect_paths)


def write_m3u_playlist(playlist_name: str, items: List[PlaylistItem], 
                      output_path: str, path_mappings: Dict[str, str] = None,
                      auto_detect_paths: bool = True) -> bool:
    """Write a playlist to M3U format with configurable path mappings.
    
    Args:
        playlist_name: Name of the playlist
        items: List of playlist items to write
        output_path: Path where to save the M3U file
        path_mappings: Dict mapping server paths to desired output paths
        auto_detect_paths: Whether to auto-detect and prompt for path mappings
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Auto-detect paths if requested and no mappings provided
        if auto_detect_paths and not path_mappings:
            path_mappings = _get_interactive_path_mappings(items)
        
        if not path_mappings:
            path_mappings = {}
        
        # Generate M3U content
        m3u_lines = ["#EXTM3U"]
        m3u_lines.append(f"# Playlist: {playlist_name}")
        m3u_lines.append("")
        
        items_written = 0
        items_skipped = 0
        
        for item in items:
            if not item.file_path:
                print(f"Skipping item without file path: {item.title}")
                items_skipped += 1
                continue
            
            # Map the file path
            mapped_path = _map_file_path(item.file_path, path_mappings)
            
            # Generate EXTINF line with metadata
            duration = item.duration // 1000 if item.duration else -1  # Convert ms to seconds
            extinf_line = f"#EXTINF:{duration},{item.title}"
            
            m3u_lines.append(extinf_line)
            m3u_lines.append(mapped_path)
            m3u_lines.append("")
            items_written += 1
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(m3u_lines))
        
        print(f"Created M3U playlist: {output_path}")
        print(f"Items written: {items_written}")
        if items_skipped > 0:
            print(f"Items skipped (no file path): {items_skipped}")
        
        return True
        
    except Exception as e:
        print(f"Error creating M3U playlist: {e}")
        return False


def _get_interactive_path_mappings(items: List[PlaylistItem]) -> Dict[str, str]:
    """Interactively get path mappings from user."""
    path_groups = analyze_playlist_paths(items)
    
    if not path_groups:
        print("No file paths detected in playlist.")
        return {}
    
    print_path_analysis(items)
    print("\nPath Mapping Configuration:")
    print("-" * 30)
    
    mappings = {}
    for base_path in path_groups.keys():
        print(f"\nServer path: {base_path}")
        
        # Suggest a default mapping
        suggested = base_path.replace('/mnt/', '').replace('/media/', '').rstrip('/')
        default_mapping = f"smb://server/{suggested}/"
        
        user_input = input(f"Map to (default: {default_mapping}): ").strip()
        
        if user_input:
            # Ensure trailing slash for consistency
            if not user_input.endswith('/'):
                user_input += '/'
            mappings[base_path] = user_input
        else:
            mappings[base_path] = default_mapping
    
    return mappings


def _map_file_path(original_path: str, path_mappings: Dict[str, str]) -> str:
    """Map a file path using the provided mappings."""
    if not path_mappings:
        return original_path
    
    # Find the longest matching prefix
    matching_prefix = None
    for server_path in sorted(path_mappings.keys(), key=len, reverse=True):
        if original_path.startswith(server_path):
            matching_prefix = server_path
            break
    
    if matching_prefix:
        # Replace the server path prefix with the mapped path
        relative_path = original_path[len(matching_prefix):]
        mapped_path = path_mappings[matching_prefix] + relative_path
        return mapped_path
    
    # No mapping found, return original
    return original_path