import { State } from '../../state.js';
import { Utils } from '../../utils/logger.js';
import { UI } from '../ui.js';
import { COLORS, UI_CONFIG } from '../../constants.js';

export const BoosterMenu = {
    create: function(ctx) {
        try {
            Utils.log('[BoosterMenu.create] START');

            const LinearLayout = Java.use('android.widget.LinearLayout');
            const TextView = Java.use('android.widget.TextView');
            const ScrollView = Java.use('android.widget.ScrollView');
            const JavaString = Java.use('java.lang.String');
            const Color = Java.use('android.graphics.Color');
            const LayoutParams = Java.use('android.widget.LinearLayout$LayoutParams');
            const ViewGroupLP = Java.use('android.view.ViewGroup$LayoutParams');
            const TypedValue = Java.use('android.util.TypedValue');

            const menu = UI.createGradientMenu(ctx, {
                gradientStart: COLORS.greenDark,
                gradientEnd: COLORS.menuBgDark,
                borderColor: COLORS.green
            });

            if (!menu) {
                Utils.log('[BoosterMenu.create] ERROR: createGradientMenu returned null');

                return;
            }

            Utils.log('[BoosterMenu.create] Root container created');

            const bitmap = UI.decodeIconBitmap();
            const titleBar = UI.createTitleBar(ctx, 'Booster', bitmap, COLORS.green);

            if (titleBar) {
                menu.addView(titleBar);

                Utils.log('[BoosterMenu.create] Title bar added');
            }

            const scrollView = ScrollView.$new(ctx);
            scrollView.setLayoutParams(LayoutParams.$new(
                ViewGroupLP.MATCH_PARENT.value,
                Math.round(Utils.dpToPx(500))
            ));

            const contentLayout = LinearLayout.$new(ctx);
            contentLayout.setOrientation(LinearLayout.VERTICAL.value);
            contentLayout.setPadding(0, Utils.dpToPx(8), 0, 0);

            const infoText = TextView.$new(ctx);
            infoText.setText(JavaString.$new(
                'Booster features\n\nComing soon...\n\nThis menu will contain:\n' +
                '- Speed boosts\n- Power-ups\n- Special abilities\n- Game enhancements'
            ));
            infoText.setTextColor(Color.parseColor(COLORS.lightBlue));
            infoText.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 14.0);
            infoText.setLineSpacing(Utils.dpToPx(4), 1.0);
            contentLayout.addView(infoText);

            Utils.log('[BoosterMenu.create] Info text added');

            const activateBtn = UI.createButton(ctx, {
                text: 'Activate Booster',
                bgColor: '#00AA00',
                textColor: COLORS.white,
                textSize: 16,
                onClick: function(v) {
                    Utils.log('[BoosterMenu] Activate button clicked');

                    messageQueue.push(JSON.stringify({ type: 'booster_activate' }));
                }
            });

            if (activateBtn) {
                const btnLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, Utils.dpToPx(48));
                btnLP.setMargins(0, Utils.dpToPx(16), 0, 0);

                activateBtn.setLayoutParams(btnLP);

                contentLayout.addView(activateBtn);

                Utils.log('[BoosterMenu.create] Activate button added');
            }

            scrollView.addView(contentLayout);
            menu.addView(scrollView);

            State.menus.booster = menu;

            Utils.log('[BoosterMenu.create] Done');

            return menu;
        } catch (e) {
            Utils.log('[BoosterMenu.create] ERROR: ' + e);

            return;
        }
    },

    show: function() {
        try {
            if (!State.menus.booster) {
                Utils.log('[BoosterMenu.show] SKIP: menu not created');

                return;
            }

            Utils.log('[BoosterMenu.show] Showing booster menu');

            const View = Java.use('android.view.View');

            State.menus.booster.setVisibility(View.VISIBLE.value);
            State.visibility.booster = true;

            Utils.log('[BoosterMenu.show] Booster menu is now VISIBLE');
        } catch (e) {
            Utils.log('[BoosterMenu.show] ERROR: ' + e);
        }
    },

    hide: function() {
        try {
            if (!State.menus.booster) {
                Utils.log('[BoosterMenu.hide] SKIP: menu not created');

                return;
            }

            Utils.log('[BoosterMenu.hide] Hiding booster menu');

            const View = Java.use('android.view.View');

            State.menus.booster.setVisibility(View.GONE.value);
            State.visibility.booster = false;

            Utils.log('[BoosterMenu.hide] Booster menu is now GONE');
        } catch (e) {
            Utils.log('[BoosterMenu.hide] ERROR: ' + e);
        }
    },

    toggle: function() {
        Utils.log('[BoosterMenu.toggle] Requested');

        globalThis._menuControllerToggle('booster');
    }
};
