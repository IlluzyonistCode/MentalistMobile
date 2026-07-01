import { State } from '../state.js';
import { Utils } from '../utils/logger.js';
import { ICON_BASE64, COLORS, UI_CONFIG } from '../constants.js';

export const UI = {
    _btnCounter: 0,

    createIcon: function(ctx, base64Str, color) {
        try {
            Utils.log('[UI.createIcon] START color=' + color);

            const Base64 = Java.use('android.util.Base64');
            const BitmapFactory = Java.use('android.graphics.BitmapFactory');
            const ImageView = Java.use('android.widget.ImageView');
            const GradientDrawable = Java.use('android.graphics.drawable.GradientDrawable');
            const Color = Java.use('android.graphics.Color');
            const ViewGroupLP = Java.use('android.view.ViewGroup$LayoutParams');

            Utils.log('[UI.createIcon] Decoding base64 string (length=' + base64Str.length + ')');

            const decodedBytes = Base64.decode(base64Str, Base64.DEFAULT.value);

            Utils.log('[UI.createIcon] Decoded bytes length: ' + decodedBytes.length);

            const bitmap = BitmapFactory.decodeByteArray(decodedBytes, 0, decodedBytes.length);

            if (!bitmap) {
                Utils.log('[UI.createIcon] ERROR: bitmap is null after decode');

                return;
            }

            Utils.log('[UI.createIcon] Bitmap decoded: ' + bitmap.getWidth() + 'x' + bitmap.getHeight());

            const imageView = ImageView.$new(ctx);
            imageView.setImageBitmap(bitmap);

            const iconSize = Utils.dpToPx(UI_CONFIG.iconSize);
            const layoutParams = ViewGroupLP.$new(iconSize, iconSize);
            imageView.setLayoutParams(layoutParams);

            Utils.log('[UI.createIcon] Layout params set: ' + iconSize + 'x' + iconSize + 'px');

            const bg = GradientDrawable.$new();
            bg.setShape(GradientDrawable.OVAL.value);
            bg.setColor(Color.parseColor(color));
            imageView.setBackground(bg);

            const padding = Utils.dpToPx(4);
            imageView.setPadding(padding, padding, padding, padding);
            imageView.setScaleType(Java.use('android.widget.ImageView$ScaleType').CENTER_INSIDE.value);
            imageView.setElevation(12.0);

            Utils.log('[UI.createIcon] Done');

            return imageView;
        } catch (e) {
            Utils.log('[UI.createIcon] ERROR: ' + e);

            return;
        }
    },

    createButton: function(ctx, params) {
        try {
            Utils.log('[UI.createButton] Creating button: text="' + params.text + '"');

            const Button = Java.use('android.widget.Button');
            const JavaString = Java.use('java.lang.String');
            const GradientDrawable = Java.use('android.graphics.drawable.GradientDrawable');
            const Color = Java.use('android.graphics.Color');
            const TypedValue = Java.use('android.util.TypedValue');

            const button = Button.$new(ctx);
            button.setText(JavaString.$new(params.text || 'Button'));

            if (params.textColor) button.setTextColor(Color.parseColor(params.textColor));

            if (params.textSize)
                button.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, parseFloat(params.textSize));

            if (params.bgColor) {
                const bg = GradientDrawable.$new();
                bg.setShape(GradientDrawable.RECTANGLE.value);
                bg.setColor(Color.parseColor(params.bgColor));
                bg.setCornerRadius(Utils.dpToPx(8));
                button.setBackground(bg);
            }

            if (params.onClick) {
                const listenerName = 'com.mentalist.BtnListener' + UI._btnCounter++;

                Utils.log('[UI.createButton] Registering listener: ' + listenerName);

                const listener = Java.registerClass({
                    name: listenerName,
                    implements: [Java.use('android.view.View$OnClickListener')],
                    methods: {
                        onClick: function(v) {
                            try {
                                Utils.log('[UI.createButton] onClick fired: ' + listenerName);

                                params.onClick(v);
                            } catch (e) {
                                Utils.log('[UI.createButton] onClick ERROR: ' + e);
                            }
                        }
                    }
                });

                button.setOnClickListener(listener.$new());

                Utils.log('[UI.createButton] Listener attached');
            }

            Utils.log('[UI.createButton] Done: "' + params.text + '"');

            return button;
        } catch (e) {
            Utils.log('[UI.createButton] ERROR: ' + e);

            return;
        }
    },

    createTextField: function(ctx, params) {
        try {
            Utils.log('[UI.createTextField] Creating field: hint="' + (params.hint || '') + '"');

            const EditText = Java.use('android.widget.EditText');
            const JavaString = Java.use('java.lang.String');
            const GradientDrawable = Java.use('android.graphics.drawable.GradientDrawable');
            const Color = Java.use('android.graphics.Color');
            const TypedValue = Java.use('android.util.TypedValue');
            const BufferType = Java.use('android.widget.TextView$BufferType');

            const field = EditText.$new(ctx);

            if (params.hint) field.setHint(JavaString.$new(params.hint));
            if (params.textColor) field.setTextColor(Color.parseColor(params.textColor));
            if (params.hintColor) field.setHintTextColor(Color.parseColor(params.hintColor));
            if (params.textSize) field.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, parseFloat(params.textSize));
            if (params.inputType) field.setInputType(params.inputType);

            if (params.text)
                field.setText(JavaString.$new(params.text), BufferType.EDITABLE.value);

            if (params.bgColor) {
                const bg = GradientDrawable.$new();
                bg.setShape(GradientDrawable.RECTANGLE.value);
                bg.setColor(Color.parseColor(params.bgColor));
                bg.setCornerRadius(Utils.dpToPx(8));

                if (params.borderColor)
                    bg.setStroke(Utils.dpToPx(1), Color.parseColor(params.borderColor));

                field.setBackground(bg);
            }

            field.setPadding(Utils.dpToPx(12), Utils.dpToPx(8), Utils.dpToPx(12), Utils.dpToPx(8));

            Utils.log('[UI.createTextField] Done');

            return field;
        } catch (e) {
            Utils.log('[UI.createTextField] ERROR: ' + e);

            return;
        }
    },

    createGradientMenu: function(ctx, params) {
        try {
            Utils.log('[UI.createGradientMenu] START params=' + JSON.stringify(params));

            const LinearLayout = Java.use('android.widget.LinearLayout');
            const GradientDrawable = Java.use('android.graphics.drawable.GradientDrawable');
            const Color = Java.use('android.graphics.Color');
            const JavaFloat = Java.use('java.lang.Float');

            const menu = LinearLayout.$new(ctx);
            menu.setOrientation(LinearLayout.VERTICAL.value);
            menu.setFocusable(true);
            menu.setFocusableInTouchMode(true);

            const pad = Utils.dpToPx(UI_CONFIG.menuPadding);
            menu.setPadding(pad, pad, pad, pad);

            const bg = GradientDrawable.$new();
            bg.setShape(GradientDrawable.RECTANGLE.value);

            const colors = Java.array('int', [
                Color.parseColor(params.gradientStart || COLORS.redDark),
                Color.parseColor(params.gradientEnd || COLORS.menuBgDark)
            ]);

            bg.setColors(colors);
            bg.setGradientType(GradientDrawable.LINEAR_GRADIENT.value);
            bg.setCornerRadius(JavaFloat.parseFloat(String(Utils.dpToPx(UI_CONFIG.cornerRadius))));
            bg.setStroke(Utils.dpToPx(UI_CONFIG.borderWidth),
                Color.parseColor(params.borderColor || COLORS.crimson));

            menu.setBackground(bg);
            menu.setElevation(15.0);

            Utils.log('[UI.createGradientMenu] Done');

            return menu;
        } catch (e) {
            Utils.log('[UI.createGradientMenu] ERROR: ' + e);

            return;
        }
    },

    createTitleBar: function(ctx, titleText, bitmap, titleColor) {
        try {
            Utils.log('[UI.createTitleBar] Creating title: "' + titleText + '"');

            const LinearLayout = Java.use('android.widget.LinearLayout');
            const TextView = Java.use('android.widget.TextView');
            const ImageView = Java.use('android.widget.ImageView');
            const LayoutParams = Java.use('android.widget.LinearLayout$LayoutParams');
            const Color = Java.use('android.graphics.Color');
            const Typeface = Java.use('android.graphics.Typeface');
            const TypedValue = Java.use('android.util.TypedValue');
            const Gravity = Java.use('android.view.Gravity');
            const JavaString = Java.use('java.lang.String');
            const ScaleType = Java.use('android.widget.ImageView$ScaleType');

            const iconSize = Math.round(Utils.dpToPx(18));

            const titleLayout = LinearLayout.$new(ctx);
            titleLayout.setOrientation(LinearLayout.HORIZONTAL.value);
            titleLayout.setGravity(Gravity.CENTER.value);
            titleLayout.setPadding(0, 0, 0, Utils.dpToPx(12));

            if (bitmap) {
                const iconLeft = ImageView.$new(ctx);
                iconLeft.setImageBitmap(bitmap);
                iconLeft.setScaleType(ScaleType.CENTER_INSIDE.value);

                const lpLeft = LayoutParams.$new(iconSize, iconSize);
                lpLeft.setMargins(0, 0, Utils.dpToPx(6), 0);
                iconLeft.setLayoutParams(lpLeft);
                titleLayout.addView(iconLeft);

                Utils.log('[UI.createTitleBar] Left icon added');
            }

            const tv = TextView.$new(ctx);
            tv.setText(JavaString.$new(titleText));
            tv.setTextColor(Color.parseColor(titleColor));
            tv.setTextSize(TypedValue.COMPLEX_UNIT_SP.value, parseFloat(UI_CONFIG.titleSize));
            tv.setGravity(Gravity.CENTER.value);
            tv.setTypeface(Typeface.DEFAULT_BOLD.value);

            titleLayout.addView(tv);

            if (bitmap) {
                const iconRight = ImageView.$new(ctx);
                iconRight.setImageBitmap(bitmap);
                iconRight.setScaleType(ScaleType.CENTER_INSIDE.value);

                const lpRight = LayoutParams.$new(iconSize, iconSize);
                lpRight.setMargins(Utils.dpToPx(6), 0, 0, 0);
                iconRight.setLayoutParams(lpRight);
                titleLayout.addView(iconRight);

                Utils.log('[UI.createTitleBar] Right icon added');
            }

            Utils.log('[UI.createTitleBar] Done');

            return titleLayout;
        } catch (e) {
            Utils.log('[UI.createTitleBar] ERROR: ' + e);

            return;
        }
    },

    decodeIconBitmap: function() {
        try {
            Utils.log('[UI.decodeIconBitmap] Decoding icon bitmap');

            const Base64 = Java.use('android.util.Base64');
            const BitmapFactory = Java.use('android.graphics.BitmapFactory');

            const bytes = Base64.decode(ICON_BASE64, Base64.DEFAULT.value);
            const bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);

            if (!bitmap) Utils.log('[UI.decodeIconBitmap] WARN: bitmap is null');

            else Utils.log('[UI.decodeIconBitmap] Bitmap ready: ' + bitmap.getWidth() + 'x' + bitmap.getHeight());

            return bitmap;
        } catch (e) {
            Utils.log('[UI.decodeIconBitmap] ERROR: ' + e);

            return;
        }
    }
};
