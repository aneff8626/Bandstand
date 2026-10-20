// Development-only polling; no git pull, external fetching, or recording interruption.
(()=>{
 let stopped=false,pending=false,lastNotice='';
 const busy=()=>typeof state==='undefined'||!state||document.body.classList.contains('app-loading')||document.querySelector('dialog[open]')||['setup','run'].includes(document.body.dataset.journeyStep)||state.session?.running||state.typing?.running||state.typing?.fitting||state.personal?.running||state.developer?.recording||(['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName));
 async function tick(){
  if(stopped||pending||!window.museNative)return;
  pending=true;
  try{
   const s=await rawApi('development/status');
   if(!s.enabled){stopped=true;return}
   if(!s.changed)return;
   const message=s.manual?'Source changed: native, dependency or backend changes need a manual restart/new build.':busy()||s.busy?'Development update ready. It will apply when idle on Headset, Activity or Results.':'';
   if(message&&message!==lastNotice){toast(message);lastNotice=message}
   if(s.manual||!s.settled||s.busy||busy())return;
   window.bandstandReloading=true;
   const result=await rawApi('development/apply',{revision:s.revision});
   if(!result.ready)return;
   if(result.restart){toast('Applying development changes…');setTimeout(()=>location.reload(),800);stopped=true}
   else {for(const link of document.querySelectorAll('link[rel="stylesheet"]')){const u=new URL(link.href);u.searchParams.set('development',String(Date.now()));link.href=u.href}toast('Styles updated');lastNotice=''}
  }catch(e){if(!String(e.message).includes('Unknown request')){const m='Development refresh paused: '+e.message;if(m!==lastNotice){toast(m);lastNotice=m}}else stopped=true}
  finally{if(!stopped)window.bandstandReloading=false;pending=false}
 }
 setInterval(tick,2000);
})();
