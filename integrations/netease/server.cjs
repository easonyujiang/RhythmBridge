const http=require('http');
const api=require('@neteasecloudmusicapienhanced/api');
const port=8850;
const server=http.createServer(async(req,res)=>{
 const send=(code,payload)=>{const data=JSON.stringify(payload);res.writeHead(code,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(data);};
 if(req.headers.host!==`127.0.0.1:${port}`&&req.headers.host!==`localhost:${port}`)return send(403,{error:'Invalid host'});
 if(req.method!=='GET'||req.headers.origin)return send(403,{error:'Local backend requests only'});
 const url=new URL(req.url,`http://127.0.0.1:${port}`);
 try{
  let response;
  if(url.pathname==='/playlist/detail'&&/^\d{1,20}$/.test(url.searchParams.get('id')||''))response=await api.playlist_detail({id:url.searchParams.get('id')});
  else if(url.pathname==='/song/detail'&&/^\d{1,20}(,\d{1,20}){0,199}$/.test(url.searchParams.get('ids')||''))response=await api.song_detail({ids:url.searchParams.get('ids')});
  else return send(400,{error:'Only playlist and song metadata requests are supported'});
  send(200,response.body);
 }catch(error){send(502,{error:'Metadata service unavailable'});}
});
server.requestTimeout=60000;
server.listen(port,'127.0.0.1',()=>console.log(`RhythmBridge 网易云元数据服务 http://127.0.0.1:${port}`));
