import { State } from '../state.js';
import { Utils } from '../utils/logger.js';
import { TrackerMenu } from './menus/trackerMenu.js';
import { BoosterMenu } from './menus/boosterMenu.js';
import { SpinnerMenu } from './menus/spinnerMenu.js';
import { InviterMenu } from './menus/inviterMenu.js';

export const MenuController = {
    closeAll: function() {
        try {
            Utils.log('[MenuController.closeAll] Closing all menus');

            TrackerMenu.hide();
            BoosterMenu.hide();
            SpinnerMenu.hide();
            InviterMenu.hide();

            Utils.log('[MenuController.closeAll] All menus hidden');
        } catch (e) {
            Utils.log('[MenuController.closeAll] ERROR: ' + e);
        }
    },

    openOne: function(menuName) {
        try {
            Utils.log('[MenuController.openOne] Opening: ' + menuName);

            MenuController.closeAll();

            if (menuName === 'tracker') TrackerMenu.show();
            if (menuName === 'booster') BoosterMenu.show();
            if (menuName === 'spinner') SpinnerMenu.show();
            if (menuName === 'inviter') InviterMenu.show();

            Utils.log('[MenuController.openOne] Done: ' + menuName);
        } catch (e) {
            Utils.log('[MenuController.openOne] ERROR: ' + e);
        }
    },

    toggleOne: function(menuName) {
        try {
            Utils.log('[MenuController.toggleOne] menuName=' + menuName);

            let isVisible = false;

            if (menuName === 'tracker') isVisible = State.visibility.tracker;
            if (menuName === 'booster') isVisible = State.visibility.booster;
            if (menuName === 'spinner') isVisible = State.visibility.spinner;
            if (menuName === 'inviter') isVisible = State.visibility.inviter;
            
            Utils.log('[MenuController.toggleOne] Currently visible: ' + isVisible);

            if (isVisible) MenuController.closeAll();

            else MenuController.openOne(menuName);

            Utils.log('[MenuController.toggleOne] Done');
        } catch (e) {
            Utils.log('[MenuController.toggleOne] ERROR: ' + e);
        }
    }
};

globalThis._menuControllerToggle = MenuController.toggleOne.bind(MenuController);
