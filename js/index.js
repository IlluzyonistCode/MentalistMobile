import { State } from './state.js';
import { Utils } from './utils/logger.js';
import { Hooks } from './hooks/hooks.js';
import { Game } from './game/game.js';
import { Invites } from './modules/inviter.js';
import { UI } from './ui/ui.js';
import { Buttons } from './ui/buttons.js';
import { TrackerMenu } from './ui/menus/trackerMenu.js';
import { InviterMenu } from './ui/menus/inviterMenu.js';
import { BoosterMenu } from './ui/menus/boosterMenu.js';
import { SpinnerMenu } from './ui/menus/spinnerMenu.js';
import { MenuController } from './ui/menuController.js';
import { UI_CONFIG, POSITIONS } from './constants.js';

function waitForJava() {
    return new Promise(function(resolve) {
        const checkJava = setInterval(function() {
            if (typeof Java !== 'undefined' && Java.available) {
                clearInterval(checkJava);

                resolve();
            }
        }, 100);
    });
}

const Init = {
    loadJavaClasses: function() {
        try {
            Utils.log('[Init.loadJavaClasses] START');

            const ActivityThread = Java.use('android.app.ActivityThread');

            Utils.log('[Init.loadJavaClasses] ActivityThread acquired');

            const app = ActivityThread.currentApplication();

            if (!app) {
                Utils.log('[Init.loadJavaClasses] FATAL: currentApplication() returned null');

                return;
            }

            Utils.log('[Init.loadJavaClasses] Application acquired');

            const context = app.getApplicationContext();

            if (!context) {
                Utils.log('[Init.loadJavaClasses] FATAL: getApplicationContext() returned null');

                return;
            }

            State.context = context;

            Utils.log('[Init.loadJavaClasses] Context stored in State');

            const Context = Java.use('android.content.Context');
            const WindowManagerImpl = Java.use('android.view.WindowManagerImpl');

            Utils.log('[Init.loadJavaClasses] Getting WINDOW_SERVICE');

            const wm = context.getSystemService(Context.WINDOW_SERVICE.value);

            if (!wm) {
                Utils.log('[Init.loadJavaClasses] FATAL: getSystemService(WINDOW_SERVICE) returned null');

                return;
            }

            State.windowManager = Java.cast(wm, WindowManagerImpl);

            Utils.log('[Init.loadJavaClasses] WindowManager cast to WindowManagerImpl: OK');
            Utils.log('[Init.loadJavaClasses] Done');
        } catch (e) {
            Utils.log('[Init.loadJavaClasses] ERROR: ' + e);
        }
    },

    setupAccessibilityHook: function() {
        try {
            Utils.log('[RPC.accessHook] START');

            const serviceClassName = 'com.mentalist.mobile.MentalistAccessibilityService';
            const ACTION = 'com.mentalist.ACCESSIBILITY_EVENT';

            // Hook onAccessibilityEvent directly
            try {
                const ServiceClass = Java.use(serviceClassName);
                ServiceClass.onAccessibilityEvent.implementation = function(event) {
                    if (!State.accessibilityInstance) {
                        State.accessibilityInstance = this;
                        Utils.log('[RPC.accessHook] Instance captured via onAccessibilityEvent!');
                    }
                    this.onAccessibilityEvent(event);
                };
                Utils.log('[RPC.accessHook] onAccessibilityEvent hooked OK');
            } catch(e) {
                Utils.log('[RPC.accessHook] onAccessibilityEvent hook error: ' + e);
            }

            // Hook ContextImpl.sendBroadcast - this is the ACTUAL implementation
            // Application/ContextWrapper both delegate to ContextImpl
            try {
                const ContextImpl = Java.use('android.app.ContextImpl');
                ContextImpl.sendBroadcast.overload('android.content.Intent').implementation = function(intent) {
                    try {
                        const action = intent.getAction();
                        if (action === ACTION && !State.accessibilityInstance) {
                            Utils.log('[RPC.accessHook] ContextImpl caught broadcast! Doing Java.choose...');
                            Java.choose(serviceClassName, {
                                onMatch: function(inst) {
                                    if (!State.accessibilityInstance) {
                                        State.accessibilityInstance = inst;
                                        Utils.log('[RPC.accessHook] Instance captured via ContextImpl!');
                                    }
                                },
                                onComplete: function() {}
                            });
                        }
                    } catch(e) {}
                    return this.sendBroadcast(intent);
                };
                Utils.log('[RPC.accessHook] ContextImpl.sendBroadcast hooked OK');
            } catch(e) {
                Utils.log('[RPC.accessHook] ContextImpl hook error: ' + e);
            }

            Utils.log('[RPC.accessHook] DONE');
        } catch (e) {
            Utils.log('[RPC.accessHook] FATAL: ' + e);
        }
    },

    setupUI: function() {
        try {
            Utils.log('[Init.setupUI] Scheduling UI creation on main thread');

            Java.scheduleOnMainThread(function() {
                try {
                    Utils.log('[Init.setupUI] START on main thread');

                    if (!State.context) {
                        Utils.log('[Init.setupUI] FATAL: context is null, aborting UI setup');

                        return;
                    }

                    if (!State.windowManager) {
                        Utils.log('[Init.setupUI] FATAL: windowManager is null, aborting UI setup');

                        return;
                    }

                    const BuildVersion = Java.use('android.os.Build$VERSION');
                    const sdkInt = BuildVersion.SDK_INT.value;

                    Utils.log('[Init.setupUI] Android SDK: ' + sdkInt);

                    const WindowManagerLP = Java.use('android.view.WindowManager$LayoutParams');
                    const layoutType = sdkInt >= 26 ?
                        WindowManagerLP.TYPE_APPLICATION_OVERLAY.value :
                        WindowManagerLP.TYPE_PHONE.value;

                    Utils.log('[Init.setupUI] Layout type: ' + layoutType);

                    const ViewGroupLP = Java.use('android.view.ViewGroup$LayoutParams');
                    const Gravity = Java.use('android.view.Gravity');
                    const View = Java.use('android.view.View');
                    const JavaInteger = Java.use('java.lang.Integer');

                    const iconSize = Utils.dpToPx(UI_CONFIG.iconSize);

                    Utils.log('[Init.setupUI] Icon size: ' + iconSize + 'px');

                    Utils.log('[Init.setupUI] Creating button panel');

                    const LinearLayout = Java.use('android.widget.LinearLayout');
                    const GradientDrawable = Java.use('android.graphics.drawable.GradientDrawable');
                    const JavaFloat = Java.use('java.lang.Float');
                    const Color = Java.use('android.graphics.Color');
                    const PanelLP = Java.use('android.widget.LinearLayout$LayoutParams');

                    const panel = LinearLayout.$new(State.context);
                    panel.setOrientation(LinearLayout.VERTICAL.value);
                    panel.setPadding(
                        Utils.dpToPx(8), Utils.dpToPx(8),
                        Utils.dpToPx(8), Utils.dpToPx(8)
                    );

                    const GradientOrientation = Java.use('android.graphics.drawable.GradientDrawable$Orientation');
                    const borderBg = GradientDrawable.$new(
                        GradientOrientation.TL_BR.value,
                        Java.array('int', [Color.parseColor('#FF4444'), Color.parseColor('#7B0000')])
                    );
                    borderBg.setShape(GradientDrawable.RECTANGLE.value);
                    borderBg.setCornerRadius(JavaFloat.parseFloat('24.0'));

                    const innerBg = GradientDrawable.$new();
                    innerBg.setShape(GradientDrawable.RECTANGLE.value);
                    innerBg.setColor(Color.parseColor('#E8000000'));
                    innerBg.setCornerRadius(JavaFloat.parseFloat('22.0'));

                    const LayerDrawable = Java.use('android.graphics.drawable.LayerDrawable');
                    const layers = Java.array('android.graphics.drawable.Drawable', [borderBg, innerBg]);
                    const layered = LayerDrawable.$new(layers);
                    layered.setLayerInset(1,
                        Utils.dpToPx(2), Utils.dpToPx(2), Utils.dpToPx(2), Utils.dpToPx(2)
                    );
                    panel.setBackground(layered);

                    const redButton = Buttons.createRed(State.context);
                    const greenButton = Buttons.createGreen(State.context);
                    const blueButton = Buttons.createBlue(State.context);
                    const yellowButton = Buttons.createYellow(State.context);

                    if (redButton) {
                        const lp = PanelLP.$new(iconSize, iconSize);
                        lp.setMargins(0, 0, 0, Utils.dpToPx(8));
                        redButton.setLayoutParams(lp);
                        panel.addView(redButton);

                        Utils.log('[Init.setupUI] Red button added to panel');
                    }

                    if (greenButton) {
                        const lp = PanelLP.$new(iconSize, iconSize);
                        lp.setMargins(0, 0, 0, Utils.dpToPx(8));
                        greenButton.setLayoutParams(lp);
                        panel.addView(greenButton);

                        Utils.log('[Init.setupUI] Green button added to panel');
                    }

                    if (blueButton) {
                        const lp = PanelLP.$new(iconSize, iconSize);
                        lp.setMargins(0, 0, 0, Utils.dpToPx(8));
                        blueButton.setLayoutParams(lp);
                        panel.addView(blueButton);

                        Utils.log('[Init.setupUI] Blue button added to panel');
                    }

                    if (yellowButton) {
                        const lp = PanelLP.$new(iconSize, iconSize);
                        yellowButton.setLayoutParams(lp);
                        panel.addView(yellowButton);

                        Utils.log('[Init.setupUI] Yellow button added to panel');
                    }

                    const MotionEvent = Java.use('android.view.MotionEvent');

                    State.buttonParams.panel = WindowManagerLP.$new(
                        ViewGroupLP.WRAP_CONTENT.value,
                        ViewGroupLP.WRAP_CONTENT.value,
                        layoutType,
                        WindowManagerLP.FLAG_NOT_FOCUSABLE.value,
                        JavaInteger.parseInt('1', 16)
                    );
                    State.buttonParams.panel.gravity = Gravity.TOP.value | Gravity.RIGHT.value;
                    State.buttonParams.panel.x.value = 0;
                    State.buttonParams.panel.y.value = 0;

                    const PanelTouchListener = Java.registerClass({
                        name: 'com.mentalist.PanelTouchListener',
                        implements: [Java.use('android.view.View$OnTouchListener')],
                        methods: {
                            onTouch: function(v, event) {
                                try {
                                    const action = event.getAction();

                                    if (action === MotionEvent.ACTION_DOWN.value) {
                                        State.drag = {
                                            startX: event.getRawX(),
                                            startY: event.getRawY(),
                                            origX: State.buttonParams.panel.x.value,
                                            origY: State.buttonParams.panel.y.value,
                                            moved: false
                                        };

                                        return true;
                                    } else if (action === MotionEvent.ACTION_MOVE.value && State.drag) {
                                        const dx = Math.abs(event.getRawX() - State.drag.startX);
                                        const dy = Math.abs(event.getRawY() - State.drag.startY);

                                        if (dx > 8 || dy > 8) {
                                            State.drag.moved = true;
                                            State.buttonParams.panel.x.value = Math.round(
                                                State.drag.origX + event.getRawX() - State.drag.startX
                                            );
                                            State.buttonParams.panel.y.value = Math.round(
                                                State.drag.origY + event.getRawY() - State.drag.startY
                                            );
                                            State.windowManager.updateViewLayout(
                                                Java.cast(panel, View),
                                                Java.cast(State.buttonParams.panel, ViewGroupLP)
                                            );

                                            return true;
                                        }

                                        return false;
                                    } else if (action === MotionEvent.ACTION_UP.value) {
                                        const wasMoved = State.drag && State.drag.moved;

                                        State.drag = null;

                                        if (!wasMoved) {
                                            const y = event.getY();
                                            const size = iconSize + Utils.dpToPx(6);
                                            const idx = Math.floor(y / size);

                                            if (idx === 0) MenuController.toggleOne('tracker');
                                            else if (idx === 1) MenuController.toggleOne('booster');
                                            else if (idx === 2) MenuController.toggleOne('spinner');
                                            else if (idx === 3) MenuController.toggleOne('inviter');
                                        }

                                        return true;
                                    }
                                } catch (e) {
                                    Utils.log('[PanelTouch] ERROR: ' + e);
                                }

                                return false;
                            }
                        }
                    });

                    panel.setOnTouchListener(PanelTouchListener.$new());

                    Utils.log('[Init.setupUI] All buttons processed');

                    const menuDefs = [
                        { key: 'tracker', factory: function() { return TrackerMenu.create(State.context); } },
                        { key: 'booster', factory: function() { return BoosterMenu.create(State.context); } },
                        { key: 'inviter', factory: function() { return InviterMenu.create(State.context); } },
                        { key: 'spinner', factory: function() { return SpinnerMenu.create(State.context); } }
                    ];

                    menuDefs.forEach(function(def) {
                        Utils.log('[Init.setupUI] Creating ' + def.key + ' menu');

                        const menuView = def.factory();

                        if (menuView) {
                            Utils.log('[Init.setupUI] ' + def.key + ' menu created, building WM params');

                            State.menuParams[def.key] = WindowManagerLP.$new(
                                WindowManagerLP.MATCH_PARENT.value,
                                WindowManagerLP.WRAP_CONTENT.value,
                                layoutType,
                                WindowManagerLP.FLAG_NOT_TOUCH_MODAL.value,
                                JavaInteger.parseInt('1F', 16)
                            );
                            State.menuParams[def.key].gravity =
                                Gravity.TOP.value | Gravity.CENTER_HORIZONTAL.value;
                            State.menuParams[def.key].x = 0;
                            State.menuParams[def.key].y = Utils.dpToPx(POSITIONS.menuY);

                            State.windowManager.addView(
                                Java.cast(menuView, View),
                                Java.cast(State.menuParams[def.key], ViewGroupLP)
                            );

                            Java.cast(menuView, View).setVisibility(View.GONE.value);

                            State.visibility[def.key] = false;

                            Utils.log('[Init.setupUI] ' + def.key +
                                ' menu added to WindowManager (GONE)');
                        } else
                            Utils.log('[Init.setupUI] WARN: ' + def.key +
                                ' menu creation failed, skipping');
                    });

                    State.windowManager.addView(
                        Java.cast(panel, View),
                        Java.cast(State.buttonParams.panel, ViewGroupLP)
                    );

                    Utils.log('[Init.setupUI] Button panel added to WindowManager (on top)');

                    Utils.log('[Init.setupUI] UI setup complete');
                } catch (e) {
                    Utils.log('[Init.setupUI] ERROR on main thread: ' + e);
                    Utils.log('[Init.setupUI] Stack: ' + (e.stack || 'no stack'));
                }
            });
        } catch (e) {
            Utils.log('[Init.setupUI] ERROR scheduling main thread: ' + e);
        }
    },

    setupRPC: function() {
        try {
            Utils.log('[Init.setupRPC] Registering RPC exports');

            rpc.exports.setviewdata = function(jsonStr) {
                try {
                    Utils.log('[RPC.setviewdata] Called, payload length: ' +
                        (jsonStr ? jsonStr.length : 0));

                    if (!jsonStr || typeof jsonStr !== 'string') {
                        Utils.log('[RPC.setviewdata] WARN: invalid payload');

                        return;
                    }

                    const data = Utils.safeJsonParse(jsonStr);

                    if (!data) {
                        Utils.log('[RPC.setviewdata] WARN: JSON parse failed');

                        return;
                    }

                    State.game.latestRenderData = data;

                    if (data.players && Array.isArray(data.players)) {
                        Utils.log('[RPC.setviewdata] Upserting ' +
                            data.players.length + ' players from render data');

                        data.players.forEach(function(p) { Game.upsertPlayer(p); });
                    }

                    Game.updateUI();

                    Utils.log('[RPC.setviewdata] Done');
                } catch (e) {
                    Utils.log('[RPC.setviewdata] ERROR: ' + e);
                }
            };

            rpc.exports.seterror = function(errorStr) {
                try {
                    Utils.log('[RPC.seterror] Called: "' + errorStr + '"');

                    if (!State.ui.errorTextView || !errorStr) {
                        Utils.log('[RPC.seterror] SKIP: errorTextView null or errorStr empty');

                        return;
                    }

                    Java.scheduleOnMainThread(function() {
                        try {
                            const JavaString = Java.use('java.lang.String');
                            const TextView = Java.use('android.widget.TextView');

                            const tv = Java.cast(State.ui.errorTextView, TextView);

                            tv.setText.overload('java.lang.CharSequence').call(
                                tv, JavaString.$new(errorStr)
                            );

                            Utils.log('[RPC.seterror] Error text set');
                        } catch (e) {
                            Utils.log('[RPC.seterror] UI update ERROR: ' + e);
                        }
                    });
                } catch (e) {
                    Utils.log('[RPC.seterror] ERROR: ' + e);
                }
            };

            rpc.exports.setpredictresult = function(resultStr) {
                try {
                    Utils.log('[RPC.setpredictresult] Called, length: ' +
                        (resultStr ? resultStr.length : 0));

                    if (!State.ui.predictResultTextView || !resultStr) {
                        Utils.log('[RPC.setpredictresult] SKIP: view null or result empty');

                        return;
                    }

                    Java.scheduleOnMainThread(function() {
                        try {
                            const JavaString = Java.use('java.lang.String');
                            const TextView = Java.use('android.widget.TextView');
                            const Button = Java.use('android.widget.Button');

                            const resultView = Java.cast(State.ui.predictResultTextView, TextView);
                            resultView.setText.overload('java.lang.CharSequence').call(
                                resultView, JavaString.$new(resultStr)
                            );

                            Utils.log('[RPC.setpredictresult] Result text updated');

                            if (State.ui.predictButton) {
                                const btn = Java.cast(State.ui.predictButton, Button);
                                btn.setEnabled(true);
                                btn.setText(JavaString.$new('Predict'));

                                Utils.log('[RPC.setpredictresult] Predict button re-enabled');
                            }
                        } catch (e) {
                            Utils.log('[RPC.setpredictresult] UI update ERROR: ' + e);
                        }
                    });
                } catch (e) {
                    Utils.log('[RPC.setpredictresult] ERROR: ' + e);
                }
            };

            rpc.exports.toggletrackermenu = function() {
                try {
                    Utils.log('[RPC.toggletrackermenu] Called');

                    MenuController.toggleOne('tracker');

                    Utils.log('[RPC.toggletrackermenu] Visibility now: ' + State.visibility.tracker);

                    return State.visibility.tracker;
                } catch (e) {
                    Utils.log('[RPC.toggletrackermenu] ERROR: ' + e);

                    return false;
                }
            };

            rpc.exports.toggleboostermenu = function() {
                try {
                    Utils.log('[RPC.toggleboostermenu] Called');

                    MenuController.toggleOne('booster');

                    Utils.log('[RPC.toggleboostermenu] Visibility now: ' + State.visibility.booster);

                    return State.visibility.booster;
                } catch (e) {
                    Utils.log('[RPC.toggleboostermenu] ERROR: ' + e);

                    return false;
                }
            };

            rpc.exports.toggleinvitermenu = function() {
                try {
                    Utils.log('[RPC.toggleinvitermenu] Called');

                    MenuController.toggleOne('inviter');

                    Utils.log('[RPC.toggleinvitermenu] Visibility now: ' + State.visibility.inviter);

                    return State.visibility.inviter;
                } catch (e) {
                    Utils.log('[RPC.toggleinvitermenu] ERROR: ' + e);

                    return false;
                }
            };

            rpc.exports.togglespinnermenu = function() {
                try {
                    Utils.log('[RPC.togglespinnermenu] Called');

                    MenuController.toggleOne('spinner');

                    Utils.log('[RPC.togglespinnermenu] Visibility now: ' + State.visibility.spinner);

                    return State.visibility.spinner;
                } catch (e) {
                    Utils.log('[RPC.togglespinnermenu] ERROR: ' + e);

                    return false;
                }
            };

            rpc.exports.sendinvite = function(targetPlayerId) {
                try {
                    Utils.log('[RPC.sendinvite] Called for: ' + targetPlayerId);

                    const result = Invites.sendSingle(String(targetPlayerId));

                    Utils.log('[RPC.sendinvite] Result: ' + result);

                    return result;
                } catch (e) {
                    Utils.log('[RPC.sendinvite] ERROR: ' + e);

                    return false;
                }
            };

            rpc.exports.setbotapikey = function(apiKey) {
                try {
                    if (apiKey && typeof apiKey === 'string') {
                        State.network.botApiKey = apiKey;

                        Utils.log('[RPC.setbotapikey] Bot API key set: ***' +
                            apiKey.slice(-8));
                    }
                } catch (e) {
                    Utils.log('[RPC.setbotapikey] ERROR: ' + e);
                }
            };

            Utils.log('[Init.setupRPC] Registering helper functions...');

            const _sleep = function(ms) {
                Java.use('java.lang.Thread').sleep(ms);
            };

            // Traverse View tree (works in-process, no AccessibilityService needed)
            const findViewByText = function(view, pattern) {
                try {
                    if (!view) return null;

                    // Check if it's a TextView with matching text
                    try {
                        const text = view.getText();
                        if (text && pattern.test(text.toString())) {
                            return view;
                        }
                    } catch(e) {}

                    // Check contentDescription
                    try {
                        const desc = view.getContentDescription();
                        if (desc && pattern.test(desc.toString())) {
                            return view;
                        }
                    } catch(e) {}

                    // Recurse into children (ViewGroup)
                    try {
                        const childCount = view.getChildCount();
                        for (let i = 0; i < childCount; i++) {
                            try {
                                const child = view.getChildAt(i);
                                const result = findViewByText(child, pattern);
                                if (result) return result;
                            } catch(e) {}
                        }
                    } catch(e) {}

                    return null;
                } catch (e) {
                    Utils.log('[findViewByText] ERROR: ' + e);
                    return null;
                }
            };

            // Helper functions for AccessibilityService
            const findNodeByText = function(node, pattern) {
                if (!node) return null;
                
                try {
                    const text = node.getText();
                    
                    if (text && pattern.test(text.toString())) {
                        if (node.isClickable()) {
                            return node;
                        }
                        
                        let parent = node.getParent();
                        
                        while (parent) {
                            if (parent.isClickable()) {
                                return parent;
                            }
                            
                            parent = parent.getParent();
                        }
                        
                        return node;
                    }
                    
                    const childCount = node.getChildCount();
                    
                    for (let i = 0; i < childCount; i++) {
                        const child = node.getChildAt(i);
                        
                        if (child) {
                            const result = findNodeByText(child, pattern);
                            
                            if (result) {
                                return result;
                            }
                            
                            child.recycle();
                        }
                    }
                } catch (e) {
                    Utils.log('[findNodeByText] ERROR: ' + e);
                }
                
                return null;
            };

            const printNodeTree = function(node, depth) {
                if (!node) return;
                
                try {
                    const indent = '  '.repeat(depth);
                    const text = node.getText();
                    const className = node.getClassName();
                    const clickable = node.isClickable();
                    const Rect = Java.use('android.graphics.Rect');
                    const rect = Rect.$new();
                    node.getBoundsInScreen(rect);
                    
                    let info = indent + className;
                    
                    if (text) {
                        info += ' [' + text + ']';
                    }
                    
                    if (clickable) {
                        info += ' CLICKABLE';
                    }
                    
                    info += ' (' + rect.left.value + ',' + rect.top.value + '-' + rect.right.value + ',' + rect.bottom.value + ')';
                    
                    Utils.log(info);
                    
                    const childCount = node.getChildCount();
                    
                    for (let i = 0; i < childCount; i++) {
                        const child = node.getChildAt(i);
                        
                        if (child) {
                            printNodeTree(child, depth + 1);
                            child.recycle();
                        }
                    }
                } catch (e) {
                    Utils.log('printNodeTree ERROR: ' + e);
                }
            };

            Utils.log('[Init.setupRPC] Registering findAndClickByText...');

            const _findAndClickByText = function(regex, timeout) {
                timeout = timeout || 5000;
                try {
                    Utils.log('[RPC.findAndClickByText] Searching for: ' + regex);
                    const pattern = new RegExp(regex, 'i');
                    const startTime = Date.now();
                    let found = false;

                    while (Date.now() - startTime < timeout && !found) {
                        // If still no instance — try Java.choose directly
                        if (!State.accessibilityInstance) {
                            try {
                                Java.perform(function() {
                                    Java.choose('com.mentalist.mobile.MentalistAccessibilityService', {
                                        onMatch: function(inst) {
                                            if (!State.accessibilityInstance) {
                                                State.accessibilityInstance = inst;
                                                Utils.log('[RPC.findAndClickByText] Got instance via direct choose!');
                                            }
                                        },
                                        onComplete: function() {}
                                    });
                                });
                            } catch(e) {}
                        }
                        try {
                            Java.perform(function() {
                                const instance = State.accessibilityInstance;
                                if (!instance) {
                                    Utils.log('[RPC.findAndClickByText] No instance yet...');
                                    return;
                                }
                                let rootNode = null;
                                try { rootNode = instance.getRootInActiveWindow(); } catch(e) {}
                                if (!rootNode) {
                                    try {
                                        const wins = instance.getWindows();
                                        for (let w = 0; w < wins.size(); w++) {
                                            const r = wins.get(w).getRoot();
                                            if (r) { rootNode = r; break; }
                                        }
                                    } catch(e) {}
                                }
                                if (!rootNode) {
                                    Utils.log('[RPC.findAndClickByText] No root node');
                                    return;
                                }
                                try { Utils.log('[RPC.findAndClickByText] Root pkg: ' + rootNode.getPackageName()); } catch(e) {}
                                const targetNode = findNodeByText(rootNode, pattern);
                                if (targetNode) {
                                    Utils.log('[RPC.findAndClickByText] Found: ' + targetNode.getText());
                                    if (targetNode.performAction(16)) {
                                        found = true;
                                        Utils.log('[RPC.findAndClickByText] Clicked!');
                                    } else {
                                        try {
                                            const p = targetNode.getParent();
                                            if (p && p.performAction(16)) { found = true; Utils.log('[RPC.findAndClickByText] Parent clicked!'); }
                                        } catch(pe) {}
                                    }
                                }
                                rootNode.recycle();
                            });
                        } catch(e) {
                            Utils.log('[RPC.findAndClickByText] Error: ' + e);
                        }
                        if (!found) _sleep(500);
                    }

                    if (!found) Utils.log('[RPC.findAndClickByText] Not found after ' + timeout + 'ms');
                    return found;
                } catch(e) {
                    Utils.log('[RPC.findAndClickByText] ERROR: ' + e);
                    return false;
                }
            };

            // Expose to Python via rpc.exports AND store direct reference in State for internal use
            rpc.exports.findAndClickByText = _findAndClickByText;
            State.accessibility = {
                findAndClickByText: _findAndClickByText
            };
            Utils.log('[Init.setupRPC] State.accessibility set, typeof findAndClickByText: ' + typeof _findAndClickByText);
            
            Utils.log('[Init.setupRPC] Registering debugPrintUITree...');
            
            rpc.exports.debugPrintUITree = function() {
                try {
                    Utils.log('[RPC.debugPrintUITree] Printing UI tree...');
                    
                    const serviceClassName = 'com.mentalist.mobile.MentalistAccessibilityService';
                    
                    Java.choose(serviceClassName, {
                        onMatch: function(instance) {
                            try {
                                const rootNode = instance.getRootInActiveWindow();
                                
                                if (!rootNode) {
                                    Utils.log('[RPC.debugPrintUITree] No root node');
                                    return;
                                }
                                
                                Utils.log('[RPC.debugPrintUITree] === UI TREE START ===');
                                printNodeTree(rootNode, 0);
                                Utils.log('[RPC.debugPrintUITree] === UI TREE END ===');
                                
                                rootNode.recycle();
                                
                            } catch (e) {
                                Utils.log('[RPC.debugPrintUITree] Error: ' + e);
                            }
                        },
                        onComplete: function() {}
                    });
                    
                    return true;
                } catch (e) {
                    Utils.log('[RPC.debugPrintUITree] ERROR: ' + e);
                    return false;
                }
            };

            Utils.log('[Init.setupRPC] Registering accessibilityClick...');

            rpc.exports.accessibilityClick = function(x, y) {
                try {
                    Utils.log('[RPC.accessibilityClick] Click at ' + x + ',' + y);
                    
                    Java.scheduleOnMainThread(function() {
                        try {
                            const GestureDescription = Java.use('android.accessibilityservice.GestureDescription');
                            const Path = Java.use('android.graphics.Path');
                            const GestureDescriptionBuilder = GestureDescription.Builder.$new();
                            const StrokeDescription = Java.use('android.accessibilityservice.GestureDescription$StrokeDescription');
                            
                            const path = Path.$new();
                            path.moveTo(x, y);
                            
                            const stroke = StrokeDescription.$new(path, 0, 100);
                            GestureDescriptionBuilder.addStroke(stroke);
                            
                            const gesture = GestureDescriptionBuilder.build();
                            
                            const serviceClassName = 'com.mentalist.mobile.MentalistAccessibilityService';
                            const AccessibilityService = Java.use(serviceClassName);
                            
                            Java.choose(serviceClassName, {
                                onMatch: function(instance) {
                                    instance.dispatchGesture(gesture, null, null);
                                    Utils.log('[RPC.accessibilityClick] Gesture dispatched');
                                },
                                onComplete: function() {
                                    Utils.log('[RPC.accessibilityClick] Search complete');
                                }
                            });
                            
                        } catch (e) {
                            Utils.log('[RPC.accessibilityClick] Java ERROR: ' + e);
                        }
                    });
                    
                    return true;
                } catch (e) {
                    Utils.log('[RPC.accessibilityClick] ERROR: ' + e);
                    return false;
                }
            };

            Utils.log('[Init.setupRPC] RPC exports registered: ' +
                Object.keys(rpc.exports).join(', '));
        } catch (e) {
            Utils.log('[Init.setupRPC] ERROR: ' + e);
        }
    }
};

