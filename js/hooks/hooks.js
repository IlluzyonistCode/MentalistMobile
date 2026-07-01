import { State } from '../state.js';
import { Utils } from '../utils/logger.js';
import { Game } from '../game/game.js';
import { LOG_HTTP, MENTALIST_MODE } from '../constants.js';

// Унифицированная отправка: в debug кладём в _mq, в production — через Transport WS
const sendToServer = function(obj) {
    const str = JSON.stringify(obj);
    if (MENTALIST_MODE === 'production' && globalThis._transport) {
        globalThis._transport.send(obj.type, obj);
    } else {
        globalThis._mq.push(str);
    }
};

export const Hooks = {
    setupWebSocket: function() {
        try {
            Utils.log('[Hooks.setupWebSocket] START');

            const RealWebSocket = Java.use('okhttp3.internal.ws.RealWebSocket');

            Utils.log('[Hooks.setupWebSocket] RealWebSocket class acquired');

            try {
                RealWebSocket.onReadMessage.overload('java.lang.String').implementation = function(text) {
                    try {
                        if (!State.network.wsUrl) {
                            try {
                                const req = this.request();
                                const wsUrl = String(req.url().toString());

                                const bearer = String(req.header('Authorization') || '');
                                const cfJwt = String(req.header('Cf-Jwt') || req.header('cf-jwt') || '');

                                State.network.wsUrl = wsUrl;

                                Utils.log('[Hooks.WS] onReadMessage: wsUrl=' + wsUrl + ' bearer=' + bearer.substring(0, 20) + ' cfJwt=' + cfJwt.substring(0, 20));

                                globalThis._mq.push(JSON.stringify({
                                    type: 'ws_connection',
                                    url: wsUrl,
                                    bearer: bearer,
                                    cf_jwt: cfJwt
                                }));
                            } catch (urlErr) {
                                globalThis._mq.push(JSON.stringify({ type: 'log', message: '[Hooks.WS] onReadMessage: url capture failed: ' + urlErr }));
                            }
                        }

                        sendToServer({
                            type: 'ws_message',
                            direction: 'INBOUND',
                            data: text,
                            dataType: 'String'
                        });

                        const parsed = Utils.parseSocketIoEnvelope(text);

                        if (parsed) Game.handleEvent(parsed.event, parsed.payload);
                    } catch (e) {
                        Utils.log('[Hooks.WS] onReadMessage(String) handler ERROR: ' + e);
                    }

                    return this.onReadMessage(text);
                };

                Utils.log('[Hooks.setupWebSocket] onReadMessage(String) hooked');
            } catch (e) {
                Utils.log('[Hooks.setupWebSocket] WARN: onReadMessage(String) hook failed: ' + e);
            }

            try {
                RealWebSocket.onReadMessage.overload('okio.ByteString').implementation = function(bytes) {
                    try {
                        const text = bytes.utf8();

                        sendToServer({
                            type: 'ws_message',
                            direction: 'INBOUND',
                            data: text,
                            dataType: 'ByteString'
                        });

                        const parsed = Utils.parseSocketIoEnvelope(text);

                        if (parsed) Game.handleEvent(parsed.event, parsed.payload);
                    } catch (e) {
                        Utils.log('[Hooks.WS] onReadMessage(ByteString) handler ERROR: ' + e);
                    }

                    return this.onReadMessage(bytes);
                };

                Utils.log('[Hooks.setupWebSocket] onReadMessage(ByteString) hooked');
            } catch (e) {
                Utils.log('[Hooks.setupWebSocket] WARN: onReadMessage(ByteString) hook failed: ' + e);
            }

            try {
                const originalSend = RealWebSocket.send.overload('java.lang.String');

                RealWebSocket.send.overload('java.lang.String').implementation = function(text) {
                    try {
                        State.network.realWebSocket = this;
                        State.network.websocket = this;
                        State.network.originalSend = originalSend;

                        sendToServer({
                            type: 'ws_message',
                            direction: 'OUTBOUND',
                            data: text,
                            dataType: 'String'
                        });
                    } catch (e) {
                        Utils.log('[Hooks.WS] send handler ERROR: ' + e);
                    }

                    return originalSend.call(this, text);
                };

                Utils.log('[Hooks.setupWebSocket] send(String) hooked');
            } catch (e) {
                Utils.log('[Hooks.setupWebSocket] WARN: send hook failed: ' + e);
            }

            try {
                const ByteString = Java.use('okio.ByteString');

                RealWebSocket.send.overload('okio.ByteString').implementation = function(bytes) {
                    try {
                        State.network.realWebSocket = this;
                        State.network.websocket = this;
                        State.network.originalSend = RealWebSocket.send.overload('java.lang.String');

                        const text = bytes.utf8();

                        sendToServer({
                            type: 'ws_message',
                            direction: 'OUTBOUND',
                            data: String(text),
                            dataType: 'String'
                        });
                    } catch (e) {}

                    return this.send(bytes);
                };

                Utils.log('[Hooks.setupWebSocket] send(ByteString) hooked');
            } catch (e) {
                Utils.log('[Hooks.setupWebSocket] WARN: send(ByteString) hook failed: ' + e);
            }

            try {
                RealWebSocket.loopReader.implementation = function() {
                    try {
                        State.network.websocket = this;
                        State.network.originalSend = RealWebSocket.send.overload('java.lang.String');

                        if (!State.network.wsUrl) {
                            try {
                                const url = String(this.url());

                                State.network.wsUrl = url;

                                Utils.log('[Hooks.WS] loopReader: captured wsUrl=' + url);

                                globalThis._mq.push(JSON.stringify({
                                    type: 'ws_connection',
                                    url: url
                                }));
                            } catch (urlErr) {
                                Utils.log('[Hooks.WS] loopReader: url capture failed: ' + urlErr);
                            }
                        }
                    } catch (e) {
                        Utils.log('[Hooks.WS] loopReader capture ERROR: ' + e);
                    }

                    return this.loopReader();
                };

                Utils.log('[Hooks.setupWebSocket] loopReader hooked');
            } catch (e) {
                Utils.log('[Hooks.setupWebSocket] WARN: loopReader hook failed: ' + e);
            }

            try {
                const WebSocketListener = Java.use('okhttp3.WebSocketListener');

                WebSocketListener.onMessage.overload('okhttp3.WebSocket', 'java.lang.String').implementation = function(ws, text) {
                    try {
                        State.network.websocket = ws;

                        if (!State.network.wsUrl) {
                            try {
                                const request = ws.request();
                                const wsUrl = String(request.url().toString());
                                const bearer = String(request.header('Authorization') || '');
                                const cfJwt = String(request.header('Cf-Jwt') || '');

                                State.network.wsUrl = wsUrl;

                                Utils.log('[Hooks.WS] onMessage: captured wsUrl=' + wsUrl);

                                globalThis._mq.push(JSON.stringify({
                                    type: 'ws_connection',
                                    url: wsUrl,
                                    bearer: bearer,
                                    cf_jwt: cfJwt
                                }));
                            } catch (urlErr) {
                                Utils.log('[Hooks.WS] onMessage: url capture failed: ' + urlErr);
                            }
                        }
                    } catch (e) {
                        Utils.log('[Hooks.WS] WebSocketListener capture ERROR: ' + e);
                    }

                    return this.onMessage(ws, text);
                };

                Utils.log('[Hooks.setupWebSocket] WebSocketListener.onMessage hooked');
            } catch (e) {
                Utils.log('[Hooks.setupWebSocket] WARN: WebSocketListener hook failed: ' + e);
            }

            Utils.log('[Hooks.setupWebSocket] Done');
        } catch (e) {
            Utils.log('[Hooks.setupWebSocket] FATAL ERROR: ' + e);
        }
    },

    setupHTTP: function() {
        try {
            Utils.log('[Hooks.setupHTTP] START');

            try {
                const Context = Java.use('android.content.Context');

                const ctx = State.context;
                const prefs = ctx.getSharedPreferences(
                    'RCTAsyncLocalStorage_V1', Context.MODE_PRIVATE.value
                );

                const raw = prefs.getString('authtokens', null);

                if (raw) {
                    const parsed = Utils.safeJsonParse(String(raw));

                    if (parsed && parsed.idToken) {
                        const token = String(parsed.idToken);

                        State.network.bearerToken = token;

                        Utils.log('[Hooks.HTTP] idToken from SharedPreferences: ***' + token.slice(-8));

                        sendToServer({
                            type: 'ws_connection',
                            url: State.network.wsUrl || '',
                            bearer: token,
                            cf_jwt: ''
                        });
                    }

                    else Utils.log('[Hooks.HTTP] authtokens found but no idToken');
                }

                else Utils.log('[Hooks.HTTP] authtokens not found in SharedPreferences');
            } catch (e) {
                Utils.log('[Hooks.setupHTTP] SharedPreferences read ERROR: ' + e);
            }

            try {
                const OkHttpClient = Java.use('okhttp3.OkHttpClient');
                const WSListener = Java.use('okhttp3.WebSocketListener');

                OkHttpClient.newWebSocket.overload(
                    'okhttp3.Request', 'okhttp3.WebSocketListener'
                ).implementation = function(request, listener) {
                    try {
                        const url = String(request.url().toString());

                        Utils.log('[Hooks.WS] newWebSocket: url=' + url.substring(0, 80));

                        State.network.wsUrl = url;

                        sendToServer({
                            type: 'ws_connection',
                            url: url
                        });
                    } catch (e) {
                        Utils.log('[Hooks.WS] newWebSocket capture ERROR: ' + e);
                    }

                    return this.newWebSocket(request, listener);
                };

                Utils.log('[Hooks.setupHTTP] newWebSocket hooked');
            } catch (e) {
                Utils.log('[Hooks.setupHTTP] WARN: newWebSocket hook failed: ' + e);
            }

            try {
                const RealChain = Java.use('okhttp3.internal.http.RealInterceptorChain');

                RealChain.proceed.overload('okhttp3.Request').implementation = function(request) {
                    try {
                        const url = String(request.url().toString());
                        const method = String(request.method());
                        const headers = request.headers();

                        const auth = headers.get('Authorization') || headers.get('authorization') || '';
                        const cfJwt = headers.get('Cf-Jwt') || headers.get('cf-jwt') || headers.get('CF-JWT') || '';

                        if (auth.startsWith('Bearer ')) {
                            const token = auth.substring(7);

                            if (!State.network.bearerToken) {
                                Utils.log('[Hooks.HTTP] Bearer token captured');

                                globalThis._mq.push(JSON.stringify({
                                    type: 'auth',
                                    message: 'Bearer token captured (***' + token.slice(-8) + ')'
                                }));
                            }

                            State.network.bearerToken = token;
                            State.auth.bearerToken = token;

                            if (cfJwt) State.auth.cfJwt = cfJwt;
                        }

                        if (auth.startsWith('Bot ') && !State.network.botApiKey) {
                            State.network.botApiKey = auth.substring(4);

                            Utils.log('[Hooks.HTTP] Bot API key captured');
                        }

                        if (LOG_HTTP && (auth || cfJwt)) {
                            const headersObj = {};

                            if (auth) headersObj['Authorization'] = auth;

                            if (cfJwt) headersObj['Cf-Jwt'] = cfJwt;

                            Utils.log('[Hooks.HTTP] ' + method + ' ' + url);
                            
                            globalThis._mq.push(JSON.stringify({
                                type: 'http_headers',
                                url: url,
                                headers: headersObj
                            }));
                        }
                    } catch (e) {
                        Utils.log('[Hooks.HTTP] proceed handler ERROR: ' + e);
                    }

                    return this.proceed(request);
                };

                Utils.log('[Hooks.setupHTTP] RealInterceptorChain.proceed hooked');
            } catch (e) {
                Utils.log('[Hooks.setupHTTP] WARN: RealInterceptorChain hook failed: ' + e);
            }

            Utils.log('[Hooks.setupHTTP] Done');
        } catch (e) {
            Utils.log('[Hooks.setupHTTP] FATAL ERROR: ' + e);
        }
    }
};
