"""Playlist metadata adapters. Network destinations are fixed, never user URLs."""
import json
import re
import time
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from .parsers import Track, MAX_TRACKS


def identify_playlist(source):
    if not isinstance(source,str) or len(source)>4096:
        raise ValueError('请输入有效歌单链接。')
    url = urlsplit(source.strip())
    if url.scheme not in ('http','https') or url.username or url.password or url.port not in (None,80,443):
        raise ValueError('请使用音乐平台的标准歌单链接。')
    if url.hostname=='open.spotify.com':
        match=re.fullmatch(r'/(?:intl-[A-Za-z-]+/)?playlist/([A-Za-z0-9]{22})/?',url.path)
        if match:return {'provider':'spotify','id':match[1],'url':'https://open.spotify.com/playlist/'+match[1]}
    if url.hostname in ('music.youtube.com','www.youtube.com','youtube.com') and url.path in ('/playlist','/watch'):
        ids=parse_qs(url.query).get('list',[])
        if len(ids)==1 and re.fullmatch(r'[A-Za-z0-9_-]{10,150}',ids[0]):
            return {'provider':'youtube','id':ids[0],'url':'https://music.youtube.com/playlist?list='+ids[0]}
    if url.hostname in ('music.163.com','y.music.163.com'):
        path,query=url.path,url.query
        if url.fragment.startswith('/playlist?'):
            path,query=url.fragment.split('?',1)
        if path.rstrip('/')!='/playlist':
            raise ValueError('这是网易云链接，但不是标准歌单链接。')
        ids=parse_qs(query).get('id',[])
        if len(ids)==1 and re.fullmatch(r'[1-9]\d{0,19}',ids[0]):
            return {'provider':'netease','id':ids[0],'url':'https://music.163.com/playlist?id='+ids[0]}
    if url.hostname in ('y.qq.com','i.y.qq.com'):
        match=re.fullmatch(r'/n/ryqq/playlist/([1-9]\d{0,19})/?',url.path)
        ids=parse_qs(url.query).get('id',parse_qs(url.query).get('disstid',[]))
        sid=match[1] if match else ids[0] if len(ids)==1 and re.fullmatch(r'[1-9]\d{0,19}',ids[0]) and ('playlist' in url.path or 'taoge' in url.path) else None
        if sid:return {'provider':'qqmusic','id':sid,'url':'https://y.qq.com/n/ryqq/playlist/'+sid}
    raise ValueError('支持网易云、QQ、Spotify 与 YouTube 标准歌单链接；短链接请先在浏览器打开，再复制完整链接。')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def helper_json(path,params,game='netease'):
    port=8850 if game=='netease' else 8851
    label='网易云' if game=='netease' else 'QQ 音乐'
    url=f'http://127.0.0.1:{port}'+path+'?'+urlencode(params)
    try:
        with build_opener(NoRedirect()).open(Request(url,headers={'Accept':'application/json'}),timeout=30) as response:
            content=response.read(12*1024*1024+1)
        if len(content)>12*1024*1024:raise ValueError('歌单服务响应过大。')
        data=json.loads(content)
    except (HTTPError,URLError,OSError,TimeoutError):
        raise ValueError(f'无法读取{label}元数据。请先启动对应辅助服务，或检查平台是否需要登录。') from None
    except (json.JSONDecodeError,UnicodeError):
        raise ValueError('网易云服务返回无效响应。') from None
    if not isinstance(data,dict) or data.get('code')!=200:
        raise ValueError('网易云未成功返回歌单；可能失效、私密、需要登录或被限流。')
    return data


def playlist_ids(detail):
    playlist=detail.get('playlist')
    if not isinstance(playlist,dict):raise ValueError('歌单详情缺失。')
    ids=playlist.get('trackIds');count=playlist.get('trackCount')
    if not isinstance(ids,list) or type(count) is not int or count<0:
        raise ValueError('平台没有提供可核对的歌曲总数与完整 ID 列表。')
    if count>MAX_TRACKS:raise ValueError(f'单次最多读取 {MAX_TRACKS:,} 首。')
    if len(ids)!=count:raise ValueError('歌曲 ID 列表与歌单总数不一致，拒绝导入不完整歌单。')
    result=[]
    for item in ids:
        sid=item.get('id') if isinstance(item,dict) else None
        if type(sid) is not int or sid<=0:raise ValueError('歌单歌曲 ID 无效。')
        result.append(sid)
    return result,playlist


