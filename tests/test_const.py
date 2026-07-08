from lydian.const import EmojiStr


def test_emojistr_from_chars() -> None:
    assert EmojiStr.from_int(1234567890) == '1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣8️⃣9️⃣0️⃣'
