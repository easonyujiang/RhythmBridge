import json
import os
import threading
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {g: f"https://maimai.lxns.net/api/v0/{g}/song/list" for g in ("maimai", "chunithm")}
ALIASES = {g: f"https://maimai.lxns.net/api/v0/{g}/alias/list" for g in SOURCES}

def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "RhythmBridge/0.1 (local playlist lookup)"})
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read(10_000_001)
    if len(raw) > 10_000_000:
        raise ValueError("曲库响应过大。")
    return json.loads(raw)

def build_catalog(payloads, alias_payloads, timestamp):
    songs = []
    versions = {}
    for game, payload in payloads.items():
        if not isinstance(payload.get("songs"), list) or not payload["songs"]:
            raise ValueError(f"{game} 曲库格式不完整。")
        alias_map = {x["song_id"]: x["aliases"] for x in alias_payloads[game].get("aliases", [])}
        for s in payload["songs"]:
            # Special charts share the original work; exclude their duplicate IDs.
            if s["id"] >= (100000 if game == "maimai" else 8000):
                continue
            songs.append({"key": f'{game}:{s["id"]}', "game": game, "id": s["id"],
                "title": s["title"], "artist": s["artist"], "disabled": bool(s.get("disabled", False)),
                "version": s.get("version"), "genre": s.get("genre", ""),
                "aliases": alias_map.get(s["id"], []), "region": "cn",
                "url": f'https://maimai.lxns.net/songs?game={game}&song_id={s["id"]}'})
        versions[game] = payload.get("versions", [])
    return {"updated_at": timestamp, "sources": SOURCES, "versions": versions, "songs": songs}

class CatalogStore:
    def __init__(self, root=ROOT):
        self.root = root
        self.lock = threading.RLock()
        self.refresh_lock = threading.Lock()
        self.data = self._read()

    def _read(self):
        paths = [self.root / ".cache/catalog.json", self.root / "data/catalog.json"]
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("songs"):
                    return data
            except (OSError, ValueError):
                continue
        raise RuntimeError("缺少可用曲库，请检查 data/catalog.json。")

    def snapshot(self):
        with self.lock:
            return self.data

    def refresh(self):
        if not self.refresh_lock.acquire(blocking=False):
            raise ValueError("正在更新曲库，请稍后再试。")
        try:
            payloads = {g: get_json(url) for g, url in SOURCES.items()}
            alias_payloads = {g: get_json(url) for g, url in ALIASES.items()}
            data = build_catalog(payloads, alias_payloads, datetime.now(timezone.utc).isoformat())
            directory = self.root / ".cache"
            directory.mkdir(exist_ok=True)
            temporary = directory / "catalog.json.tmp"
            temporary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, directory / "catalog.json")
            with self.lock:
                self.data = data
            return data
        finally:
            self.refresh_lock.release()
