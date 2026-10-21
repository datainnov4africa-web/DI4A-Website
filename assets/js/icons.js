/**
 * Inline SVG icon sprite (24×24, 1.75px strokes), injected once into the
 * document so that `<svg><use href="#i-name"/></svg>` works on every page.
 * Theme icons referenced from `_meta.yml` (`icon:` key) must exist here;
 * unknown names fall back to "folder".
 */
export const THEME_ICONS = [
  'satellite', 'chat', 'sparkles', 'chart', 'map', 'database', 'code', 'globe', 'book', 'folder', 'flask', 'layers',
];

const P = (d) => `<path d="${d}"/>`;

const ICONS = {
  // --- theme icons -------------------------------------------------------
  satellite: P('M13 7 17 3l4 4-4 4zM9 11l4 4M7 21l-4-4 4-4 4 4zM14 14l3 3M4 4l2 2M10 10l2-2m6 10a4 4 0 0 0 4-4'),
  chat: P('M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12zM8 12h.01M12 12h.01M16 12h.01'),
  sparkles: P('M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 17l.8 2.2L22 20l-2.2.8L19 23l-.8-2.2L16 20l2.2-.8zM4 3l.6 1.4L6 5l-1.4.6L4 7l-.6-1.4L2 5l1.4-.6z'),
  chart: P('M3 3v18h18M7 16V10M12 16V6M17 16v-4'),
  map: P('M12 21s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11zM12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z'),
  database: P('M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3'),
  code: P('M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16'),
  globe: P('M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z'),
  book: P('M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5v14zM4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5'),
  folder: P('M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z'),
  flask: P('M9 3h6M10 3v6.5L4.5 19a1.5 1.5 0 0 0 1.3 2.2h12.4a1.5 1.5 0 0 0 1.3-2.2L14 9.5V3M7 16h10'),
  layers: P('M12 3l9 5-9 5-9-5zM3 13l9 5 9-5M3 17l9 5 9-5'),
  // --- UI icons ----------------------------------------------------------
  'file-text': P('M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5M9 13h6M9 17h6'),
  download: P('M12 4v11M7 10l5 5 5-5M4 19h16'),
  eye: P('M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z'),
  external: P('M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5'),
  search: P('M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-5-5'),
  'arrow-right': P('M4 12h16M13 5l7 7-7 7'),
  check: P('M4 12.5l5 5L20 7'),
  close: P('M6 6l12 12M18 6L6 18'),
  'chevron-left': P('M15 5l-7 7 7 7'),
  'chevron-right': P('M9 5l7 7-7 7'),
  'chevron-up': P('M5 15l7-7 7 7'),
  menu: P('M4 7h16M4 12h16M4 17h16'),
  'zoom-in': P('M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-5-5M11 8v6M8 11h6'),
  'zoom-out': P('M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-5-5M8 11h6'),
  calendar: P('M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zM4 10h16M8 2v4M16 2v4'),
  drive: P('M4 8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v3H4zM4 13h16v3a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zM16 15.5h.01'),
  refresh: P('M20 11A8 8 0 0 0 6.3 6.3L4 8.5M4 4v4.5h4.5M4 13a8 8 0 0 0 13.7 4.7l2.3-2.2M20 20v-4.5h-4.5'),
  unlock: P('M7 11V7a5 5 0 0 1 9.6-2M5 11h14v10H5zM12 15v2'),
  // Official Google Colaboratory logo (from the public "Open in Colab" badge), brand colours kept.
  colab: { viewBox: '0 5.2 24.5 14.6', body: '<g stroke="none"><path fill="#e8710a" d="M1.977,16.77c-2.667-2.277-2.605-7.079,0-9.357C2.919,8.057,3.522,9.075,4.49,9.691c-1.152,1.6-1.146,3.201-0.004,4.803C3.522,15.111,2.918,16.126,1.977,16.77z"/><path fill="#f9ab00" d="M12.257,17.114c-1.767-1.633-2.485-3.658-2.118-6.02c0.451-2.91,2.139-4.893,4.946-5.678c2.565-0.718,4.964-0.217,6.878,1.819c-0.884,0.743-1.707,1.547-2.434,2.446C18.488,8.827,17.319,8.435,16,8.856c-2.404,0.767-3.046,3.241-1.494,5.644c-0.241,0.275-0.493,0.541-0.721,0.826C13.295,15.939,12.511,16.3,12.257,17.114z"/><path fill="#e8710a" d="M19.529,9.682c0.727-0.899,1.55-1.703,2.434-2.446c2.703,2.783,2.701,7.031-0.005,9.764c-2.648,2.674-6.936,2.725-9.701,0.115c0.254-0.814,1.038-1.175,1.528-1.788c0.228-0.285,0.48-0.552,0.721-0.826c1.053,0.916,2.254,1.268,3.6,0.83C20.502,14.551,21.151,11.927,19.529,9.682z"/><path fill="#f9ab00" d="M4.49,9.691C3.522,9.075,2.919,8.057,1.977,7.413c2.209-2.398,5.721-2.942,8.476-1.355c0.555,0.32,0.719,0.606,0.285,1.128c-0.157,0.188-0.258,0.422-0.391,0.631c-0.299,0.47-0.509,1.067-0.929,1.371C8.933,9.539,8.523,8.847,8.021,8.746C6.673,8.475,5.509,8.787,4.49,9.691z"/><path fill="#f9ab00" d="M1.977,16.77c0.941-0.644,1.545-1.659,2.509-2.277c1.373,1.152,2.85,1.433,4.45,0.499c0.332-0.194,0.503-0.088,0.673,0.19c0.386,0.635,0.753,1.285,1.181,1.89c0.34,0.48,0.222,0.715-0.253,1.006C7.84,19.73,4.205,19.188,1.977,16.77z"/></g>' },
  github: '<path fill="currentColor" stroke="none" d="M12 1.8a10.2 10.2 0 0 0-3.2 19.9c.5.1.7-.2.7-.5v-1.9c-2.8.6-3.4-1.2-3.4-1.2-.5-1.2-1.1-1.5-1.1-1.5-.9-.6.1-.6.1-.6 1 .1 1.6 1 1.6 1 .9 1.6 2.4 1.1 3 .9.1-.7.4-1.1.6-1.4-2.3-.3-4.7-1.1-4.7-5a4 4 0 0 1 1-2.8c-.1-.3-.5-1.3.1-2.8 0 0 .9-.3 2.8 1a9.7 9.7 0 0 1 5.2 0c2-1.3 2.8-1 2.8-1 .6 1.5.2 2.5.1 2.8a4 4 0 0 1 1 2.8c0 3.9-2.4 4.7-4.7 5 .4.3.7.9.7 1.9v2.8c0 .3.2.6.7.5A10.2 10.2 0 0 0 12 1.8z"/>',
};

export function injectIconSprite() {
  if (document.getElementById('di4a-icons')) return;
  const symbols = Object.entries(ICONS)
    .map(([name, def]) => {
      const { viewBox = '0 0 24 24', body } = typeof def === 'string' ? { body: def } : def;
      return `<symbol id="i-${name}" viewBox="${viewBox}" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">${body}</symbol>`;
    })
    .join('');
  const sprite = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  sprite.setAttribute('id', 'di4a-icons');
  sprite.setAttribute('aria-hidden', 'true');
  sprite.setAttribute('style', 'position:absolute;width:0;height:0;overflow:hidden');
  sprite.innerHTML = symbols;
  document.body.prepend(sprite);
}

export function iconName(name) {
  return ICONS[name] ? name : 'folder';
}