class NeteaseProvider:
    name='netease'

    def __init__(self,fetch=helper_json):self.fetch=fetch

    def load(self,source,**options):return self.load_playlist(source)['tracks']

    def load_playlist(self,source):
        identity=identify_playlist(source)
        if identity['provider']!=self.name:raise ValueError('歌单平台不匹配。')
        started=time.monotonic()
        ids,playlist=playlist_ids(self.fetch('/playlist/detail',{'id':identity['id']}))
        unique=list(dict.fromkeys(ids));songs={}
        for offset in range(0,len(unique),100):
            if time.monotonic()-started>180:raise ValueError('读取歌单超时，未导入部分结果。')
            batch=unique[offset:offset+100]
            response=self.fetch('/song/detail',{'ids':','.join(map(str,batch))})
            returned=response.get('songs')
            if not isinstance(returned,list):raise ValueError('歌曲详情列表缺失。')
            page={}
            for raw in returned:
                sid=raw.get('id') if isinstance(raw,dict) else None
                if type(sid) is not int or sid not in batch or sid in page:raise ValueError('歌曲详情包含重复或不属于本页的 ID。')
                if not isinstance(raw.get('name'),str) or not raw['name'].strip():raise ValueError('歌曲缺少曲名，未导入部分歌单。')
                page[sid]=raw
            if set(page)!=set(batch):raise ValueError('部分歌曲详情缺失，未导入不完整歌单。请登录后重试或导出 CSV。')
            songs.update(page)
        final_ids,_=playlist_ids(self.fetch('/playlist/detail',{'id':identity['id']}))
        if final_ids!=ids:raise ValueError('读取期间歌单发生变化，请重新导入。')
        tracks=[]
        for index,sid in enumerate(ids,1):
            raw=songs[sid]
            artists=raw.get('ar',raw.get('artists',[]))
            if not isinstance(artists,list):raise ValueError('歌手信息格式无效。')
            names=[a['name'] for a in artists if isinstance(a,dict) and isinstance(a.get('name'),str)]
            album=raw.get('al',raw.get('album',{}))
            album_name=album.get('name','') if isinstance(album,dict) else ''
            tracks.append(Track(str(index),raw['name'].strip(),', '.join(names),album_name if isinstance(album_name,str) else '',f'https://music.163.com/song?id={sid}',self.name))
        title=playlist.get('name','网易云歌单')
        return {'tracks':tracks,'title':title if isinstance(title,str) else '网易云歌单','source_url':identity['url'],'provider':self.name,'count':len(tracks),'complete':True,'warnings':[]}


def qq_json(path,params):return helper_json(path,params,'qqmusic')


