import { State } from '../state.js';
import { Utils } from '../utils/logger.js';

export const Tracker = {
    analyzePlayer: function(playerId) {
        if (!playerId || !State.game.playersById[playerId]) return null;

        const player = State.game.playersById[playerId];
        const sent = State.game.messagesBySender[playerId] || [];
        const mentioned = State.game.messagesByMentioned[playerId] || [];

        return {
            player: player,
            sent: sent,
            mentioned: mentioned,
            sentCount: sent.length,
            mentionedCount: mentioned.length
        };
    },

    getAllPlayers: function() {
        const players = [];

        for (const id in State.game.playersById) {
            const p = State.game.playersById[id];

            if (p && p.username) {
                const sent = State.game.messagesBySender[id] || [];
                const mentioned = State.game.messagesByMentioned[id] || [];

                players.push({
                    id: id,
                    username: p.username,
                    playerNum: p.playerNum || '?',
                    num: p.num,
                    sentCount: sent.length,
                    mentionedCount: mentioned.length
                });
            }
        }

        return players;
    },

    getSortedPlayers: function(sortBy) {
        const players = Tracker.getAllPlayers();

        if (sortBy === 'sent')
            return players.sort(function(a, b) {
                return b.sentCount - a.sentCount;
            });

        if (sortBy === 'mentioned')
            return players.sort(function(a, b) {
                return b.mentionedCount - a.mentionedCount;
            });

        return players.sort(function(a, b) {
            const numA = parseInt(a.playerNum) || 999;
            const numB = parseInt(b.playerNum) || 999;

            return numA - numB;
        });
    },

    getPlayersList: function() {
        return Object.values(State.game.playersById)
            .filter(function(p) { return p.num != null; })
            .sort(function(a, b) { return a.num - b.num; });
    },

    formatPlayersList: function(sortBy) {
        const players = Tracker.getSortedPlayers(sortBy);
        const lines = [];

        for (let i = 0; i < players.length; i++) {
            const p = players[i];
            const line = '#' + p.playerNum + ' ' + p.username +
                ' [S:' + p.sentCount + ' M:' + p.mentionedCount + ']';
            
            lines.push(line);
        }

        return lines.join('\n');
    },

    formatPlayerSent: function(playerId) {
        const analysis = Tracker.analyzePlayer(playerId);

        if (!analysis || analysis.sentCount === 0) return 'No messages sent';

        const lines = [];

        for (let i = 0; i < analysis.sent.length; i++) {
            const msg = analysis.sent[i];

            lines.push('Day ' + msg.day + ': ' + msg.text);
        }

        return lines.join('\n');
    },

    formatPlayerMentioned: function(playerId) {
        const analysis = Tracker.analyzePlayer(playerId);

        if (!analysis || analysis.mentionedCount === 0) return 'Not mentioned';

        const lines = [];

        for (let i = 0; i < analysis.mentioned.length; i++) {
            const msg = analysis.mentioned[i];
            const senderNum = msg.senderNum || '?';

            lines.push('Day ' + msg.day + ' by #' + senderNum + ': ' + msg.text);
        }

        return lines.join('\n');
    },

    getMessagesForSelectedPlayer: function() {
        const pid = State.game.selectedPlayerId;

        if (!pid) return { sent: [], mentioned: [] };

        return {
            sent: State.game.messagesBySender[pid] || [],
            mentioned: State.game.messagesByMentioned[pid] || []
        };
    },

    formatMessagesText: function() {
        const msgs = Tracker.getMessagesForSelectedPlayer();
        const lines = [];

        if (msgs.sent.length > 0) {
            lines.push('=== SENT ===');

            for (let i = 0; i < msgs.sent.length; i++) {
                const m = msgs.sent[i];

                lines.push('Day ' + m.day + ': ' + m.text);
            }
        }

        if (msgs.mentioned.length > 0) {
            if (lines.length > 0) lines.push('');

            lines.push('=== MENTIONED ===');

            for (let i = 0; i < msgs.mentioned.length; i++) {
                const m = msgs.mentioned[i];

                lines.push('Day ' + m.day + ' by #' + (m.senderNum || '?') + ': ' + m.text);
            }
        }

        if (lines.length === 0) return 'No messages';

        return lines.join('\n');
    },

    predictMastermind: function() {
        const players = Tracker.getAllPlayers();

        if (players.length === 0) return { result: 'No data available', details: '' };

        let bestCandidate = null;
        let bestScore = -1;

        for (let i = 0; i < players.length; i++) {
            const p = players[i];
            const score = (p.mentionedCount * 2) - (p.sentCount * 0.5);

            if (score > bestScore) {
                bestScore = score;
                bestCandidate = p;
            }
        }

        if (!bestCandidate) return { result: 'Unable to predict', details: '' };

        const result = '#' + bestCandidate.playerNum + ' ' + bestCandidate.username;
        const details = 'Score: ' + bestScore.toFixed(1) +
            ' (Mentioned: ' + bestCandidate.mentionedCount +
            ', Sent: ' + bestCandidate.sentCount + ')';

        return { result: result, details: details };
    },

    findPlayerByUsername: function(username) {
        return Object.values(State.game.playersById).find(function(p) {
            return p.username === username;
        });
    },

    clearData: function() {
        State.game.playersById = {};
        State.game.idByNum = {};
        State.game.chat = [];
        State.game.messages = [];
        State.game.messagesBySender = {};
        State.game.messagesByMentioned = {};
        State.game.selectedPlayerId = null;
    }
};
