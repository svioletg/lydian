import pytest

from lydian.cogs.voice import MediaItem, MediaQueue
from lydian.errors import MediaQueueLimitError


def test_media_queue_maxlen() -> None:
    queue = MediaQueue()
    queue.append(MediaItem('', ''))
    queue.extend(MediaItem('', '') for _ in range(1000))

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
