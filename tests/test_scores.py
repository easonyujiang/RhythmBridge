import json
import unittest
from io import BytesIO
from urllib.error import HTTPError, URLError
from unittest.mock import patch
from rhythmbridge.scores import normalize_scores, fetch_personal_scores


class ScoreTests(unittest.TestCase):
    def test_maimai_chart_keys_and_precision(self):
        records=[{'id':1,'level_index':3,'type':kind,'achievements':100.1234,'fc':'app','secret':'discard'} for kind in ('standard','dx')]
        result=normalize_scores('maimai',{'success':True,'data':records})
        self.assertEqual(len(result['scores']),2)
        self.assertEqual(result['scores'][0]['achievements'],100.1234)
        self.assertNotIn('secret',result['scores'][0])

    def test_chunithm_ajc(self):
        score=normalize_scores('chunithm',[{'id':3,'level_index':4,'score':1010000,'full_combo':'alljusticecritical'}])['scores'][0]
        self.assertEqual(score['full_combo'],'alljusticecritical')

    def test_simple_scores_are_rejected(self):
        with self.assertRaises(ValueError):normalize_scores('maimai',[{'id':1,'level_index':3,'rate':'sss'}])

    def test_invalid_score_values(self):
        for value in (True,None,float('nan'),102,-1,'100'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                normalize_scores('maimai',[{'id':1,'level_index':3,'achievements':value}])

    def test_invalid_game_and_envelope(self):
        for game,payload in [('other',[]),('maimai',{}),('maimai',{'success':False,'data':[]})]:
            with self.assertRaises(ValueError):normalize_scores(game,payload)

    def test_empty_is_valid_but_not_unplayed(self):
        self.assertEqual(normalize_scores('maimai',[])['coverage'],'provided records')

    @patch('urllib.request.build_opener')
    def test_personal_endpoint_and_credentials(self,opener):
        opener.return_value.open.return_value=BytesIO(json.dumps({'success':True,'data':[]}).encode())
        result=fetch_personal_scores('maimai','test-fixture-token')
        request=opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url,'https://maimai.lxns.net/api/v0/user/maimai/player/scores')
        self.assertEqual(request.get_header('X-user-token'),'test-fixture-token')
        self.assertNotIn('token',json.dumps(result))
        self.assertEqual(result['source'],'lxns-personal')

    @patch('urllib.request.build_opener')
    def test_error_does_not_echo_upstream_secret(self,opener):
        opener.return_value.open.side_effect=HTTPError('hidden',401,'secret-token',{},None)
        with self.assertRaisesRegex(ValueError,'个人密钥无效'):fetch_personal_scores('chunithm','test-fixture-token')

    @patch('urllib.request.build_opener')
    def test_network_failure(self,opener):
        opener.return_value.open.side_effect=URLError('secret')
        with self.assertRaisesRegex(ValueError,'检查网络'):fetch_personal_scores('maimai','test-fixture-token')

    def test_header_injection(self):
        with self.assertRaises(ValueError):fetch_personal_scores('maimai','bad\nheader')

if __name__=='__main__':unittest.main()
