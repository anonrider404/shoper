from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from flask_sock import Sock
import json
import time
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = str(uuid.uuid4())
CORS(app)
sock = Sock(app)

SESSION_ID = "mirror"

page_data = {
    'html': '<html><body style="margin:0;padding:20px;font-family:monospace;">Waiting for connection...<br><br>Paste the capture script into the target website console.</body></html>',
    'title': 'Mirror',
    'timestamp': 0,
    'scrollX': 0,
    'scrollY': 0
}

original_ws = None
viewer_ws = None

STREAM_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Mirror</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { overflow: hidden; background: white; }
        iframe {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            border: none;
        }
    </style>
</head>
<body>
    <iframe id="frame" sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-modals allow-top-navigation"></iframe>
    <script>
        const frame = document.getElementById('frame');
        let lastUpdate = 0;
        let lastHtmlHash = '';
        let pendingActions = [];
        let isApplying = false;
        let ws = null;
        let userInteracting = false;
        let interactionTimer = null;
        let reconnectAttempts = 0;
        let pingInterval = null;

        function connectWebSocket() {
            if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
            ws = new WebSocket(`ws://localhost:5000/viewer-ws/mirror`);
            
            ws.onopen = () => {
                console.log('[Viewer WS] Connected');
                reconnectAttempts = 0;
                if (pingInterval) clearInterval(pingInterval);
                pingInterval = setInterval(() => {
                    if (ws.readyState === WebSocket.OPEN) ws.send('ping');
                }, 30000);
            };
            
            ws.onmessage = (event) => {
                if (event.data === 'pong') return;
                try {
                    const action = JSON.parse(event.data);
                    pendingActions.push(action);
                    processNextAction();
                } catch(e) {}
            };
            
            ws.onclose = () => {
                if (pingInterval) clearInterval(pingInterval);
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
                reconnectAttempts++;
                setTimeout(connectWebSocket, delay);
            };
            ws.onerror = (err) => ws.close();
        }

        function processNextAction() {
            if (isApplying || pendingActions.length === 0) return;
            isApplying = true;
            const action = pendingActions.shift();
            applyActionWithRetry(action, 0);
            setTimeout(() => { isApplying = false; processNextAction(); }, 10);
        }

        function applyActionWithRetry(action, retryCount) {
            const doc = frame.contentDocument || frame.contentWindow.document;
            if (!doc) {
                if (retryCount < 5) setTimeout(() => applyActionWithRetry(action, retryCount+1), 20);
                else isApplying = false;
                return;
            }
            
            let el = resolveSelector(doc, action.target);
            if (!el && action.type === 'input') {
                if (action.target.includes('user') || action.target.includes('email'))
                    el = doc.querySelector('input[type="text"], input[type="email"], input[name*="user"]');
                else if (action.target.includes('pass'))
                    el = doc.querySelector('input[type="password"], input[name*="pass"]');
            }
            if (!el && action.type === 'click') {
                el = doc.querySelector('button, input[type="submit"]');
            }
            
            if (!el) {
                if (retryCount < 5) setTimeout(() => applyActionWithRetry(action, retryCount+1), 20);
                return;
            }
            
            const marker = Date.now().toString();
            el.setAttribute('data-mirror', marker);
            try {
                switch (action.type) {
                    case 'click':
                        el.click();
                        el.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                        break;
                    case 'input':
                        el.focus();
                        el.value = action.data.value;
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                        break;
                    case 'change':
                        if (el.type === 'checkbox' || el.type === 'radio')
                            el.checked = action.data.checked;
                        else
                            el.value = action.data.value;
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                        break;
                    case 'focus': el.focus(); break;
                    case 'blur': el.blur(); break;
                }
            } catch(e) {}
            setTimeout(() => el.removeAttribute('data-mirror'), 200);
        }

        function resolveSelector(doc, selector) {
            if (!selector) return null;
            try {
                if (selector.startsWith('/')) {
                    return doc.evaluate(selector, doc, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                } else {
                    return doc.querySelector(selector);
                }
            } catch(e) {
                return null;
            }
        }

        async function poll() {
            try {
                const res = await fetch('/page/mirror');
                const data = await res.json();
                if (data.html && data.timestamp > lastUpdate && !userInteracting) {
                    // Prevent white screen: ensure HTML contains <body>
                    if (!data.html.includes('<body')) {
                        // Bad HTML – skip update
                        return;
                    }
                    const hash = await simpleHash(data.html);
                    if (hash !== lastHtmlHash) {
                        lastHtmlHash = hash;
                        lastUpdate = data.timestamp;
                        const doc = frame.contentDocument || frame.contentWindow.document;
                        const activeId = doc.activeElement?.id;
                        const activeName = doc.activeElement?.name;
                        const scrollX = frame.contentWindow?.scrollX || 0;
                        const scrollY = frame.contentWindow?.scrollY || 0;
                        
                        try {
                            doc.open();
                            doc.write(data.html);
                            doc.close();
                            document.title = data.title || 'Mirror';
                        } catch(e) {
                            // If write fails, keep old content
                            return;
                        }
                        
                        setTimeout(() => {
                            if (frame.contentWindow) {
                                frame.contentWindow.scrollTo(data.scrollX || 0, data.scrollY || 0);
                            }
                            if (activeId) doc.getElementById(activeId)?.focus();
                            else if (activeName) doc.querySelector(`[name="${activeName}"]`)?.focus();
                            injectForwarder(doc);
                        }, 100);
                    } else {
                        lastUpdate = data.timestamp;
                    }
                }
            } catch(e) {}
            setTimeout(poll, 200);
        }

        async function simpleHash(str) {
            const encoder = new TextEncoder();
            const data = encoder.encode(str);
            const hash = await crypto.subtle.digest('SHA-1', data);
            return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
        }

        function getXPath(el) {
            if (el.id) return '//*[@id="' + el.id + '"]';
            let parts = [];
            while (el && el.nodeType === Node.ELEMENT_NODE) {
                let idx = 0;
                let sib = el.previousSibling;
                while (sib) {
                    if (sib.nodeType === 1 && sib.tagName === el.tagName) idx++;
                    sib = sib.previousSibling;
                }
                parts.unshift(idx ? el.tagName.toLowerCase() + '[' + (idx+1) + ']' : el.tagName.toLowerCase());
                el = el.parentNode;
            }
            return '/' + parts.join('/');
        }

        function injectForwarder(doc) {
            const old = doc.getElementById('viewer-forwarder');
            if (old) old.remove();
            const script = doc.createElement('script');
            script.id = 'viewer-forwarder';
            script.textContent = `
                (function() {
                    function getXPath(el) {
                        if (el.id) return '//*[@id="' + el.id + '"]';
                        let parts = [];
                        while (el && el.nodeType === Node.ELEMENT_NODE) {
                            let idx = 0;
                            let sib = el.previousSibling;
                            while (sib) {
                                if (sib.nodeType === 1 && sib.tagName === el.tagName) idx++;
                                sib = sib.previousSibling;
                            }
                            parts.unshift(idx ? el.tagName.toLowerCase() + '[' + (idx+1) + ']' : el.tagName.toLowerCase());
                            el = el.parentNode;
                        }
                        return '/' + parts.join('/');
                    }
                    function sendToParent(type, target, data) {
                        if (target.getAttribute && target.getAttribute('data-mirror')) return;
                        const sel = target.id ? '#' + target.id : getXPath(target);
                        window.parent.postMessage({
                            type: 'viewer-event',
                            eventType: type,
                            target: sel,
                            data: data
                        }, '*');
                    }
                    function notifyInteraction(active) {
                        window.parent.postMessage({ type: 'interaction', active: active }, '*');
                    }
                    document.addEventListener('focusin', (e) => {
                        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) {
                            notifyInteraction(true);
                        }
                    }, true);
                    document.addEventListener('focusout', (e) => {
                        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) {
                            notifyInteraction(false);
                        }
                    }, true);
                    document.addEventListener('click', (e) => {
                        if (e.target.closest && e.target.closest('[data-mirror]')) return;
                        e.preventDefault();
                        e.stopPropagation();
                        sendToParent('click', e.target, {});
                    }, true);
                    document.addEventListener('input', (e) => {
                        if (e.target.closest && e.target.closest('[data-mirror]')) return;
                        sendToParent('input', e.target, { value: e.target.value });
                    }, true);
                    document.addEventListener('change', (e) => {
                        if (e.target.closest && e.target.closest('[data-mirror]')) return;
                        sendToParent('change', e.target, { value: e.target.value, checked: e.target.checked });
                    }, true);
                    document.addEventListener('focus', (e) => {
                        if (e.target.closest && e.target.closest('[data-mirror]')) return;
                        sendToParent('focus', e.target, {});
                    }, true);
                    document.addEventListener('blur', (e) => {
                        if (e.target.closest && e.target.closest('[data-mirror]')) return;
                        sendToParent('blur', e.target, {});
                    }, true);
                })();
            `;
            if (doc.body) doc.body.appendChild(script);
            else {
                const obs = new MutationObserver(() => {
                    if (doc.body) { doc.body.appendChild(script); obs.disconnect(); }
                });
                obs.observe(doc, { childList: true, subtree: true });
            }
        }

        window.addEventListener('message', (event) => {
            if (event.data.type === 'viewer-event') {
                fetch('/viewer-action', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        session: 'mirror',
                        type: event.data.eventType,
                        target: event.data.target,
                        data: event.data.data
                    })
                }).catch(()=>{});
            } else if (event.data.type === 'interaction') {
                userInteracting = event.data.active;
                if (interactionTimer) clearTimeout(interactionTimer);
                if (!userInteracting) {
                    interactionTimer = setTimeout(() => { userInteracting = false; }, 500);
                }
            }
        });

        connectWebSocket();
        poll();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(STREAM_HTML)

