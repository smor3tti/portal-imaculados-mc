/**
 * Portal Imaculados M.C. — Service Worker
 *
 * Guarda os arquivos do portal no aparelho para que ele abra rápido e funcione
 * mesmo sem internet. Os dados (planilha/API) NUNCA são guardados aqui: eles
 * precisam estar sempre atualizados, e guardá-los poderia mostrar informação
 * financeira vencida ou vazar dados no aparelho.
 */
var VERSAO = 'imaculados-v1';

var ARQUIVOS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './brasao-animado.mp4',
  './brasao-poster.jpg',
  './icone-192.png',
  './icone-512.png',
  './icone-maskable-192.png',
  './icone-maskable-512.png',
  './apple-touch-icon.png',
  './favicon.png'
];

self.addEventListener('install', function (evento) {
  evento.waitUntil(
    caches.open(VERSAO).then(function (cache) {
      // addAll falha inteiro se um item falhar; guardamos um a um por segurança
      return Promise.all(ARQUIVOS.map(function (url) {
        return cache.add(url).catch(function () { /* item opcional */ });
      }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (evento) {
  evento.waitUntil(
    caches.keys().then(function (chaves) {
      return Promise.all(chaves.filter(function (c) { return c !== VERSAO; })
                              .map(function (c) { return caches.delete(c); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (evento) {
  var req = evento.request;

  // Só interceptamos leitura simples do próprio site
  if (req.method !== 'GET') return;

  var url = new URL(req.url);

  // Chamadas à planilha/API sempre vão à rede: dados não podem ficar velhos
  if (url.origin !== self.location.origin) return;

  // Estratégia "rede primeiro, cache como reserva": o portal fica sempre
  // atualizado quando há sinal, e continua abrindo quando não há.
  evento.respondWith(
    fetch(req).then(function (resposta) {
      var copia = resposta.clone();
      caches.open(VERSAO).then(function (cache) { cache.put(req, copia); });
      return resposta;
    }).catch(function () {
      return caches.match(req).then(function (guardado) {
        return guardado || caches.match('./index.html');
      });
    })
  );
});
