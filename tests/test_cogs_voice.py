from copy import deepcopy
from unittest.mock import MagicMock

import discord
import pytest

from lydian.cogs.voice import MediaItem, MediaQueue, VoteSkip
from lydian.errors import MediaQueueLimitError


def test_media_item_copy() -> None:
    item = MediaItem('Title', 'url', duration=1.5, thumbnail_url='thumburl', user_id=1234)
    copied = deepcopy(item)
    assert copied is not item
    assert copied == item

def test_media_queue_maxlen() -> None:
    queue = MediaQueue()
    many_items: list[MediaItem] = [MediaItem('', '') for _ in range(1000)]

    queue.append(MediaItem('', ''))
    queue.extend(many_items)

    queue = MediaQueue(maxlen=10)
    assert queue.maxlen

    queue.append(MediaItem('', ''))
    queue.extend(MediaItem('', '') for _ in range(9))
    assert len(queue) == queue.maxlen

    with pytest.raises(MediaQueueLimitError):
        queue.append(MediaItem('', ''))

    with pytest.raises(MediaQueueLimitError):
        queue.extend(MediaItem('', '') for _ in range(5))

    queue.clear()

    with pytest.raises(MediaQueueLimitError):
        queue.extend(MediaItem('', '') for _ in range(11))

    queue.clear()
    queue.extend_max(many_items)
    assert len(queue) == queue.maxlen

    queue.clear()
    queue.extendleft_max(many_items)
    assert len(queue) == queue.maxlen

def test_media_queue_move() -> None:
    queue = MediaQueue()
    queue.extend(MediaItem(str(n), str(n)) for n in range(100))
    assert queue[20].title == '20'
    queue.move(50, 20)
    assert queue[20].title == '50'
    queue.move(20, 50)
    assert queue[50].title == '50'
    with pytest.raises(IndexError):
        queue.move(200, 0)
    with pytest.raises(IndexError):
        queue.move(50, 200)

def test_vote_skip() -> None:
    mock_channel = MagicMock(discord.VoiceChannel)

    voteskip = VoteSkip(50, 'percentage')
    mock_channel.members.__len__.return_value = 0
    assert voteskip.remaining(mock_channel) == 0
    mock_channel.members.__len__.return_value = 1
    assert voteskip.remaining(mock_channel) == 1
    mock_channel.members.__len__.return_value = 2
    assert voteskip.remaining(mock_channel) == 1
    voteskip.voted.add(1)
    assert voteskip.remaining(mock_channel) == 0

    mock_channel.members.__len__.return_value = 3
    assert voteskip.remaining(mock_channel) == 1
    voteskip.voted.add(2)
    assert voteskip.remaining(mock_channel) == 0
    voteskip.voted.add(3)
    assert voteskip.remaining(mock_channel) == 0

    voteskip = VoteSkip(3, 'literal')
    mock_channel.members.__len__.return_value = 0
    assert voteskip.remaining(mock_channel) == 3  # noqa: PLR2004
    mock_channel.members.__len__.return_value = 1
    assert voteskip.remaining(mock_channel) == 3  # noqa: PLR2004
    mock_channel.members.__len__.return_value = 2
    assert voteskip.remaining(mock_channel) == 3  # noqa: PLR2004
    mock_channel.members.__len__.return_value = 3
    assert voteskip.remaining(mock_channel) == 3  # noqa: PLR2004

    voteskip.voted.add(1)
    assert voteskip.remaining(mock_channel) == 2  # noqa: PLR2004
    voteskip.voted.add(2)
    assert voteskip.remaining(mock_channel) == 1
    voteskip.voted.add(3)
    assert voteskip.remaining(mock_channel) == 0
