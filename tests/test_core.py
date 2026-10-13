import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from rhythmbridge.catalog import CatalogStore
from rhythmbridge.matching import Matcher
from rhythmbridge.parsers import Track, decode_csv, parse_csv
from rhythmbridge.server import handler_class

class CSVTests(unittest.TestCase):
    def test_quoted_artists(self):
        parsed = parse_csv('title,artist\r\n"Title, One","A, B"\r\n')
        self.assertEqual(parsed['tracks'][0].title, 'Title, One')
        self.assertEqual(parsed['tracks'][0].artist, 'A, B')
    def test_exportify(self):
        track = parse_csv('Track Name,Artist Name(s),Album Name\nSong,Artist,Album')['tracks'][0]
        self.assertEqual((track.title, track.artist, track.album), ('Song', 'Artist', 'Album'))
    def test_chinese_and_encoding(self):
        text='曲名,歌手\n深海少女,ゆうゆ'
        self.assertEqual(decode_csv(text.encode('gb18030')), text)
        self.assertEqual(parse_csv(text)['tracks'][0].title, '深海少女')
    def test_utf16(self):
        self.assertEqual(decode_csv('title,artist\nSong,Artist'.encode('utf-16')), 'title,artist\nSong,Artist')
    def test_manual_columns(self):
        parsed=parse_csv('作品,作者\nSong,Artist',{'title':'作品','artist':'作者'})
        self.assertEqual(parsed['tracks'][0].artist,'Artist')
    def test_invalid_inputs(self):
        for text in ('', 'title,title\nA,B', 'title,artist\nA,B,C'):
            with self.assertRaises(ValueError):parse_csv(text)
    def test_missing_artist_needs_review(self):
        self.assertEqual(parse_csv('title\nSong')['tracks'][0].artist,'')

class MatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.matcher=Matcher(CatalogStore().snapshot())
    def test_true_original(self):
        row=self.matcher.match(Track('1','アンドロイドガール','DECO*27, 初音ミク'))
        self.assertEqual(row['status'],'confirmed')
        self.assertEqual({m['game'] for m in row['matches'] if m['status']=='confirmed'},{'maimai','chunithm'})
    def test_known_cover(self):
        row=self.matcher.match(Track('1','天ノ弱 -うぃんぐPiano Ver.-','Akie秋绘'))
        self.assertEqual(row['status'],'confirmed')
        self.assertEqual(row['romaji'],'Amanojaku')
    def test_false_same_title(self):
        for title,artist in [('ALIVE','ClariS'),('Oracle','黄霄雲, HOYO-MiX'),('Higher','Tobu'),('Life','Tobu')]:
            row=self.matcher.match(Track('1',title,artist))
            self.assertNotEqual(row['status'],'confirmed',(title,row))
    def test_alias_does_not_confirm(self):
        row=self.matcher.match(Track('1','追光者','岑宁儿'))
        self.assertNotEqual(row['status'],'confirmed')
    def test_disabled(self):
        result=self.matcher.analyze([Track('1','Burn My Soul','She is Legend')])
        self.assertEqual(result['rows'][0]['status'],'disabled')
        self.assertEqual(result['stats']['works'],0)
    def test_unknown_artist(self):
        self.assertEqual(self.matcher.match(Track('1','深海少女'))['status'],'candidate')
    def test_missing_rule_target(self):
        matcher=Matcher({'songs':[],'updated_at':'test'},rules=[{'title':'Song','romaji':'Song','targets':['maimai:999999'],'variants':[{'title':'Song','artist':'Artist'}]}])
        self.assertEqual(matcher.match(Track('1','Song','Artist'))['status'],'unmatched')
    def test_failed_refresh_keeps_snapshot(self):
        store=CatalogStore();before=store.snapshot()
        with patch('rhythmbridge.catalog.get_json',side_effect=OSError('offline')):
            with self.assertRaises(OSError):store.refresh()
        self.assertIs(store.snapshot(),before)

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),handler_class(CatalogStore()))
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join()
    def request(self,path,body=None,headers=None):
        payload=json.dumps(body).encode() if body is not None else None
        request=urllib.request.Request(self.url+path,data=payload,headers={'Content-Type':'application/json',**(headers or {})})
        return urllib.request.urlopen(request,timeout=10)
    def test_analyze(self):
        with self.request('/api/analyze',{'csv':'title,artist\nアンドロイドガール,DECO*27'}) as response:
            self.assertEqual(json.load(response)['stats']['confirmed'],1)
    def test_cross_origin(self):
        with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/analyze',{'csv':'title\nA'},{'Origin':'http://outside.invalid'})
        self.assertEqual(error.exception.code,403)
    def test_invalid_json(self):
        with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/analyze',[])
        self.assertEqual(error.exception.code,400)
    def test_path_traversal(self):
        with self.assertRaises(urllib.error.HTTPError) as error:self.request('/../../data/rules.json')
        self.assertEqual(error.exception.code,404)
    def test_malformed_base64(self):
        with self.assertRaises(urllib.error.HTTPError) as error:self.request('/api/inspect',{'csv_base64':'???'})
        self.assertEqual(error.exception.code,400)

if __name__=='__main__':unittest.main()
