/* Framework visual edits are requests, never serialized replacements for JSX. */
(() => {
  const token = __STUDIO_TOKEN__;
  const endpoint = '/__draft_studio/changes';
  function start() {
    if (document.getElementById('__draft_studio_host')) return;
    const host = document.createElement('div');
    host.id = '__draft_studio_host';
    host.dataset.draftChrome = '';
    const shadow = host.attachShadow({mode: 'open'});
    document.documentElement.append(host);
    shadow.innerHTML = `
      <style>
        :host {all:initial;position:fixed;right:16px;top:16px;z-index:2147483647;font:13px/1.45 system-ui;color:#e7edf6}
        *{box-sizing:border-box} button,input,textarea,select{font:inherit}
        .panel{width:300px;background:#151d2c;border:1px solid #42516c;border-radius:12px;padding:14px;box-shadow:0 10px 40px #0005}
        header{display:flex;align-items:center;justify-content:space-between;gap:8px}strong{font-size:15px}
        button{border:1px solid #52627d;border-radius:6px;background:#29374e;color:#fff;padding:6px 9px;cursor:pointer}
        button:disabled{opacity:.45;cursor:default}button.active{background:#3158c9}button.primary{background:#3158c9}
        label{display:block;margin:10px 0 4px;color:#c4cfe1}input,textarea,select{display:block;width:100%;background:#0b1320;color:#fff;border:1px solid #52627d;border-radius:5px;padding:7px}
        textarea{resize:vertical;min-height:68px}.row{display:flex;gap:6px;margin-top:10px}.row>*{flex:1}
        .small{font-size:12px;color:#aebcd3;margin:8px 0}.status{margin:10px 0 0;overflow-wrap:anywhere}.target{font-family:monospace;overflow-wrap:anywhere;color:#9eb9ff}
        [hidden]{display:none!important}.outline{position:fixed;pointer-events:none;border:2px solid #7199ff;background:#7199ff0a;z-index:-1}
        details{margin-top:10px}li{margin:5px 0}ul{padding-left:18px;max-height:140px;overflow:auto}
      </style>
      <div class="outline" hidden></div>
      <section class="panel" aria-label="Draft Studio visual editor">
        <header><strong>Draft Studio</strong><button id="collapse" aria-label="Collapse editor">−</button></header>
        <div id="body">
          <p class="small">Edit the preview. Save requests for your agent to apply to React source.</p>
          <button id="select" aria-pressed="false">Select element</button>
          <p class="target" id="target">No element selected</p>
          <div id="controls" hidden>
            <label for="text">Text</label><textarea id="text" placeholder="Select a text-only element"></textarea>
            <button id="textApply">Apply text</button>
            <label for="property">Style property</label>
            <select id="property">
              <option value="font-size">Font size</option><option value="color">Text color</option>
              <option value="background-color">Background color</option><option value="padding">Padding</option>
              <option value="margin">Margin</option><option value="gap">Gap</option>
              <option value="border-radius">Corner radius</option><option value="width">Width</option>
              <option value="max-width">Maximum width</option><option value="font-weight">Font weight</option>
              <option value="text-align">Text alignment</option><option value="display">Display</option>
            </select>
            <label for="value">Value</label><input id="value" placeholder="e.g. 32px, 1.5rem, #2563eb">
            <button id="styleApply">Apply style</button>
            <div class="row"><button id="parent">Select parent</button><button id="hide">Hide element</button></div>
          </div>
          <label for="note">Note for next edit (optional)</label><input id="note" placeholder="Apply this across all cards">
          <div class="row"><button id="undo" disabled>Undo</button><button class="primary" id="save">Save changes</button></div>
          <details><summary id="count">0 change requests</summary><ul id="list"></ul><button id="clear">Clear requests</button></details>
          <p class="status" id="status" role="status">Loading saved requests…</p>
        </div>
      </section>`;
    const $ = id => shadow.getElementById(id);
    const outline = shadow.querySelector('.outline');
    let revision = 0, changes = [], selected = null, selecting = false, dirty = false, ready = false;
    let history = [], busy = false;
    const undoPreview = [];
    const route = () => location.pathname + location.search;
    const status = message => { $('status').textContent = message; };
    function selectorFor(el) {
      if (el.id && document.querySelectorAll('#' + CSS.escape(el.id)).length === 1) return '#' + CSS.escape(el.id);
      const parts = [];
      while (el && el !== document.documentElement) {
        const tag = el.localName;
        const siblings = [...el.parentElement.children].filter(e => e.localName === tag);
        parts.unshift(tag + (siblings.length > 1 ? ':nth-of-type(' + (siblings.indexOf(el) + 1) + ')' : ''));
        el = el.parentElement;
      }
      return 'html > ' + parts.join(' > ');
    }
    function textNode(el) {
      if (el.children.length || /^(input|textarea|select|script|style|svg|iframe)$/i.test(el.localName)) return null;
      const nodes = [...el.childNodes].filter(n => n.nodeType === Node.TEXT_NODE && n.nodeValue.trim());
      return nodes.length === 1 ? nodes[0] : null;
    }
    function positionOutline() {
      if (!selected || !selected.isConnected) { outline.hidden = true; return; }
      const b = selected.getBoundingClientRect();
      outline.hidden = false;
      Object.assign(outline.style, {left:b.x+'px',top:b.y+'px',width:b.width+'px',height:b.height+'px'});
    }
    function choose(el) {
      selected = el;
      $('target').textContent = selectorFor(el);
      $('controls').hidden = false;
      const node = textNode(el);
      $('text').disabled = $('textApply').disabled = !node;
      $('text').value = node ? node.nodeValue : '';
      $('parent').disabled = !el.parentElement || el.parentElement === document.documentElement;
      $('value').value = getComputedStyle(el).getPropertyValue($('property').value);
      positionOutline();
    }
    function draw() {
      $('count').textContent = `${changes.length} change request${changes.length === 1 ? '' : 's'}`;
      $('list').replaceChildren();
      for (const c of changes) {
        const li = document.createElement('li');
        li.textContent = `${c.kind}${c.property ? ' '+c.property : ''}: ${c.selector} (${c.route})`;
        $('list').append(li);
      }
      $('undo').disabled = !history.length || busy;
      $('save').disabled = !ready || busy;
    }
    function preview(c, el) {
      if (c.kind === 'text') {
        const node = textNode(el);
        if (!node || (node.nodeValue !== c.before && node.nodeValue !== c.after)) return false;
        const old = node.nodeValue;
        node.nodeValue = c.after;
        undoPreview.push(() => { if (node.isConnected) node.nodeValue = old; });
      } else {
        const textEdit = changes.find(item => item.route === c.route && item.selector === c.selector && item.kind === 'text');
        const matchesTextEdit = textEdit && el.textContent.slice(0,1000) === textEdit.after.slice(0,1000);
        if (c.context?.text !== undefined && el.textContent.slice(0,1000) !== c.context.text && !matchesTextEdit) return false;
        const prop = c.kind === 'hide' ? 'display' : c.property;
        const old = el.style.getPropertyValue(prop), priority = el.style.getPropertyPriority(prop);
        el.style.setProperty(prop, c.kind === 'hide' ? 'none' : c.after, 'important');
        undoPreview.push(() => old ? el.style.setProperty(prop, old, priority) : el.style.removeProperty(prop));
      }
      return true;
    }
    function restorePreviews() { while (undoPreview.length) undoPreview.pop()(); }
    function replay() {
      let skipped = 0;
      for (const c of changes.filter(c => c.route === route())) {
        try {
          const els = document.querySelectorAll(c.selector);
          if (els.length !== 1 || els[0].localName !== c.tag || !preview(c, els[0])) skipped++;
        } catch { skipped++; }
      }
      return skipped;
    }
    function record(kind, after, property) {
      if (!ready || busy || !selected?.isConnected) return;
      if (kind === 'text' && !textNode(selected)) return;
      history.push(JSON.stringify(changes));
      const selector = selectorFor(selected);
      let c = changes.find(c => c.route === route() && c.selector === selector && c.kind === kind && c.property === property);
      if (!c) {
        c = {id:crypto.randomUUID(),route:route(),selector,tag:selected.localName,kind,
             before:kind === 'text' ? textNode(selected).nodeValue : getComputedStyle(selected).getPropertyValue(property || 'display'),
             after, context:{html:selected.outerHTML.slice(0,8000),text:selected.textContent.slice(0,1000),parentText:selected.parentElement?.textContent.slice(0,1000)}};
        if (property) c.property = property;
        changes.push(c);
      }
      restorePreviews();
      c.after = after;
      c.note = $('note').value;
      changes = changes.filter(c => c.before !== c.after);
      replay();
      dirty = true;
      draw(); positionOutline();
      status('Preview changed. Save changes to hand this to your agent.');
    }
    $('select').onclick = () => {
      selecting = !selecting;
      $('select').classList.toggle('active', selecting);
      $('select').setAttribute('aria-pressed', String(selecting));
      $('select').textContent = selecting ? 'Selecting… click the page' : 'Select element';
    };
    document.addEventListener('click', e => {
      if (!selecting || e.composedPath().includes(host)) return;
      const el = e.target;
      if (!(el instanceof HTMLElement) || el.closest('script,style,iframe')) return;
      e.preventDefault(); e.stopImmediatePropagation();
      choose(el);
    }, true);
    $('parent').onclick = () => choose(selected.parentElement);
    $('property').onchange = () => { if (selected) $('value').value = getComputedStyle(selected).getPropertyValue($('property').value); };
    $('textApply').onclick = () => record('text', $('text').value);
    $('styleApply').onclick = () => {
      const prop = $('property').value, value = $('value').value.trim();
      if (!CSS.supports(prop, value) || /url\s*\(/i.test(value)) return status('Enter a valid CSS value for this property.');
      record('style', value, prop);
    };
    $('hide').onclick = () => record('hide', 'none');
    $('undo').onclick = () => {
      if (!history.length || busy) return;
      restorePreviews(); changes = JSON.parse(history.pop()); replay(); dirty = true; draw(); positionOutline();
      if (selected?.isConnected) choose(selected);
      status('Last preview edit undone. Save to update your requests.');
    };
    async function save() {
      if (!ready || busy) return;
      busy = true; draw();
      try {
        const response = await fetch(endpoint, {method:'POST',headers:{'Content-Type':'application/json','X-Draft-Token':token},body:JSON.stringify({revision,changes})});
        const doc = await response.json();
        if (!response.ok) throw new Error(doc.error || 'Could not save');
        revision = doc.revision; dirty = false;
        status('Saved to .draft-studio/changes.json. Tell your agent “apply my visual changes”.');
      } catch (error) { status('Not saved: ' + error.message); }
      finally { busy = false; draw(); }
    }
    $('save').onclick = save;
    $('clear').onclick = async () => {
      if (!ready || busy || !confirm('Clear all saved visual requests? Component source will not change.')) return;
      history.push(JSON.stringify(changes)); restorePreviews(); changes = []; dirty = true; draw(); await save();
    };
    $('collapse').onclick = () => {
      $('body').hidden = !$('body').hidden;
      $('collapse').textContent = $('body').hidden ? '+' : '−';
      $('collapse').setAttribute('aria-label', $('body').hidden ? 'Expand editor' : 'Collapse editor');
    };
    addEventListener('scroll',positionOutline,true); addEventListener('resize',positionOutline);
    addEventListener('beforeunload', e => { if(dirty){e.preventDefault();e.returnValue='';} });
    document.addEventListener('keydown',e=>{if(e.key==='Escape' && selecting) $('select').click();});
    fetch(endpoint).then(r => {if(!r.ok)throw new Error('Cannot load requests');return r.json();}).then(doc => {
      revision = doc.revision; changes = doc.changes; ready = true;
      const skipped = replay(); draw();
      status(skipped ? `${skipped} saved previews no longer match this page. Requests remain saved for your agent.` : 'Ready. Select an element to edit.');
    }).catch(e => status(e.message));
    // HMR stays active. Requests survive rerenders even when a preview is reset.
    let currentRoute = route();
    setInterval(() => {
      if (route() !== currentRoute) {
        currentRoute = route(); selected = null; $('controls').hidden = true; outline.hidden = true;
        restorePreviews(); replay();
        status('Route changed. Saved requests are retained; select an element on this page.');
      }
      positionOutline();
    }, 500);
  }
  if (document.readyState === 'complete') setTimeout(start, 300);
  else addEventListener('load', () => setTimeout(start, 300), {once:true});
})();
