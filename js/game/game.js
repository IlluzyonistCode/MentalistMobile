import { State } from '../state.js';
import { Utils } from '../utils/logger.js';

export const Game = {
    upsertPlayer: function(player) {
        try {
            if (!player || !player.id) return;

            const prev = State.game.playersById[player.id] || {};
            const gridIdx = player.gridIdx != null ? player.gridIdx : (prev.num ? prev.num - 1 : -1);
            const num = gridIdx >= 0 ? (gridIdx + 1) : (prev.num || null);
            const alive = player.isAlive != null ?
                player.isAlive :
                (prev.alive != null ? prev.alive : true);

            State.game.playersById[player.id] = {
                id: player.id,
                username: player.username || prev.username || '',
                num: num,
                alive: alive,
                roleRevealed: player.roleRevealed != null ?
                    player.roleRevealed : (prev.roleRevealed || null)
            };

            if (num != null) State.game.idByNum[num] = player.id;

            Utils.log('[Game.upsertPlayer] Player stored: id=' + player.id +
                ' username=' + (player.username || '?') + ' num=' + num);
        } catch (e) {
            Utils.log('[Game.upsertPlayer] ERROR: ' + e);
        }
    },

    handleEvent: function(evt, payload) {
        try {
            switch (evt) {
                case 'players-and-equipped-items':
                    if (payload && Array.isArray(payload.players))
                        payload.players.forEach(function(p) { Game.upsertPlayer(p); });

                    Game.rebuildPlayersList();

                    break;

                case 'player-joined-and-equipped-items':
                    if (payload && payload.player) Game.upsertPlayer(payload.player);

                    Game.rebuildPlayersList();

                    break;

                case 'player-grid-idx':
                    if (payload && payload.playerId && payload.gridIdx != null)
                        Game.upsertPlayer({ id: payload.playerId, gridIdx: payload.gridIdx });

                    Game.rebuildPlayersList();

                    break;

                case 'player-disconnected':
                    if (payload && payload.id)
                        Game.upsertPlayer({
                            id: payload.id,
                            isAlive: payload.isAlive != null ? payload.isAlive : true
                        });

                    Game.rebuildPlayersList();

                    break;

                case 'game-started':
                    if (payload && Array.isArray(payload.players))
                        payload.players.forEach(function(p) { Game.upsertPlayer(p); });

                    Game.rebuildPlayersList();

                    break;

                case 'game-role-revealed':
                case 'role-revealed':
                    if (payload && payload.playerId && payload.role) {
                        const p = State.game.playersById[payload.playerId];

                        if (p) p.roleRevealed = payload.role;
                    }

                    Game.updateUI();

                    break;

                case 'game-players-killed':
                    if (payload && Array.isArray(payload.victims)) {
                        payload.victims.forEach(function(v) {
                            if (v && v.targetPlayerId)
                                Game.upsertPlayer({ id: v.targetPlayerId, isAlive: false });
                        });
                    }

                    Game.rebuildPlayersList();

                    break;

                case 'game:chat-public:msg':
                case 'chat-message':
                case 'message-sent':
                    if (payload) {
                        State.game.chat.push({
                            t: Date.now(),
                            authorId: payload.authorId || 'system',
                            msg: payload.msg || payload.message || ''
                        });

                        if (State.game.chat.length > 400) State.game.chat.shift();
                    }

                    Game.updateUI();

                    break;

                default:
            }
        } catch (e) {
            Utils.log('[Game.handleEvent] ERROR: evt=' + evt + ' | ' + e);
        }
    },

    rebuildPlayersList: function() {
        try {
            if (!State.ui.selectedPlayerSpinner) {
                Utils.log('[Game.rebuildPlayersList] SKIP: spinner not initialized yet');

                return;
            }

            Utils.log('[Game.rebuildPlayersList] Scheduling rebuild on main thread');

            Java.scheduleOnMainThread(function() {
                try {
                    Utils.log('[Game.rebuildPlayersList] START on main thread');

                    const ArrayAdapter = Java.use('android.widget.ArrayAdapter');
                    const JavaString = Java.use('java.lang.String');
                    const Spinner = Java.use('android.widget.Spinner');

                    const players = Object.values(State.game.playersById)
                        .filter(function(p) { return p.num != null; })
                        .sort(function(a, b) { return a.num - b.num; });

                    Utils.log('[Game.rebuildPlayersList] Players count: ' + players.length);

                    const labels = ['Select player'].concat(
                        players.map(function(p) {
                            const dead = p.alive ? '' : ' (dead)';

                            return '#' + p.num + ' ' + p.username + dead;
                        })
                    );

                    const items = Java.array('java.lang.String', labels.map(function(s) {
                        return JavaString.$new(s);
                    }));

                    const adapter = ArrayAdapter.$new(State.context, 17367048, items);
                    adapter.setDropDownViewResource(17367049);

                    const castedSpinner = Java.cast(State.ui.selectedPlayerSpinner, Spinner);
                    castedSpinner.setAdapter(adapter);

                    const current = State.game.selectedPlayerId;
                    let idxToSelect = 0;

                    if (current) {
                        const idx = players.findIndex(function(p) { return p.id === current; });

                        if (idx >= 0) idxToSelect = idx + 1;
                    }

                    castedSpinner.setSelection(idxToSelect);

                    Utils.log('[Game.rebuildPlayersList] Done. Selected index: ' + idxToSelect);
                } catch (e) {
                    Utils.log('[Game.rebuildPlayersList] ERROR on main thread: ' + e);
                }
            });
        } catch (e) {
            Utils.log('[Game.rebuildPlayersList] ERROR: ' + e);
        }
    },

    _lastUiUpdate: 0,
    _lastPlayersText: '',
    _lastSentText: '',
    _lastMentionedText: '',

    updateUI: function() {
        try {
            const now = Date.now();

            if (now - Game._lastUiUpdate < 1000) return;

            Game._lastUiUpdate = now;

            Java.scheduleOnMainThread(function() {
                try {
                    const TextView = Java.use('android.widget.TextView');
                    const JavaString = Java.use('java.lang.String');

                    if (State.ui.playersTextView) {
                        let text = '';

                        if (State.game.latestRenderData && State.game.latestRenderData.players) {
                            const lines = State.game.latestRenderData.players.map(function(p) {
                                if (!p) return '';

                                let line = '' + p.num;

                                if (p.name) line += ' ' + p.name;

                                if (p.level !== -1) line += ' ⭐' + p.level;

                                else if (p.min_level !== -1) line += ' ⭐' + p.min_level + '+';

                                line += ' (' + (p.messages || 0) + ')';

                                if (p.claim) line += ' C: ' + p.claim;

                                if (p.contradiction) line += ' ⚠️CC: ' + p.contradiction;

                                if (p.alliances && p.alliances.length > 0)
                                    p.alliances.forEach(function(a) { line += ' 🛡️ ' + a; });

                                if (p.role)
                                    line += ' — ' + p.role;

                                else if (p.team)
                                    line += ' [' + p.team + ']';

                                else if (p.teams_exclude && p.teams_exclude.length > 0)
                                    line += ' [NOT ' + p.teams_exclude.join(', ') + ']';

                                if (p.possible && p.possible.length > 0) {
                                    line += ' + POSSIBLE ';

                                    p.possible.forEach(function(pos, idx) {
                                        line += pos.role;

                                        if (!pos.has_card && !pos.has_icon) line += ' ❌⭕';
                                        else if (!pos.has_card) line += ' ❌';
                                        else if (!pos.has_icon) line += ' ⭕';
                                        if (idx < p.possible.length - 1) line += ' / ';
                                    });
                                }

                                if (p.threat != null) {
                                    let icon = '🟢';

                                    if (p.threat >= 70) icon = '🔴';

                                    else if (p.threat >= 30) icon = '🟡';

                                    line += ' ' + icon + '[' + p.threat + '%❕]';
                                }

                                if (p.aura === 'GOOD') line = '🟢 ' + line;
                                else if (p.aura === 'EVIL') line = '🔴 ' + line;
                                else if (p.aura === 'UNKNOWN') line = '🔵 ' + line;

                                if (p.dead) line = '  ~~' + line + '~~';

                                return line;
                            });

                            text = lines.join('\n');

                            if (State.game.latestRenderData.remaining) {
                                const rem = State.game.latestRenderData.remaining;

                                text += '\n\n━━ REMAINING ━━';

                                if (rem.GOOD && rem.GOOD.length) text += '\n🟢 GOOD: ' + rem.GOOD.join(', ');
                                if (rem.EVIL && rem.EVIL.length) text += '\n🔴 EVIL: ' + rem.EVIL.join(', ');
                                if (rem.UNKNOWN && rem.UNKNOWN.length) text += '\n🔵 UNKNOWN: ' + rem.UNKNOWN.join(', ');
                            }

                        } else {
                            const lines = Object.values(State.game.playersById)
                                .sort(function(a, b) { return (a.num || 99) - (b.num || 99); })
                                .map(function(p) {
                                    const num = p.num != null ? String(p.num) : '?';
                                    const dead = p.alive === false ? ' ✖' : ' ✓';
                                    const role = p.roleRevealed ? ' [' + p.roleRevealed + ']' : '';
                                    const lvl = (p.level && p.level > 0) ? ' ⭐' + p.level : '';

                                    return num + '. ' + (p.username || '') + lvl + dead + role;
                                });

                            text = lines.join('\n');
                        }

                        if (text !== Game._lastPlayersText) {
                            Game._lastPlayersText = text;

                            const castedTV = Java.cast(State.ui.playersTextView, TextView);

                            castedTV.setText.overload('java.lang.CharSequence').call(
                                castedTV,
                                JavaString.$new(text || 'Waiting for players...')
                            );
                        }
                    }

                    const selId = State.game.selectedPlayerId;

                    if (selId && State.ui.sentTextView && State.ui.mentionedTextView) {
                        const sel = State.game.playersById[selId];
                        const selName = sel ? sel.username : null;
                        const selNum = sel && sel.num != null ? sel.num : null;

                        const sentLines = [];
                        const mentionedLines = [];

                        const startIdx = Math.max(0, State.game.chat.length - 100);

                        for (let i = startIdx; i < State.game.chat.length; i++) {
                            const c = State.game.chat[i];

                            if (!c || !c.msg) continue;

                            const author = State.game.playersById[c.authorId];
                            const authorName = author ?
                                (author.num != null ? author.num + ' ' + author.username : author.username) :
                                'system';
                            const line = authorName + ': ' + c.msg;

                            if (c.authorId === selId) sentLines.push(line);

                            else {
                                let mentioned = false;

                                if (selName && c.msg && typeof c.msg === 'string') {
                                    const msgLower = c.msg.toLowerCase();
                                    const nameLower = selName.toLowerCase();

                                    if (msgLower.indexOf(nameLower) !== -1) mentioned = true;

                                    if (!mentioned && selNum != null) {
                                        const re = new RegExp('(^|[^\\d])' + selNum + '([^\\d]|$)');

                                        if (re.test(c.msg)) mentioned = true;
                                    }
                                }

                                if (mentioned) mentionedLines.push(line);
                            }
                        }

                        const sentText = sentLines.join('\n') || 'No sent messages';
                        const mentionedText = mentionedLines.join('\n') || 'No mentions';

                        if (sentText !== Game._lastSentText) {
                            Game._lastSentText = sentText;

                            const castedSent = Java.cast(State.ui.sentTextView, TextView);
                            castedSent.setText.overload('java.lang.CharSequence').call(
                                castedSent,
                                JavaString.$new(sentText)
                            );
                        }

                        if (mentionedText !== Game._lastMentionedText) {
                            Game._lastMentionedText = mentionedText;

                            const castedMentioned = Java.cast(State.ui.mentionedTextView, TextView);
                            castedMentioned.setText.overload('java.lang.CharSequence').call(
                                castedMentioned,
                                JavaString.$new(mentionedText)
                            );
                        }
                    }
                } catch (e) {
                    Utils.log('[Game.updateUI] ERROR on main thread: ' + e);
                }
            });
        } catch (e) {
            Utils.log('[Game.updateUI] ERROR: ' + e);
        }
    }
};
