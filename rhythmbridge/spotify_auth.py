"""Single-user local PKCE authorization; no token files or client secret."""
import base64
import hashlib
import json
import re
import secrets
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError,URLError


def exchange_token(params):
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    try:
        request=Request('https://accounts.spotify.com/api/token',data=urlencode(params).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
        with build_opener(NoRedirect()).open(request,timeout=25) as response:raw=response.read(1024*1024+1)
        if len(raw)>1024*1024:raise ValueError('Spotify 授权响应过大。')
        payload=json.loads(raw)
    except (HTTPError,URLError,OSError,TimeoutError,json.JSONDecodeError,UnicodeError):
        raise ValueError('Spotify 授权失败，请检查应用配置、网络和账号权限后重试。') from None
    if not isinstance(payload,dict):raise ValueError('Spotify 授权响应格式无效。')
    token=payload.get('access_token');expires=payload.get('expires_in');kind=payload.get('token_type')
    if not isinstance(token,str) or not token or type(expires) is not int or expires<=0 or not isinstance(kind,str) or kind.lower()!='bearer':
        raise ValueError('Spotify 授权未返回有效凭证。')
    return payload


class SpotifyAuth:
    def __init__(self,exchange=exchange_token):
        self.lock=threading.Lock();self.exchange=exchange;self.pending=None;self.credentials=None;self.generation=0

    def begin(self,client_id,redirect_uri):
        if not isinstance(client_id,str) or not re.fullmatch(r'[A-Za-z0-9]{32}',client_id):raise ValueError('请输入 Spotify 开发者应用的 Client ID（32 位字母数字）。')
        verifier=secrets.token_urlsafe(64);state=secrets.token_urlsafe(32)
        challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        with self.lock:
            self.generation+=1
            self.pending={'state':state,'verifier':verifier,'client_id':client_id,'redirect_uri':redirect_uri,'created':time.monotonic(),'generation':self.generation}
        params={'client_id':client_id,'response_type':'code','redirect_uri':redirect_uri,'scope':'playlist-read-private playlist-read-collaborative','state':state,'code_challenge_method':'S256','code_challenge':challenge}
        return {'url':'https://accounts.spotify.com/authorize?'+urlencode(params),'redirect_uri':redirect_uri}

    def callback(self,state,code=None,error=None):
        with self.lock:
            pending=self.pending
            if not pending or not isinstance(state,str) or not secrets.compare_digest(state,pending['state']) or time.monotonic()-pending['created']>600:
                raise ValueError('授权状态无效或已过期，请重新发起授权。')
            self.pending=None
        if error:raise ValueError('Spotify 授权已取消，保留此前的授权状态。')
        if not isinstance(code,str) or not code or len(code)>4096:raise ValueError('Spotify 未返回授权码。')
        payload=self.exchange({'grant_type':'authorization_code','code':code,'redirect_uri':pending['redirect_uri'],'client_id':pending['client_id'],'code_verifier':pending['verifier']})
        with self.lock:
            if self.generation!=pending['generation']:raise ValueError('该次授权已被清除或替换，请重新授权。')
            self.credentials={'token':payload['access_token'],'refresh':payload.get('refresh_token'),'expires':time.monotonic()+payload['expires_in'],'client_id':pending['client_id']}

    def token(self):
        with self.lock:
            creds=self.credentials
            if not creds:raise ValueError('请先在本地页面授权 Spotify，或导入 Exportify CSV。')
            if creds['expires']-time.monotonic()>60:return creds['token']
            if not creds.get('refresh'):raise ValueError('Spotify 授权已过期，请重新授权。')
            payload=self.exchange({'grant_type':'refresh_token','refresh_token':creds['refresh'],'client_id':creds['client_id']})
            creds.update(token=payload['access_token'],expires=time.monotonic()+payload['expires_in'],refresh=payload.get('refresh_token',creds['refresh']))
            return creds['token']

    def status(self):
        with self.lock:
            if self.pending and time.monotonic()-self.pending['created']>600:self.pending=None
            return {'connected':bool(self.credentials),'pending':bool(self.pending)}

    def clear(self):
        with self.lock:self.pending=None;self.credentials=None;self.generation+=1
