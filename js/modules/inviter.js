import { State } from '../state.js';
import { Utils } from '../utils/logger.js';

if (!globalThis._inviterSeq) globalThis._inviterSeq = 0;

function uid(base) { return base + (++globalThis._inviterSeq); }

function setStatus(textView, msg) {
    if (!textView) return;

    try {
        Java.scheduleOnMainThread(function() {
            try {
                const JavaString = Java.use('java.lang.String');
                const TextView = Java.use('android.widget.TextView');

                Java.cast(textView, TextView)
                    .setText.overload('java.lang.CharSequence')
                    .call(textView, JavaString.$new(msg));
            } catch (e) {}
        });
    } catch (e) {}
}

function encodeUrl(str) {
    if (!str) return '';

    return str.split('').map(function(c) {
        if (/[A-Za-z0-9\-_.~]/.test(c)) return c;

        const hex = c.charCodeAt(0).toString(16).toUpperCase();

        return '%' + (hex.length < 2 ? '0' + hex : hex);
    }).join('');
}

function getAppVersion() {
    try {
        if (!State.context) return '4194913';

        const PackageManager = Java.use('android.content.pm.PackageManager');
        const pkgName = String(State.context.getPackageName());
        const pkgInfo = State.context.getPackageManager().getPackageInfo(pkgName, 0);
        const versionCode = pkgInfo.versionCode.value;

        Utils.log('[InviterSession] App version code: ' + versionCode);

        return String(versionCode);
    } catch (e) {
        Utils.log('[InviterSession.getAppVersion] ERROR: ' + e + ', using default');

        return '4194913';
    }
}

function buildWsUrl(firebaseToken, cfJwt) {
    if (!firebaseToken) return null;

    const appVersion = getAppVersion();

    const params = [
        'firebaseToken=' + encodeUrl(firebaseToken),
        'gameId=undefined',
        'playWithFriends=true',
        'gameMode=en',
        'platform=android',
        'appVersionNumber=' + appVersion,
        'ids=1'
    ];

    if (cfJwt)
        params.push('Cf-JWT=' + encodeUrl(cfJwt));

    params.push('apiV=1');
    params.push('b=92');
    params.push('EIO=4');
    params.push('transport=websocket');

    return 'https://game.api-wolvesville.com/socket.io/?' + params.join('&');
}

