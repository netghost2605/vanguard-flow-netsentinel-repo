const CACHE='nm-shell-v21';
const SHELL=['/','/manifest.webmanifest','/icon-192.png','/icon-512.png'];
self.addEventListener('install',function(e){
  e.waitUntil(caches.open(CACHE).then(function(c){return c.addAll(SHELL);}).then(function(){return self.skipWaiting();}));
});
self.addEventListener('activate',function(e){
  e.waitUntil(caches.keys().then(function(ks){
    return Promise.all(ks.filter(function(k){return k!==CACHE;}).map(function(k){return caches.delete(k);}));
  }).then(function(){return self.clients.claim();}));
});
self.addEventListener('fetch',function(e){
  var u=new URL(e.request.url);
  if(u.pathname.indexOf('/api/')===0||u.pathname==='/3d'||u.pathname.indexOf('/flag/')===0
     ||u.pathname==='/sonar.mp3'||u.pathname==='/radar-map.png'||u.pathname==='/world-map.jpg'||u.pathname==='/day-map.jpg'
     ||u.pathname==='/guide-shot'||u.pathname==='/talkers'||u.pathname==='/sankey'){return;}
  /* live data, 3D, flags and embedded binaries: always straight to network.
     The cache-first branch below falls back to caches.match('/'), which
     resolves to undefined for an uncached asset and makes respondWith
     throw 'Failed to fetch' — that killed /sonar.mp3 and /radar-map.png. */
  var isHTML=e.request.mode==='navigate'||(e.request.headers.get('accept')||'').indexOf('text/html')>=0;
  if(isHTML){ /* pages: network-first so a new build shows on the next open */
    e.respondWith(fetch(e.request).catch(function(){
      return caches.match(e.request).then(function(r){return r||caches.match('/');});
    }));
    return;
  }
  e.respondWith( /* static assets (icons/manifest): cache-first */
    caches.match(e.request).then(function(r){
      return r||fetch(e.request).then(function(resp){
        var cp=resp.clone();
        caches.open(CACHE).then(function(c){c.put(e.request,cp);}).catch(function(){});
        return resp;
      }).catch(function(){
        return caches.match('/').then(function(f){
          return f||new Response('',{status:504,statusText:'offline'});
        });
      });
    })
  );
});