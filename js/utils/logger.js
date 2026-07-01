import { LOG_WS, LOG_UI, LOG_RPC, LOG_HTTP } from '../constants.js';
import { State } from '../state.js';

export const Utils = {
    log: function(msg) {
        try {
            const isUI = msg.indexOf('[Init.') !== -1 || msg.indexOf('[UI.') !== -1 ||
                msg.indexOf('[TrackerMenu') !== -1 || msg.indexOf('[Buttons') !== -1 ||
                msg.indexOf('[BoosterMenu') !== -1 || msg.indexOf('[InviterMenu') !== -1 ||
                msg.indexOf('[SpinnerMenu') !== -1 || msg.indexOf('[MenuController') !== -1 ||
                msg.indexOf('[Game.updateUI') !== -1 || msg.indexOf('[Game.rebuild') !== -1 ||
                msg.indexOf('[PanelTouch') !== -1 || msg.indexOf('[dpToPx') !== -1;
            const isRPC = msg.indexOf('[Init.setupRPC]') !== -1 || msg.indexOf('[RPC.') !== -1;
            const isWS = msg.indexOf('[Hooks.') !== -1 || msg.indexOf('[WS') !== -1 ||
                msg.indexOf('[Game.handleEvent') !== -1;
            const isHTTP = msg.indexOf('[Hooks.HTTP]') !== -1 || msg.indexOf('[HTTP') !== -1;

            if (isRPC && !LOG_RPC) return;
            if (isUI && !isRPC && !LOG_UI) return;
            if (isWS && !LOG_WS) return;
            if (isHTTP && !LOG_HTTP) return;

            globalThis._mq.push(JSON.stringify({
                type: 'log',
                message: msg
            }));
        } catch (e) {
            console.error('[LOGGER FATAL] ' + e);
        }
    },

    dpToPx: function(dp) {
        try {
            if (!State.context) return Math.round(dp);

            const metrics = State.context.getResources().getDisplayMetrics();
            const TypedValue = Java.use('android.util.TypedValue');
            const result = TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_DIP.value,
                dp,
                metrics
            );

            return Math.round(result);
        } catch (e) {
            Utils.log('[dpToPx] ERROR: ' + e + ' | dp=' + dp);

            return Math.round(dp);
        }
    },

    safeJsonParse: function(text) {
        try {
            return JSON.parse(text);
        } catch (_) {}
    },

    parseSocketIoEnvelope: function(text) {
        if (typeof text !== 'string') return;

        if (!text.startsWith('42')) return;

        const idx = text.indexOf('[');

        if (idx < 0) return;

        const arr = Utils.safeJsonParse(text.slice(idx));

        if (!Array.isArray(arr) || arr.length < 1) return;

        const evt = arr[0];
        
        let payload = arr.length > 1 ? arr[1] : null;

        if (typeof payload === 'string') {
            const inner = Utils.safeJsonParse(payload);

            if (inner) payload = inner;
        }

        return { event: evt, payload: payload };
    }
};
