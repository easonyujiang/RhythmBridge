async function spotifyStatus(){try{const data=await api('/api/spotify/status');$('spotify-state').textContent=data.connected?'已授权 · 凭证只保留在本地服务内存，关闭服务后清除':data.pending?'等待 Spotify 授权 · 完成后点击刷新状态':'未授权 · 也可继续使用 Exportify CSV';}catch(e){message(e.message,true);}}
$('spotify-connect').addEventListener('click',async()=>{const client_id=$('spotify-client').value.trim();if(!client_id){message('请输入自己的 Spotify 应用 Client ID。',true);return;}const popup=window.open('about:blank','_blank');if(popup)popup.opener=null;try{const data=await api('/api/spotify/begin',{client_id});if(popup)popup.location=data.url;else message('浏览器阻止了授权窗口，请允许弹窗后重试。',true);await spotifyStatus();}catch(e){if(popup)popup.close();message(e.message,true);}});
$('spotify-status').addEventListener('click',spotifyStatus);
$('spotify-clear').addEventListener('click',async()=>{try{await api('/api/spotify/clear',{});await spotifyStatus();message('已清除本地 Spotify 授权。如需撤销平台权限，请在 Spotify 账号应用管理中移除。');}catch(e){message(e.message,true);}});
window.addEventListener('focus',spotifyStatus);spotifyStatus();

$('spotify-redirect').textContent='重定向地址：http://127.0.0.1:'+location.port+'/spotify/callback';
