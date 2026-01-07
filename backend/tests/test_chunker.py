from app.indexing.chunker import SimpleChunker


def test_chunker_empty_returns_empty():
    chunker = SimpleChunker(window_size=3, overlap=1)
    assert chunker.chunk_file('', file_path='empty.txt') == []


def test_chunker_creates_overlapping_chunks():
    chunker = SimpleChunker(window_size=3, overlap=1)
    content = 'a\nb\nc\nd\ne'
    chunks = chunker.chunk_file(content, file_path='sample.txt')

    assert len(chunks) == 2
    assert chunks[0].content.split('\n')[-1] == 'c'
    assert chunks[1].content.split('\n')[0] == 'c'
    assert chunks[0].start_line == 0
    assert chunks[1].start_line == 2


def test_chunk_text_alias():
    chunker = SimpleChunker(window_size=2, overlap=0)
    chunks = chunker.chunk_text('x\ny')
    assert len(chunks) == 1
    assert chunks[0].content == 'x\ny'
