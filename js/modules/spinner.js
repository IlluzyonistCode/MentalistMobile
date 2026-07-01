import { State } from '../state.js';
import { Utils } from '../utils/logger.js';

const PATTERNS = {
    play: /^(ИГРАТЬ|PLAY|OYNA)$/i,
    rejoin_normal: /Твоя игра всё ещё идëт|Your game is still running, would you like to rejoin|Oynadığın oyun hala devam ediyor/i,
    rejoin_dead: /Твоя последняя игра ещё идёт|Your last game is still running|Son oynadığın oyun hala devam ediyor/i,
    cancel: /^(Отмена|Cancel|Vazgeç)$/i,
    free_gold: /^(Бесплатное золото!|Free gold!|Ücretsiz altın!)$/i,
    ad_watch: /^(РЕКЛАМА|WATCH VIDEO|REKLAM İZLE)$/i,
    spin: /^(КРУТИТЬ|SPIN|ÇEVİR)$/i,
    done: /(Новые награды будут доступны через|New rewards will be available in|Yeni ödüller)/i,
    reset_ad: /(Сбросить рекламный идентификатор|Reset advertising ID|Reklam kimliğini sıfırla)/i,
    ok_confirm: /^(ОК|OK|ONAYLA)$/i
};

const PACKAGE = 'com.mentalist.mobile';

function setStatus(textView, msg) {
    if (!textView) return;
    try {
        Java.scheduleOnMainThread(function() {
            try {
                const JavaString = Java.use('java.lang.String');
                const TextView = Java.use('android.widget.TextView');
                Java.cast(textView, TextView)
                    .setText.overload('java.lang.CharSequence')
                    .call(textView, JavaString.$new(msg));
            } catch (e) {}
        });
    } catch (e) {}
}

function sleep(ms) {
    Java.use('java.lang.Thread').sleep(ms);
}

function getRootView() {
    try {
        const ActivityThread = Java.use('android.app.ActivityThread');
        const currentThread = ActivityThread.currentActivityThread();
        
        if (!currentThread || !currentThread.mActivities) return null;
        
        const ActivityClientRecord = Java.use('android.app.ActivityThread$ActivityClientRecord');
        const activities = currentThread.mActivities.value;
        
        if (!activities) return null;
        
        const values = activities.values().toArray();
        
        for (let i = 0; i < values.length; i++) {
            try {
                const record = Java.cast(values[i], ActivityClientRecord);
                const activity = record.activity.value;
                
                if (!activity || record.stopped.value || record.paused.value) continue;
                
                const window = activity.getWindow();
                
                if (window) {
                    const decorView = window.getDecorView();
                    
                    if (decorView) return decorView;
                }
            } catch (e) {}
        }
        
        return null;
    } catch (e) {
        Utils.log('[Spinner.getRootView] ERROR: ' + e);
        
        return null;
    }
}

