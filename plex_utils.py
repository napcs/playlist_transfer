"""Shared utilities for Plex operations."""

from typing import List
from playlist_types import PlaylistItem


def populate_file_paths(items: List[PlaylistItem], plex_server) -> List[PlaylistItem]:
    """Populate file paths for playlist items by looking them up in server libraries."""
    libraries = plex_server.library.sections()
    print(f"Found {len(libraries)} libraries on server")
    
    for item in items:
        if item.file_path:  # Skip if already populated
            print(f"Item already has file path: {item.title}")
            continue
            
        print(f"Looking up file path for: {item}")
        print(f"  Item details: type={item.media_type}, show={item.show_title}, season={item.season}, episode={item.episode}")
        try:
            file_path = _find_file_path_in_libraries(item, libraries)
            if file_path:
                item.file_path = file_path
                print(f"  SUCCESS: Found file path: {file_path}")
            else:
                print(f"  FAILED: No file path found")
        except Exception as e:
            print(f"  ERROR finding file path: {e}")
    
    return items


def _find_file_path_in_libraries(item: PlaylistItem, libraries):
    """Find file path for a playlist item by searching through libraries."""
    for library in libraries:
        print(f"    Searching library: {library.title} (type: {library.type})")
        if library.type in ['movie', 'show', 'video']:
            try:
                # For TV episodes
                if item.media_type == 'episode' and item.show_title:
                    print(f"      Looking for episode: {item.show_title} S{item.season}E{item.episode}")
                    found_item = _find_episode_in_library(item, library)
                    if found_item:
                        print(f"      Found episode: {found_item.title}")
                        file_path = _extract_file_path_from_plex_item(found_item)
                        if file_path:
                            return file_path
                
                # For movies and other videos
                else:
                    print(f"      Looking for {item.media_type}: {item.title}")
                    found_item = _find_item_by_title_in_library(item, library)
                    if found_item:
                        print(f"      Found item: {found_item.title}")
                        file_path = _extract_file_path_from_plex_item(found_item)
                        if file_path:
                            return file_path
                        
            except Exception as e:
                print(f"      Library search error: {e}")
    
    return None


def _find_episode_in_library(item: PlaylistItem, library):
    """Find TV episode in library by show title, season, and episode."""
    if not (item.show_title and item.season and item.episode):
        return None
        
    show_results = library.search(title=item.show_title)
    for show in show_results:
        try:
            if hasattr(show, 'episode'):
                matching_episode = show.episode(season=item.season, episode=item.episode)
                if matching_episode:
                    return matching_episode
        except Exception:
            continue
    
    return None


def _find_item_by_title_in_library(item: PlaylistItem, library):
    """Find item in library by title match."""
    results = library.search(title=item.title)
    for result in results:
        if result.title == item.title:
            return result
    
    return None


def _extract_file_path_from_plex_item(plex_item):
    """Extract file path from a Plex item."""
    try:
        if hasattr(plex_item, 'media') and plex_item.media and len(plex_item.media) > 0:
            if hasattr(plex_item.media[0], 'parts') and len(plex_item.media[0].parts) > 0:
                return plex_item.media[0].parts[0].file
    except Exception:
        pass
    
    return None