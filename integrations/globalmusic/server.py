"""Optional MIT-licensed Spotipy / ytmusicapi metadata integration."""
import json
import logging
import re
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import requests
from spotipy import Spotify
from spotipy.exceptions import SpotifyException
from ytmusicapi import YTMusic

logging.disable(logging.CRITICAL)


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,data):
        raw=json.dumps(data,ensure_ascii=False).encode('utf8');self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
    def do_POST(self):
        if self.headers.get('Host') not in ('127.0.0.1:8852','localhost:8852') or self.headers.get('Origin'):
            return self.send({'code':403})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=16384 or self.headers.get_content_type()!='application/json':raise ValueError()
            body=json.loads(self.rfile.read(length));sid=body.get('id')
            if self.path=='/youtube/playlist' and isinstance(sid,str) and re.fullmatch(r'[A-Za-z0-9_-]{10,150}',sid):
                session=requests.Session()
                original=session.request
                started=time.monotonic()
                def request(method,url,**kwargs):
                    if time.monotonic()-started>150:raise TimeoutError()
                    kwargs.setdefault('timeout',25)
                    return original(method,url,**kwargs)
                session.request=request
                try:data=YTMusic(requests_session=session,language='en').get_playlist(sid,limit=10001)
                finally:session.close()
                return self.send({'code':200,'data':data})
            if self.path in ('/spotify/detail','/spotify/page') and isinstance(sid,str) and re.fullmatch(r'[A-Za-z0-9]{22}',sid):
                token=body.get('token')
                if not isinstance(token,str) or not token or len(token)>8192 or any(ord(c)<33 or ord(c)>126 for c in token):raise ValueError()
                client=Spotify(auth=token,requests_timeout=25,retries=0,status_retries=0)
                if self.path=='/spotify/detail':
                    data=client.playlist(sid)
                    items=data.get('items',data.get('tracks'))
                    return self.send({'code':200,'data':{'name':data.get('name'),'snapshot_id':data.get('snapshot_id'),'total':items.get('total') if isinstance(items,dict) else None}})
                offset=body.get('offset')
                if type(offset) is not int or not 0<=offset<=10000:raise ValueError()
                return self.send({'code':200,'data':client.playlist_items(sid,limit=50,offset=offset)})
            raise ValueError()
        except SpotifyException as error:self.send({'code':error.http_status or 502})
        except Exception:self.send({'code':502})


if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',8852),Handler)
    print('RhythmBridge Spotify / YouTube helper http://127.0.0.1:8852',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
