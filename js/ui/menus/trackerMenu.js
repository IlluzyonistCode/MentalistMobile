import { State } from '../../state.js';
import { Utils } from '../../utils/logger.js';
import { UI } from '../ui.js';
import { Game } from '../../game/game.js';
import { Invites } from '../../modules/inviter.js';
import { Tracker } from '../../modules/tracker.js';
import { COLORS, UI_CONFIG } from '../../constants.js';

export const TrackerMenu = {
    create: function(ctx) {
        try {
            Utils.log('[TrackerMenu.create] START');

            const LinearLayout = Java.use('android.widget.LinearLayout');
            const LayoutParams = Java.use('android.widget.LinearLayout$LayoutParams');
            const FrameLayout = Java.use('android.widget.FrameLayout');
            const FrameLP = Java.use('android.widget.FrameLayout$LayoutParams');
            const ViewGroupLP = Java.use('android.view.ViewGroup$LayoutParams');
            const Gravity = Java.use('android.view.Gravity');

            const menu = UI.createGradientMenu(ctx, {
                gradientStart: COLORS.redDark,
                gradientEnd: COLORS.menuBgDark,
                borderColor: COLORS.crimson
            });

            if (!menu) {
                Utils.log('[TrackerMenu.create] ERROR: createGradientMenu returned null');

                return;
            }

            Utils.log('[TrackerMenu.create] Root menu container created');

            const bitmap = UI.decodeIconBitmap();
            const titleBar = UI.createTitleBar(ctx, 'Tracker', bitmap, COLORS.red);

            if (titleBar) {
                menu.addView(titleBar);

                Utils.log('[TrackerMenu.create] Title bar added');
            } else
                Utils.log('[TrackerMenu.create] WARN: title bar is null, skipping');

            Utils.log('[TrackerMenu.create] Creating tab buttons');

            const buttonRow = LinearLayout.$new(ctx);
            buttonRow.setOrientation(LinearLayout.HORIZONTAL.value);
            buttonRow.setGravity(Gravity.CENTER.value);
            buttonRow.setLayoutParams(LayoutParams.$new(
                ViewGroupLP.MATCH_PARENT.value,
                ViewGroupLP.WRAP_CONTENT.value
            ));

            const playersBtn = UI.createButton(ctx, {
                text: 'Players',
                bgColor: '#B71C1C',
                textColor: COLORS.white,
                onClick: function(v) {
                    Utils.log('[MainMenu] Tab click: players');
                    State.game.currentSection = 'players';
                    TrackerMenu.switchSection();
                }
            });

            if (!playersBtn) {
                Utils.log('[TrackerMenu.create] ERROR: playersBtn is null');

                return;
            }

            playersBtn.setLayoutParams(LayoutParams.$new(0, ViewGroupLP.WRAP_CONTENT.value, 1.0));

            State.ui.playersSectionButton = playersBtn;

            const messagesBtn = UI.createButton(ctx, {
                text: 'Messages',
                bgColor: COLORS.darkGray,
                textColor: COLORS.lightGray,
                onClick: function(v) {
                    Utils.log('[MainMenu] Tab click: messages');

                    State.game.currentSection = 'messages';
                    TrackerMenu.switchSection();
                    Game.rebuildPlayersList();
                }
            });

            if (!messagesBtn) {
                Utils.log('[TrackerMenu.create] ERROR: messagesBtn is null');

                return;
            }

            messagesBtn.setLayoutParams(LayoutParams.$new(0, ViewGroupLP.WRAP_CONTENT.value, 1.0));

            State.ui.messagesSectionButton = messagesBtn;

            const mastermindBtn = UI.createButton(ctx, {
                text: 'Mastermind',
                bgColor: COLORS.darkGray,
                textColor: COLORS.lightGray,
                onClick: function(v) {
                    Utils.log('[MainMenu] Tab click: mastermind');
                    State.game.currentSection = 'mastermind';
                    TrackerMenu.switchSection();
                }
            });

            if (!mastermindBtn) {
                Utils.log('[TrackerMenu.create] ERROR: mastermindBtn is null');

                return;
            }

            mastermindBtn.setLayoutParams(LayoutParams.$new(0, ViewGroupLP.WRAP_CONTENT.value, 1.0));

            State.ui.mastermindSectionButton = mastermindBtn;

            buttonRow.addView(playersBtn);
            buttonRow.addView(messagesBtn);
            buttonRow.addView(mastermindBtn);
            menu.addView(buttonRow);

            Utils.log('[TrackerMenu.create] Tab buttons added to button row');

            const sectionsContainer = FrameLayout.$new(ctx);
            sectionsContainer.setLayoutParams(LayoutParams.$new(
                ViewGroupLP.MATCH_PARENT.value,
                Math.round(Utils.dpToPx(500))
            ));

            Utils.log('[TrackerMenu.create] Creating sections');

            State.ui.playersSectionView = TrackerMenu.createPlayersSection(ctx);
            State.ui.messagesSectionView = TrackerMenu.createMessagesSection(ctx);
            State.ui.mastermindSectionView = TrackerMenu.createMastermindSection(ctx);
            State.ui.invitesSectionView = TrackerMenu.createInvitesSection(ctx);

            if (!State.ui.playersSectionView) Utils.log('[TrackerMenu.create] WARN: playersSectionView is null');
            if (!State.ui.messagesSectionView) Utils.log('[TrackerMenu.create] WARN: messagesSectionView is null');
            if (!State.ui.mastermindSectionView) Utils.log('[TrackerMenu.create] WARN: mastermindSectionView is null');
            if (!State.ui.invitesSectionView) Utils.log('[TrackerMenu.create] WARN: invitesSectionView is null');

            if (State.ui.playersSectionView) sectionsContainer.addView(State.ui.playersSectionView);
            if (State.ui.messagesSectionView) sectionsContainer.addView(State.ui.messagesSectionView);
            if (State.ui.mastermindSectionView) sectionsContainer.addView(State.ui.mastermindSectionView);
            if (State.ui.invitesSectionView) sectionsContainer.addView(State.ui.invitesSectionView);

            menu.addView(sectionsContainer);

            State.menus.tracker = menu;

            TrackerMenu.switchSection();

            Utils.log('[TrackerMenu.create] Done');

            return menu;
        } catch (e) {
            Utils.log('[TrackerMenu.create] ERROR: ' + e);

            return;
        }
    },

    createPlayersSection: function(ctx) {
        try {
            Utils.log('[TrackerMenu.createPlayersSection] START');

            const LinearLayout = Java.use('android.widget.LinearLayout');
            const TextView = Java.use('android.widget.TextView');
            const ScrollView = Java.use('android.widget.ScrollView');
            const View = Java.use('android.view.View');
            const JavaString = Java.use('java.lang.String');
            const Color = Java.use('android.graphics.Color');
            const LayoutParams = Java.use('android.widget.LinearLayout$LayoutParams');
            const FrameLP = Java.use('android.widget.FrameLayout$LayoutParams');
            const ViewGroupLP = Java.use('android.view.ViewGroup$LayoutParams');
            const TypedValue = Java.use('android.util.TypedValue');

            const section = LinearLayout.$new(ctx);
            section.setOrientation(LinearLayout.VERTICAL.value);
            section.setLayoutParams(FrameLP.$new(
                ViewGroupLP.MATCH_PARENT.value,
                ViewGroupLP.MATCH_PARENT.value
            ));
            section.setVisibility(View.VISIBLE.value);

            Utils.log('[TrackerMenu.createPlayersSection] Section container created');

            const playersScroll = ScrollView.$new(ctx);
            const scrollLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, 0, 1.0);
            scrollLP.setMargins(0, Utils.dpToPx(8), 0, 0);
            playersScroll.setLayoutParams(scrollLP);

            const playersText = TextView.$new(ctx);
            playersText.setTextColor(Color.parseColor(COLORS.lightBlue));
            playersText.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 12.0);
            playersText.setTextIsSelectable(true);
            playersText.setText(JavaString.$new('Waiting for game data...'));
            playersScroll.addView(playersText);
            section.addView(playersScroll);

            State.ui.playersTextView = playersText;

            Utils.log('[TrackerMenu.createPlayersSection] Done');

            return section;
        } catch (e) {
            Utils.log('[TrackerMenu.createPlayersSection] ERROR: ' + e);

            return;
        }
    },

    createMessagesSection: function(ctx) {
        try {
            Utils.log('[TrackerMenu.createMessagesSection] START');

            const LinearLayout = Java.use('android.widget.LinearLayout');
            const TextView = Java.use('android.widget.TextView');
            const ScrollView = Java.use('android.widget.ScrollView');
            const Spinner = Java.use('android.widget.Spinner');
            const View = Java.use('android.view.View');
            const JavaString = Java.use('java.lang.String');
            const Color = Java.use('android.graphics.Color');
            const LayoutParams = Java.use('android.widget.LinearLayout$LayoutParams');
            const FrameLP = Java.use('android.widget.FrameLayout$LayoutParams');
            const ViewGroupLP = Java.use('android.view.ViewGroup$LayoutParams');
            const TypedValue = Java.use('android.util.TypedValue');
            const Typeface = Java.use('android.graphics.Typeface');
            const ArrayAdapter = Java.use('android.widget.ArrayAdapter');
            const AdapterView = Java.use('android.widget.AdapterView$OnItemSelectedListener');
            const GradientDrawable = Java.use('android.graphics.drawable.GradientDrawable');
            const JavaFloat = Java.use('java.lang.Float');

            const section = LinearLayout.$new(ctx);
            section.setOrientation(LinearLayout.VERTICAL.value);
            section.setLayoutParams(FrameLP.$new(
                ViewGroupLP.MATCH_PARENT.value,
                ViewGroupLP.MATCH_PARENT.value
            ));
            section.setVisibility(View.GONE.value);

            Utils.log('[TrackerMenu.createMessagesSection] Section container created (GONE)');

            const playerSelectLabel = TextView.$new(ctx);
            playerSelectLabel.setText(JavaString.$new('Select Player:'));
            playerSelectLabel.setTextColor(Color.parseColor(COLORS.white));
            playerSelectLabel.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 14.0);
            playerSelectLabel.setTypeface(Typeface.DEFAULT_BOLD.value);

            const psLabelLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value);
            psLabelLP.setMargins(0, 0, 0, Utils.dpToPx(6));
            playerSelectLabel.setLayoutParams(psLabelLP);
            section.addView(playerSelectLabel);

            State.ui.selectedPlayerSpinner = Spinner.$new(ctx);

            const spinnerBg = GradientDrawable.$new();
            spinnerBg.setShape(GradientDrawable.RECTANGLE.value);
            spinnerBg.setColor(Color.parseColor(COLORS.inputBg));
            spinnerBg.setCornerRadius(JavaFloat.parseFloat('8.0'));
            spinnerBg.setStroke(2, Color.parseColor(COLORS.crimson));

            State.ui.selectedPlayerSpinner.setBackground(spinnerBg);
            State.ui.selectedPlayerSpinner.setPadding(
                Utils.dpToPx(12), Utils.dpToPx(10), Utils.dpToPx(12), Utils.dpToPx(10)
            );

            const spinnerLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value);
            spinnerLP.setMargins(0, 0, 0, Utils.dpToPx(14));

            State.ui.selectedPlayerSpinner.setLayoutParams(spinnerLP);

            const initItems = Java.array('java.lang.String', [JavaString.$new('Select player')]);

            const initAdapter = ArrayAdapter.$new(ctx, 17367048, initItems);
            initAdapter.setDropDownViewResource(17367049);

            State.ui.selectedPlayerSpinner.setAdapter(initAdapter);
            State.ui.selectedPlayerSpinner.setSelection(0);

            const SpinnerListener = Java.registerClass({
                name: 'com.mentalist.MessagesSpinnerListener',
                implements: [AdapterView],
                methods: {
                    onItemSelected: function(parent, view, position, id) {
                        try {
                            Utils.log('[SpinnerListener] Item selected: position=' + position);

                            if (position === 0) State.game.selectedPlayerId = null;

                            else {
                                const players = Tracker.getPlayersList();
                                const chosen = players[position - 1];

                                State.game.selectedPlayerId = chosen ? chosen.id : null;

                                Utils.log('[SpinnerListener] Selected: ' + (chosen ? chosen.username : 'none'));
                            }

                            if (view) {
                                try {
                                    const TVs = Java.use('android.widget.TextView');
                                    const TFs = Java.use('android.graphics.Typeface');
                                    const Cs = Java.use('android.graphics.Color');
                                    const TVd = Java.use('android.util.TypedValue');

                                    const tv = Java.cast(view, TVs);

                                    tv.setTextColor(Cs.parseColor(COLORS.white));
                                    tv.setTypeface(TFs.DEFAULT_BOLD.value);
                                    tv.setTextSize(TVd.COMPLEX_UNIT_SP.value, 14.0);
                                } catch (e) {}
                            }

                            Game.updateUI();
                        } catch (e) {
                            Utils.log('[SpinnerListener] onItemSelected ERROR: ' + e);
                        }
                    },
                    onNothingSelected: function(parent) {}
                }
            });

            State.ui.selectedPlayerSpinner.setOnItemSelectedListener(SpinnerListener.$new());

            section.addView(State.ui.selectedPlayerSpinner);

            Utils.log('[TrackerMenu.createMessagesSection] Spinner added');

            const messagesOuter = LinearLayout.$new(ctx);
            messagesOuter.setOrientation(LinearLayout.HORIZONTAL.value);
            messagesOuter.setLayoutParams(LayoutParams.$new(
                ViewGroupLP.MATCH_PARENT.value, 0, 1.0
            ));

            const sentCol = LinearLayout.$new(ctx);
            sentCol.setOrientation(LinearLayout.VERTICAL.value);
            sentCol.setLayoutParams(LayoutParams.$new(0, ViewGroupLP.MATCH_PARENT.value, 1.0));

            const sentLabel = TextView.$new(ctx);
            sentLabel.setText(JavaString.$new('SENT'));
            sentLabel.setTextColor(Color.parseColor(COLORS.white));
            sentLabel.setTypeface(Typeface.DEFAULT_BOLD.value);
            sentLabel.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 14.0);

            const sentLabelLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value);
            sentLabelLP.setMargins(0, 0, 0, Utils.dpToPx(8));
            sentLabel.setLayoutParams(sentLabelLP);
            sentCol.addView(sentLabel);

            const sentScroll = ScrollView.$new(ctx);
            const sentText = TextView.$new(ctx);
            sentText.setTextColor(Color.parseColor(COLORS.paleBlue));
            sentText.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 12.0);
            sentText.setTextIsSelectable(true);
            sentScroll.addView(sentText);
            sentCol.addView(sentScroll);

            State.ui.sentTextView = sentText;

            messagesOuter.addView(sentCol);

            Utils.log('[TrackerMenu.createMessagesSection] Sent column done');

            const dividerContainer = LinearLayout.$new(ctx);
            dividerContainer.setOrientation(LinearLayout.HORIZONTAL.value);
            dividerContainer.setLayoutParams(LayoutParams.$new(
                ViewGroupLP.WRAP_CONTENT.value, ViewGroupLP.MATCH_PARENT.value
            ));

            const leftSpacer = View.$new(ctx);
            leftSpacer.setLayoutParams(LayoutParams.$new(Utils.dpToPx(4), ViewGroupLP.MATCH_PARENT.value));
            dividerContainer.addView(leftSpacer);

            const dividerLine = View.$new(ctx);
            dividerLine.setBackgroundColor(Color.parseColor(COLORS.crimson));
            dividerLine.setLayoutParams(LayoutParams.$new(
                Math.round(Utils.dpToPx(2)), ViewGroupLP.MATCH_PARENT.value
            ));
            dividerContainer.addView(dividerLine);

            const rightSpacer = View.$new(ctx);
            rightSpacer.setLayoutParams(LayoutParams.$new(Utils.dpToPx(4), ViewGroupLP.MATCH_PARENT.value));
            dividerContainer.addView(rightSpacer);
            messagesOuter.addView(dividerContainer);

            Utils.log('[TrackerMenu.createMessagesSection] Divider done');

            const mentionedCol = LinearLayout.$new(ctx);
            mentionedCol.setOrientation(LinearLayout.VERTICAL.value);
            mentionedCol.setLayoutParams(LayoutParams.$new(0, ViewGroupLP.MATCH_PARENT.value, 1.0));

            const mentionedLabel = TextView.$new(ctx);
            mentionedLabel.setText(JavaString.$new('MENTIONED'));
            mentionedLabel.setTextColor(Color.parseColor(COLORS.white));
            mentionedLabel.setTypeface(Typeface.DEFAULT_BOLD.value);
            mentionedLabel.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 14.0);

            const mentLabelLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value);
            mentLabelLP.setMargins(0, 0, 0, Utils.dpToPx(8));
            mentionedLabel.setLayoutParams(mentLabelLP);
            mentionedCol.addView(mentionedLabel);

            const mentionedScroll = ScrollView.$new(ctx);

            const mentionedText = TextView.$new(ctx);

            mentionedText.setTextColor(Color.parseColor(COLORS.paleBlue));
            mentionedText.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 12.0);
            mentionedText.setTextIsSelectable(true);
            mentionedScroll.addView(mentionedText);
            mentionedCol.addView(mentionedScroll);

            State.ui.mentionedTextView = mentionedText;

            messagesOuter.addView(mentionedCol);
            section.addView(messagesOuter);

            Utils.log('[TrackerMenu.createMessagesSection] Mentioned column done');
            Utils.log('[TrackerMenu.createMessagesSection] Done');

            return section;
        } catch (e) {
            Utils.log('[TrackerMenu.createMessagesSection] ERROR: ' + e);

            return;
        }
    },

    createMastermindSection: function(ctx) {
        try {
            Utils.log('[TrackerMenu.createMastermindSection] START');

            const LinearLayout = Java.use('android.widget.LinearLayout');
            const TextView = Java.use('android.widget.TextView');
            const ScrollView = Java.use('android.widget.ScrollView');
            const View = Java.use('android.view.View');
            const JavaString = Java.use('java.lang.String');
            const Color = Java.use('android.graphics.Color');
            const LayoutParams = Java.use('android.widget.LinearLayout$LayoutParams');
            const FrameLP = Java.use('android.widget.FrameLayout$LayoutParams');
            const ViewGroupLP = Java.use('android.view.ViewGroup$LayoutParams');
            const TypedValue = Java.use('android.util.TypedValue');

            const section = LinearLayout.$new(ctx);
            section.setOrientation(LinearLayout.VERTICAL.value);
            section.setLayoutParams(FrameLP.$new(
                ViewGroupLP.MATCH_PARENT.value,
                ViewGroupLP.MATCH_PARENT.value
            ));
            section.setVisibility(View.GONE.value);
            section.setPadding(0, Utils.dpToPx(12), 0, 0);

            Utils.log('[TrackerMenu.createMastermindSection] Section container created (GONE)');

            const commandField = UI.createTextField(ctx, {
                hint: 'Enter command...',
                textSize: 14,
                bgColor: COLORS.inputBg,
                textColor: COLORS.white,
                hintColor: COLORS.inputBorder
            });

            if (!commandField) {
                Utils.log('[TrackerMenu.createMastermindSection] ERROR: commandField is null');

                return;
            }

            const fieldLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value);
            fieldLP.setMargins(0, 0, 0, Utils.dpToPx(8));
            commandField.setLayoutParams(fieldLP);
            section.addView(commandField);

            State.ui.commandInput = commandField;

            Utils.log('[TrackerMenu.createMastermindSection] Command input added');

            const predictBtn = UI.createButton(ctx, {
                text: 'Predict',
                bgColor: '#B71C1C',
                textColor: COLORS.white,
                textSize: 16,
                onClick: function(v) {
                    Utils.log('[MainMenu] Predict button clicked');
                    TrackerMenu.handlePredict(globalThis._mq);
                }
            });

            if (!predictBtn) {
                Utils.log('[TrackerMenu.createMastermindSection] ERROR: predictBtn is null');

                return;
            }

            const btnLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, Utils.dpToPx(UI_CONFIG.buttonHeight));
            btnLP.setMargins(0, 0, 0, Utils.dpToPx(8));
            predictBtn.setLayoutParams(btnLP);
            section.addView(predictBtn);

            State.ui.predictButton = predictBtn;

            Utils.log('[TrackerMenu.createMastermindSection] Predict button added');

            const predictScroll = ScrollView.$new(ctx);
            predictScroll.setLayoutParams(LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, 0, 1.0));

            const resultText = TextView.$new(ctx);
            resultText.setTextColor(Color.parseColor(COLORS.lightBlue));
            resultText.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 12.0);
            resultText.setTextIsSelectable(true);
            resultText.setText(JavaString.$new('No prediction yet'));
            predictScroll.addView(resultText);
            section.addView(predictScroll);

            State.ui.predictResultTextView = resultText;

            Utils.log('[TrackerMenu.createMastermindSection] Result text view added');

            const errorText = TextView.$new(ctx);
            errorText.setTextColor(Color.parseColor(COLORS.red));
            errorText.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 11.0);
            errorText.setPadding(0, Utils.dpToPx(4), 0, 0);
            errorText.setLayoutParams(LayoutParams.$new(
                ViewGroupLP.MATCH_PARENT.value,
                ViewGroupLP.WRAP_CONTENT.value
            ));
            section.addView(errorText);

            State.ui.errorTextView = errorText;

            Utils.log('[TrackerMenu.createMastermindSection] Done');

            return section;
        } catch (e) {
            Utils.log('[TrackerMenu.createMastermindSection] ERROR: ' + e);

            return;
        }
    },

    createInvitesSection: function(ctx) {
        try {
            Utils.log('[TrackerMenu.createInvitesSection] START');

            const LinearLayout = Java.use('android.widget.LinearLayout');
            const TextView = Java.use('android.widget.TextView');
            const View = Java.use('android.view.View');
            const JavaString = Java.use('java.lang.String');
            const Color = Java.use('android.graphics.Color');
            const InputType = Java.use('android.text.InputType');
            const LayoutParams = Java.use('android.widget.LinearLayout$LayoutParams');
            const FrameLP = Java.use('android.widget.FrameLayout$LayoutParams');
            const ViewGroupLP = Java.use('android.view.ViewGroup$LayoutParams');
            const TypedValue = Java.use('android.util.TypedValue');
            const Typeface = Java.use('android.graphics.Typeface');
            const Gravity = Java.use('android.view.Gravity');

            const section = LinearLayout.$new(ctx);
            section.setOrientation(LinearLayout.VERTICAL.value);
            section.setLayoutParams(FrameLP.$new(
                ViewGroupLP.MATCH_PARENT.value,
                ViewGroupLP.MATCH_PARENT.value
            ));
            section.setVisibility(View.GONE.value);

            Utils.log('[TrackerMenu.createInvitesSection] Section container created (GONE)');

            const nameLabel = TextView.$new(ctx);
            nameLabel.setText(JavaString.$new('Player Name:'));
            nameLabel.setTextColor(Color.parseColor(COLORS.white));
            nameLabel.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 14.0);
            nameLabel.setTypeface(Typeface.DEFAULT_BOLD.value);

            const nameLabelLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value);
            nameLabelLP.setMargins(0, 0, 0, Utils.dpToPx(4));
            nameLabel.setLayoutParams(nameLabelLP);
            section.addView(nameLabel);

            State.ui.invitePlayerNameInput = UI.createTextField(ctx, {
                hint: 'Enter player name',
                textSize: 14,
                bgColor: COLORS.inputBg,
                textColor: COLORS.white,
                hintColor: COLORS.inputBorder
            });

            if (!State.ui.invitePlayerNameInput) {
                Utils.log('[TrackerMenu.createInvitesSection] ERROR: invitePlayerNameInput is null');

                return;
            }

            const nameInputLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value);
            nameInputLP.setMargins(0, 0, 0, Utils.dpToPx(12));

            State.ui.invitePlayerNameInput.setLayoutParams(nameInputLP);

            section.addView(State.ui.invitePlayerNameInput);

            Utils.log('[TrackerMenu.createInvitesSection] Name input added');

            const countLabel = TextView.$new(ctx);
            countLabel.setText(JavaString.$new('Count:'));
            countLabel.setTextColor(Color.parseColor(COLORS.white));
            countLabel.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 14.0);
            countLabel.setTypeface(Typeface.DEFAULT_BOLD.value);

            const countLabelLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value);
            countLabelLP.setMargins(0, 0, 0, Utils.dpToPx(4));
            countLabel.setLayoutParams(countLabelLP);
            section.addView(countLabel);

            State.ui.inviteCountInput = UI.createTextField(ctx, {
                hint: 'Enter count',
                text: '10',
                textSize: 14,
                bgColor: COLORS.inputBg,
                textColor: COLORS.white,
                hintColor: COLORS.inputBorder,
                inputType: InputType.TYPE_CLASS_NUMBER.value
            });

            if (!State.ui.inviteCountInput) {
                Utils.log('[TrackerMenu.createInvitesSection] ERROR: inviteCountInput is null');

                return;
            }

            const countInputLP = LayoutParams.$new(ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value);
            countInputLP.setMargins(0, 0, 0, Utils.dpToPx(12));

            State.ui.inviteCountInput.setLayoutParams(countInputLP);

            section.addView(State.ui.inviteCountInput);

            Utils.log('[TrackerMenu.createInvitesSection] Count input added');

            State.ui.inviteButton = UI.createButton(ctx, {
                text: 'Send Invites',
                bgColor: '#B71C1C',
                textColor: COLORS.white,
                textSize: 16,
                onClick: function(v) {
                    Utils.log('[MainMenu] Invite button clicked');

                    TrackerMenu.handleInvite();
                }
            });

            if (!State.ui.inviteButton) {
                Utils.log('[TrackerMenu.createInvitesSection] ERROR: inviteButton is null');

                return;
            }

            const inviteBtnLP = LayoutParams.$new(
                ViewGroupLP.MATCH_PARENT.value, Utils.dpToPx(UI_CONFIG.buttonHeight)
            );
            inviteBtnLP.setMargins(0, 0, 0, Utils.dpToPx(8));

            State.ui.inviteButton.setLayoutParams(inviteBtnLP);

            section.addView(State.ui.inviteButton);

            Utils.log('[TrackerMenu.createInvitesSection] Invite button added');

            State.ui.inviteStatusTextView = TextView.$new(ctx);
            State.ui.inviteStatusTextView.setText(JavaString.$new('Ready to send'));
            State.ui.inviteStatusTextView.setTextColor(Color.parseColor(COLORS.lightGray));
            State.ui.inviteStatusTextView.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, 12.0);
            State.ui.inviteStatusTextView.setGravity(Gravity.CENTER.value);
            State.ui.inviteStatusTextView.setLayoutParams(LayoutParams.$new(
                ViewGroupLP.MATCH_PARENT.value, ViewGroupLP.WRAP_CONTENT.value
            ));

            section.addView(State.ui.inviteStatusTextView);

            Utils.log('[TrackerMenu.createInvitesSection] Done');

            return section;
        } catch (e) {
            Utils.log('[TrackerMenu.createInvitesSection] ERROR: ' + e);

            return;
        }
    },

    switchSection: function() {
        try {
            Utils.log('[TrackerMenu.switchSection] Switching to: ' + State.game.currentSection);

            const View = Java.use('android.view.View');
            const Color = Java.use('android.graphics.Color');

            const sections = {
                players: State.ui.playersSectionView,
                messages: State.ui.messagesSectionView,
                mastermind: State.ui.mastermindSectionView,
                invites: State.ui.invitesSectionView
            };

            const buttons = {
                players: State.ui.playersSectionButton,
                messages: State.ui.messagesSectionButton,
                mastermind: State.ui.mastermindSectionButton,
                invites: State.ui.invitesSectionButton
            };

            const cur = State.game.currentSection;

            for (const name in sections) {
                const sectionView = sections[name];

                if (!sectionView) {
                    Utils.log('[TrackerMenu.switchSection] WARN: section view null for: ' + name);

                    continue;
                }

                const vis = (name === cur) ? View.VISIBLE.value : View.GONE.value;

                sectionView.setVisibility(vis);

                Utils.log('[TrackerMenu.switchSection] Section "' + name + '" => ' +
                    (name === cur ? 'VISIBLE' : 'GONE'));
            }

            for (const name in buttons) {
                const btn = buttons[name];
                const active = (name === cur);

                if (!btn) {
                    Utils.log('[TrackerMenu.switchSection] WARN: button null for: ' + name);

                    continue;
                }

                Java.scheduleOnMainThread(function() {
                    try {
                        btn.setBackgroundColor(Color.parseColor(active ? '#B71C1C' : COLORS.darkGray));
                        btn.setTextColor(Color.parseColor(active ? COLORS.white : COLORS.lightGray));
                    } catch (e) {
                        Utils.log('[TrackerMenu.switchSection] btn update ERROR: ' + e);
                    }
                });
            }

            Utils.log('[TrackerMenu.switchSection] Done');
        } catch (e) {
            Utils.log('[TrackerMenu.switchSection] ERROR: ' + e);
        }
    },

    handlePredict: function(messageQueue) {
        try {
            Utils.log('[TrackerMenu.handlePredict] START');

            const EditText = Java.use('android.widget.EditText');
            const Button = Java.use('android.widget.Button');
            const JavaString = Java.use('java.lang.String');

            if (!State.ui.commandInput || !State.ui.predictButton) {
                Utils.log('[TrackerMenu.handlePredict] ERROR: commandInput or predictButton is null');

                return;
            }

            const castedInput = Java.cast(State.ui.commandInput, EditText);

            const CharSeq1 = Java.use('java.lang.CharSequence');

            const command = Java.cast(castedInput.getText(), CharSeq1).toString().trim();

            if (!command) {
                Utils.log('[TrackerMenu.handlePredict] WARN: empty command, ignoring');

                return;
            }

            Utils.log('[TrackerMenu.handlePredict] Command: "' + command + '"');

            const castedBtn = Java.cast(State.ui.predictButton, Button);
            castedBtn.setEnabled(false);
            castedBtn.setText(JavaString.$new('Processing...'));

            messageQueue.push(JSON.stringify({
                type: 'predict_command',
                command: command
            }));

            Utils.log('[TrackerMenu.handlePredict] Predict request queued');
        } catch (e) {
            Utils.log('[TrackerMenu.handlePredict] ERROR: ' + e);
        }
    },

    handleInvite: function() {
        try {
            Utils.log('[TrackerMenu.handleInvite] START');

            const EditText = Java.use('android.widget.EditText');

            if (!State.ui.invitePlayerNameInput || !State.ui.inviteCountInput) {
                Utils.log('[TrackerMenu.handleInvite] ERROR: invite inputs are null');

                return;
            }

            const castedName = Java.cast(State.ui.invitePlayerNameInput, EditText);
            const castedCount = Java.cast(State.ui.inviteCountInput, EditText);

            const CharSeq2 = Java.use('java.lang.CharSequence');

            const playerName = Java.cast(castedName.getText(), CharSeq2).toString().trim();
            const countStr = Java.cast(castedCount.getText(), CharSeq2).toString().trim();

            Utils.log('[TrackerMenu.handleInvite] playerName="' + playerName +
                '" countStr="' + countStr + '"');

            if (!playerName) {
                Utils.log('[TrackerMenu.handleInvite] WARN: empty player name');

                return;
            }

            const count = parseInt(countStr) || 1;

            const found = Tracker.findPlayerByUsername(playerName);

            if (!found) {
                Utils.log('[TrackerMenu.handleInvite] Player not found in local state: "' + playerName + '"');

                if (State.ui.inviteStatusTextView) {
                    Java.scheduleOnMainThread(function() {
                        try {
                            const JavaString = Java.use('java.lang.String');
                            const TextView = Java.use('android.widget.TextView');
                            Java.cast(State.ui.inviteStatusTextView, TextView)
                                .setText.overload('java.lang.CharSequence')
                                .call(State.ui.inviteStatusTextView,
                                    JavaString.$new('Player not found: ' + playerName));
                        } catch (e) {
                            Utils.log('[TrackerMenu.handleInvite] Status update error: ' + e);
                        }
                    });
                }

                return;
            }

            const targetId = String(found.id);

            Utils.log('[TrackerMenu.handleInvite] Found player: id=' + targetId +
                ' username=' + found.username + ' count=' + count);

            if (count === 1) Invites.sendSingle(targetId);

            else Invites.sendMultiple(targetId, count, 500);
        } catch (e) {
            Utils.log('[TrackerMenu.handleInvite] ERROR: ' + e);
        }
    },

    show: function() {
        try {
            Utils.log('[TrackerMenu.show] Showing tracker menu');

            const View = Java.use('android.view.View');

            State.menus.tracker.setVisibility(View.VISIBLE.value);
            State.visibility.tracker = true;

            Utils.log('[TrackerMenu.show] Tracker menu is now VISIBLE');
        } catch (e) {
            Utils.log('[TrackerMenu.show] ERROR: ' + e);
        }
    },

    hide: function() {
        try {
            if (!State.menus.tracker) {
                Utils.log('[TrackerMenu.hide] SKIP: menu not created yet');

                return;
            }

            Utils.log('[TrackerMenu.hide] Hiding tracker menu');

            const View = Java.use('android.view.View');

            State.menus.tracker.setVisibility(View.GONE.value);
            State.visibility.tracker = false;

            Utils.log('[TrackerMenu.hide] Tracker menu is now GONE');
        } catch (e) {
            Utils.log('[TrackerMenu.hide] ERROR: ' + e);
        }
    }
};