function findAndClick(pattern, justFind) {
    try {
        const root = getRootView();
        
        if (!root) return false;
        
        const ViewGroup = Java.use('android.view.ViewGroup');
        const TextView = Java.use('android.widget.TextView');
        const Button = Java.use('android.widget.Button');
        
        let found = false;
        let targetView = null;
        
        function scan(view) {
            if (found || !view) return;
            
            try {
                if (view.getVisibility && view.getVisibility() !== 0) return;
                
                const isTextView = TextView.class.isInstance(view);
                const isButton = Button.class.isInstance(view);
                
                if (isTextView || isButton) {
                    const textWidget = Java.cast(view, TextView);
                    const text = String(textWidget.getText() || '');
                    
                    if (pattern.test(text)) {
                        found = true;
                        targetView = view;
                        return;
                    }
                }
                
                if (ViewGroup.class.isInstance(view)) {
                    const group = Java.cast(view, ViewGroup);
                    const count = group.getChildCount();
                    
                    for (let i = 0; i < count && !found; i++) {
                        scan(group.getChildAt(i));
                    }
                }
            } catch (e) {}
        }
        
        scan(root);
        
        if (found && !justFind && targetView) {
            try {
                let clickableView = targetView;
                
                while (clickableView) {
                    if (clickableView.isClickable && clickableView.isClickable()) {
                        break;
                    }
                    const parent = clickableView.getParent();
                    if (!parent || !Java.use('android.view.View').class.isInstance(parent)) {
                        break;
                    }
                    clickableView = Java.cast(parent, Java.use('android.view.View'));
                }
                
                Utils.log('[Spinner.click] Target: ' + clickableView.toString() + 
                         ' clickable=' + clickableView.isClickable());
                
                const clicked = Java.use('java.util.concurrent.atomic.AtomicBoolean').$new(false);
                
                Java.scheduleOnMainThread(function() {
                    try {
                        const result = clickableView.callOnClick();
                        Utils.log('[Spinner.click] callOnClick result: ' + result);
                        clicked.set(true);
                    } catch (e) {
                        Utils.log('[Spinner.click] callOnClick ERROR: ' + e);
                        try {
                            clickableView.performClick();
                            Utils.log('[Spinner.click] performClick fallback used');
                        } catch (e2) {
                            Utils.log('[Spinner.click] performClick ERROR: ' + e2);
                        }
                        clicked.set(true);
                    }
                });
                
                const start = Date.now();
                while (!clicked.get() && (Date.now() - start < 2000)) {
                    Java.use('java.lang.Thread').sleep(50);
                }
            } catch (e) {
                Utils.log('[Spinner.click] ERROR: ' + e);
            }
        }
        
        return found;
    } catch (e) {
        Utils.log('[Spinner.findAndClick] ERROR: ' + e);
        
        return false;
    }
}

function shellTap(x, y) {
    try {
        Utils.log('[Spinner.shellTap] Tapping at x=' + x + ' y=' + y);
        
        const Runtime = Java.use('java.lang.Runtime');
        const runtime = Runtime.getRuntime();
        
        const cmd = 'input tap ' + Math.round(x) + ' ' + Math.round(y);
        const process = runtime.exec(cmd);
        
        process.waitFor();
        
        Utils.log('[Spinner.shellTap] Done');
        
        return true;
    } catch (e) {
        Utils.log('[Spinner.shellTap] ERROR: ' + e);
        
        return false;
    }
}

function findTextViaUiDump(pattern) {
    try {
        const Runtime = Java.use('java.lang.Runtime');
        const BufferedReader = Java.use('java.io.BufferedReader');
        const InputStreamReader = Java.use('java.io.InputStreamReader');
        
        const runtime = Runtime.getRuntime();
        const dumpFile = '/sdcard/window_dump.xml';
        
        runtime.exec('uiautomator dump ' + dumpFile).waitFor();
        sleep(500);
        
        const catProcess = runtime.exec('cat ' + dumpFile);
        const reader = BufferedReader.$new(InputStreamReader.$new(catProcess.getInputStream()));
        
        let line;
        let xml = '';
        
        while ((line = reader.readLine()) != null) {
            xml += String(line);
        }
        
        reader.close();
        catProcess.waitFor();
        
        runtime.exec('rm ' + dumpFile).waitFor();
        
        if (!xml) {
            Utils.log('[Spinner.findTextViaUiDump] Empty dump');
            return null;
        }
        
        const textMatch = pattern.toString().replace(/^\/(.+)\/[gim]*$/, '$1');
        const regex = new RegExp('text="([^"]*' + textMatch + '[^"]*)"[^>]*bounds="\\[([0-9]+),([0-9]+)\\]\\[([0-9]+),([0-9]+)\\]"', 'i');
        const match = xml.match(regex);
        
        if (match) {
            const x1 = parseInt(match[2]);
            const y1 = parseInt(match[3]);
            const x2 = parseInt(match[4]);
            const y2 = parseInt(match[5]);
            
            const x = (x1 + x2) / 2;
            const y = (y1 + y2) / 2;
            
            Utils.log('[Spinner.findTextViaUiDump] Found "' + match[1] + '" at bounds=[' + x1 + ',' + y1 + '][' + x2 + ',' + y2 + ']');
            
            return { x: x, y: y, text: match[1] };
        }
        
        Utils.log('[Spinner.findTextViaUiDump] Pattern not found');
        
        return null;
    } catch (e) {
        Utils.log('[Spinner.findTextViaUiDump] ERROR: ' + e);
        
        return null;
    }
}

