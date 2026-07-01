/**
 * transport.js — слой коммуникации агента с сервером.
 *
 * В debug режиме (ADB): использует старый механизм через _mq + rpc.exports
 * В production режиме: открывает WebSocket к Mentalist Server
 *
 * Режим определяется константой MENTALIST_MODE:
 *   'debug'      — ADB + Python local
 *   'production' — WS к серверу
 */

export const Transport = {
    _mode: 'debug',
    _ws: null,
    _serverUrl: null,
    _reconnectTimer: null,
    _messageHandlers: {},
    _connected: false,
    _botApiKey: null,

    // ── Инициализация ─────────────────────────────────────────────────────────

    init: function(mode, serverUrl) {
        Transport._mode = mode || 'debug';
        Transport._serverUrl = serverUrl;

        if (Transport._mode === 'production' && serverUrl) {
            Utils.log('[Transport] Production mode, connecting to: ' + serverUrl);
            Transport._connect();
        } else {
            Utils.log('[Transport] Debug mode (ADB/RPC)');
        }
    },

    // ── Отправка сообщения серверу ────────────────────────────────────────────

    send: function(type, payload) {
        const msg = JSON.stringify({ type: type, ...payload });

        if (Transport._mode === 'production') {
            if (Transport._ws && Transport._connected) {
                try {
                    Transport._ws.send(msg);
                } catch (e) {
                    Utils.log('[Transport] WS send error: ' + e);
                    globalThis._mq.push(msg);
                }
            } else {
                // Буфер пока не подключены
                globalThis._mq.push(msg);
            }
        } else {
            // Debug: кладём в _mq, Python поллит
            globalThis._mq.push(msg);
        }
    },

    // ── Регистрация обработчика входящих сообщений от сервера ─────────────────

    on: function(type, handler) {
        Transport._messageHandlers[type] = handler;
    },

    // ── Получение bot API key ─────────────────────────────────────────────────

    getBotApiKey: function() {
        return Transport._botApiKey;
    },

    // ── WebSocket (production) ────────────────────────────────────────────────

    _connect: function() {
        try {
            Java.perform(function() {
                try {
                    const OkHttpClient = Java.use('okhttp3.OkHttpClient');
                    const Request = Java.use('okhttp3.Request');
                    const WebSocketListener = Java.use('okhttp3.WebSocketListener');

                    const client = OkHttpClient.$new();
                    const request = Request.Builder.$new()
                        .url(Transport._serverUrl)
                        .build();

                    const listener = Java.extend(WebSocketListener, {
                        onOpen: function(ws, response) {
                            Transport._ws = ws;
                            Transport._connected = true;
                            Utils.log('[Transport] WS connected to server');
                            const buffered = globalThis._mq.splice(0);
                            for (let i = 0; i < buffered.length; i++) {
                                try { ws.send(buffered[i]); } catch(e) {}
                            }
                        },
                        onMessage: function(ws, text) {
                            try {
                                const msg = JSON.parse(text);
                                const handler = Transport._messageHandlers[msg.type];
                                if (handler) handler(msg);
                            } catch (e) {
                                Utils.log('[Transport] onMessage parse error: ' + e);
                            }
                        },
                        onClosed: function(ws, code, reason) {
                            Transport._connected = false;
                            Transport._ws = null;
                            Utils.log('[Transport] WS closed: ' + code);
                            Transport._scheduleReconnect();
                        },
                        onFailure: function(ws, t, response) {
                            Transport._connected = false;
                            Transport._ws = null;
                            Utils.log('[Transport] WS failure: ' + t);
                            Transport._scheduleReconnect();
                        }
                    });

                    client.newWebSocket(request, listener.$new());
                } catch (e) {
                    Utils.log('[Transport] _connect inner error: ' + e);
                    Transport._scheduleReconnect();
                }
            });
        } catch (e) {
            Utils.log('[Transport] _connect error: ' + e);
            Transport._scheduleReconnect();
        }
    },

    _scheduleReconnect: function() {
        Java.perform(function() {
            Java.use('java.lang.Thread').sleep(5000);
        });
        Utils.log('[Transport] Reconnecting...');
        Transport._connect();
    }
};