class QQMusicProvider:
    name='qqmusic'
    def __init__(self,fetch=qq_json):self.fetch=fetch
    def load(self,source,**options):return self.load_playlist(source)['tracks']
    def load_playlist(self,source):
        identity=identify_playlist(source)
        if identity['provider']!=self.name:raise ValueError('歌单平台不匹配。')
        tracks=[];total=None;first=None;title='QQ 音乐歌单';seen=set();started=time.monotonic()
        for page in range(1,102):
            if time.monotonic()-started>180:raise ValueError('读取歌单超时，未导入部分结果。')
            data=self.fetch('/playlist/page',{'id':identity['id'],'page':page})
            count=data.get('total');songs=data.get('songs');more=data.get('hasmore')
            if type(count) is not int or count<0 or count>MAX_TRACKS or not isinstance(songs,list) or type(more) is not bool:
                raise ValueError('QQ 歌单未提供有效总数与分页信息。')
            if total is None:total=count;title=data.get('title',title)
            elif count!=total:raise ValueError('读取期间歌单总数变化，请重新导入。')
            signature=[]
            for song in songs:
                if not isinstance(song,dict) or type(song.get('id')) is not int or not isinstance(song.get('name'),str) or not song['name'].strip():raise ValueError('QQ 歌曲详情不完整。')
                artists=song.get('artists',[])
                if not isinstance(artists,list) or not all(isinstance(a,str) for a in artists):raise ValueError('QQ 歌手信息无效。')
                mid=song.get('mid','')
                if not isinstance(mid,str) or not re.fullmatch(r'[A-Za-z0-9]*',mid):raise ValueError('QQ 歌曲标识无效。')
                signature.append((song['id'],mid))
                album=song.get('album','')
                tracks.append(Track(str(len(tracks)+1),song['name'],', '.join(artists),album if isinstance(album,str) else '',f'https://y.qq.com/n/ryqq/songDetail/{mid}' if mid else '',self.name))
            signature=tuple(signature)
            if first is None:first=signature
            if signature and signature in seen:raise ValueError('QQ 接口重复返回同一页，未导入部分结果。')
            seen.add(signature)
            if len(tracks)>total or (more and not songs):raise ValueError('QQ 分页数量不一致，未导入部分结果。')
            if not more:
                if len(tracks)!=total:raise ValueError('QQ 返回数量小于歌单总数，未导入不完整歌单。')
                break
        else:raise ValueError('QQ 分页未结束，未导入部分结果。')
        latest=self.fetch('/playlist/page',{'id':identity['id'],'page':1})
        latest_songs=latest.get('songs')
        if latest.get('total')!=total or not isinstance(latest_songs,list) or tuple((s.get('id'),s.get('mid','')) for s in latest_songs)!=first:
            raise ValueError('读取期间 QQ 歌单发生变化，请重新导入。')
        return {'tracks':tracks,'title':title if isinstance(title,str) else 'QQ 音乐歌单','source_url':identity['url'],'provider':self.name,'count':len(tracks),'complete':True,'warnings':[]}


def load_online_playlist(url,spotify_token=None):
    provider=identify_playlist(url)['provider']
    if provider=='spotify':return SpotifyProvider().load_playlist(url,spotify_token)
    if provider=='youtube':return YouTubeProvider().load_playlist(url)
    return (NeteaseProvider() if provider=='netease' else QQMusicProvider()).load_playlist(url)


