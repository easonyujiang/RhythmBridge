import difflib
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import asdict
from .catalog import ROOT

def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())

def base_title(title):
    return normalize(re.sub(r"[（(【\[].*?[）)】\]]", "", title))

def grams(text):
    width = 2 if len(text) < 7 else 3
    return {text[i:i+width] for i in range(max(1, len(text)-width+1))}

def artists_compatible(a, b):
    if not a or not b:
        return False
    split = lambda s: {normalize(x) for x in re.split(r"[,，、;；/×&]|\bfeat\.?\b", s, flags=re.I) if normalize(x)}
    aa, bb = split(a), split(b)
    return normalize(a) == normalize(b) or bool(aa & bb)

class Matcher:
    def __init__(self, catalog, rules=None):
        self.catalog = catalog
        self.songs = catalog["songs"]
        self.by_key = {s["key"]: s for s in self.songs}
        self.exact = defaultdict(set)
        self.aliases = defaultdict(set)
        self.inverted = defaultdict(set)
        self.names = {}
        for s in self.songs:
            key = s["key"]
            n = normalize(s["title"])
            self.names[key] = n
            for title in {n, base_title(s["title"])}:
                self.exact[title].add(key)
            for alias in s.get("aliases", []):
                self.aliases[normalize(alias)].add(key)
            for gram in grams(n):
                self.inverted[gram].add(key)
        self.rules = rules if rules is not None else json.loads((ROOT / "data/rules.json").read_text(encoding="utf-8"))
        self.rule_index = defaultdict(list)
        self.romaji = {}
        for rule in self.rules:
            self.romaji[normalize(rule["title"])] = rule["romaji"]
            for pair in rule["variants"]:
                self.rule_index[(normalize(pair["title"]), normalize(pair["artist"]))].append(rule)

    def match(self, track):
        n, base = normalize(track.title), base_title(track.title)
        accepted = {}
        for rule in self.rule_index.get((n, normalize(track.artist)), []):
            for key in rule["targets"]:
                if key in self.by_key:
                    accepted[key] = ("confirmed", "已核对的原作／翻唱／改编关系", rule["romaji"], rule["title"])
        for key in self.exact.get(n, set()) | self.exact.get(base, set()):
            s = self.by_key[key]
            if key not in accepted:
                same_artist = artists_compatible(track.artist, s["artist"])
                accepted[key] = ("confirmed" if same_artist else "candidate",
                    "曲名与作者对应" if same_artist else "曲名对应，但作者／翻唱关系待核对",
                    self.romaji.get(normalize(s["title"]), ""), s["title"])
        for key in self.aliases.get(n, set()) | self.aliases.get(base, set()):
            if key not in accepted:
                s = self.by_key[key]
                accepted[key] = ("candidate", "仅别名相同，不能证明是同一作品", self.romaji.get(normalize(s["title"]), ""), s["title"])
        if not accepted:
            scores = defaultdict(int)
            for gram in grams(base):
                for key in self.inverted.get(gram, []):
                    scores[key] += 1
            ranked = sorted(scores, key=scores.get, reverse=True)[:35]
            near = []
            for key in ranked:
                ratio = difflib.SequenceMatcher(None, base, self.names[key]).ratio()
                if ratio >= 0.76:
                    near.append((ratio, key))
            for ratio, key in sorted(near, reverse=True)[:4]:
                s = self.by_key[key]
                accepted[key] = ("candidate", "曲名相近，仅供人工核对", self.romaji.get(normalize(s["title"]), ""), s["title"])
        matches = []
        for key, (status, reason, romaji, work) in accepted.items():
            song = self.by_key[key]
            if song["disabled"]:
                status = "disabled" if status == "confirmed" else "candidate"
                reason += "；该游戏曲目已标记禁用"
            matches.append({**song, "status": status, "reason": reason, "romaji": romaji, "work": work})
        priority = {"confirmed": 0, "disabled": 1, "candidate": 2}
        matches.sort(key=lambda m: (priority[m["status"]], m["game"], m["id"]))
        status = min((m["status"] for m in matches), key=lambda x: priority[x]) if matches else "unmatched"
        return {**asdict(track), "status": status, "matches": matches,
            "romaji": matches[0]["romaji"] if matches else ""}

    def analyze(self, tracks):
        rows = [self.match(track) for track in tracks]
        stats = {"total": len(rows), **{s: sum(r["status"] == s for r in rows) for s in ("confirmed", "candidate", "disabled", "unmatched")}}
        works, ids = set(), {"maimai": set(), "chunithm": set()}
        for row in rows:
            for m in row["matches"]:
                if m["status"] == "confirmed":
                    works.add(normalize(m["work"]))
                    ids[m["game"]].add(m["id"])
        stats.update(works=len(works), maimai=len(ids["maimai"]), chunithm=len(ids["chunithm"]))
        return {"rows": rows, "stats": stats, "catalog_updated_at": self.catalog["updated_at"], "scope": "当前国服目录"}
