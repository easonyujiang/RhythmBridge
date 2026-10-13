import argparse
import base64
import binascii
import csv
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from html import escape
from .catalog import CatalogStore, ROOT
from .matching import Matcher
from .parsers import decode_csv, parse_csv
from .scores import fetch_personal_scores, normalize_scores
from .online import load_online_playlist, identify_playlist
from .spotify_auth import SpotifyAuth

MAX_BODY = 15 * 1024 * 1024

def handler_class(store):
    spotify_auth = SpotifyAuth()
    state = {"catalog": None, "matcher": None}
    matcher_lock = threading.Lock()
    def matcher():
        catalog = store.snapshot()
        with matcher_lock:
            if state["catalog"] is not catalog:
                state.update(catalog=catalog, matcher=Matcher(catalog))
            return state["matcher"]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Do not log playlist contents, authentication materials, or uploaded filenames.
            pass

        def send(self, payload, status=200, mime="application/json; charset=utf-8"):
            data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def trusted_host(self):
            return self.headers.get("Host", "") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

        def do_GET(self):
            if not self.trusted_host():
                return self.send({"error": "无效主机。"}, 403)
            route = urlparse(self.path).path
            if route == '/api/spotify/status':
                return self.send(spotify_auth.status())
            if route == '/spotify/callback':
                query=parse_qs(urlparse(self.path).query)
                try:
                    spotify_auth.callback(query.get('state',[''])[0],query.get('code',[None])[0],query.get('error',[None])[0])
                    message='Spotify 授权完成。返回原页面刷新授权状态，再读取歌单。'
                except ValueError as error:
                    message=str(error)
                page=f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Spotify 授权结果</title><p>{escape(message)}</p><a href="/">返回 RhythmBridge</a></html>'
                return self.send(page.encode('utf8'),mime='text/html; charset=utf-8')
            if route == "/api/catalog":
                data = store.snapshot()
                counts = {g: sum(s["game"] == g and not s["disabled"] for s in data["songs"]) for g in ("maimai", "chunithm")}
                return self.send({"updated_at": data["updated_at"], "counts": counts, "sources": data["sources"], "scope": "当前国服目录"})
            static = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/online.js": ("online.js", "text/javascript"), "/spotify.js": ("spotify.js", "text/javascript"), "/extras.js": ("extras.js", "text/javascript"), "/styles.css": ("styles.css", "text/css"), "/sample.csv": ("../examples/sample.csv", "text/csv")}
            if route not in static:
                return self.send({"error": "页面不存在。"}, 404)
            filename, mime = static[route]
            return self.send((ROOT / "web" / filename).read_bytes(), mime=mime + "; charset=utf-8")

        def do_POST(self):
            if not self.trusted_host():
                return self.send({"error": "无效主机。"}, 403)
            origin = self.headers.get("Origin")
            if origin and origin not in (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"):
                return self.send({"error": "不接受跨站请求。"}, 403)
            if self.headers.get_content_type() != "application/json":
                return self.send({"error": "需要 JSON 请求。"}, 415)
            route = urlparse(self.path).path
            if route not in ("/api/inspect", "/api/analyze", "/api/refresh", "/api/scores/sync", "/api/scores/import", "/api/playlist", '/api/spotify/begin', '/api/spotify/clear'):
                return self.send({"error": "接口不存在。"}, 404)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    return self.send({"error": "文件过大或请求为空（最多 10 MB CSV）。"}, 413)
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("请求格式无效。")
                if route == '/api/spotify/begin':
                    return self.send(spotify_auth.begin(body.get('client_id'),f'http://127.0.0.1:{self.server.server_port}/spotify/callback'))
                if route == '/api/spotify/clear':
                    spotify_auth.clear()
                    return self.send(spotify_auth.status())
                if route == "/api/playlist":
                    token = spotify_auth.token() if identify_playlist(body.get('url'))['provider']=='spotify' else None
                    playlist = load_online_playlist(body.get('url'),token)
                    if not playlist['tracks']:
                        raise ValueError('歌单确认为空，没有可匹配的歌曲。')
                    result = matcher().analyze(playlist.pop('tracks'))
                    result.update(warnings=playlist.pop('warnings'), playlist=playlist)
                    return self.send(result)
                if route == "/api/scores/sync":
                    return self.send(fetch_personal_scores(body.get('game'), body.get('token')))
                if route == "/api/scores/import":
                    return self.send(normalize_scores(body.get('game'), body.get('payload')))
                if route == "/api/refresh":
                    try:
                        data = store.refresh()
                    except Exception:
                        return self.send({"error": "更新失败，保留原曲库。请检查网络后重试。"}, 502)
                    return self.send({"updated_at": data["updated_at"], "count": len(data["songs"])})
                if body.get("csv_base64"):
                    raw = base64.b64decode(body["csv_base64"], validate=True)
                    if len(raw) > 10 * 1024 * 1024:
                        return self.send({"error": "CSV 最多 10 MB。"}, 413)
                    text = decode_csv(raw)
                else:
                    text = body.get("csv", "")
                if not isinstance(text, str):
                    raise ValueError("CSV 内容必须是文本。")
                columns = body.get("columns")
                if columns is not None and not isinstance(columns, dict):
                    raise ValueError("列映射格式无效。")
                parsed = parse_csv(text, columns)
                if route == "/api/inspect":
                    return self.send({"headers": parsed["headers"], "columns": parsed["columns"], "count": len(parsed["tracks"]), "warnings": parsed["warnings"][:10]})
                if not parsed["columns"]["title"]:
                    raise ValueError("请先选择曲名列。")
                if not parsed["tracks"]:
                    raise ValueError("未找到有效歌曲记录。")
                result = matcher().analyze(parsed["tracks"])
                result.update(warnings=parsed["warnings"][:20], columns=parsed["columns"])
                self.send(result)
            except (ValueError, UnicodeError, binascii.Error, csv.Error) as error:
                self.send({"error": str(error)}, 400)
            except Exception:
                self.send({"error": "处理失败，请检查文件格式或查看本地测试。"}, 500)
    return Handler

def main():
    parser = argparse.ArgumentParser(description="RhythmBridge local web application")
    parser.add_argument("--port", type=int, default=8848)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_class(CatalogStore()))
    except OSError:
        parser.exit(1, "端口被占用，请使用 --port 8849 指定另一个端口。\n")
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"RhythmBridge 0.4.0  {url}\n关闭此窗口或按 Ctrl+C 停止。", flush=True)
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