def global_json(path,body):
    try:
        request=Request('http://127.0.0.1:8852'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with build_opener(NoRedirect()).open(request,timeout=180) as response:raw=response.read(12*1024*1024+1)
        if len(raw)>12*1024*1024:raise ValueError('歌单响应过大。')
        payload=json.loads(raw)
    except (HTTPError,URLError,OSError,TimeoutError,json.JSONDecodeError,UnicodeError):
        raise ValueError('无法读取歌单，请启动 Spotify／YouTube 辅助服务并检查网络。') from None
    code=payload.get('code') if isinstance(payload,dict) else None
    if code!=200:
        messages={401:'Spotify 授权无效或已过期，请重新授权。',403:'平台拒绝读取；Spotify 开发模式需要读取自己的或协作的歌单，私密 YouTube 歌单需要授权。',404:'歌单不存在或无法访问。',429:'平台请求限流，请稍后重试。'}
        raise ValueError(messages.get(code,'歌单读取失败，未导入部分结果。请检查网络、辅助服务与歌单权限。'))
    data=payload.get('data')
    if not isinstance(data,dict):raise ValueError('歌单响应格式无效。')
    return data


class SpotifyProvider:
    name='spotify'
    def __init__(self,fetch=global_json):self.fetch=fetch
    def load(self,source,**options):return self.load_playlist(source,options.get('token'))['tracks']
    def load_playlist(self,source,token):
        identity=identify_playlist(source)
        if identity['provider']!=self.name:raise ValueError('歌单平台不匹配。')
        if not isinstance(token,str) or not token:raise ValueError('请先授权 Spotify，或导入 Exportify CSV。')
        body={'id':identity['id'],'token':token}
        initial=self.fetch('/spotify/detail',body);total=initial.get('total');snapshot=initial.get('snapshot_id')
        if type(total) is not int or not 0<=total<=MAX_TRACKS or not isinstance(snapshot,str) or not snapshot:
            raise ValueError('Spotify 未返回可读取的完整歌单；开发模式可能只允许自己的或协作歌单。')
        tracks=[];offset=0;episodes=0;unavailable=0;started=time.monotonic()
        while offset<total:
            if time.monotonic()-started>180:raise ValueError('Spotify 读取超时，未导入部分结果。')
            data=self.fetch('/spotify/page',{**body,'offset':offset})
            items=data.get('items')
            if data.get('total')!=total or data.get('offset')!=offset or not isinstance(items,list) or not 0<len(items)<=50 or offset+len(items)>total:
                raise ValueError('Spotify 分页或歌曲总数不一致，未导入部分结果。')
            for index,entry in enumerate(items,offset+1):
                item=entry.get('item',entry.get('track')) if isinstance(entry,dict) else None
                if not isinstance(item,dict) or not isinstance(item.get('name'),str) or not item['name'].strip():
                    raise ValueError('Spotify 包含无法读取的歌曲，未导入不完整歌单；请使用 CSV 导出核对。')
                if item.get('type')=='episode':episodes+=1;continue
                if item.get('type')!='track':raise ValueError('Spotify 返回非歌曲条目，无法完整解析。')
                artists=item.get('artists',[])
                if not isinstance(artists,list):raise ValueError('Spotify 歌手信息无效。')
                names=[a['name'] for a in artists if isinstance(a,dict) and isinstance(a.get('name'),str)]
                album=item.get('album',{});album_name=album.get('name','') if isinstance(album,dict) else ''
                sid=item.get('id');url='https://open.spotify.com/track/'+sid if isinstance(sid,str) and re.fullmatch(r'[A-Za-z0-9]{22}',sid) else ''
                if item.get('is_playable') is False:unavailable+=1
                tracks.append(Track(str(index),item['name'],', '.join(names),album_name if isinstance(album_name,str) else '',url,self.name))
            offset+=len(items)
            if bool(data.get('next'))!=(offset<total):raise ValueError('Spotify 分页提前终止或超出总数。')
        final=self.fetch('/spotify/detail',body)
        if final.get('snapshot_id')!=snapshot or final.get('total')!=total:raise ValueError('读取期间 Spotify 歌单发生变化，请重试。')
        warnings=[]
        if episodes:warnings.append(f'歌单共 {total} 个条目，其中 {episodes} 个播客条目未用于歌曲匹配。')
        if unavailable:warnings.append(f'{unavailable} 首歌曲在当前 Spotify 市场不可播放，仍保留其可读取的元数据。')
        return {'tracks':tracks,'title':initial.get('name') or 'Spotify 歌单','source_url':identity['url'],'provider':self.name,'count':len(tracks),'item_count':total,'skipped_episodes':episodes,'complete':True,'warnings':warnings}


class YouTubeProvider:
    name='youtube'
    def __init__(self,fetch=global_json):self.fetch=fetch
    def load(self,source,**options):return self.load_playlist(source)['tracks']
    def load_playlist(self,source):
        identity=identify_playlist(source)
        if identity['provider']!=self.name:raise ValueError('歌单平台不匹配。')
        data=self.fetch('/youtube/playlist',{'id':identity['id']})
        items=data.get('tracks');total=data.get('trackCount')
        if type(total) is not int or not 0<=total<=MAX_TRACKS or not isinstance(items,list) or len(items)!=total:
            raise ValueError('YouTube 未返回完整歌曲数量与列表；动态电台或缺失条目无法完整导入。')
        tracks=[];unavailable=0
        for index,item in enumerate(items,1):
            if not isinstance(item,dict) or not isinstance(item.get('title'),str) or not item['title'].strip():raise ValueError('YouTube 歌曲标题缺失，未导入不完整歌单。')
            vid=item.get('videoId')
            if not isinstance(vid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid):raise ValueError('YouTube 包含无法读取的视频条目，未导入部分结果。')
            artists=item.get('artists',[])
            if not isinstance(artists,list):raise ValueError('YouTube 歌手信息无效。')
            names=[a['name'] for a in artists if isinstance(a,dict) and isinstance(a.get('name'),str)]
            album=item.get('album');album_name=album.get('name','') if isinstance(album,dict) else ''
            if item.get('isAvailable') is False:unavailable+=1
            tracks.append(Track(str(index),item['title'],', '.join(names),album_name if isinstance(album_name,str) else '',f'https://music.youtube.com/watch?v={vid}',self.name))
        title=data.get('title');warnings=[f'{unavailable} 个视频不可播放，但保留可读取的元数据。'] if unavailable else []
        return {'tracks':tracks,'title':title if isinstance(title,str) else 'YouTube 歌单','source_url':identity['url'],'provider':self.name,'count':len(tracks),'complete':True,'warnings':warnings}