function findText(pattern) {
    return findAndClick(pattern, true);
}

function clickText(pattern, useShell) {
    if (useShell) {
        const result = findTextViaUiDump(pattern);
        
        if (result) {
            return shellTap(result.x, result.y);
        }
        
        return false;
    }
    
    return findAndClick(pattern, false);
}

function pressBack() {
    try {
        Java.scheduleOnMainThread(function() {
            try {
                const ActivityThread = Java.use('android.app.ActivityThread');
                const currentThread = ActivityThread.currentActivityThread();
                
                if (!currentThread || !currentThread.mActivities) return;
                
                const ActivityClientRecord = Java.use('android.app.ActivityThread$ActivityClientRecord');
                const activities = currentThread.mActivities.value;
                
                if (!activities) return;
                
                const values = activities.values().toArray();
                
                for (let i = 0; i < values.length; i++) {
                    try {
                        const record = Java.cast(values[i], ActivityClientRecord);
                        const activity = record.activity.value;
                        
                        if (activity && !record.stopped.value && !record.paused.value) {
                            activity.onBackPressed();
                        }
                    } catch (e) {}
                }
            } catch (e) {
                Utils.log('[Spinner.pressBack] ERROR: ' + e);
            }
        });
    } catch (e) {}
}

function waitFor(patternKey, opts) {
    const pattern = PATTERNS[patternKey];
    const timeoutMs = (opts.timeout || 15) * 1000;
    const intervalMs = (opts.interval || 1) * 1000;
    const click = opts.click !== false;
    const failThres = opts.failThreshold || null;
    const stopFlag = opts.stopFlag;
    
    const start = Date.now();
    let fails = 0;
    
    while (Date.now() - start < timeoutMs) {
        if (stopFlag && stopFlag()) return -1;
        
        const found = findText(pattern);
        
        if (found) {
            if (click) {
                sleep(300);
                
                if (!clickText(pattern)) {
                    Utils.log('[Spinner.waitFor] Click failed for: ' + patternKey);
                }
            }
            
            return 0;
        }
        
        fails++;
        
        if (failThres && fails >= failThres) return 1;
        
        sleep(intervalMs);
    }
    
    return 1;
}

