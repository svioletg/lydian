import pytest

from lydian.cogs.voice import MediaItem, MediaQueue
from lydian.errors import MediaQueueLimitError


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
    queue.move(50, 20)
    assert queue[20].title == '20'
    with pytest.raises(IndexError):
        queue.move(200, 0)
    with pytest.raises(IndexError):
        queue.move(50, 200)
