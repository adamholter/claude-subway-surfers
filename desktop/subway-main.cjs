const { app, webContents } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const clip = path.join(process.resourcesPath, 'subway-gameplay.mp4');
const pane = fs.readFileSync(path.join(__dirname, 'pane.js'), 'utf8');
const script = pane.replace('__SUBWAY_VIDEO_URL__', 'data:video/mp4;base64,' + fs.readFileSync(clip).toString('base64'));
const wired = new WeakSet();
function wire(contents) {
  if (wired.has(contents)) return;
  wired.add(contents);
  const inject = () => {
    if (contents.isDestroyed()) return;
    const url = contents.getURL();
    if (!/^https:\/\/(claude\.ai|claude\.com)\//.test(url) || /\/(login|magic-link)/.test(url)) return;
    contents.executeJavaScript(script).catch(error => console.error('Subway video pane:', error.message));
  };
  contents.on('did-finish-load', inject);
  contents.on('did-navigate-in-page', inject);
  setTimeout(inject, 1800);
}
app.on('web-contents-created', (_, contents) => wire(contents));
app.whenReady().then(() => webContents.getAllWebContents().forEach(wire));
