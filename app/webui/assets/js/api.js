async function json(url,opt){const r=await fetch(url,opt);let d={};try{d=await r.json()}catch{}return{r,d}}
