"""Voice-related commands."""
import yt_dlp
from discord.ext import commands

from lydian.config import config
from lydian.const import DL_DIR

ytdl_format_options = {
    'format': 'bestaudio/best',
    'paths': {'home': str(DL_DIR)},
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'max_filesize': config.max_filesize,
}

ytdl = yt_dlp.YoutubeDL()

class VoiceCog(commands.Cog):
    """Voice-related commands."""

