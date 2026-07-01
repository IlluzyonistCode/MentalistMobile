import { State } from '../../state.js';
import { Utils } from '../../utils/logger.js';
import { UI } from '../ui.js';
import { InviterSession } from '../../modules/inviter.js';
import { COLORS, UI_CONFIG } from '../../constants.js';

const INVITE_COUNT_MIN = 1;
const INVITE_COUNT_MAX = 1000;
const INVITE_DELAY_MIN = 1000;
const INVITE_DELAY_MAX = 60000;

export const InviterMenu = {
    create: function(ctx) {
        try {
            Utils.log('[InviterMenu.create] START');

            const LinearLayout = Java.use('android.widget.LinearLayout');
            const TextView = Java.use('android.widget.TextView');
            const JavaString = Java.use('java.lang.String');
            const Color = Java.use('android.graphics.Color');
            const InputType = Java.use('android.text.InputType');
            const LayoutParams = Java.use('android.widget.LinearLayout$LayoutParams');
            const ViewGroupLP = Java.use('android.view.ViewGroup$LayoutParams');
            const TypedValue = Java.use('android.util.TypedValue');
            const Typeface = Java.use('android.graphics.Typeface');
            const Gravity = Java.use('android.view.Gravity');

            const menu = UI.createGradientMenu(ctx, {
                gradientStart: '#7A6000',
                gradientEnd: COLORS.menuBgDark,
                borderColor: '#FFD600'
            });

            if (!menu) {
                Utils.log('[InviterMenu.create] ERROR: createGradientMenu returned null');

                return;
            }

            Utils.log('[InviterMenu.create] Root container created');

            const bitmap = UI.decodeIconBitmap();
            const titleBar = UI.createTitleBar(ctx, 'Inviter', bitmap, '#FFD600');

            if (titleBar) {
                menu.addView(titleBar);

                Utils.log('[InviterMenu.create] Title bar added');
            }

            const nameLabel = TextView.$new(ctx);
            nameLabel.setText(JavaString.$new('Player Name:'));
            nameLabel.setTextColor(Color.parseColor(COLORS.white));
            nameLabel.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 14.0);
            nameLabel.setTypeface(Typeface.DEFAULT_BOLD.value);

            const nameLabelLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value);
            nameLabelLP.setMargins(0, 0, 0, Utils.dpToPx(4));
            nameLabel.setLayoutParams(nameLabelLP);
            menu.addView(nameLabel);

            const inviteNameInput = UI.createTextField(ctx, {
                hint: 'Enter player name',
                textSize: 14,
                bgColor: COLORS.inputBg,
                textColor: COLORS.white,
                hintColor: COLORS.inputBorder
            });

            if (!inviteNameInput) {
                Utils.log('[InviterMenu.create] ERROR: inviteNameInput is null');

                return;
            }

            const nameInputLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value);
            nameInputLP.setMargins(0, 0, 0, Utils.dpToPx(12));
            inviteNameInput.setLayoutParams(nameInputLP);
            menu.addView(inviteNameInput);

            Utils.log('[InviterMenu.create] Name input added');

            const countLabel = TextView.$new(ctx);
            countLabel.setText(JavaString.$new('Count (1–1000):'));
            countLabel.setTextColor(Color.parseColor(COLORS.white));
            countLabel.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 14.0);
            countLabel.setTypeface(Typeface.DEFAULT_BOLD.value);

            const countLabelLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value);
            countLabelLP.setMargins(0, 0, 0, Utils.dpToPx(4));
            countLabel.setLayoutParams(countLabelLP);
            menu.addView(countLabel);

            const inviteCountInput = UI.createTextField(ctx, {
                hint: 'Enter count',
                text: '10',
                textSize: 14,
                bgColor: COLORS.inputBg,
                textColor: COLORS.white,
                hintColor: COLORS.inputBorder,
                inputType: InputType.TYPE_CLASS_NUMBER.value
            });

            if (!inviteCountInput) {
                Utils.log('[InviterMenu.create] ERROR: inviteCountInput is null');

                return;
            }

            const countInputLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value);
            countInputLP.setMargins(0, 0, 0, Utils.dpToPx(12));
            inviteCountInput.setLayoutParams(countInputLP);
            menu.addView(inviteCountInput);

            Utils.log('[InviterMenu.create] Count input added');

            const delayLabel = TextView.$new(ctx);
            delayLabel.setText(JavaString.$new('Delay ms (1000–60000):'));
            delayLabel.setTextColor(Color.parseColor(COLORS.white));
            delayLabel.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 14.0);
            delayLabel.setTypeface(Typeface.DEFAULT_BOLD.value);

            const delayLabelLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value);
            delayLabelLP.setMargins(0, 0, 0, Utils.dpToPx(4));
            delayLabel.setLayoutParams(delayLabelLP);
            menu.addView(delayLabel);

            const inviteDelayInput = UI.createTextField(ctx, {
                hint: 'Delay',
                text: '1500',
                textSize: 14,
                bgColor: COLORS.inputBg,
                textColor: COLORS.white,
                hintColor: COLORS.inputBorder,
                inputType: InputType.TYPE_CLASS_NUMBER.value
            });

            const delayInputLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value);
            delayInputLP.setMargins(0, 0, 0, Utils.dpToPx(12));
            inviteDelayInput.setLayoutParams(delayInputLP);
            menu.addView(inviteDelayInput);

            Utils.log('[InviterMenu.create] Delay input added');

            const inviteStatus = TextView.$new(ctx);
            inviteStatus.setText(JavaString.$new('Ready'));
            inviteStatus.setTextColor(Color.parseColor(COLORS.lightGray));
            inviteStatus.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 12.0);
            inviteStatus.setGravity(Gravity.CENTER.value);

            InviterSession.setStatusView(inviteStatus);

            const sendBtn = UI.createButton(ctx, {
                text: 'SEND INVITES',
                bgColor: '#FFD600',
                textColor: '#000000',
                textSize: 16,
                onClick: function(v) {
                    try {
                        Utils.log('[InviterMenu] SEND INVITES clicked');

                        const EditText = Java.use('android.widget.EditText');
                        const CharSeq = Java.use('java.lang.CharSequence');

                        const playerName = String(Java.cast(
                            Java.cast(inviteNameInput, EditText).getText(), CharSeq
                        ).toString()).trim();

                        const countRaw = parseInt(String(Java.cast(
                            Java.cast(inviteCountInput, EditText).getText(), CharSeq
                        ).toString())) || 1;

                        const delayRaw = parseInt(String(Java.cast(
                            Java.cast(inviteDelayInput, EditText).getText(), CharSeq
                        ).toString())) || INVITE_DELAY_MIN;

                        const count = Math.max(INVITE_COUNT_MIN, Math.min(INVITE_COUNT_MAX, countRaw));
                        const delay = Math.max(INVITE_DELAY_MIN, Math.min(INVITE_DELAY_MAX, delayRaw));

                        Utils.log('[InviterMenu] name="' + playerName + '" count=' + count + ' delay=' + delay + 'ms');

                        if (!playerName) {
                            Utils.log('[InviterMenu] WARN: empty player name');

                            return;
                        }

                        InviterSession.resolveAndInvite(playerName, count, delay, inviteStatus);
                    } catch (e) {
                        Utils.log('[InviterMenu] onClick ERROR: ' + e);
                    }
                }
            });

            if (sendBtn) {
                const btnLP = LayoutParams.$new(
                    ViewGroupLP.MATCH_PARENT.value, Utils.dpToPx(UI_CONFIG.buttonHeight)
                );
                btnLP.setMargins(0, 0, 0, Utils.dpToPx(8));
                sendBtn.setLayoutParams(btnLP);
                menu.addView(sendBtn);

                Utils.log('[InviterMenu.create] Send button added');
            }

            inviteStatus.setLayoutParams(LayoutParams.$new(
                ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value
            ));
            menu.addView(inviteStatus);

            State.menus.inviter = menu;

            Utils.log('[InviterMenu.create] Done');

            return menu;
        } catch (e) {
            Utils.log('[InviterMenu.create] ERROR: ' + e);
        }
    },

    show: function() {
        try {
            if (!State.menus.inviter) return;

            Utils.log('[InviterMenu.show] Showing inviter menu');

            const View = Java.use('android.view.View');

            State.menus.inviter.setVisibility(View.VISIBLE.value);
            State.visibility.inviter = true;

            InviterSession.open();

            Utils.log('[InviterMenu.show] Inviter menu is now VISIBLE');
        } catch (e) {
            Utils.log('[InviterMenu.show] ERROR: ' + e);
        }
    },

    hide: function() {
        try {
            if (!State.menus.inviter) return;

            Utils.log('[InviterMenu.hide] Hiding inviter menu');

            const View = Java.use('android.view.View');

            State.menus.inviter.setVisibility(View.GONE.value);
            State.visibility.inviter = false;

            InviterSession.close();

            Utils.log('[InviterMenu.hide] Inviter menu is now GONE');
        } catch (e) {
            Utils.log('[InviterMenu.hide] ERROR: ' + e);
        }
    },

    toggle: function() {
        Utils.log('[InviterMenu.toggle] Requested');
        
        globalThis._menuControllerToggle('inviter');
    }
};
