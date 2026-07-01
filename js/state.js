export const State = {
    menus: {
        tracker: null,
        booster: null,
        inviter: null,
        spinner: null
    },

    buttons: {
        red: null,
        green: null,
        blue: null,
        yellow: null
    },

    buttonParams: {
        red: null,
        green: null,
        blue: null,
        yellow: null,
        panel: null
    },

    menuParams: {
        tracker: null,
        booster: null,
        inviter: null,
        spinner: null
    },

    visibility: {
        tracker: false,
        booster: false,
        inviter: false,
        spinner: false
    },

    windowManager: null,
    context: null,
    drag: null,
    accessibility: null,
    accessibilityInstance: null,
    accessibilityReady: false,
    accessibilityReceiver: null,

    game: {
        playersById: {},
        idByNum: {},
        chat: [],
        messages: [],
        messagesBySender: {},
        messagesByMentioned: {},
        selectedPlayerId: null,
        currentSection: 'players',
        latestRenderData: null
    },

    network: {
        websocket: null,
        realWebSocket: null,
        originalSend: null,
        botApiKey: null,
        bearerToken: null,
        wsUrl: null
    },

    auth: {
        bearerToken: null,
        cfJwt: null
    },

    ui: {
        playersTextView: null,
        selectedPlayerSpinner: null,
        sentTextView: null,
        mentionedTextView: null,
        mastermindTextView: null,
        errorTextView: null,
        predictButton: null,
        predictResultTextView: null,
        commandInput: null,
        invitePlayerNameInput: null,
        inviteCountInput: null,
        inviteButton: null,
        inviteStatusTextView: null,
        playersSectionView: null,
        messagesSectionView: null,
        mastermindSectionView: null,
        invitesSectionView: null,
        playersSectionButton: null,
        messagesSectionButton: null,
        mastermindSectionButton: null,
        invitesSectionButton: null
    }
};