Utils.log('[Agent] Script loaded at ' + new Date().toISOString());
Utils.log('[Agent] messageQueue ready: ' + (globalThis._mq ? 'yes' : 'NO - FATAL'));
Utils.log('[Agent] Waiting for Java runtime...');

waitForJava().then(function() {
    Utils.log('[Agent] Java runtime ready, entering Java.perform');

    try {
        Java.perform(function() {
            try {
                Utils.log('[Agent] Inside Java.perform');
                Utils.log('[Agent] Step 1/3: Setting up WebSocket hooks');

                Hooks.setupWebSocket();

                Utils.log('[Agent] Step 2/3: Setting up HTTP hooks');

                Hooks.setupHTTP();

                Utils.log('[Agent] Step 3a/3: Loading Java classes (context, wm)');

                Init.loadJavaClasses();

                if (!State.context) {
                    Utils.log('[Agent] FATAL: context not acquired after loadJavaClasses, aborting');

                    return;
                }
                if (!State.windowManager) {
                    Utils.log('[Agent] FATAL: windowManager not acquired after loadJavaClasses, aborting');

                    return;
                }

                Init.setupUI();

                Utils.log('[Agent] Step 3b/3: Hooking AccessibilityService');

                Init.setupAccessibilityHook();

                Utils.log('[Agent] Step 3c/3: Registering RPC exports');

                Init.setupRPC();

                Utils.log('[Agent] Initialization complete');
                Utils.log('[Agent] Ready');
            } catch (innerError) {
                Utils.log('[Agent] Java.perform inner ERROR: ' + innerError.toString());
                Utils.log('[Agent] Stack: ' + (innerError.stack || 'no stack'));
            }
        });
    } catch (outerError) {
        Utils.log('[Agent] Java.perform outer ERROR: ' + outerError.toString());
        Utils.log('[Agent] Stack: ' + (outerError.stack || 'no stack'));
    }
});
