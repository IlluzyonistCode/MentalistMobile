import { State } from '../../state.js';
import { Utils } from '../../utils/logger.js';
import { UI } from '../ui.js';
import { Spinner } from '../../modules/spinner.js';
import { COLORS, UI_CONFIG } from '../../constants.js';

export const SpinnerMenu = {
    create: function(ctx) {
        try {
            Utils.log('[SpinnerMenu.create] START');

            const LinearLayout = Java.use('android.widget.LinearLayout');
            const TextView = Java.use('android.widget.TextView');
            const JavaString = Java.use('java.lang.String');
            const Color = Java.use('android.graphics.Color');
            const LayoutParams = Java.use('android.widget.LinearLayout$LayoutParams');
            const ViewGroupLP = Java.use('android.view.ViewGroup$LayoutParams');
            const TypedValue = Java.use('android.util.TypedValue');
            const Typeface = Java.use('android.graphics.Typeface');
            const Gravity = Java.use('android.view.Gravity');

            const menu = UI.createGradientMenu(ctx, {
                gradientStart: COLORS.blueDark,
                gradientEnd: COLORS.menuBgDark,
                borderColor: COLORS.blue
            });

            if (!menu) {
                Utils.log('[SpinnerMenu.create] ERROR: createGradientMenu returned null');

                return;
            }

            const bitmap = UI.decodeIconBitmap();
            const titleBar = UI.createTitleBar(ctx, 'Spinner', bitmap, '#00BFFF');

            if (titleBar) menu.addView(titleBar);

            const descText = TextView.$new(ctx);
            descText.setText(JavaString.$new(
                'Auto-spins the gold wheel by watching ads.\n' +
                'Resets advertising ID before each run.'
            ));
            descText.setTextColor(Color.parseColor(COLORS.lightGray));
            descText.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 12.0);
            descText.setTypeface(Typeface.DEFAULT.value);
            const descLP = LayoutParams.$new(
                ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value
            );
            descLP.setMargins(0, 0, 0, Utils.dpToPx(12));
            descText.setLayoutParams(descLP);
            menu.addView(descText);

            const statusView = TextView.$new(ctx);
            statusView.setText(JavaString.$new('Ready'));
            statusView.setTextColor(Color.parseColor(COLORS.lightGray));
            statusView.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 12.0);
            statusView.setGravity(Gravity.CENTER.value);
            statusView.setLayoutParams(LayoutParams.$new(
                ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value
            ));
            Spinner.setStatusView(statusView);

            const btnRow = LinearLayout.$new(ctx);
            btnRow.setOrientation(LinearLayout.HORIZONTAL.value);
            const rowLP = LayoutParams.$new(
                ViewGroupLP.MATCH_PARENT.value, Utils.dpToPx(UI_CONFIG.buttonHeight)
            );
            rowLP.setMargins(0, 0, 0, Utils.dpToPx(8));
            btnRow.setLayoutParams(rowLP);

            const startBtn = UI.createButton(ctx, {
                text: 'START',
                bgColor: '#00AA44',
                textColor: COLORS.white,
                textSize: 15,
                onClick: function(v) {
                    try {
                        Utils.log('[SpinnerMenu] START clicked');

                        if (Spinner._running) {
                            Utils.log('[SpinnerMenu] Already running');

                            return;
                        }

                        Spinner.start();
                    } catch (e) {
                        Utils.log('[SpinnerMenu] START ERROR: ' + e);
                    }
                }
            });

            const stopBtn = UI.createButton(ctx, {
                text: 'STOP',
                bgColor: '#CC2200',
                textColor: COLORS.white,
                textSize: 15,
                onClick: function(v) {
                    try {
                        Utils.log('[SpinnerMenu] STOP clicked');
                        
                        Spinner.stop();
                    } catch (e) {
                        Utils.log('[SpinnerMenu] STOP ERROR: ' + e);
                    }
                }
            });

            if (startBtn && stopBtn) {
                const btnLP = LayoutParams.$new(0, ViewGroupLP.MATCH_PARENT.value, 1.0);
                btnLP.setMargins(0, 0, Utils.dpToPx(6), 0);
                startBtn.setLayoutParams(btnLP);

                const stopLP = LayoutParams.$new(0, ViewGroupLP.MATCH_PARENT.value, 1.0);
                stopBtn.setLayoutParams(stopLP);

                btnRow.addView(startBtn);
                btnRow.addView(stopBtn);
                menu.addView(btnRow);
            }

            const resetBtn = UI.createButton(ctx, {
                text: 'RESET AD ID',
                bgColor: '#FF8800',
                textColor: COLORS.white,
                textSize: 13,
                onClick: function(v) {
                    try {
                        Utils.log('[SpinnerMenu] RESET AD ID clicked');
                        Spinner.openAdsSettings();
                    } catch (e) {
                        Utils.log('[SpinnerMenu] RESET AD ID ERROR: ' + e);
                    }
                }
            });

            if (resetBtn) {
                const resetLP = LayoutParams.$new(
                    ViewGroupLP.MATCH_PARENT.value, Utils.dpToPx(UI_CONFIG.buttonHeight)
                );
                resetLP.setMargins(0, 0, 0, Utils.dpToPx(8));
                resetBtn.setLayoutParams(resetLP);
                menu.addView(resetBtn);
            }

            menu.addView(statusView);

            State.menus.spinner = menu;

            Utils.log('[SpinnerMenu.create] Done');

            return menu;
        } catch (e) {
            Utils.log('[SpinnerMenu.create] ERROR: ' + e);

            return;
        }
    },

    show: function() {
        try {
            if (!State.menus.spinner) return;

            const View = Java.use('android.view.View');

            State.menus.spinner.setVisibility(View.VISIBLE.value);
            State.visibility.spinner = true;

            Utils.log('[SpinnerMenu.show] VISIBLE');
        } catch (e) {
            Utils.log('[SpinnerMenu.show] ERROR: ' + e);
        }
    },

    hide: function() {
        try {
            if (!State.menus.spinner) return;

            const View = Java.use('android.view.View');

            State.menus.spinner.setVisibility(View.GONE.value);
            State.visibility.spinner = false;

            Utils.log('[SpinnerMenu.hide] GONE');
        } catch (e) {
            Utils.log('[SpinnerMenu.hide] ERROR: ' + e);
        }
    },

    toggle: function() {
        globalThis._menuControllerToggle('spinner');
    }
};
