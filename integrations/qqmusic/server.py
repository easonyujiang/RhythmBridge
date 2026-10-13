"""Original metadata adapter for optional GPL-3.0-or-later QQMusicApi."""
import asyncio
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from qqmusic_api import Client


async def read_page(sid,page):
    async with Client() as client:
        result=await client.songlist.get_detail(sid,num=100,page=page)
        if result.code or result.subcode:raise ValueError('QQ rejected request')
        return {'code':200,'total':result.total,'hasmore':bool(result.hasmore),'title':result.info.title,
                'songs':[{'id':s.id,'mid':s.mid,'name':s.name,'artists':[a.name for a in s.singer],'album':s.album.name} for s in result.songs]}


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,code,data):
        raw=json.dumps(data,ensure_ascii=False).encode('utf8');self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if self.headers.get('Host') not in ('127.0.0.1:8851','localhost:8851') or self.headers.get('Origin'):
            return self.send(403,{'error':'Local backend requests only'})
        url=urlsplit(self.path);query=parse_qs(url.query)
        sid=query.get('id',[''])[0];page=query.get('page',[''])[0]
        if url.path!='/playlist/page' or not re.fullmatch(r'[1-9]\d{0,19}',sid) or not re.fullmatch(r'[1-9]\d{0,2}',page):
            return self.send(400,{'error':'Invalid playlist request'})
        try:self.send(200,asyncio.run(asyncio.wait_for(read_page(int(sid),int(page)),timeout=25)))
        except Exception:self.send(502,{'error':'QQ metadata unavailable; playlist may require login'})


if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',8851),Handler)
    print('RhythmBridge QQ metadata helper http://127.0.0.1:8851',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
