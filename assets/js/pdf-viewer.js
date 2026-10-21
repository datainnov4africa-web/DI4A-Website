/**
 * Lightweight PDF preview built on PDF.js (loaded on demand from cdnjs).
 *
 * Pages are rendered lazily into <canvas> elements as they scroll into view,
 * so even long decks open instantly. The dialog relies on the native <dialog>
 * element for focus trapping and the Escape key.
 */
const PDFJS_VERSION = '4.10.38';
const PDFJS_CDN = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${PDFJS_VERSION}/`;

let pdfjsPromise = null;
function loadPdfJs() {
  if (!pdfjsPromise) {
    pdfjsPromise = import(`${PDFJS_CDN}pdf.min.mjs`).then((lib) => {
      lib.GlobalWorkerOptions.workerSrc = `${PDFJS_CDN}pdf.worker.min.mjs`;
      return lib;
    });
  }
  return pdfjsPromise;
}

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/**
 * Open the preview dialog.
 * @param {object} opts
 * @param {string} opts.url            relative URL of the PDF (same origin)
 * @param {string} opts.title          document title
 * @param {string} opts.downloadName   file name for the download button
 * @param {(key:string, vars?:object)=>string} opts.t   translation function
 */
export async function openPdfPreview({ url, title, downloadName, t }) {
  const dialog = document.getElementById('pdf-dialog');
  if (!dialog) return;

  dialog.innerHTML = `
    <div class="pdf-shell">
      <header class="pdf-toolbar">
        <h2 class="pdf-title" id="pdf-title">
          <svg class="icon" aria-hidden="true"><use href="#i-file-text"/></svg>
          <span>${esc(title)}</span>
        </h2>
        <div class="pdf-controls">
          <button type="button" class="icon-btn" data-act="prev" aria-label="${esc(t('preview.prev'))}" title="${esc(t('preview.prev'))}"><svg class="icon" aria-hidden="true"><use href="#i-chevron-left"/></svg></button>
          <span class="pdf-page-indicator" aria-live="polite">
            <span class="visually-hidden">${esc(t('preview.page'))} </span><span data-role="current">1</span> <span aria-hidden="true">/</span><span class="visually-hidden"> ${esc(t('preview.of'))} </span><span data-role="total">…</span>
          </span>
          <button type="button" class="icon-btn" data-act="next" aria-label="${esc(t('preview.next'))}" title="${esc(t('preview.next'))}"><svg class="icon" aria-hidden="true"><use href="#i-chevron-right"/></svg></button>
          <span class="pdf-sep" aria-hidden="true"></span>
          <button type="button" class="icon-btn" data-act="zoom-out" aria-label="${esc(t('preview.zoom_out'))}" title="${esc(t('preview.zoom_out'))}"><svg class="icon" aria-hidden="true"><use href="#i-zoom-out"/></svg></button>
          <button type="button" class="icon-btn" data-act="zoom-in" aria-label="${esc(t('preview.zoom_in'))}" title="${esc(t('preview.zoom_in'))}"><svg class="icon" aria-hidden="true"><use href="#i-zoom-in"/></svg></button>
          <span class="pdf-sep" aria-hidden="true"></span>
          <a class="icon-btn" href="${esc(url)}" target="_blank" rel="noopener" aria-label="${esc(t('preview.open_new'))}" title="${esc(t('preview.open_new'))}"><svg class="icon" aria-hidden="true"><use href="#i-external"/></svg></a>
          <a class="icon-btn" href="${esc(url)}" download="${esc(downloadName)}" aria-label="${esc(t('preview.download'))}" title="${esc(t('preview.download'))}"><svg class="icon" aria-hidden="true"><use href="#i-download"/></svg></a>
        </div>
        <button type="button" class="icon-btn icon-btn-close" data-act="close" aria-label="${esc(t('preview.close'))}" title="${esc(t('preview.close'))}"><svg class="icon" aria-hidden="true"><use href="#i-close"/></svg></button>
      </header>
      <div class="pdf-pages" data-role="pages" tabindex="0">
        <p class="pdf-status" data-role="status">${esc(t('preview.loading'))}</p>
      </div>
    </div>`;

  const pagesEl = dialog.querySelector('[data-role="pages"]');
  const statusEl = dialog.querySelector('[data-role="status"]');
  const currentEl = dialog.querySelector('[data-role="current"]');
  const totalEl = dialog.querySelector('[data-role="total"]');

  dialog.showModal();
  document.body.classList.add('has-dialog');

  let pdf = null;
  let zoom = 1;
  let baseScale = 1;
  const pageEls = [];
  let observer = null;
  let disposed = false;

  const cleanup = () => {
    disposed = true;
    document.body.classList.remove('has-dialog');
    observer?.disconnect();
    pdf?.destroy?.();
    dialog.innerHTML = '';
  };
  dialog.addEventListener('close', cleanup, { once: true });
  dialog.addEventListener('click', (e) => {
    if (e.target === dialog) dialog.close(); // backdrop click
  });

  dialog.querySelector('[data-act="close"]').addEventListener('click', () => dialog.close());

  try {
    const pdfjsLib = await loadPdfJs();
    pdf = await pdfjsLib.getDocument({ url }).promise;
    if (disposed) return;
    totalEl.textContent = String(pdf.numPages);
    statusEl.remove();

    const first = await pdf.getPage(1);
    const unscaled = first.getViewport({ scale: 1 });
    const available = Math.max(280, pagesEl.clientWidth - 32);
    baseScale = Math.min(1.6, available / unscaled.width);

    for (let i = 1; i <= pdf.numPages; i++) {
      const holder = document.createElement('div');
      holder.className = 'pdf-page';
      holder.dataset.page = String(i);
      holder.style.aspectRatio = `${unscaled.width} / ${unscaled.height}`;
      holder.style.width = `${Math.round(unscaled.width * baseScale * zoom)}px`;
      holder.setAttribute('aria-label', `${t('preview.page')} ${i}`);
      pagesEl.appendChild(holder);
      pageEls.push(holder);
    }

    const renderPage = async (holder) => {
      if (holder.dataset.rendered === String(zoom)) return;
      holder.dataset.rendered = String(zoom);
      const page = await pdf.getPage(Number(holder.dataset.page));
      if (disposed) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const viewport = page.getViewport({ scale: baseScale * zoom });
      const canvas = document.createElement('canvas');
      canvas.width = Math.floor(viewport.width * dpr);
      canvas.height = Math.floor(viewport.height * dpr);
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;
      const ctx = canvas.getContext('2d', { alpha: false });
      await page.render({ canvasContext: ctx, viewport, transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : null }).promise;
      if (disposed) return;
      holder.replaceChildren(canvas);
    };

    observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) renderPage(entry.target);
      });
    }, { root: pagesEl, rootMargin: '400px 0px' });
    pageEls.forEach((el) => observer.observe(el));

    // Current page indicator = page whose top is closest to the viewport top.
    const updateIndicator = () => {
      const top = pagesEl.scrollTop + 40;
      let current = 1;
      for (const el of pageEls) {
        if (el.offsetTop <= top) current = Number(el.dataset.page);
      }
      currentEl.textContent = String(current);
    };
    pagesEl.addEventListener('scroll', updateIndicator, { passive: true });

    const goTo = (n) => {
      const el = pageEls[Math.min(Math.max(n, 1), pageEls.length) - 1];
      el?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    };
    const applyZoom = (factor) => {
      zoom = Math.min(2.5, Math.max(0.5, zoom * factor));
      pageEls.forEach((el) => {
        el.style.width = `${Math.round(unscaled.width * baseScale * zoom)}px`;
        delete el.dataset.rendered;
      });
      observer.disconnect();
      pageEls.forEach((el) => observer.observe(el));
    };

    dialog.querySelector('[data-act="prev"]').addEventListener('click', () => goTo(Number(currentEl.textContent) - 1));
    dialog.querySelector('[data-act="next"]').addEventListener('click', () => goTo(Number(currentEl.textContent) + 1));
    dialog.querySelector('[data-act="zoom-in"]').addEventListener('click', () => applyZoom(1.25));
    dialog.querySelector('[data-act="zoom-out"]').addEventListener('click', () => applyZoom(0.8));
    pagesEl.focus({ preventScroll: true });
  } catch (err) {
    console.error('PDF preview failed', err);
    if (!disposed) {
      statusEl.textContent = t('preview.error');
      statusEl.classList.add('is-error');
    }
  }
}