@app.route('/update', methods=['POST'])
def update():
    global page_data
    data = request.json
    if data.get('id') == SESSION_ID:
        page_data = {
            'html': data['html'],
            'title': data['title'],
            'timestamp': time.time(),
            'scrollX': data.get('scrollX', 0),
            'scrollY': data.get('scrollY', 0)
        }
    return 'OK'

@app.route('/page/<sid>')
def get_page(sid):
    if sid == SESSION_ID:
        return jsonify(page_data)
    return jsonify({'html': 'Invalid session', 'timestamp': 0})

@app.route('/event', methods=['POST'])
def receive_event():
    data = request.json
    if data.get('id') == SESSION_ID and viewer_ws:
        try:
            viewer_ws.send(json.dumps({
                'type': data['type'],
                'target': data['target'],
                'data': data.get('data', {})
            }))
        except:
            pass
    return 'OK'

@app.route('/viewer-action', methods=['POST'])
def viewer_action():
    data = request.json
    if data.get('session') == SESSION_ID and original_ws:
        try:
            original_ws.send(json.dumps({
                'type': data['type'],
                'target': data['target'],
                'data': data.get('data', {})
            }))
        except:
            pass
    return 'OK'

@sock.route('/ws/mirror')
def original_websocket(ws):
    global original_ws
    original_ws = ws
    print("[ORIGINAL] Connected")
    try:
        while True:
            msg = ws.receive()
            if msg == 'ping':
                ws.send('pong')
    except:
        pass
    finally:
        original_ws = None
        print("[ORIGINAL] Disconnected")

@sock.route('/viewer-ws/mirror')
def viewer_websocket(ws):
    global viewer_ws
    viewer_ws = ws
    print("[VIEWER] Connected")
    try:
        while True:
            msg = ws.receive()
            if msg == 'ping':
                ws.send('pong')
    except:
        pass
    finally:
        viewer_ws = None
        print("[VIEWER] Disconnected")
