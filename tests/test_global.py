import base64
import hashlib
import threading
import unittest
from urllib.parse import parse_qs,urlsplit
from rhythmbridge.online import SpotifyProvider,YouTubeProvider,identify_playlist
from rhythmbridge.spotify_auth import SpotifyAuth


SP='https://open.spotify.com/playlist/'+'a'*22
YT='https://music.youtube.com/playlist?list='+'PL'+'a'*32


class GlobalProviderTests(unittest.TestCase):
    def test_urls(self):
        self.assertEqual(identify_playlist(SP)['provider'],'spotify')
        self.assertEqual(identify_playlist(YT)['provider'],'youtube')
        self.assertEqual(identify_playlist(SP.replace('/playlist/','/intl-zh/playlist/'))['id'],'a'*22)

    def spotify_fetch(self,change=False,missing=False,episode=False,old=False):
        calls=[]
        def fetch(path,body):
            calls.append((path,body))
            if path.endswith('detail'):return {'name':'Test','total':53,'snapshot_id':'changed' if change and len(calls)>1 else 'original'}
            offset=body['offset'];items=[]
            for i in range(offset,min(offset+50,53)):
                track={'id':'b'*22,'name':f'Song {i}','type':'episode' if episode and i==52 else 'track','artists':[{'name':'Artist'}],'album':{'name':'Album'}}
                items.append({'track' if old else 'item':None if missing and i==0 else track})
            return {'items':items,'total':53,'offset':offset,'next':'next' if offset==0 else None}
        return fetch,calls

    def test_spotify_pagination_and_order(self):
        fetch,calls=self.spotify_fetch();r=SpotifyProvider(fetch).load_playlist(SP,'fixture')
        self.assertEqual(len(r['tracks']),53);self.assertEqual(r['tracks'][-1].title,'Song 52')
        self.assertEqual([b['offset'] for p,b in calls if p.endswith('page')],[0,50])

    def test_spotify_legacy_field_and_episode(self):
        fetch,_=self.spotify_fetch(episode=True,old=True);r=SpotifyProvider(fetch).load_playlist(SP,'fixture')
        self.assertEqual(r['skipped_episodes'],1);self.assertEqual(len(r['tracks']),52);self.assertTrue(r['warnings'])

    def test_spotify_missing_and_snapshot_change(self):
        for options in ({'change':True},{'missing':True}):
            fetch,_=self.spotify_fetch(**options)
            with self.assertRaises(ValueError):SpotifyProvider(fetch).load_playlist(SP,'fixture')

    def test_spotify_needs_auth(self):
        with self.assertRaisesRegex(ValueError,'授权'):SpotifyProvider().load_playlist(SP,None)

    def youtube_data(self):return {'title':'Test','trackCount':2,'tracks':[{'title':'Song','videoId':'a'*11,'artists':[],'album':None},{'title':'Song','videoId':'a'*11,'artists':[{'name':'Artist'}],'isAvailable':False}]}

    def test_youtube_duplicate_and_unavailable(self):
        r=YouTubeProvider(lambda *args:self.youtube_data()).load_playlist(YT)
        self.assertEqual(len(r['tracks']),2);self.assertEqual(r['tracks'][0].artist,'');self.assertTrue(r['warnings'])

    def test_youtube_partial_and_dynamic_rejected(self):
        for count in (None,3,10001):
            d=self.youtube_data();d['trackCount']=count
            with self.assertRaises(ValueError):YouTubeProvider(lambda *args:d).load_playlist(YT)


class PKCETests(unittest.TestCase):
    def auth(self):
        calls=[]
        def exchange(params):calls.append(params);return {'access_token':'fixture-token','expires_in':3600,'refresh_token':'fixture-refresh'}
        return SpotifyAuth(exchange),calls

    def test_challenge_and_exchange(self):
        auth,calls=self.auth();result=auth.begin('c'*32,'http://127.0.0.1:8848/spotify/callback');q=parse_qs(urlsplit(result['url']).query)
        expected=base64.urlsafe_b64encode(hashlib.sha256(auth.pending['verifier'].encode()).digest()).decode().rstrip('=')
        self.assertEqual(q['code_challenge'],[expected]);self.assertEqual(q['code_challenge_method'],['S256'])
        auth.callback(q['state'][0],'code');self.assertEqual(auth.token(),'fixture-token')
        self.assertEqual(calls[0]['grant_type'],'authorization_code');self.assertNotIn('token',auth.status())

    def test_invalid_state_and_replay(self):
        auth,_=self.auth();auth.begin('c'*32,'http://127.0.0.1:8848/spotify/callback');state=auth.pending['state']
        with self.assertRaises(ValueError):auth.callback('wrong','code')
        auth.callback(state,'code')
        with self.assertRaises(ValueError):auth.callback(state,'code')

    def test_cancel_preserves_previous_auth(self):
        auth,_=self.auth();auth.begin('c'*32,'http://127.0.0.1:8848/spotify/callback');auth.callback(auth.pending['state'],'code')
        auth.begin('c'*32,'http://127.0.0.1:8848/spotify/callback')
        with self.assertRaises(ValueError):auth.callback(auth.pending['state'],error='access_denied')
        self.assertEqual(auth.token(),'fixture-token');auth.clear();self.assertFalse(auth.status()['connected'])

    def test_refresh(self):
        auth,calls=self.auth();auth.begin('c'*32,'http://127.0.0.1:8848/spotify/callback');auth.callback(auth.pending['state'],'code');auth.credentials['expires']=0
        self.assertEqual(auth.token(),'fixture-token');self.assertEqual(calls[-1]['grant_type'],'refresh_token')

    def test_clear_during_callback_prevents_resurrection(self):
        started=threading.Event();finish=threading.Event();errors=[]
        def exchange(params):started.set();finish.wait(3);return {'access_token':'fixture','expires_in':3600}
        auth=SpotifyAuth(exchange);auth.begin('c'*32,'http://127.0.0.1:8848/spotify/callback');state=auth.pending['state']
        def callback():
            try:auth.callback(state,'code')
            except ValueError as e:errors.append(e)
        thread=threading.Thread(target=callback);thread.start();self.assertTrue(started.wait(2));auth.clear();finish.set();thread.join(3)
        self.assertFalse(thread.is_alive());self.assertFalse(auth.status()['connected']);self.assertEqual(len(errors),1)

    def test_invalid_client(self):
        auth,_=self.auth()
        with self.assertRaises(ValueError):auth.begin('bad','http://127.0.0.1:8848/spotify/callback')

if __name__=='__main__':unittest.main()
