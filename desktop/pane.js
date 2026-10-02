(() => {
  if (document.getElementById('subway-video-pane')) return;
  const style = document.createElement('style');
  style.id = 'subway-video-style';
  style.textContent = `
    html.subway-on body { width:calc(100% - 338px)!important; }
    #subway-video-pane { position:fixed;top:0;right:0;bottom:0;width:338px;z-index:99999;background:#141413;border-left:1px solid #343432;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px;font-family:system-ui;color:#dad9d4; }
    #subway-video-pane header { width:300px;display:flex;align-items:center;justify-content:space-between;font-size:13px; }
    #subway-video-pane video { width:300px;max-height:calc(100vh - 150px);border-radius:14px;background:#000;object-fit:contain; }
    #subway-video-pane button { background:#282826;color:#dad9d4;border:1px solid #484843;border-radius:7px;padding:7px 13px;font:12px system-ui;cursor:pointer; }
    #subway-video-pane button:hover { background:#393936; }
    #subway-video-pane nav { display:flex;gap:10px; }
    #subway-video-pane footer { font-size:11px;color:#83837c; }
  `;
  document.head.append(style);
  const pane = document.createElement('aside');
  pane.id = 'subway-video-pane';
  pane.setAttribute('aria-label', 'Subway Surfers video');
  pane.innerHTML = '<header><span>Subway Surfers</span><button aria-label="Hide video" id="subway-hide">Hide</button></header><video autoplay muted loop playsinline aria-label="Looping Subway Surfers gameplay"></video><nav><button id="subway-pause">Pause</button><button id="subway-restart">Restart</button></nav><footer>⌘⇧S to show or hide</footer>';
  document.body.append(pane);
  document.documentElement.classList.add('subway-on');
  const video = pane.querySelector('video');
  const encoded = '__SUBWAY_VIDEO_URL__'.split(',')[1];
  const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
  video.src = URL.createObjectURL(new Blob([bytes], {type:'video/mp4'}));
  video.muted = true;
  const play = () => video.play().catch(() => { pane.querySelector('#subway-pause').textContent = 'Play'; });
  play();
  const toggle = () => {const show=pane.style.display==='none';pane.style.display=show?'flex':'none';document.documentElement.classList.toggle('subway-on',show);if(show)play();else video.pause();};
  pane.querySelector('#subway-hide').onclick = toggle;
  pane.querySelector('#subway-pause').onclick = () => {if(video.paused)play();else video.pause();};
  video.onplay = () => pane.querySelector('#subway-pause').textContent='Pause';
  video.onpause = () => pane.querySelector('#subway-pause').textContent='Play';
  pane.querySelector('#subway-restart').onclick = () => {video.currentTime=0;play();};
  document.addEventListener('keydown', event => {if(event.metaKey&&event.shiftKey&&event.code==='KeyS'){event.preventDefault();toggle();}},true);
})();
