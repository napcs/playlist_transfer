"""Data structures for playlist items."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PlaylistItem:
    """Universal playlist item that works across different platforms."""
    title: str
    file_path: Optional[str] = None
    year: Optional[int] = None
    duration: Optional[int] = None  # seconds
    
    # TV episode specific
    show_title: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    
    # Movie/video specific  
    media_type: str = "unknown"  # movie, episode, video, etc.
    
    def __str__(self):
        if self.show_title and self.season and self.episode:
            return f"{self.show_title} S{self.season:02d}E{self.episode:02d} - {self.title}"
        return self.title