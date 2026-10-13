import unittest
from rhythmbridge.online import identify_playlist,NeteaseProvider,QQMusicProvider


class OnlineTests(unittest.TestCase):
    def test_normal_and_fragment_urls(self):
        for url in ['https://music.163.com/playlist?id=123&userid=4','https://music.163.com/#/playlist?id=123']:
            self.assertEqual(identify_playlist(url)['id'],'123')

    def test_bad_urls(self):
        for url in ['file:///playlist?id=1','https://music.163.com.evil.test/playlist?id=1','https://music.163.com/song?id=1','http://127.0.0.1/playlist?id=1','https://music.163.com/playlist?id=1&id=2','https://user:pass@music.163.com/playlist?id=1']:
            with self.subTest(url=url),self.assertRaises(ValueError):identify_playlist(url)

    def fetcher(self,ids,count=None,missing=False,change=False):
        calls=[]
        def fetch(path,params):
            calls.append((path,params))
            if path=='/playlist/detail':
                actual=ids[::-1] if change and len(calls)>1 else ids
                return {'code':200,'playlist':{'name':'Test','trackCount':len(ids) if count is None else count,'trackIds':[{'id':i} for i in actual]}}
            requested=list(map(int,params['ids'].split(',')))
            return {'code':200,'songs':[{'id':i,'name':f'Song {i}','ar':[],'al':{'name':'Album'}} for i in reversed(requested[1:] if missing else requested)]}
        return fetch,calls

    def test_pagination_order_duplicates_missing_artist(self):
        ids=list(range(1,452))+[2];fetch,calls=self.fetcher(ids)
        result=NeteaseProvider(fetch).load_playlist('https://music.163.com/playlist?id=123')
        self.assertEqual(len(result['tracks']),452)
        self.assertEqual(result['tracks'][-1].title,'Song 2')
        self.assertEqual(result['tracks'][0].artist,'')
        self.assertEqual(len([c for c in calls if c[0]=='/song/detail']),5)
        self.assertTrue(result['complete'])

    def test_partial_ids_rejected(self):
        fetch,_=self.fetcher([1,2],count=3)
        with self.assertRaisesRegex(ValueError,'不完整'):NeteaseProvider(fetch).load('https://music.163.com/playlist?id=1')

    def test_missing_song_rejected(self):
        fetch,_=self.fetcher([1,2],missing=True)
        with self.assertRaisesRegex(ValueError,'缺失'):NeteaseProvider(fetch).load('https://music.163.com/playlist?id=1')

    def test_changed_playlist_rejected(self):
        fetch,_=self.fetcher([1,2],change=True)
        with self.assertRaisesRegex(ValueError,'发生变化'):NeteaseProvider(fetch).load('https://music.163.com/playlist?id=1')

    def test_empty_verified_playlist(self):
        fetch,_=self.fetcher([])
        self.assertEqual(NeteaseProvider(fetch).load('https://music.163.com/playlist?id=1'),[])

    def test_service_failure_is_not_empty(self):
        def fail(*args):raise ValueError('login required')
        with self.assertRaisesRegex(ValueError,'login required'):NeteaseProvider(fail).load('https://music.163.com/playlist?id=1')

    def test_qq_url(self):
        self.assertEqual(identify_playlist('https://y.qq.com/n/ryqq/playlist/123')['provider'],'qqmusic')

    def qq_fetch(self,partial=False,repeated=False):
        calls=[]
        def fetch(path,params):
            page=params['page'];calls.append(page)
            songs=[{'id':1 if page==1 or repeated else 2,'mid':'one','name':'Song','artists':[],'album':''}]
            return {'code':200,'total':2,'hasmore':page==1 and not partial,'title':'QQ test','songs':songs}
        return fetch,calls

    def test_qq_pagination(self):
        fetch,calls=self.qq_fetch();result=QQMusicProvider(fetch).load_playlist('https://y.qq.com/n/ryqq/playlist/123')
        self.assertEqual(len(result['tracks']),2);self.assertEqual(calls,[1,2,1])

    def test_qq_partial_and_repeated(self):
        for options in ({'partial':True},{'repeated':True}):
            fetch,_=self.qq_fetch(**options)
            with self.assertRaises(ValueError):QQMusicProvider(fetch).load('https://y.qq.com/n/ryqq/playlist/123')

if __name__=='__main__':unittest.main()
