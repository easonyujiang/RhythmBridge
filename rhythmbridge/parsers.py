"""All playlist providers return the same Track model."""
import csv
import io
import re
from dataclasses import asdict, dataclass
from typing import Protocol

MAX_TRACKS = 10000
FIELDS = {
    "title": ["title", "track name", "song name", "name", "歌曲名", "歌曲名称", "歌名", "曲名", "标题"],
    "artist": ["artist", "artists", "artist name(s)", "artist names", "歌手", "歌手名", "歌手名称", "艺术家"],
    "album": ["album", "album name", "专辑", "专辑名"],
    "url": ["url", "track uri", "链接", "歌曲链接"],
    "index": ["index", "序号"],
}

@dataclass(frozen=True)
class Track:
    index: str
    title: str
    artist: str = ""
    album: str = ""
    url: str = ""
    source: str = "csv"

class PlaylistProvider(Protocol):
    """Future URL/API providers must expose this metadata-only contract."""
    name: str
    def load(self, source: str, **options) -> list[Track]: ...

def decode_csv(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030", "utf-16"):
        try:
            text = raw.decode(encoding)
            if "\x00" not in text:
                return text
        except UnicodeError:
            continue
    raise ValueError("无法识别文件编码，请另存为 UTF-8 CSV。")

def parse_csv(text: str, columns: dict | None = None) -> dict:
    text = text.lstrip("\ufeff")
    if not text.strip():
        raise ValueError("CSV 文件是空的。")
    try:
        dialect = csv.Sniffer().sniff(text[:32768], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text, newline=""), dialect=dialect)
    headers = reader.fieldnames or []
    if not headers or len(headers) != len(set(headers)):
        raise ValueError("请使用带有唯一列名的 CSV。")
    normalized = {re.sub(r"\s+", " ", h.strip().lower()): h for h in headers}
    mapping = {field: next((normalized[a] for a in aliases if a in normalized), "") for field, aliases in FIELDS.items()}
    for field, header in (columns or {}).items():
        if field in FIELDS:
            if header and header not in headers:
                raise ValueError(f"找不到列：{header}")
            mapping[field] = header
    tracks, warnings = [], []
    if mapping["title"]:
        for number, row in enumerate(reader, 1):
            if number > MAX_TRACKS:
                raise ValueError(f"单次最多导入 {MAX_TRACKS:,} 条记录。")
            if None in row:
                raise ValueError(f"第 {number + 1} 行字段数量超过表头，请检查 CSV 引号与分隔符。")
            value = lambda key: (row.get(mapping[key]) or "").strip() if mapping[key] else ""
            if not value("title"):
                warnings.append(f"跳过第 {number + 1} 行：曲名为空。")
                continue
            tracks.append(Track(value("index") or str(number), value("title"), value("artist"), value("album"), value("url")))
    return {"headers": headers, "columns": mapping, "tracks": tracks, "warnings": warnings}

class CSVProvider:
    name = "csv"
    def load(self, source: str, **options) -> list[Track]:
        parsed = parse_csv(source, options.get("columns"))
        if not parsed["columns"]["title"]:
            raise ValueError("未识别曲名列，请手动选择曲名列。")
        return parsed["tracks"]

PROVIDERS: dict[str, PlaylistProvider] = {"csv": CSVProvider()}
