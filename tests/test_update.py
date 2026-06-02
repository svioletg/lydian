from lydian.update import ReleaseComment

SAMPLE_BODY: str = """<!-- summary: Release summary. -->
<!-- important: This is crucial. -->
<!-- note: Keep this in mind. -->
<!-- warning: Watch out!
    This one's multi-line.
-->
<!-- security: There are important security fixes in this release. -->
<!-- other: This is not a valid ReleaseComment type and will be ignored. -->

https://github.com/svioletg/lydian/compare/v0.1.0..v0.2.0

### Added

- Lorem ipsum dolor sit amet, consectetur adipiscing elit
- Fusce pharetra lacus vel nulla sollicitudin, ut scelerisque mi vulputate

### Changed

- Ut consequat augue et magna posuere, a blandit diam scelerisque
- Etiam molestie metus a nisl feugiat dapibus
- Ut eu enim nec libero tincidunt aliquet

### Fixed

- Nullam eu nulla ac metus pellentesque tempor ac tempor justo
"""

def test_release_comment() -> None:
    comment = ReleaseComment('summary', 'Summary content.')
    assert comment.block(label='auto') == '[normal][SUMMARY] Summary content.[/]'
    assert comment.block(width=10, label='auto') == '[normal][SUMMARY]\nSummary\ncontent.[/]'
    assert comment.block(label='inline') == '[normal][SUMMARY] Summary content.[/]'
    assert comment.block(label='block') == '[normal][SUMMARY]\nSummary content.[/]'

def test_release_comment_parse() -> None:
    comments = ReleaseComment.from_body(SAMPLE_BODY)
    assert len(comments) == 5, comments  # noqa: PLR2004

    summary, important, note, warning, security = comments
    assert summary.type == 'summary'
    assert summary.content == 'Release summary.'
    assert important.type == 'important'
    assert important.content == 'This is crucial.'
    assert note.type == 'note'
    assert note.content == 'Keep this in mind.'
    assert warning.type == 'warning'
    assert warning.content == "Watch out!\n    This one's multi-line."
    assert security.type == 'security'
    assert security.content == 'There are important security fixes in this release.'