export const Spinner = {
    _stopFlag: false,
    _running: false,
    _statusView: null,
    
    setStatusView: function(tv) {
        Spinner._statusView = tv;
    },
    
    start: function() {
        if (Spinner._running) {
            Utils.log('[Spinner.start] Already running');
            return;
        }
        
        Spinner._stopFlag = false;
        Spinner._running = true;
        setStatus(Spinner._statusView, 'Starting...');
        Utils.log('[Spinner.start]');
        
        Java.perform(function() {
            const Thread = Java.use('java.lang.Thread');
            const Runnable = Java.use('java.lang.Runnable');
            
            const cls = Java.registerClass({
                name: 'com.mentalist.SpinThread' + Date.now(),
                implements: [Runnable],
                methods: {
                    run: function() {
                        try {
                            Spinner._run();
                        } catch (e) {
                            Utils.log('[Spinner.thread] ERROR: ' + e);
                            setStatus(Spinner._statusView, 'Error: ' + String(e));
                            Spinner._running = false;
                        }
                    }
                }
            });
            
            Thread.$new(cls.$new()).start();
        });
    },
    
    stop: function() {
        Utils.log('[Spinner.stop]');
        Spinner._stopFlag = true;
    },
    
    _checkStop: function() {
        return Spinner._stopFlag;
    },
    
    _run: function() {
        try {
            while (true) {
                if (Spinner._checkStop()) {
                    setStatus(Spinner._statusView, 'Stopped');
                    Spinner._running = false;
                    return;
                }
                
                if (!Spinner._prepare()) {
                    if (!Spinner._checkStop()) setStatus(Spinner._statusView, 'Preparation failed');
                    Spinner._running = false;
                    return;
                }
                
                const result = Spinner._spin();
                
                if (result === -1) {
                    setStatus(Spinner._statusView, 'Stopped');
                    Spinner._running = false;
                    return;
                } else if (result === 1) {
                    setStatus(Spinner._statusView, 'Done! All spins used.');
                    Spinner._running = false;
                    return;
                } else {
                    setStatus(Spinner._statusView, 'Restarting game...');
                    Spinner._forceStopGame();
                    sleep(3000);
                }
            }
        } catch (e) {
            Utils.log('[Spinner._run] ERROR: ' + e);
            setStatus(Spinner._statusView, 'Fatal: ' + String(e));
            Spinner._running = false;
        }
    },
    
    _prepare: function() {
        while (true) {
            if (Spinner._checkStop()) return false;
            
            try {
                setStatus(Spinner._statusView, 'Launching game...');
                Spinner._launchGame();
                sleep(5000);
                
                setStatus(Spinner._statusView, 'Waiting for main menu...');
                
                const result = waitFor('play', {
                    timeout: 30,
                    interval: 1.5,
                    click: false,
                    failThreshold: 20,
                    stopFlag: Spinner._checkStop.bind(Spinner)
                });
                
                if (result === -1) return false;
                
                if (result === 1) {
                    setStatus(Spinner._statusView, 'Load timeout, retrying...');
                    Spinner._forceStopGame();
                    sleep(2000);
                    continue;
                }
                
                Utils.log('[Spinner._prepare] Main menu detected');
                
                Spinner._handleRejoinPopup();
                
                if (Spinner._checkStop()) return false;
                
                setStatus(Spinner._statusView, 'Opening gold wheel...');
                waitFor('free_gold', {
                    timeout: 5,
                    interval: 0.8,
                    click: true,
                    failThreshold: 6,
                    stopFlag: Spinner._checkStop.bind(Spinner)
                });
                
                return true;
            } catch (e) {
                if (Spinner._checkStop()) return false;
                Utils.log('[Spinner._prepare] ERROR: ' + e);
                setStatus(Spinner._statusView, 'Load failed, retrying...');
                Spinner._forceStopGame();
                sleep(3000);
            }
        }
    },
    
    _spin: function() {
        try {
            while (true) {
                if (Spinner._checkStop()) return -1;
                
                setStatus(Spinner._statusView, 'Checking ad button...');
                
                let result = waitFor('done', {
                    timeout: 5,
                    interval: 1,
                    click: false,
                    failThreshold: 5,
                    stopFlag: Spinner._checkStop.bind(Spinner)
                });
                
                if (result === -1) return -1;
                
                if (result === 0) {
                    Utils.log('[Spinner.spin] DONE!');
                    return 1;
                }
                
                result = waitFor('ad_watch', {
                    timeout: 15,
                    interval: 1,
                    click: false,
                    failThreshold: 12,
                    stopFlag: Spinner._checkStop.bind(Spinner)
                });
                
                if (result === -1) return -1;
                
                if (result === 1) {
                    setStatus(Spinner._statusView, 'Loading takes too long.');
                    return 2;
                }
                
                setStatus(Spinner._statusView, 'Clicking ad...');
                const adStart = Date.now();
                let adLaunched = false;
                
                while (Date.now() - adStart < 30000) {
                    if (Spinner._checkStop()) return -1;
                    
                    if (findText(PATTERNS.ad_watch)) {
                        clickText(PATTERNS.ad_watch);
                        sleep(2000);
                    } else {
                        adLaunched = true;
                        break;
                    }
                }
                
                if (!adLaunched) {
                    setStatus(Spinner._statusView, 'Ad button stuck.');
                    return 2;
                }
                
                setStatus(Spinner._statusView, 'Watching ad...');
                
                for (let i = 0; i < 6; i++) {
                    if (Spinner._checkStop()) return -1;
                    sleep(5000);
                }
                
                setStatus(Spinner._statusView, 'Closing ad...');
                result = Spinner._closeAd();
                
                if (result === -1) return -1;
                
                if (result === 1) {
                    setStatus(Spinner._statusView, 'Could not close ad.');
                    return 2;
                }
                
                setStatus(Spinner._statusView, 'Spinning...');
                waitFor('spin', {
                    timeout: 5,
                    interval: 1,
                    click: true,
                    stopFlag: Spinner._checkStop.bind(Spinner)
                });
                
                sleep(3000);
            }
        } catch (e) {
            Utils.log('[Spinner._spin] ERROR: ' + e);
            return 2;
        }
    },
    
    _handleRejoinPopup: function() {
        const stopFlag = Spinner._checkStop.bind(Spinner);
        
        const res = waitFor('rejoin_normal', {
            timeout: 3,
            interval: 0.5,
            click: false,
            stopFlag
        });
        
        if (res === 0) {
            waitFor('cancel', {
                timeout: 5,
                interval: 0.8,
                click: true,
                stopFlag
            });
        }
    },
    
    _closeAd: function() {
        const stopFlag = Spinner._checkStop.bind(Spinner);
        
        for (let i = 0; i < 8; i++) {
            if (stopFlag()) return -1;
            
            if (findText(PATTERNS.spin) || findText(PATTERNS.play) || findText(PATTERNS.free_gold)) {
                return 0;
            }
            
            pressBack();
            sleep(2000);
            
            const res = waitFor('spin', {
                timeout: 3,
                interval: 0.8,
                click: false,
                failThreshold: 3,
                stopFlag
            });
            
            if (res === 0) return 0;
        }
        
        return 1;
    },

    openAdsSettings: function() {
        try {
            Utils.log('[Spinner.openAdsSettings] Opening Google Ads Privacy settings...');
            Java.scheduleOnMainThread(function() {
                try {
                    const Intent = Java.use('android.content.Intent');
                    const intent = Intent.$new('com.google.android.gms.settings.ADS_PRIVACY');
                    intent.addFlags(0x10000000);
                    State.context.startActivity(intent);
                    Utils.log('[Spinner.openAdsSettings] Launched');
                } catch (e) {
                    Utils.log('[Spinner.openAdsSettings] ERROR: ' + e);
                }
            });
        } catch (e) {
            Utils.log('[Spinner.openAdsSettings] ERROR: ' + e);
        }
    },

    _launchGame: function() {
        try {
            Java.scheduleOnMainThread(function() {
                try {
                    const pkgManager = State.context.getPackageManager();
                    const launchIntent = pkgManager.getLaunchIntentForPackage(PACKAGE);
                    
                    if (launchIntent) {
                        launchIntent.addFlags(0x10000000);
                        State.context.startActivity(launchIntent);
                    } else {
                        Utils.log('[Spinner._launchGame] No launch intent for ' + PACKAGE);
                        
                        const Intent = Java.use('android.content.Intent');
                        const intent = Intent.$new();
                        intent.setAction(Intent.ACTION_MAIN.value);
                        intent.addCategory(Intent.CATEGORY_LAUNCHER.value);
                        intent.setPackage(PACKAGE);
                        intent.addFlags(0x10000000);
                        State.context.startActivity(intent);
                    }
                } catch (e) {
                    Utils.log('[Spinner._launchGame] ERROR: ' + e);
                }
            });
        } catch (e) {}
    },
    
    _forceStopGame: function() {
        try {
            Java.scheduleOnMainThread(function() {
                try {
                    const ActivityManager = Java.use('android.app.ActivityManager');
                    const am = Java.cast(State.context.getSystemService('activity'), ActivityManager);
                    am.killBackgroundProcesses(PACKAGE);
                } catch (e) {
                    Utils.log('[Spinner._forceStopGame] ERROR: ' + e);
                }
            });
        } catch (e) {}
    }
};
