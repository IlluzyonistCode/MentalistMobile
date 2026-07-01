import { State } from '../state.js';
import { Utils } from '../utils/logger.js';

let _seq = 0;

function uid(base) {
    return base + (++_seq);
}

export const WebSocketClient = {
    _ws: null,
    _ready: false,
    _stopFlag: false,
    _statusView: null,

    setStatusView: function(tv) {
        WebSocketClient._statusView = tv;
    },

    open: function() {
        Utils.log('[WS.open] stopFlag=false');

        WebSocketClient._stopFlag = false;

        if (!State.network.wsUrl) {
            try {
                const RealWebSocket = Java.use('okhttp3.internal.ws.RealWebSocket');

                Java.choose(RealWebSocket, {
                    onMatch: function(instance) {
                        try {
                            const req = instance.request();
                            const u = String(req.url().toString());

                            if (u && u.startsWith('wss://')) {
                                State.network.wsUrl = u;

                                Utils.log('[WS.open] wsUrl via Java.choose: ' + u.slice(0, 80));

                                return 'stop';
                            }
                        } catch (e) {}
                    },
                    onComplete: function() {
                        Utils.log('[WS.open] Java.choose done, wsUrl=' + !!State.network.wsUrl);
                    }
                });
            } catch (e) {
                Utils.log('[WS.open] Java.choose failed: ' + e);
            }
        }

        const url = State.network.wsUrl;

        if (url && !WebSocketClient._ws)
            WebSocketClient._thread(function() {
                WebSocketClient._openWs(url);
            });
        
        else Utils.log('[WS.open] wsUrl not available yet');
    },

    close: function() {
        Utils.log('[WS.close] closing');

        WebSocketClient._stopFlag = true;

        if (WebSocketClient._ws) {
            try {
                WebSocketClient._ws.close();
            } catch (e) {}

            WebSocketClient._ws = null;
        }

        WebSocketClient._ready = false;
    },

    send: function(payload) {
        if (!WebSocketClient._ready || !WebSocketClient._ws) {
            Utils.log('[WS.send] not ready');

            return false;
        }

        try {
            const ByteString = Java.use('okio.ByteString');

            const bs = ByteString.encodeUtf8(payload);
            WebSocketClient._ws.send(bs);

            return true;
        } catch (e) {
            Utils.log('[WS.send] ERROR: ' + e);

            return false;
        }
    },

    _openWs: function(url) {
        if (WebSocketClient._stopFlag) return;

        const OkHttpClient = Java.use('okhttp3.OkHttpClient');
        const Request = Java.use('okhttp3.Request$Builder');
        const WebSocketListener = Java.use('okhttp3.WebSocketListener');

        const ListenerClass = Java.registerClass({
            name: uid('com.frida.WSListener'),
            implements: [WebSocketListener],
            methods: {
                onOpen: function(ws, response) {
                    WebSocketClient._ws = ws;
                    WebSocketClient._ready = true;

                    Utils.log('[WS.onOpen] connected');

                    WebSocketClient._setStatus('Connected');
                },
                onMessage: [{
                    returnType: 'void',
                    argumentTypes: ['okhttp3.WebSocket', 'java.lang.String'],
                    implementation: function(ws, text) {
                        Utils.log('[WS.onMessage] ' + text.slice(0, 100));
                    }
                }],
                onFailure: function(ws, t, response) {
                    Utils.log('[WS.onFailure] ' + t);

                    WebSocketClient._ready = false;
                    WebSocketClient._setStatus('Failed');
                },
                onClosing: function(ws, code, reason) {
                    Utils.log('[WS.onClosing] ' + code);
                },
                onClosed: function(ws, code, reason) {
                    Utils.log('[WS.onClosed] ' + code);

                    WebSocketClient._ready = false;
                    WebSocketClient._setStatus('Closed');
                }
            }
        });

        const listener = ListenerClass.$new();
        const client = OkHttpClient.$new();
        const req = Request.$new().url(url).build();

        client.newWebSocket(req, listener);

        WebSocketClient._setStatus('Connecting...');
    },

    _thread: function(fn) {
        const Thread = Java.use('java.lang.Thread');
        const Runnable = Java.registerClass({
            name: uid('com.frida.WSRunnable'),
            implements: ['java.lang.Runnable'],
            methods: {
                run: function() {
                    try {
                        fn();
                    } catch (e) {
                        Utils.log('[WS._thread] ERROR: ' + e);
                    }
                }
            }
        });
        Thread.$new(Runnable.$new()).start();
    },

    _setStatus: function(msg) {
        if (!WebSocketClient._statusView) return;

        try {
            Java.scheduleOnMainThread(function() {
                try {
                    const JavaString = Java.use('java.lang.String');
                    const TextView = Java.use('android.widget.TextView');

                    Java.cast(WebSocketClient._statusView, TextView)
                        .setText.overload('java.lang.CharSequence')
                        .call(WebSocketClient._statusView, JavaString.$new(msg));
                } catch (e) {}
            });
        } catch (e) {}
    }
};
