function waitForJava() {
    return new Promise((resolve) => {
        const checkJava = setInterval(() => {
            if (typeof Java !== 'undefined' && Java.available) {
                clearInterval(checkJava);
                resolve();
            }
        }, 100);
    });
}

waitForJava().then(() => {
    Java.perform(function () {
        let menuView;
        let iconView;
        let windowManager;
        let titleTextView;
        let isMenuVisible = false;
        let iconParams;
        let playersTextView;
        let selectedPlayerSpinner;
        let sentTextView;
        let mentionedTextView;
        let latestRenderData = null;
        let currentSection = 'players';
        let playersSectionView;
        let messagesSectionView;
        let mastermindSectionView;
        let commandInput;
        let errorTextView;
        let predictButton;
        let predictResultTextView;
        let menuParamsRef = null;

        const messageQueue = [];

        const gameState = {
            playersById: {},
            idByNum: {},
            chat: [],
            selectedPlayerId: null,
        };

        function safeJsonParse(text) {
            try { return JSON.parse(text); } catch (_) { return null; }
        }

        function parseSocketIoEnvelope(text) {
            if (typeof text !== 'string') return null;
            if (!text.startsWith('42')) return null;
            const idx = text.indexOf('[');
            if (idx < 0) return null;
            const arr = safeJsonParse(text.slice(idx));
            if (!Array.isArray(arr) || arr.length < 1) return null;
            const evt = arr[0];
            let payload = arr.length > 1 ? arr[1] : null;
            if (typeof payload === 'string') {
                const inner = safeJsonParse(payload);
                if (inner) payload = inner;
            }
            return { event: evt, payload };
        }

        function upsertPlayer(player) {
            if (!player || !player.id) return;
            const prev = gameState.playersById[player.id] || {};
            const gridIdx = (player.gridIdx != null ? player.gridIdx : (prev.num ? prev.num - 1 : -1));
            const num = gridIdx >= 0 ? (gridIdx + 1) : (prev.num || null);
            const alive = player.isAlive != null ? player.isAlive : (prev.alive != null ? prev.alive : true);
            gameState.playersById[player.id] = {
                id: player.id,
                username: player.username || prev.username || '',
                num,
                alive,
                roleRevealed: player.roleRevealed != null ? player.roleRevealed : (prev.roleRevealed || null),
            };
            if (num != null) gameState.idByNum[num] = player.id;
        }

        function onEvent(evt, payload) {
            switch (evt) {
                case 'players-and-equipped-items':
                    if (payload && Array.isArray(payload.players)) payload.players.forEach(upsertPlayer);
                    rebuildSpinnerOptions();
                    break;
                case 'player-joined-and-equipped-items':
                    if (payload && payload.player) upsertPlayer(payload.player);
                    rebuildSpinnerOptions();
                    break;
                case 'player-grid-idx':
                    if (payload && payload.playerId && payload.gridIdx != null) upsertPlayer({ id: payload.playerId, gridIdx: payload.gridIdx });
                    rebuildSpinnerOptions();
                    break;
                case 'player-disconnected':
                    if (payload && payload.id) upsertPlayer({ id: payload.id, isAlive: payload.isAlive != null ? payload.isAlive : true });
                    rebuildSpinnerOptions();
                    break;
                case 'game-started':
                    if (payload && Array.isArray(payload.players)) payload.players.forEach(upsertPlayer);
                    rebuildSpinnerOptions();
                    break;
                case 'game-role-revealed':
                    if (payload && payload.playerId && payload.roleId) upsertPlayer({ id: payload.playerId, roleRevealed: payload.roleId });
                    break;
                case 'game-players-killed':
                    if (payload && Array.isArray(payload.victims)) payload.victims.forEach(v => { if (v && v.targetPlayerId) upsertPlayer({ id: v.targetPlayerId, isAlive: false }); });
                    rebuildSpinnerOptions();
                    break;
                case 'game:chat-public:msg':
                    if (payload) {
                        gameState.chat.push({
                            t: Date.now(),
                            authorId: payload.authorId || 'system',
                            msg: payload.msg || '',
                        });
                        if (gameState.chat.length > 400) gameState.chat.shift();
                    }
                    break;
            }
            scheduleUiUpdate();
        }

        function toggleMenu() {
            if (!menuView || !windowManager || !iconView) return;

            Java.scheduleOnMainThread(function () {
                try {
                    const View = Java.use('android.view.View');
                    const castedMenu = Java.cast(menuView, View);

                    if (isMenuVisible) {
                        castedMenu.setVisibility(View.GONE.value);
                        isMenuVisible = false;
                    } else {
                        castedMenu.setVisibility(View.VISIBLE.value);
                        isMenuVisible = true;

                        try {
                            const castedIconView = Java.cast(iconView, View);
                            const ViewGroupLayoutParams = Java.use('android.view.ViewGroup$LayoutParams');
                            const castedIconParams = Java.cast(iconParams, ViewGroupLayoutParams);

                            windowManager.removeView(castedIconView);
                            windowManager.addView(castedIconView, castedIconParams);
                        } catch (e_readd) {
                            messageQueue.push(JSON.stringify({ type: 'log', message: '[OVERLAY ERROR] Re-adding icon failed: ' + e_readd.toString() }));
                        }
                    }
                } catch (e) {
                    messageQueue.push(JSON.stringify({ type: 'log', message: '[MENU ERROR] ' + e.toString() }));
                }
            });
        }

        let uiUpdateScheduled = false;

        function scheduleUiUpdate() {
            if (uiUpdateScheduled) return;
            uiUpdateScheduled = true;
            Java.scheduleOnMainThread(function () {
                try { updateUI(); } finally { uiUpdateScheduled = false; }
            });
        }

        function formatPlayerLineFromRenderData(p) {
            if (!p) return '';
            let line = `${p.num}`;
            if (p.name) line += ` ${p.name}`;
            if (p.level !== -1) line += ` ⭐${p.level}`;
            else if (p.min_level !== -1) line += ` ⭐${p.min_level}+`;
            line += ` (${p.messages})`;
            if (p.claim) line += ` C: ${p.claim}`;
            if (p.contradiction) line += ` CC: ${p.contradiction}`;
            if (p.alliances && p.alliances.length > 0) {
                p.alliances.forEach(a => line += ` 🛡️ ${a}`);
            }
            if (p.role) line += ` - ${p.role}`;
            else if (p.team) line += ` [${p.team}]`;
            else if (p.teams_exclude && p.teams_exclude.length > 0) {
                line += ` [NOT ${p.teams_exclude.join(', ')}]`;
            }
            if (p.possible && p.possible.length > 0) {
                line += ' + POSSIBLE ';
                p.possible.forEach((pos, idx) => {
                    line += pos.role;
                    if (!pos.has_card && !pos.has_icon) line += ' ❌⭕';
                    else if (!pos.has_card) line += ' ❌';
                    else if (!pos.has_icon) line += ' ⭕';
                    if (idx < p.possible.length - 1) line += ' / ';
                });
            }
            if (p.threat != null) {
                let threatColor = '';
                if (p.threat >= 70) threatColor = '🔴';
                else if (p.threat >= 30) threatColor = '🟡';
                else threatColor = '🟢';
                line += ` ${threatColor}[${p.threat}% ❕]`;
            }
            if (p.aura === 'GOOD') line = `🟢 ${line}`;
            else if (p.aura === 'EVIL') line = `🔴 ${line}`;
            else if (p.aura === 'UNKNOWN') line = `🔵 ${line}`;
            if (p.dead) line = `\t~~${line}~~`;
            return line;
        }

        function updateUI() {
            if (!menuView) return;
            const JavaString = Java.use('java.lang.String');
            if (playersTextView) {
                let text = '';
                if (latestRenderData && latestRenderData.players) {
                    const lines = latestRenderData.players.map(formatPlayerLineFromRenderData);
                    text = lines.join('\n');
                    if (latestRenderData.remaining) {
                        const rem = latestRenderData.remaining;
                        const remGood = rem.GOOD ? rem.GOOD.join(', ') : '';
                        const remEvil = rem.EVIL ? rem.EVIL.join(', ') : '';
                        const remUnknown = rem.UNKNOWN ? rem.UNKNOWN.join(', ') : '';
                        text += '\n\nREMAINING\n';
                        if (remGood) text += `GOOD: ${remGood}\n`;
                        if (remEvil) text += `EVIL: ${remEvil}\n`;
                        if (remUnknown) text += `UNKNOWN: ${remUnknown}\n`;
                    }
                } else {
                    const lines = Object.values(gameState.playersById)
                        .sort((a, b) => (a.num || 99) - (b.num || 99))
                        .map(p => {
                            const num = (p.num != null) ? `${p.num}` : '?';
                            const aliveMark = p.alive === false ? '✖' : '✓';
                            const role = p.roleRevealed ? ` [${p.roleRevealed}]` : '';
                            return `${num}. ${p.username || ''} ${aliveMark}${role}`;
                        });
                    text = lines.join('\n');
                }
                playersTextView.setText.overload('java.lang.CharSequence').call(playersTextView, JavaString.$new(text || ''));
            }
            const selId = gameState.selectedPlayerId;
            if (selId) {
                const sel = gameState.playersById[selId];
                const selName = sel ? sel.username : null;
                const selNum = sel && sel.num != null ? sel.num : null;
                const sentLines = [];
                const mentionedLines = [];
                for (let i = Math.max(0, gameState.chat.length - 120); i < gameState.chat.length; i++) {
                    const c = gameState.chat[i];
                    if (!c || !c.msg) continue;
                    const author = gameState.playersById[c.authorId];
                    const authorName = author ? (author.num != null ? `${author.num} ${author.username}` : author.username) : 'system';
                    const line = `${authorName}: ${c.msg}`;
                    if (c.authorId === selId) {
                        sentLines.push(line);
                    } else {
                        let mentioned = false;
                        if (selName && c.msg && typeof c.msg === 'string') {
                            if (c.msg.toLowerCase().includes(selName.toLowerCase())) mentioned = true;
                            if (!mentioned && selNum != null) {
                                const re = new RegExp(`(^|[^\\d])${selNum}([^\\d]|$)`);
                                if (re.test(c.msg)) mentioned = true;
                            }
                        }
                        if (mentioned) mentionedLines.push(line);
                    }
                }
                if (sentTextView) sentTextView.setText.overload('java.lang.CharSequence').call(sentTextView, JavaString.$new(sentLines.join('\n')));
                if (mentionedTextView) mentionedTextView.setText.overload('java.lang.CharSequence').call(mentionedTextView, JavaString.$new(mentionedLines.join('\n')));
            } else {
                if (sentTextView) sentTextView.setText.overload('java.lang.CharSequence').call(sentTextView, JavaString.$new(''));
                if (mentionedTextView) mentionedTextView.setText.overload('java.lang.CharSequence').call(mentionedTextView, JavaString.$new(''));
            }
        }

        function rebuildSpinnerOptions() {
            if (!selectedPlayerSpinner) return;
            const Spinner = Java.use('android.widget.Spinner');
            const ArrayAdapter = Java.use('android.widget.ArrayAdapter');
            const context = Java.use('android.app.ActivityThread').currentApplication().getApplicationContext();
            const players = Object.values(gameState.playersById).sort((a, b) => (a.num || 99) - (b.num || 99));
            const labels = ['None'].concat(players.map(p => `${p.num != null ? p.num + ' ' : ''}${p.username}`));
            const JavaString = Java.use('java.lang.String');
            const items = Java.array('java.lang.String', labels.map(s => JavaString.$new(s)));
            const adapter = ArrayAdapter.$new(context, Java.use('android.R$layout').simple_spinner_item.value, items);
            adapter.setDropDownViewResource(Java.use('android.R$layout').simple_spinner_dropdown_item.value);
            selectedPlayerSpinner.setAdapter(adapter);
            const current = gameState.selectedPlayerId;
            let idxToSelect = 0;
            if (current) {
                const idx = players.findIndex(p => p.id === current);
                if (idx >= 0) idxToSelect = idx + 1;
            }
            selectedPlayerSpinner.setSelection(idxToSelect);
        }

        try {
            const RealWebSocket = Java.use('okhttp3.internal.ws.RealWebSocket');
            messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS] Starting passive WebSocket monitoring...' }));
            let wsMessageCount = 0;

            try {
                const originalProcessNextFrame = RealWebSocket.processNextFrame;
                RealWebSocket.processNextFrame.implementation = function () {
                    const result = originalProcessNextFrame.call(this);
                    messageQueue.push(JSON.stringify({ type: 'log', message: '[WS] processNextFrame() -> ' + result }));
                    return result;
                };
                messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS] ✓ processNextFrame hooked' }));
            } catch (e) {
                messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS] processNextFrame not available' }));
            }

            try {
                const originalOnReadMessageString = RealWebSocket.onReadMessage.overload('java.lang.String');
                RealWebSocket.onReadMessage.overload('java.lang.String').implementation = function (text) {
                    wsMessageCount++;
                    messageQueue.push(JSON.stringify({ type: 'log', message: '[WS ✓] onReadMessage length=' + text.length + ', preview: ' + text.substring(0, 50) }));
                    messageQueue.push(JSON.stringify({ type: 'ws_message', direction: 'INBOUND', data: text, dataType: 'String' }));
                    const env = parseSocketIoEnvelope(text);
                    if (env) {
                        messageQueue.push(JSON.stringify({ type: 'log', message: '[WS EVENT] ' + env.event }));
                        onEvent(env.event, env.payload);
                    } else {
                        messageQueue.push(JSON.stringify({ type: 'log', message: '[WS] Could not parse as Socket.IO event: ' + text.substring(0, 30) }));
                    }
                    return originalOnReadMessageString.call(this, text);
                };
                messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS] ✓ onReadMessage(String) hooked' }));
            } catch (e) {
                messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS] ⚠ onReadMessage(String) failed: ' + e }));
            }

            try {
                const ByteString = Java.use('okio.ByteString');
                const originalOnReadMessageBytes = RealWebSocket.onReadMessage.overload('okio.ByteString');
                RealWebSocket.onReadMessage.overload('okio.ByteString').implementation = function (bytes) {
                    messageQueue.push(JSON.stringify({ type: 'log', message: '[WS ✓] onReadMessage(ByteString)' }));
                    try {
                        const text = bytes.utf8();
                        messageQueue.push(JSON.stringify({ type: 'ws_message', direction: 'INBOUND', data: text, dataType: 'String' }));
                        const env = parseSocketIoEnvelope(text);
                        if (env) {
                            messageQueue.push(JSON.stringify({ type: 'log', message: '[WS EVENT] ' + env.event }));
                            onEvent(env.event, env.payload);
                        }
                    } catch (e) {
                        messageQueue.push(JSON.stringify({ type: 'log', message: '[WS] ByteString decode error: ' + e }));
                    }
                    return originalOnReadMessageBytes.call(this, bytes);
                };
                messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS] ✓ onReadMessage(ByteString) hooked' }));
            } catch (e) {
                messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS] ⚠ onReadMessage(ByteString) failed: ' + e }));
            }

            try {
                const originalSendString = RealWebSocket.send.overload('java.lang.String');
                RealWebSocket.send.overload('java.lang.String').implementation = function (text) {
                    messageQueue.push(JSON.stringify({ type: 'log', message: '[WS ↑] send(String) length=' + text.length }));
                    messageQueue.push(JSON.stringify({ type: 'ws_message', direction: 'OUTBOUND', data: text, dataType: 'String' }));
                    return originalSendString.call(this, text);
                };
                messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS] ✓ send(String) hooked' }));
            } catch (e) {
                messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS] send(String) not available' }));
            }

            messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS] Skipping readMessageFrame (causes protocol errors)' }));

            try {
                const originalLoopReaderMethod = RealWebSocket.loopReader;
                RealWebSocket.loopReader.implementation = function () {
                    messageQueue.push(JSON.stringify({ type: 'log', message: '[WS] loopReader started' }));
                    try {
                        return originalLoopReaderMethod.call(this);
                    } finally {
                        messageQueue.push(JSON.stringify({ type: 'log', message: '[WS] loopReader finished' }));
                    }
                };
                messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS] ✓ loopReader hooked' }));
            } catch (e) {
                messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS] loopReader not available' }));
            }

            try {
                const WebSocketListener = Java.use('okhttp3.WebSocketListener');
                const originalOnMessageString = WebSocketListener.onMessage.overload('okhttp3.WebSocket', 'java.lang.String');
                WebSocketListener.onMessage.overload('okhttp3.WebSocket', 'java.lang.String').implementation = function (webSocket, text) {
                    messageQueue.push(JSON.stringify({ type: 'log', message: '[WS Listener ✓] onMessage length=' + text.length }));
                    messageQueue.push(JSON.stringify({ type: 'ws_message', direction: 'INBOUND', data: text, dataType: 'String' }));
                    const env = parseSocketIoEnvelope(text);
                    if (env) {
                        messageQueue.push(JSON.stringify({ type: 'log', message: '[WS EVENT] ' + env.event }));
                        onEvent(env.event, env.payload);
                    }
                    return originalOnMessageString.call(this, webSocket, text);
                };
                messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS] ✓ WebSocketListener.onMessage hooked' }));
            } catch (e) {
                messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS] WebSocketListener not used' }));
            }
            messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS] ✓ Passive monitoring setup complete!' }));
        } catch (e) {
            messageQueue.push(JSON.stringify({ type: 'log', message: '[WS HOOKS CRITICAL] ' + e.toString() }));
        }

        try {
            const OkHttpClient = Java.use('okhttp3.OkHttpClient');
            const Interceptor = Java.use('okhttp3.Interceptor');
            const ResponseBody = Java.use('okhttp3.ResponseBody');
            const MediaType = Java.use('okhttp3.MediaType');

            const ResponseInterceptor = Java.registerClass({
                name: 'com.mentalist.ResponseInterceptor',
                implements: [Interceptor],
                methods: {
                    intercept: function (chain) {
                        const request = chain.request();
                        const url = request.url().toString();

                        const response = chain.proceed(request);

                        const targetPlayerId = '3852699d-e38b-40a9-ac2b-197ab78593cd';
                        const isPlayerProfile = url.includes('/players/' + targetPlayerId);
                        const isFriendsMulti = url.includes('/friends/multiple/minimized');
                        const isFriendsMini = url.includes('/friends/' + targetPlayerId + '/minimized');
                        const isTargetUrl = isPlayerProfile || isFriendsMulti || isFriendsMini;

                        if (!response.isSuccessful() || response.body() == null || !isTargetUrl) return response;

                        const responseBody = response.body();
                        const mediaType = responseBody.contentType();
                        let responseBodyString;

                        try {
                            responseBodyString = responseBody.string();
                        } catch (readError) {
                            messageQueue.push(JSON.stringify({ type: 'log', message: '[HTTP READ ERROR] ' + readError.toString() }));
                            return response;
                        }

                        try {
                            const newUsername = '💗 Beril 💗';
                            const newIconId = 'O6k';
                            const newIconColor = '#e30b5d';
                            let modifiedBodyString = responseBodyString;

                            if (url.includes('/players/' + targetPlayerId)) {
                                let data = safeJsonParse(responseBodyString);
                                if (data && data.id === targetPlayerId) {
                                    data.username = newUsername;
                                    data.equippedProfileIconId = newIconId;
                                    data.equippedProfileIconColor = newIconColor;
                                    data.equippedProfileIconBorderId = 'DT-';
                                    data.clanTag = '';
                                    modifiedBodyString = JSON.stringify(data);
                                }
                            }
                            else if (url.includes('/friends/multiple/minimized')) {
                                let data = safeJsonParse(responseBodyString);
                                if (data && Array.isArray(data)) {
                                    data.forEach(playerArray => {
                                        if (Array.isArray(playerArray) && playerArray[0] === targetPlayerId) {
                                            playerArray[1] = newUsername;
                                            playerArray[3] = newIconId;
                                            playerArray[4] = newIconColor;
                                            playerArray[10] = '';
                                        }
                                    });
                                    modifiedBodyString = JSON.stringify(data);
                                }
                            }
                            else if (url.includes('/friends/' + targetPlayerId + '/minimized')) {
                                let data = safeJsonParse(responseBodyString);
                                if (Array.isArray(data) && data[0] === targetPlayerId) {
                                    data[1] = newUsername;
                                    data[3] = newIconId;
                                    data[4] = newIconColor;
                                    data[10] = '';
                                    modifiedBodyString = JSON.stringify(data);
                                }
                            }

                            const newBody = ResponseBody.create(mediaType, modifiedBodyString);
                            return response.newBuilder().body(newBody).build();
                        } catch (e) {
                            messageQueue.push(JSON.stringify({ type: 'log', message: '[HTTP MODIFY ERROR] ' + e.toString() }));
                            const newBody = ResponseBody.create(mediaType, responseBodyString);
                            return response.newBuilder().body(newBody).build();
                        }
                    }
                }
            });

            const originalNewCall = OkHttpClient.newCall;
            OkHttpClient.newCall.implementation = function (request) {
                const interceptors = this.interceptors();

                let alreadyAdded = false;
                for (let i = 0; i < interceptors.size(); i++) {
                    const interceptor = interceptors.get(i);
                    if (interceptor.getClass().getName() === 'com.mentalist.ResponseInterceptor') {
                        alreadyAdded = true;
                        break;
                    }
                }

                if (!alreadyAdded) {
                    try {
                        const builder = this.newBuilder();
                        builder.addInterceptor(ResponseInterceptor.$new());
                        const newClient = builder.build();
                        return originalNewCall.call(newClient, request);
                    } catch (e) {
                        messageQueue.push(JSON.stringify({ type: 'log', message: '[INTERCEPTOR ADD ERROR] ' + e.toString() }));
                    }
                }

                return originalNewCall.call(this, request);
            };

            const OkHttpClientBuilder = Java.use('okhttp3.OkHttpClient$Builder');
            const originalBuild = OkHttpClientBuilder.build;
            OkHttpClientBuilder.build.implementation = function () {
                try {
                    this.addInterceptor(ResponseInterceptor.$new());
                } catch (e) {
                    messageQueue.push(JSON.stringify({ type: 'log', message: '[INTERCEPTOR ADD ERROR] ' + e.toString() }));
                }
                return originalBuild.call(this);
            };

            messageQueue.push(JSON.stringify({ type: 'log', message: 'OkHttp Interceptor hooked successfully.' }));
        } catch (e) {
            messageQueue.push(JSON.stringify({ type: 'log', message: '[HOOK WARNING] OkHttp Interceptor setup failed: ' + e.toString() }));
        }

        try {
            const ActivityThread = Java.use('android.app.ActivityThread');
            const currentApplication = ActivityThread.currentApplication();
            if (!currentApplication) {
                messageQueue.push(JSON.stringify({ type: 'log', message: '[OVERLAY ERROR] currentApplication is null!' }));
                return;
            }
            const context = currentApplication.getApplicationContext();
            if (!context) {
                messageQueue.push(JSON.stringify({ type: 'log', message: '[OVERLAY ERROR] context is null!' }));
                return;
            }
            messageQueue.push(JSON.stringify({ type: 'log', message: '[OVERLAY] Context acquired successfully.' }));

            const TextView = Java.use('android.widget.TextView');
            const ScrollView = Java.use('android.widget.ScrollView');
            const LinearLayout = Java.use('android.widget.LinearLayout');
            const ImageView = Java.use('android.widget.ImageView');
            const BitmapFactory = Java.use('android.graphics.BitmapFactory');
            const Base64 = Java.use('android.util.Base64');
            const Spinner = Java.use('android.widget.Spinner');
            const ArrayAdapter = Java.use('android.widget.ArrayAdapter');
            const Typeface = Java.use('android.graphics.Typeface');
            const WindowManager = Java.use('android.view.WindowManager');
            const WindowManagerImpl = Java.use('android.view.WindowManagerImpl');
            const WindowManagerLayoutParams = Java.use('android.view.WindowManager$LayoutParams');
            const Gravity = Java.use('android.view.Gravity');
            const Color = Java.use('android.graphics.Color');
            const TypedValue = Java.use('android.util.TypedValue');
            const GradientDrawable = Java.use('android.graphics.drawable.GradientDrawable');
            const MotionEvent = Java.use('android.view.MotionEvent');
            const JavaFloat = Java.use('java.lang.Float');
            const JavaInteger = Java.use('java.lang.Integer');
            const JavaString = Java.use('java.lang.String');
            const View = Java.use('android.view.View');
            const ViewGroupLayoutParams = Java.use('android.view.ViewGroup$LayoutParams');
            const FrameLayoutParams = Java.use('android.widget.FrameLayout$LayoutParams');
            const LinearLayoutParams = Java.use('android.widget.LinearLayout$LayoutParams');
            const BuildVersion = Java.use('android.os.Build$VERSION');
            const SDK_INT = BuildVersion.SDK_INT.value;

            Java.scheduleOnMainThread(function () {
                try {
                    const resources = context.getResources();
                    const displayMetrics = resources.getDisplayMetrics();
                    const dpToPx = function (dp) {
                        return Java.use('android.util.TypedValue').applyDimension(
                            TypedValue.COMPLEX_UNIT_DIP.value,
                            dp,
                            displayMetrics
                        );
                    };

                    const windowServiceName = Java.use('android.content.Context').WINDOW_SERVICE.value;
                    windowManager = Java.cast(context.getSystemService(windowServiceName), WindowManagerImpl);
                    if (!windowManager) {
                        messageQueue.push(JSON.stringify({ type: 'log', message: '[OVERLAY ERROR] windowManager is null!' }));
                        return;
                    }
                    let layoutType;
                    if (SDK_INT >= 26)
                        layoutType = WindowManagerLayoutParams.TYPE_APPLICATION_OVERLAY.value;
                    else
                        layoutType = WindowManagerLayoutParams.TYPE_PHONE.value;

                    const iconSizePx = dpToPx(48);
                    const base64IconString = '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';
                    iconView = ImageView.$new(context);
                    const decodedBytes = Base64.decode(base64IconString, Base64.DEFAULT.value);
                    let bitmap = BitmapFactory.decodeByteArray(decodedBytes, 0, decodedBytes.length);
                    iconView.setImageBitmap(bitmap);
                    iconView.setScaleType(Java.use('android.widget.ImageView$ScaleType').CENTER_INSIDE.value);
                    iconView.setPadding(dpToPx(8), dpToPx(8), dpToPx(8), dpToPx(8));

                    const iconBg = GradientDrawable.$new();
                    iconBg.setShape(GradientDrawable.OVAL.value);
                    iconBg.setColor(Color.parseColor('#B71C1C'));
                    iconView.setBackground(iconBg);
                    iconView.setElevation(12.0);

                    iconParams = WindowManagerLayoutParams.$new(
                        WindowManagerLayoutParams.WRAP_CONTENT.value,
                        WindowManagerLayoutParams.WRAP_CONTENT.value,
                        layoutType,
                        WindowManagerLayoutParams.FLAG_NOT_FOCUSABLE.value |
                        WindowManagerLayoutParams.FLAG_NOT_TOUCH_MODAL.value |
                        WindowManagerLayoutParams.FLAG_LAYOUT_IN_SCREEN.value,
                        JavaInteger.parseInt('1', 16)
                    );
                    iconParams.gravity = Gravity.CENTER_VERTICAL.value | Gravity.RIGHT.value;
                    iconParams.x = 20;
                    iconParams.y = 0;

                    const dragState = { startX: 0, startY: 0, initialParamsX: 0, initialParamsY: 0 };
                    const OnTouchListener = Java.registerClass({
                        name: 'com.mentalist.DraggableIconListener',
                        implements: [Java.use('android.view.View$OnTouchListener')],
                        methods: {
                            onTouch: function (view, event) {
                                const action = event.getActionMasked();
                                switch (action) {
                                    case MotionEvent.ACTION_DOWN.value:
                                        dragState.startX = event.getRawX();
                                        dragState.startY = event.getRawY();
                                        dragState.initialParamsX = iconParams.x.value;
                                        dragState.initialParamsY = iconParams.y.value;
                                        view.animate().scaleX(0.85).scaleY(0.85).setDuration(80).start();
                                        return true;
                                    case MotionEvent.ACTION_MOVE.value:
                                        const deltaX = event.getRawX() - dragState.startX;
                                        const deltaY = event.getRawY() - dragState.startY;
                                        iconParams.x.value = dragState.initialParamsX + Math.round(deltaX);
                                        iconParams.y.value = dragState.initialParamsY + Math.round(deltaY);
                                        try {
                                            windowManager.updateViewLayout(iconView, iconParams);
                                        } catch (e) {
                                            messageQueue.push(JSON.stringify({ type: 'log', message: '[DRAG UPDATE ERROR] ' + e }));
                                        }
                                        return true;
                                    case MotionEvent.ACTION_UP.value:
                                    case MotionEvent.ACTION_CANCEL.value:
                                        view.animate().scaleX(1.0).scaleY(1.0).setDuration(100).start();
                                        const movedX = Math.abs(event.getRawX() - dragState.startX);
                                        const movedY = Math.abs(event.getRawY() - dragState.startY);
                                        if (movedX < 25 && movedY < 25) toggleMenu();
                                        return true;
                                }
                                return false;
                            }
                        }
                    });
                    iconView.setOnTouchListener(OnTouchListener.$new());
                    windowManager.addView(Java.cast(iconView, View), Java.cast(iconParams, ViewGroupLayoutParams));
                    messageQueue.push(JSON.stringify({ type: 'log', message: '[OVERLAY] Icon created successfully.' }));

                    menuView = LinearLayout.$new(context);
                    menuView.setOrientation(LinearLayout.VERTICAL.value);
                    menuView.setFocusable(true);
                    menuView.setFocusableInTouchMode(true);
                    menuView.setPadding(15, 15, 15, 15);

                    const bgDrawable = GradientDrawable.$new();
                    bgDrawable.setShape(GradientDrawable.RECTANGLE.value);
                    const colors = Java.array('int', [Color.parseColor('#8B0000'), Color.parseColor('#000000')]);
                    bgDrawable.setColors(colors);
                    bgDrawable.setGradientType(GradientDrawable.LINEAR_GRADIENT.value);
                    bgDrawable.setCornerRadius(JavaFloat.parseFloat('12.0'));
                    bgDrawable.setStroke(3, Color.parseColor('#DC143C'));
                    menuView.setBackground(bgDrawable);
                    menuView.setElevation(15.0);

                    const Button = Java.use('android.widget.Button');
                    const EditText = Java.use('android.widget.EditText');
                    const FrameLayout = Java.use('android.widget.FrameLayout');

                    const titleLayout = LinearLayout.$new(context);
                    titleLayout.setOrientation(LinearLayout.HORIZONTAL.value);
                    titleLayout.setGravity(Gravity.CENTER.value);
                    titleLayout.setPadding(0, 0, 0, dpToPx(12));
                    const titleIconSizePx = Math.round(dpToPx(18));

                    const titleIconLeft = ImageView.$new(context);
                    titleIconLeft.setImageBitmap(bitmap);
                    const iconParamsLeft = LinearLayoutParams.$new(titleIconSizePx, titleIconSizePx);
                    iconParamsLeft.setMargins(0, 0, dpToPx(6), 0);
                    titleIconLeft.setLayoutParams(iconParamsLeft);
                    titleIconLeft.setScaleType(Java.use('android.widget.ImageView$ScaleType').CENTER_INSIDE.value);
                    titleLayout.addView(titleIconLeft);

                    titleTextView = TextView.$new(context);
                    titleTextView.setText(JavaString.$new('Mentalist Mobile'));
                    titleTextView.setTextColor(Color.parseColor('#FF0000'));
                    titleTextView.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 16.0);
                    titleTextView.setGravity(Gravity.CENTER.value);
                    titleTextView.setTypeface(Typeface.DEFAULT_BOLD.value);
                    titleLayout.addView(titleTextView);

                    const titleIconRight = ImageView.$new(context);
                    titleIconRight.setImageBitmap(bitmap);
                    const iconParamsRight = LinearLayoutParams.$new(titleIconSizePx, titleIconSizePx);
                    iconParamsRight.setMargins(dpToPx(6), 0, 0, 0);
                    titleIconRight.setLayoutParams(iconParamsRight);
                    titleIconRight.setScaleType(Java.use('android.widget.ImageView$ScaleType').CENTER_INSIDE.value);
                    titleLayout.addView(titleIconRight);

                    menuView.addView(titleLayout);

                    const buttonRow = LinearLayout.$new(context);
                    buttonRow.setOrientation(LinearLayout.HORIZONTAL.value);
                    buttonRow.setGravity(Gravity.CENTER.value);
                    const btnParams = Java.use('android.widget.LinearLayout$LayoutParams');
                    buttonRow.setLayoutParams(btnParams.$new(ViewGroupLayoutParams.MATCH_PARENT.value, ViewGroupLayoutParams.WRAP_CONTENT.value));

                    const playersBtn = Button.$new(context);
                    playersBtn.setText(JavaString.$new('Players'));
                    playersBtn.setTextColor(Color.parseColor('#FFFFFF'));
                    playersBtn.setBackgroundColor(Color.parseColor('#B71C1C'));
                    playersBtn.setLayoutParams(btnParams.$new(0, ViewGroupLayoutParams.WRAP_CONTENT.value, 1.0));
                    const messagesBtn = Button.$new(context);
                    messagesBtn.setText(JavaString.$new('Messages'));
                    messagesBtn.setTextColor(Color.parseColor('#CCCCCC'));
                    messagesBtn.setBackgroundColor(Color.parseColor('#4A4A4A'));
                    messagesBtn.setLayoutParams(btnParams.$new(0, ViewGroupLayoutParams.WRAP_CONTENT.value, 1.0));
                    const mastermindBtn = Button.$new(context);
                    mastermindBtn.setText(JavaString.$new('Mastermind'));
                    mastermindBtn.setTextColor(Color.parseColor('#CCCCCC'));
                    mastermindBtn.setBackgroundColor(Color.parseColor('#4A4A4A'));
                    mastermindBtn.setLayoutParams(btnParams.$new(0, ViewGroupLayoutParams.WRAP_CONTENT.value, 1.0));

                    function showSection(section) {
                        playersSectionView.setVisibility(section === 'players' ? View.VISIBLE.value : View.GONE.value);
                        messagesSectionView.setVisibility(section === 'messages' ? View.VISIBLE.value : View.GONE.value);
                        mastermindSectionView.setVisibility(section === 'mastermind' ? View.VISIBLE.value : View.GONE.value);
                        playersBtn.setBackgroundColor(section === 'players' ? Color.parseColor('#B71C1C') : Color.parseColor('#4A4A4A'));
                        playersBtn.setTextColor(section === 'players' ? Color.parseColor('#FFFFFF') : Color.parseColor('#CCCCCC'));
                        messagesBtn.setBackgroundColor(section === 'messages' ? Color.parseColor('#B71C1C') : Color.parseColor('#4A4A4A'));
                        messagesBtn.setTextColor(section === 'messages' ? Color.parseColor('#FFFFFF') : Color.parseColor('#CCCCCC'));
                        mastermindBtn.setBackgroundColor(section === 'mastermind' ? Color.parseColor('#B71C1C') : Color.parseColor('#4A4A4A'));
                        mastermindBtn.setTextColor(section === 'mastermind' ? Color.parseColor('#FFFFFF') : Color.parseColor('#CCCCCC'));
                        if (section === 'messages') rebuildSpinnerOptions();
                    }

                    playersBtn.setOnClickListener(Java.registerClass({
                        name: 'com.mentalist.SectionButtonListener',
                        implements: [Java.use('android.view.View$OnClickListener')],
                        methods: {
                            onClick: function (view) {
                                currentSection = 'players';
                                showSection('players');
                            }
                        }
                    }).$new());
                    buttonRow.addView(playersBtn);

                    messagesBtn.setOnClickListener(Java.registerClass({
                        name: 'com.mentalist.SectionButtonListener2',
                        implements: [Java.use('android.view.View$OnClickListener')],
                        methods: {
                            onClick: function (view) {
                                currentSection = 'messages';
                                showSection('messages');
                            }
                        }
                    }).$new());
                    buttonRow.addView(messagesBtn);

                    mastermindBtn.setOnClickListener(Java.registerClass({
                        name: 'com.mentalist.SectionButtonListener3',
                        implements: [Java.use('android.view.View$OnClickListener')],
                        methods: {
                            onClick: function (view) {
                                currentSection = 'mastermind';
                                showSection('mastermind');
                            }
                        }
                    }).$new());
                    buttonRow.addView(mastermindBtn);

                    menuView.addView(buttonRow);

                    const sectionsContainer = FrameLayout.$new(context);
                    sectionsContainer.setLayoutParams(FrameLayoutParams.$new(ViewGroupLayoutParams.MATCH_PARENT.value, Math.round(dpToPx(500))));

                    playersSectionView = LinearLayout.$new(context);
                    playersSectionView.setOrientation(LinearLayout.VERTICAL.value);
                    playersSectionView.setLayoutParams(FrameLayoutParams.$new(ViewGroupLayoutParams.MATCH_PARENT.value, ViewGroupLayoutParams.MATCH_PARENT.value));
                    const playersScroll = ScrollView.$new(context);
                    const playersScrollParams = LinearLayoutParams.$new(ViewGroupLayoutParams.MATCH_PARENT.value, 0, 1.0);
                    playersScrollParams.setMargins(0, dpToPx(8), 0, 0);
                    playersScroll.setLayoutParams(playersScrollParams);
                    playersTextView = TextView.$new(context);
                    playersTextView.setTextColor(Color.parseColor('#BBDEFB'));
                    playersTextView.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 12.0);
                    playersScroll.addView(playersTextView);
                    playersSectionView.addView(playersScroll);
                    commandInput = EditText.$new(context);
                    commandInput.setHint(JavaString.$new('Enter command...'));
                    commandInput.setTextColor(Color.parseColor('#FFFFFF'));
                    commandInput.setHintTextColor(Color.parseColor('#888888'));
                    commandInput.setBackgroundColor(Color.parseColor('#333333'));
                    commandInput.setPadding(dpToPx(8), dpToPx(8), dpToPx(8), dpToPx(8));
                    commandInput.setLayoutParams(LinearLayoutParams.$new(ViewGroupLayoutParams.MATCH_PARENT.value, ViewGroupLayoutParams.WRAP_CONTENT.value));
                    const originalMenuY = 50;
                    const screenHeight = displayMetrics.heightPixels;
                    commandInput.setOnFocusChangeListener(Java.registerClass({
                        name: 'com.mentalist.CommandInputFocusListener',
                        implements: [Java.use('android.view.View$OnFocusChangeListener')],
                        methods: {
                            onFocusChange: function (view, hasFocus) {
                                Java.scheduleOnMainThread(function () {
                                    try {
                                        if (menuParamsRef && windowManager && menuView && playersScroll) {
                                            if (hasFocus) {
                                                const castedInput = Java.cast(view, View);
                                                const castedScroll = Java.cast(playersScroll, ScrollView);
                                                const estimatedKeyboardHeight = Math.floor(screenHeight * 0.4);
                                                const inputLocation = Java.array('int', [0, 0]);
                                                castedInput.getLocationOnScreen(inputLocation);
                                                const inputY = inputLocation[1];
                                                const inputHeight = castedInput.getHeight();
                                                const visibleAreaBottom = screenHeight - estimatedKeyboardHeight;

                                                if (inputY + inputHeight > visibleAreaBottom) {
                                                    const scrollNeeded = (inputY + inputHeight) - visibleAreaBottom + dpToPx(30);
                                                    castedScroll.smoothScrollBy(0, Math.floor(scrollNeeded));
                                                }

                                                const menuShift = Math.min(Math.floor(screenHeight * 0.25), Math.floor(estimatedKeyboardHeight * 0.6));
                                                menuParamsRef.y.value = Math.max(0, originalMenuY - menuShift);
                                                windowManager.updateViewLayout(Java.cast(menuView, View), Java.cast(menuParamsRef, ViewGroupLayoutParams));
                                            } else {
                                                menuParamsRef.y.value = originalMenuY;
                                                windowManager.updateViewLayout(Java.cast(menuView, View), Java.cast(menuParamsRef, ViewGroupLayoutParams));
                                            }
                                        }
                                    } catch (e) {
                                        try {
                                            if (hasFocus && menuParamsRef && windowManager && menuView) {
                                                menuParamsRef.y.value = Math.max(0, originalMenuY - Math.floor(screenHeight * 0.2));
                                                windowManager.updateViewLayout(Java.cast(menuView, View), Java.cast(menuParamsRef, ViewGroupLayoutParams));
                                            } else if (menuParamsRef && windowManager && menuView) {
                                                menuParamsRef.y.value = originalMenuY;
                                                windowManager.updateViewLayout(Java.cast(menuView, View), Java.cast(menuParamsRef, ViewGroupLayoutParams));
                                            }
                                        } catch (e2) { }
                                    }
                                });
                            }
                        }
                    }).$new());
                    commandInput.setOnEditorActionListener(Java.registerClass({
                        name: 'com.mentalist.CommandInputListener',
                        implements: [Java.use('android.widget.TextView$OnEditorActionListener')],
                        methods: {
                            onEditorAction: function (view, actionId, event) {
                                try {
                                    const cmd = view.getText().toString();
                                    if (cmd) {
                                        messageQueue.push(JSON.stringify({ type: 'command', data: cmd }));
                                        view.setText(JavaString.$new(''));
                                        errorTextView.setText(JavaString.$new(''));
                                    }
                                    return true;
                                } catch (e) {
                                    return false;
                                }
                            }
                        }
                    }).$new());
                    playersSectionView.addView(commandInput);
                    errorTextView = TextView.$new(context);
                    errorTextView.setTextColor(Color.parseColor('#FF6B6B'));
                    errorTextView.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 11.0);
                    errorTextView.setPadding(0, dpToPx(4), 0, 0);
                    errorTextView.setLayoutParams(LinearLayoutParams.$new(ViewGroupLayoutParams.MATCH_PARENT.value, ViewGroupLayoutParams.WRAP_CONTENT.value));
                    playersSectionView.addView(errorTextView);
                    sectionsContainer.addView(playersSectionView);

                    messagesSectionView = LinearLayout.$new(context);
                    messagesSectionView.setOrientation(LinearLayout.VERTICAL.value);
                    messagesSectionView.setLayoutParams(FrameLayoutParams.$new(ViewGroupLayoutParams.MATCH_PARENT.value, ViewGroupLayoutParams.MATCH_PARENT.value));
                    messagesSectionView.setVisibility(View.GONE.value);
                    selectedPlayerSpinner = Spinner.$new(context);
                    selectedPlayerSpinner.setClickable(true);
                    selectedPlayerSpinner.setEnabled(true);
                    selectedPlayerSpinner.setPadding(dpToPx(12), dpToPx(10), dpToPx(12), dpToPx(10));
                    const spinnerBg = GradientDrawable.$new();
                    spinnerBg.setShape(GradientDrawable.RECTANGLE.value);
                    spinnerBg.setColor(Color.parseColor('#4A4A4A'));
                    spinnerBg.setCornerRadius(JavaFloat.parseFloat('8.0'));
                    spinnerBg.setStroke(2, Color.parseColor('#DC143C'));
                    selectedPlayerSpinner.setBackground(spinnerBg);
                    const initItems = Java.array('java.lang.String', [JavaString.$new('None')]);
                    const initAdapter = ArrayAdapter.$new(context, Java.use('android.R$layout').simple_spinner_item.value, initItems);
                    initAdapter.setDropDownViewResource(Java.use('android.R$layout').simple_spinner_dropdown_item.value);
                    selectedPlayerSpinner.setAdapter(initAdapter);
                    selectedPlayerSpinner.setSelection(0);
                    gameState.selectedPlayerId = null;
                    const spinnerParams = LinearLayoutParams.$new(ViewGroupLayoutParams.MATCH_PARENT.value, ViewGroupLayoutParams.WRAP_CONTENT.value);
                    spinnerParams.setMargins(0, dpToPx(8), 0, dpToPx(8));
                    selectedPlayerSpinner.setLayoutParams(spinnerParams);
                    selectedPlayerSpinner.setOnItemSelectedListener(Java.registerClass({
                        name: 'com.mentalist.MessagesSpinnerListener',
                        implements: [Java.use('android.widget.AdapterView$OnItemSelectedListener')],
                        methods: {
                            onItemSelected: function (parent, view, position, id) {
                                try {
                                    if (position === 0) {
                                        gameState.selectedPlayerId = null;
                                    } else {
                                        const players = Object.values(gameState.playersById).sort((a, b) => (a.num || 99) - (b.num || 99));
                                        const chosen = players[position - 1];
                                        gameState.selectedPlayerId = chosen ? chosen.id : null;
                                    }
                                    if (view) {
                                        const tv = Java.cast(view, TextView);
                                        tv.setTextColor(Color.parseColor('#FFFFFF'));
                                        tv.setTypeface(Typeface.DEFAULT_BOLD.value);
                                        tv.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 14.0);
                                    }
                                    scheduleUiUpdate();
                                } catch (_) { }
                            },
                            onNothingSelected: function (parent) { }
                        }
                    }).$new());
                    messagesSectionView.addView(selectedPlayerSpinner);
                    const messagesOuter = LinearLayout.$new(context);
                    messagesOuter.setOrientation(LinearLayout.HORIZONTAL.value);
                    messagesOuter.setLayoutParams(LinearLayoutParams.$new(ViewGroupLayoutParams.MATCH_PARENT.value, 0, 1.0));
                    const colParams = Java.use('android.widget.LinearLayout$LayoutParams');
                    const sentCol = LinearLayout.$new(context);
                    sentCol.setOrientation(LinearLayout.VERTICAL.value);
                    sentCol.setLayoutParams(colParams.$new(0, ViewGroupLayoutParams.MATCH_PARENT.value, 1.0));
                    const sentLabel = TextView.$new(context);
                    sentLabel.setText(JavaString.$new('SENT'));
                    sentLabel.setTextColor(Color.parseColor('#FFFFFF'));
                    sentLabel.setTypeface(Typeface.DEFAULT_BOLD.value);
                    sentCol.addView(sentLabel);
                    const sentScroll = ScrollView.$new(context);
                    sentTextView = TextView.$new(context);
                    sentTextView.setTextColor(Color.parseColor('#E0E0E0'));
                    sentTextView.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 12.0);
                    sentScroll.addView(sentTextView);
                    sentCol.addView(sentScroll);
                    messagesOuter.addView(sentCol);
                    const dividerContainer = LinearLayout.$new(context);
                    dividerContainer.setOrientation(LinearLayout.HORIZONTAL.value);
                    const dividerContainerParams = colParams.$new(ViewGroupLayoutParams.WRAP_CONTENT.value, ViewGroupLayoutParams.MATCH_PARENT.value);
                    dividerContainer.setLayoutParams(dividerContainerParams);
                    const dividerLeftSpacer = View.$new(context);
                    dividerLeftSpacer.setLayoutParams(colParams.$new(dpToPx(4), ViewGroupLayoutParams.MATCH_PARENT.value));
                    dividerContainer.addView(dividerLeftSpacer);
                    const divider = View.$new(context);
                    divider.setBackgroundColor(Color.parseColor('#DC143C'));
                    divider.setLayoutParams(colParams.$new(Math.round(dpToPx(2)), ViewGroupLayoutParams.MATCH_PARENT.value));
                    dividerContainer.addView(divider);
                    const dividerRightSpacer = View.$new(context);
                    dividerRightSpacer.setLayoutParams(colParams.$new(dpToPx(4), ViewGroupLayoutParams.MATCH_PARENT.value));
                    dividerContainer.addView(dividerRightSpacer);
                    messagesOuter.addView(dividerContainer);
                    const mentionedCol = LinearLayout.$new(context);
                    mentionedCol.setOrientation(LinearLayout.VERTICAL.value);
                    mentionedCol.setLayoutParams(colParams.$new(0, ViewGroupLayoutParams.MATCH_PARENT.value, 1.0));
                    const mentionedLabel = TextView.$new(context);
                    mentionedLabel.setText(JavaString.$new('MENTIONED'));
                    mentionedLabel.setTextColor(Color.parseColor('#FFFFFF'));
                    mentionedLabel.setTypeface(Typeface.DEFAULT_BOLD.value);
                    mentionedCol.addView(mentionedLabel);
                    const mentionedScroll = ScrollView.$new(context);
                    mentionedTextView = TextView.$new(context);
                    mentionedTextView.setTextColor(Color.parseColor('#E0E0E0'));
                    mentionedTextView.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 12.0);
                    mentionedScroll.addView(mentionedTextView);
                    mentionedCol.addView(mentionedScroll);
                    messagesOuter.addView(mentionedCol);
                    messagesSectionView.addView(messagesOuter);
                    sectionsContainer.addView(messagesSectionView);

                    mastermindSectionView = LinearLayout.$new(context);
                    mastermindSectionView.setOrientation(LinearLayout.VERTICAL.value);
                    mastermindSectionView.setLayoutParams(FrameLayoutParams.$new(ViewGroupLayoutParams.MATCH_PARENT.value, ViewGroupLayoutParams.MATCH_PARENT.value));
                    mastermindSectionView.setVisibility(View.GONE.value);
                    predictButton = Button.$new(context);
                    predictButton.setText(JavaString.$new('Predict'));
                    predictButton.setTextColor(Color.parseColor('#FFFFFF'));
                    predictButton.setBackgroundColor(Color.parseColor('#B71C1C'));
                    const predictBtnParams = LinearLayoutParams.$new(ViewGroupLayoutParams.MATCH_PARENT.value, ViewGroupLayoutParams.WRAP_CONTENT.value);
                    predictBtnParams.setMargins(0, dpToPx(8), 0, dpToPx(8));
                    predictButton.setLayoutParams(predictBtnParams);
                    predictButton.setOnClickListener(Java.registerClass({
                        name: 'com.mentalist.PredictButtonListener',
                        implements: [Java.use('android.view.View$OnClickListener')],
                        methods: {
                            onClick: function (view) {
                                try {
                                    const btn = Java.cast(view, Button);
                                    btn.setEnabled(false);
                                    btn.setText(JavaString.$new('Predicting...'));
                                    messageQueue.push(JSON.stringify({ type: 'predict_request' }));
                                } catch (e) { }
                            }
                        }
                    }).$new());
                    mastermindSectionView.addView(predictButton);
                    const predictScroll = ScrollView.$new(context);
                    predictScroll.setLayoutParams(LinearLayoutParams.$new(ViewGroupLayoutParams.MATCH_PARENT.value, 0, 1.0));
                    predictResultTextView = TextView.$new(context);
                    predictResultTextView.setTextColor(Color.parseColor('#BBDEFB'));
                    predictResultTextView.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 12.0);
                    predictScroll.addView(predictResultTextView);
                    mastermindSectionView.addView(predictScroll);
                    sectionsContainer.addView(mastermindSectionView);

                    menuView.addView(sectionsContainer);

                    const menuParams = WindowManagerLayoutParams.$new(
                        WindowManagerLayoutParams.MATCH_PARENT.value,
                        WindowManagerLayoutParams.WRAP_CONTENT.value,
                        layoutType,
                        WindowManagerLayoutParams.FLAG_NOT_TOUCH_MODAL.value,
                        JavaInteger.parseInt('1F', 16)
                    );
                    menuParams.gravity = Gravity.TOP.value | Gravity.CENTER_HORIZONTAL.value;
                    menuParams.x = 0;
                    menuParams.y = 50;
                    menuParamsRef = menuParams;

                    windowManager.addView(Java.cast(menuView, View), Java.cast(menuParams, ViewGroupLayoutParams));
                    menuView.setVisibility(View.GONE.value);
                    isMenuVisible = false;

                    rebuildSpinnerOptions();
                    messageQueue.push(JSON.stringify({ type: 'log', message: '[OVERLAY] Mod menu successfully created.' }));
                    scheduleUiUpdate();

                } catch (e_main_thread) {
                    messageQueue.push(JSON.stringify({ type: 'log', message: '[OVERLAY ERROR on MainThread] ' + e_main_thread.toString() }));
                }
            });

        } catch (e) {
            messageQueue.push(JSON.stringify({ type: 'log', message: '[OVERLAY ERROR] Failed to create overlay: ' + e.toString() }));
        }

        rpc.exports = {
            setviewdata: function (jsonStr) {
                try {
                    latestRenderData = null;
                    if (jsonStr && typeof jsonStr === 'string') {
                        const data = safeJsonParse(jsonStr);
                        if (data) latestRenderData = data;
                    }
                    scheduleUiUpdate();
                } catch (e) {
                    messageQueue.push(JSON.stringify({ type: 'log', message: '[SETVIEWDATA ERROR] ' + e.toString() }));
                }
            },
            seterror: function (errorStr) {
                try {
                    if (errorTextView && errorStr) {
                        const JavaString = Java.use('java.lang.String');
                        errorTextView.setText(JavaString.$new(errorStr));
                    }
                } catch (e) {
                    messageQueue.push(JSON.stringify({ type: 'log', message: '[SETERROR ERROR] ' + e.toString() }));
                }
            },
            setpredictresult: function (resultStr) {
                try {
                    if (predictResultTextView && resultStr) {
                        const JavaString = Java.use('java.lang.String');
                        Java.scheduleOnMainThread(function () {
                            try {
                                predictResultTextView.setText(JavaString.$new(resultStr));
                                if (predictButton) {
                                    const Button = Java.use('android.widget.Button');
                                    const btn = Java.cast(predictButton, Button);
                                    btn.setEnabled(true);
                                    btn.setText(JavaString.$new('Predict'));
                                }
                            } catch (e) { }
                        });
                    }
                } catch (e) {
                    messageQueue.push(JSON.stringify({ type: 'log', message: '[SETPREDICTRESULT ERROR] ' + e.toString() }));
                }
            },
            togglemenu: function () {
                toggleMenu();
                return isMenuVisible;
            },
            getqueuedmessages: function () {
                if (messageQueue.length === 0) {
                    return null;
                }
                const messages = messageQueue.splice(0, messageQueue.length);
                return JSON.stringify(messages);
            }
        };

        messageQueue.push(JSON.stringify({ type: 'log', message: 'Frida agent loaded successfully.' }));
    });
});
