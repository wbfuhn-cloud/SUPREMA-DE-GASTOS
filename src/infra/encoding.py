import sys
import io


def force_utf8_encoding():
    """Force UTF-8 encoding for stdout and stderr."""
    for stream_name in ('stdout', 'stderr'):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        if getattr(stream, 'encoding', None) and stream.encoding.lower() != 'utf-8':
            if hasattr(stream, 'buffer'):
                setattr(sys, stream_name, io.TextIOWrapper(stream.buffer, encoding='utf-8'))
