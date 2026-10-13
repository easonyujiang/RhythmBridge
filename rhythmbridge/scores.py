"""Read-only personal scores. Credentials are never persisted or returned."""
import json
import math
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request

GAMES = ('maimai', 'chunithm')
MAX_RESPONSE = 12 * 1024 * 1024


def normalize_scores(game, payload):
    if game not in GAMES:
        raise ValueError('请选择舞萌 DX 或中二节奏。')
    if isinstance(payload, dict):
        if payload.get('success') is False:
            raise ValueError('成绩来源返回失败，未导入。')
        payload = payload.get('data', payload.get('scores'))
    if not isinstance(payload, list) or len(payload) > 100000:
        raise ValueError('需要完整成绩数组，或包含 data / scores 数组的 JSON。')
    result = []
    for raw in payload:
        if not isinstance(raw, dict):
            raise ValueError('成绩记录格式无效。')
        sid, difficulty = raw.get('id'), raw.get('level_index')
        if type(sid) is not int or sid < 0 or type(difficulty) is not int or not 0 <= difficulty <= (4 if game == 'maimai' else 5):
            raise ValueError('成绩缺少有效曲目 ID 或难度。')
        metric = 'achievements' if game == 'maimai' else 'score'
        value = raw.get(metric)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= (101 if game == 'maimai' else 1010000):
            raise ValueError('成绩缺少有效达成率／分数。简化成绩接口不能用于此功能。')
        if game == 'chunithm' and type(value) is not int:
            raise ValueError('中二分数必须是整数。')
        kind = raw.get('type', 'standard') if game == 'maimai' else 'standard'
        if kind not in ('standard', 'dx', 'utage'):
            raise ValueError('成绩谱面类型无效。')
        # Whitelist values; discard arbitrary upstream fields and any credentials.
        record = dict(game=game, id=sid, level_index=difficulty, type=kind, **{metric:value})
        for key in ('level','fc','fs','dx_score','dx_star','dx_rating','rate','rating','over_power','clear','full_combo','full_chain','rank','play_time','upload_time','last_played_time'):
            value = raw.get(key)
            if value is None or type(value) in (str,int,float):
                if isinstance(value, str) and len(value) > 200:
                    raise ValueError('成绩字段过长。')
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError('成绩字段无效。')
                record[key] = value
        result.append(record)
    return {'game':game, 'scores':result, 'fetched_at':datetime.now(timezone.utc).isoformat(), 'source':'json', 'coverage':'provided records'}


def fetch_personal_scores(game, token):
    if game not in GAMES:
        raise ValueError('游戏无效。')
    if not isinstance(token,str) or not token.strip() or len(token)>512 or any(ord(c)<33 or ord(c)>126 for c in token):
        raise ValueError('请输入有效个人 API 密钥。')
    request = Request(f'https://maimai.lxns.net/api/v0/user/{game}/player/scores', headers={'X-User-Token':token,'Accept':'application/json','User-Agent':'RhythmBridge/0.2'})
    # Refuse redirects so credentials cannot be forwarded to a different endpoint.
    from urllib.request import HTTPRedirectHandler, build_opener
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        with build_opener(NoRedirect()).open(request,timeout=25) as response:
            content = response.read(MAX_RESPONSE+1)
            if len(content)>MAX_RESPONSE:
                raise ValueError('成绩响应过大，未导入。')
        payload = json.loads(content)
    except HTTPError as error:
        messages={401:'个人密钥无效或已过期。',403:'账号没有读取成绩的权限。',404:'该游戏玩家资料不存在。',429:'落雪请求过于频繁，请稍后重试。'}
        raise ValueError(messages.get(error.code,'落雪服务暂时无法读取成绩，请稍后重试。')) from None
    except (URLError,TimeoutError,OSError):
        raise ValueError('读取成绩失败，请检查网络后重试。') from None
    except (json.JSONDecodeError,UnicodeError):
        raise ValueError('落雪响应格式无效，未导入。') from None
    result = normalize_scores(game,payload)
    result.update(source='lxns-personal',coverage='all returned personal scores')
    return result