export const InviterSession = {
    _ws: null,
    _ready: false,
    _stopFlag: false,
    _statusView: null,
    _pending: null,

    setStatusView: function(tv) { InviterSession._statusView = tv; },

    open: function() {
        Utils.log('[InviterSession.open]');

        InviterSession._stopFlag = false;

        let url = State.network.wsUrl;

        if (!url) {
            const bearer = State.network.bearerToken || State.auth.bearerToken;
            const cfJwt = State.auth.cfJwt;

            if (bearer && cfJwt) {
                url = buildWsUrl(bearer, cfJwt);

                if (url) {
                    Utils.log('[InviterSession.open] Built wsUrl from tokens');
                    State.network.wsUrl = url;
                }
            }
        }

        if (!url) {
            try {
                Java.choose('okhttp3.internal.ws.RealWebSocket', {
                    onMatch: function(instance) {
                        if (State.network.wsUrl) return;

                        try {
                            const u = String(instance.url());

                            if (u && u.includes('wolvesville')) {
                                State.network.wsUrl = u;
                                State.network.realWebSocket = Java.retain(instance);

                                Utils.log('[InviterSession.open] wsUrl via Java.choose: ' + u.slice(0, 80));
                            }
                        } catch (e) {}
                    },
                    onComplete: function() {
                        Utils.log('[InviterSession.open] Java.choose done, wsUrl=' + !!State.network.wsUrl);
                    }
                });
            } catch (e) {
                Utils.log('[InviterSession.open] Java.choose failed: ' + e);
            }

            url = State.network.wsUrl;
        }

        if (url && !InviterSession._ws)
            InviterSession._thread(function() { InviterSession._openWs(url); });
    },

    close: function() {
        Utils.log('[InviterSession.close]');

        InviterSession._stopFlag = true;
        InviterSession._pending = null;

        if (InviterSession._ws) {
            try {
                InviterSession._ws.close(1000, 'menu closed');
            } catch (_) {}

            try {
                InviterSession._ws.$dispose();
            } catch (_) {}

            InviterSession._ws = null;
            InviterSession._ready = false;
        }

        setStatus(InviterSession._statusView, 'Ready');
    },

    resolveAndInvite: function(playerName, count, delayMs, statusView) {
        InviterSession._statusView = statusView;
        InviterSession._stopFlag = false;

        Utils.log('[InviterSession] "' + playerName + '" count=' + count + ' delay=' + delayMs);

        setStatus(statusView, 'Resolving: ' + playerName + '...');

        const apiKey = State.network.botApiKey || '';

        if (!apiKey) {
            setStatus(statusView, 'Error: API key not ready');

            return;
        }

        InviterSession._thread(function() {
            try {
                const OkHttpClient = Java.use('okhttp3.OkHttpClient');
                const RequestBuilder = Java.use('okhttp3.Request$Builder');

                const http = OkHttpClient.$new();
                const apiUrl = 'https://api.wolvesville.com/players/search?username=' + encodeUrl(playerName);
                const req = RequestBuilder.$new()
                    .url(apiUrl)
                    .addHeader('Authorization', 'Bot ' + apiKey)
                    .addHeader('Accept', 'application/json')
                    .build();

                const resp = http.newCall(req).execute();
                const code = resp.code();
                const bodyStr = String(resp.body().string());

                if (!resp.isSuccessful()) {
                    setStatus(statusView, 'HTTP Error ' + code);

                    return;
                }

                const body = Utils.safeJsonParse(bodyStr);

                if (!body || !body.id) {
                    setStatus(statusView, 'Player not found: ' + playerName);

                    return;
                }

                const targetId = String(body.id);

                Utils.log('[InviterSession] resolved "' + playerName + '" -> ' + targetId);

                if (InviterSession._ready && InviterSession._ws) {
                    setStatus(statusView, 'Sending... 0/' + count);

                    InviterSession._doInvite(targetId, count, delayMs, statusView);

                    return;
                }

                InviterSession._pending = { playerId: targetId, count, delayMs, statusView };

                setStatus(statusView, 'Connecting...');

                let wsUrl = State.network.wsUrl;

                if (!wsUrl) {
                    const bearer = State.network.bearerToken || State.auth.bearerToken;
                    const cfJwt = State.auth.cfJwt;

                    if (bearer && cfJwt) {
                        wsUrl = buildWsUrl(bearer, cfJwt);

                        if (wsUrl) {
                            Utils.log('[InviterSession] Built wsUrl from tokens');
                            State.network.wsUrl = wsUrl;
                        }
                    }
                }

                if (!wsUrl && State.network.realWebSocket) {
                    try {
                        const u = String(State.network.realWebSocket.url());

                        if (u) State.network.wsUrl = u;

                        wsUrl = State.network.wsUrl;
                    } catch (e) {}
                }

                if (!wsUrl && State.network.websocket) {
                    try {
                        const u = String(State.network.websocket.request().url().toString());

                        if (u) State.network.wsUrl = u;

                        wsUrl = State.network.wsUrl;
                    } catch (e) {}
                }

                if (!wsUrl) {
                    try {
                        Java.choose('okhttp3.internal.ws.RealWebSocket', {
                            onMatch: function(instance) {
                                if (State.network.wsUrl) return;

                                try {
                                    const u = String(instance.url());

                                    if (u && u.includes('wolvesville')) {
                                        State.network.wsUrl = u;
                                        State.network.realWebSocket = Java.retain(instance);
                                    }
                                } catch (e) {}
                            },
                            onComplete: function() {}
                        });
                    } catch (e) {}

                    wsUrl = State.network.wsUrl;
                }

                if (!wsUrl) {
                    setStatus(statusView, 'Error: no WS URL');

                    return;
                }

                if (!InviterSession._ws) InviterSession._openWs(wsUrl);
            } catch (e) {
                Utils.log('[InviterSession.resolveAndInvite] ERROR: ' + e);

                setStatus(statusView, 'Error: ' + String(e));
            }
        });
    },

    _openWs: function(wsUrl) {
        if (InviterSession._ws) return;

        try {
            Utils.log('[InviterSession._openWs] ' + wsUrl.slice(0, 80));

            const OkHttpClient = Java.use('okhttp3.OkHttpClient');
            const RequestBuilder = Java.use('okhttp3.Request$Builder');
            const WebSocketListener = Java.use('okhttp3.WebSocketListener');

            const self = InviterSession;

            const listenerCls = Java.registerClass({
                name: uid('com.mentalist.InviterListener'),
                superClass: WebSocketListener,
                methods: {
                    'onOpen': {
                        returnType: 'void',
                        argumentTypes: ['okhttp3.WebSocket', 'okhttp3.Response'],
                        implementation: function(ws, response) {
                            try {
                                Utils.log('[InviterSession.WS] onOpen — sending 40');

                                self._ws = Java.retain(ws);

                                ws.send('40');
                            } catch (e) {
                                Utils.log('[InviterSession.WS] onOpen ERROR: ' + e);
                            }
                        }
                    },
                    'onMessage': [{
                            returnType: 'void',
                            argumentTypes: ['okhttp3.WebSocket', 'java.lang.String'],
                            implementation: function(ws, text) {
                                try {
                                    const t = String(text);

                                    if (t === '2') { ws.send('3'); return; }

                                    if (t.startsWith('42')) {
                                        const parsed = Utils.parseSocketIoEnvelope(t);

                                        if (parsed && parsed.event === 'game-joined') {
                                            Utils.log('[InviterSession.WS] game-joined');

                                            self._ready = true;

                                            setStatus(self._statusView, 'Session ready');

                                            self._startHeartbeat();

                                            if (self._pending) {
                                                const p = self._pending;

                                                self._pending = null;
                                                self._doInvite(p.playerId, p.count, p.delayMs, p.statusView);
                                            }
                                        }
                                    }
                                } catch (e) {
                                    Utils.log('[InviterSession.WS] onMessage ERROR: ' + e);
                                }
                            }
                        },
                        {
                            returnType: 'void',
                            argumentTypes: ['okhttp3.WebSocket', 'okio.ByteString'],
                            implementation: function(ws, bytes) {}
                        }
                    ],
                    'onClosing': {
                        returnType: 'void',
                        argumentTypes: ['okhttp3.WebSocket', 'int', 'java.lang.String'],
                        implementation: function(ws, code, reason) {
                            Utils.log('[InviterSession.WS] onClosing ' + code);

                            try {
                                ws.close(1000, '');
                            } catch (_) {}
                        }
                    },
                    'onClosed': {
                        returnType: 'void',
                        argumentTypes: ['okhttp3.WebSocket', 'int', 'java.lang.String'],
                        implementation: function(ws, code, reason) {
                            Utils.log('[InviterSession.WS] onClosed ' + code);

                            if (self._ws)
                                try {
                                    self._ws.$dispose();
                                } catch (_) {}

                            self._ws = null;
                            self._ready = false;
                        }
                    },
                    'onFailure': {
                        returnType: 'void',
                        argumentTypes: ['okhttp3.WebSocket', 'java.lang.Throwable', 'okhttp3.Response'],
                        implementation: function(ws, throwable, response) {
                            try {
                                const msg = throwable ? String(throwable.getMessage()) : 'unknown';

                                Utils.log('[InviterSession.WS] onFailure: ' + msg);

                                setStatus(self._statusView, 'WS error: ' + msg);

                                if (self._ws)
                                    try {
                                        self._ws.$dispose();
                                    } catch (_) {}

                                self._ws = null;
                                self._ready = false;
                            } catch (e) {}
                        }
                    }
                }
            });

            const client = OkHttpClient.$new();
            const request = RequestBuilder.$new()
                .url(wsUrl)
                .addHeader('User-Agent', 'okhttp/4.9.2')
                .addHeader('Origin', 'https://game.api-wolvesville.com')
                .build();

            client.newWebSocket(request, listenerCls.$new());

            Utils.log('[InviterSession._openWs] newWebSocket called');
        } catch (e) {
            Utils.log('[InviterSession._openWs] ERROR: ' + e);

            setStatus(InviterSession._statusView, 'WS init error: ' + String(e));
        }
    },

    _startHeartbeat: function() {
        const self = InviterSession;

        InviterSession._thread(function() {
            try {
                const Thread = Java.use('java.lang.Thread');

                while (self._ws !== null && !self._stopFlag) {
                    Thread.sleep(30000);

                    if (self._ws && !self._stopFlag)
                        try {
                            self._ws.send('42["player-heartbeat"]');
                        } catch (_) {
                            break;
                        }
                }
            } catch (e) {}
        });
    },

    _doInvite: function(playerId, count, delayMs, statusView) {
        const self = InviterSession;

        InviterSession._thread(function() {
            let sent = 0;

            try {
                const Thread = Java.use('java.lang.Thread');
                for (let i = 0; i < count; i++) {
                    if (self._stopFlag || !self._ws) {
                        setStatus(statusView, 'Stopped: ' + sent + '/' + count);

                        return;
                    }

                    const frame = '42' + JSON.stringify([
                        'friends-game-invite-player',
                        JSON.stringify({ targetPlayerId: playerId })
                    ]);

                    try {
                        self._ws.send(frame);
                        
                        sent++;
                    } catch (e) {
                        setStatus(statusView, 'Send error at ' + sent + '/' + count);

                        Utils.log('[InviterSession._doInvite] send ERROR: ' + e);

                        return;
                    }

                    setStatus(statusView, 'Sending... ' + sent + '/' + count);

                    if (i < count - 1) Thread.sleep(delayMs);
                }

                setStatus(statusView, 'Done: ' + sent + '/' + count + ' sent');

                Utils.log('[InviterSession._doInvite] DONE ' + sent + '/' + count);
            } catch (e) {
                Utils.log('[InviterSession._doInvite] ERROR: ' + e);

                setStatus(statusView, 'Error: ' + String(e));
            }
        });
    },

    _thread: function(fn) {
        try {
            const Runnable = Java.use('java.lang.Runnable');
            const Thread = Java.use('java.lang.Thread');

            const cls = Java.registerClass({
                name: uid('com.mentalist.InviterThread'),
                implements: [Runnable],
                methods: {
                    run: function() {
                        try { fn(); } catch (e) { Utils.log('[InviterSession._thread] ' + e); }
                    }
                }
            });

            Thread.$new(cls.$new()).start();
        } catch (e) {
            Utils.log('[InviterSession._thread] ERROR: ' + e);
        }
    }
};

export const Invites = {
    sendSingle: function(playerId) {
        try {
            globalThis._mq.push(JSON.stringify({
                type: 'invite_request',
                playerId: String(playerId),
                count: 1,
                delayMs: 0
            }));

            return true;
        } catch (e) {
            Utils.log('[Invites.sendSingle] ERROR: ' + e);

            return false;
        }
    },

    sendMultiple: function(playerId, count, delayMs) {
        try {
            globalThis._mq.push(JSON.stringify({
                type: 'invite_request',
                playerId: String(playerId),
                count: count,
                delayMs: delayMs
            }));

            return true;
        } catch (e) {
            Utils.log('[Invites.sendMultiple] ERROR: ' + e);

            return false;
        }
    }
};
