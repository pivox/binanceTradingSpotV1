import zlib


def shard_id(symbol: str, shard_count: int) -> int:
    return zlib.crc32(symbol.encode("utf-8")) % shard_count
