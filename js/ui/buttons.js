import { State } from '../state.js';
import { Utils } from '../utils/logger.js';
import { UI } from './ui.js';
import { COLORS, ICON_BASE64 } from '../constants.js';

export const Buttons = {
    createRed: function(ctx) {
        try {
            Utils.log('[Buttons.createRed] START');

            const iconView = UI.createIcon(ctx, ICON_BASE64, COLORS.red);

            if (!iconView) {
                Utils.log('[Buttons.createRed] ERROR: icon creation failed');

                return;
            }

            Java.registerClass({
                name: 'com.mentalist.RedBtnListener',
                implements: [Java.use('android.view.View$OnClickListener')],
                methods: {
                    onClick: function(v) {
                        try {
                            Utils.log('[Buttons.createRed] onClick fired');

                            globalThis._menuControllerToggle('tracker');
                        } catch (e) {
                            Utils.log('[Buttons.createRed] onClick ERROR: ' + e);
                        }
                    }
                }
            });

            iconView.setTag(Java.use('java.lang.String').$new('red'));

            State.buttons.red = iconView;

            Utils.log('[Buttons.createRed] Done');

            return iconView;
        } catch (e) {
            Utils.log('[Buttons.createRed] ERROR: ' + e);

            return;
        }
    },

    createGreen: function(ctx) {
        try {
            Utils.log('[Buttons.createGreen] START');

            const iconView = UI.createIcon(ctx, ICON_BASE64, COLORS.green);

            if (!iconView) {
                Utils.log('[Buttons.createGreen] ERROR: icon creation failed');

                return;
            }

            Java.registerClass({
                name: 'com.mentalist.GreenBtnListener',
                implements: [Java.use('android.view.View$OnClickListener')],
                methods: {
                    onClick: function(v) {
                        try {
                            Utils.log('[Buttons.createGreen] onClick fired');

                            globalThis._menuControllerToggle('booster');
                        } catch (e) {
                            Utils.log('[Buttons.createGreen] onClick ERROR: ' + e);
                        }
                    }
                }
            });

            iconView.setTag(Java.use('java.lang.String').$new('green'));

            State.buttons.green = iconView;

            Utils.log('[Buttons.createGreen] Done');

            return iconView;
        } catch (e) {
            Utils.log('[Buttons.createGreen] ERROR: ' + e);

            return;
        }
    },

    createBlue: function(ctx) {
        try {
            Utils.log('[Buttons.createBlue] START');

            const iconView = UI.createIcon(ctx, ICON_BASE64, COLORS.blue);

            if (!iconView) {
                Utils.log('[Buttons.createBlue] ERROR: icon creation failed');

                return;
            }

            Java.registerClass({
                name: 'com.mentalist.BlueBtnListener',
                implements: [Java.use('android.view.View$OnClickListener')],
                methods: {
                    onClick: function(v) {
                        try {
                            Utils.log('[Buttons.createBlue] onClick fired');

                            globalThis._menuControllerToggle('spinner');
                        } catch (e) {
                            Utils.log('[Buttons.createBlue] onClick ERROR: ' + e);
                        }
                    }
                }
            });

            iconView.setTag(Java.use('java.lang.String').$new('blue'));

            State.buttons.blue = iconView;

            Utils.log('[Buttons.createBlue] Done');

            return iconView;
        } catch (e) {
            Utils.log('[Buttons.createBlue] ERROR: ' + e);

            return;
        }
    },

    createYellow: function(ctx) {
        try {
            Utils.log('[Buttons.createYellow] START');

            const iconView = UI.createIcon(ctx, ICON_BASE64, '#FFD600');

            if (!iconView) {
                Utils.log('[Buttons.createYellow] ERROR: icon creation failed');

                return;
            }

            Java.registerClass({
                name: 'com.mentalist.YellowBtnListener',
                implements: [Java.use('android.view.View$OnClickListener')],
                methods: {
                    onClick: function(v) {
                        try {
                            Utils.log('[Buttons.createYellow] onClick fired');

                            globalThis._menuControllerToggle('spam');
                        } catch (e) {
                            Utils.log('[Buttons.createYellow] onClick ERROR: ' + e);
                        }
                    }
                }
            });

            iconView.setTag(Java.use('java.lang.String').$new('yellow'));

            State.buttons.yellow = iconView;

            Utils.log('[Buttons.createYellow] Done');

            return iconView;
        } catch (e) {
            Utils.log('[Buttons.createYellow] ERROR: ' + e);

            return;
        }
    }
};
