import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Controls.Basic as Controls

Rectangle {
    id: root
    width: 1920
    height: 1080
    color: cfg("background", "#161a22")

    function cfg(key, fallback) {
        const value = config[key];
        return value === undefined || value === null || String(value) === "" ? fallback : String(value);
    }
    readonly property color surface: cfg("surface", "#202530")
    readonly property color field: cfg("field", "#2b3240")
    readonly property color foreground: cfg("foreground", "#ecedf3")
    readonly property color muted: cfg("muted", "#b6bfd0")
    readonly property color accent: cfg("accent", "#a9c7ff")
    readonly property color onAccent: cfg("onAccent", "#102d53")
    readonly property color outline: cfg("outline", "#465064")
    readonly property color error: cfg("error", "#ffb4ab")
    readonly property string family: bundledFont.status === FontLoader.Ready ? bundledFont.name : cfg("font", "Inter")
    readonly property int corner: Math.max(0, Number(cfg("radius", "14")))
    readonly property int edge: Math.max(0, Number(cfg("border", "1")))
    readonly property bool motion: cfg("animations", "true") === "true"
    readonly property bool narrow: width < 900
    readonly property bool compact: height < 760
    readonly property int inset: compact ? 20 : 28
    property bool busy: false
    property bool entered: false
    property bool exiting: false
    property real shakeOffset: 0
    property string message: ""
    property string powerAction: ""
    property date now: new Date()

    function cycleSession(step) {
        if (busy || session.count <= 1) return;
        session.currentIndex = (session.currentIndex + step + session.count) % session.count;
        message = qsTr("Session: %1").arg(session.displayText);
    }

    function cycleUser() {
        if (busy || userItems.count <= 1) {
            username.forceActiveFocus();
            username.selectAll();
            return;
        }
        const total = userItems.count;
        let current = -1;
        for (let i = 0; i < total; i++) {
            const item = userItems.objectAt(i);
            if (item && item.name === username.text) {
                current = i;
                break;
            }
        }
        const nextItem = userItems.objectAt((current + 1) % total);
        if (nextItem) {
            username.text = nextItem.name;
            message = "";
            password.forceActiveFocus();
        }
    }

    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Escape) {
            if (powerPrompt.opened) { powerPrompt.close(); event.accepted = true; return; }
            if (users.opened) { users.close(); event.accepted = true; return; }
            if (session.popup.opened) { session.popup.close(); event.accepted = true; return; }
            password.clear();
            message = "";
            password.forceActiveFocus();
            event.accepted = true;
        } else if (event.key === Qt.Key_F1 || ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_Tab) ||
                   ((event.modifiers & Qt.AltModifier) && event.key === Qt.Key_S)) {
            cycleSession(1);
            event.accepted = true;
        } else if (event.key === Qt.Key_F2 || ((event.modifiers & Qt.AltModifier) && event.key === Qt.Key_U)) {
            cycleUser();
            event.accepted = true;
        } else if ((event.modifiers & Qt.AltModifier) && event.key === Qt.Key_H) {
            if (!busy) showPassword.toggle();
            event.accepted = true;
        } else if ((event.modifiers & Qt.AltModifier) && event.key === Qt.Key_R) {
            if (!busy && sddm.canReboot) confirmPower("restart");
            event.accepted = true;
        } else if ((event.modifiers & Qt.AltModifier) && event.key === Qt.Key_P) {
            if (!busy && sddm.canPowerOff) confirmPower("shutdown");
            event.accepted = true;
        }
    }

    FontLoader { id: bundledFont; source: cfg("fontFile", "") }
    Image {
        id: wallpaperImage
        anchors.fill: parent
        source: root.cfg("wallpaper", "")
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        visible: status === Image.Ready
        opacity: root.exiting ? 0.45 : (root.entered ? 1.0 : 0.0)
        Behavior on opacity { enabled: root.motion; NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }
    }
    Rectangle {
        anchors.fill: parent
        visible: root.cfg("wallpaper", "") !== ""
        opacity: root.exiting ? 0.72 : 1.0
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(root.color.r, root.color.g, root.color.b, 0.34) }
            GradientStop { position: 0.55; color: Qt.rgba(root.color.r, root.color.g, root.color.b, 0.52) }
            GradientStop { position: 1.0; color: Qt.rgba(root.color.r, root.color.g, root.color.b, 0.72) }
        }
        Behavior on opacity { enabled: root.motion; NumberAnimation { duration: 240; easing.type: Easing.OutCubic } }
    }

    component Label: Text {
        color: root.foreground
        font.family: root.family
        font.pixelSize: 14
        elide: Text.ElideRight
    }
    component Action: Controls.Button {
        id: action
        property bool primary: false
        implicitHeight: 44
        padding: 12
        spacing: 10
        font.family: root.family
        font.pixelSize: 14
        font.weight: primary ? Font.DemiBold : Font.Normal
        icon.width: 18
        icon.height: 18
        icon.color: primary || hovered || down ? root.onAccent : root.foreground
        palette.buttonText: primary || hovered || down ? root.onAccent : root.foreground
        opacity: enabled ? 1 : 0.45
        scale: down ? 0.985 : (hovered ? 1.012 : 1.0)
        Behavior on scale { enabled: root.motion; NumberAnimation { duration: 110; easing.type: Easing.OutQuad } }
        onActiveFocusChanged: if (activeFocus) viewport.ensureVisible(action)
        Keys.onReturnPressed: if (enabled) clicked()
        Keys.onEnterPressed: if (enabled) clicked()
        background: Rectangle {
            radius: Math.min(root.corner, 10)
            color: action.primary || action.hovered || action.down ? root.accent : "transparent"
            border.width: action.visualFocus ? 2 : (action.primary ? 0 : root.edge)
            border.color: action.visualFocus ? root.accent : root.outline
            Behavior on color { enabled: root.motion; ColorAnimation { duration: 110 } }
            Behavior on border.color { enabled: root.motion; ColorAnimation { duration: 110 } }
        }
    }
    component Field: Controls.TextField {
        id: input
        implicitHeight: 48
        leftPadding: 14
        rightPadding: 14
        color: root.foreground
        placeholderTextColor: root.muted
        selectionColor: root.accent
        selectedTextColor: root.onAccent
        font.family: root.family
        font.pixelSize: 15
        selectByMouse: true
        onActiveFocusChanged: if (activeFocus) viewport.ensureVisible(input)
        background: Rectangle {
            color: root.field
            radius: Math.min(root.corner, 10)
            border.width: input.activeFocus ? 2 : root.edge
            border.color: input.activeFocus ? root.accent : root.outline
        }
    }

    // Clock belongs to the wallpaper. It recedes on smaller displays.
    Column {
        x: card.x + 4
        y: Math.max(24, card.y - height - 32)
        spacing: 4
        visible: root.height > 850 && !root.narrow
        opacity: root.exiting ? 0.0 : (root.entered ? 1.0 : 0.0)
        transform: Translate {
            y: root.exiting ? -14 : (root.entered ? 0 : 18)
            Behavior on y { enabled: root.motion; NumberAnimation { duration: root.exiting ? 220 : 360; easing.type: root.exiting ? Easing.InCubic : Easing.OutCubic } }
        }
        Behavior on opacity { enabled: root.motion; NumberAnimation { duration: root.exiting ? 200 : 340; easing.type: root.exiting ? Easing.InCubic : Easing.OutCubic } }
        Label { text: Qt.formatTime(root.now, "h:mm ap").toUpperCase(); font.pixelSize: 44; font.weight: Font.DemiBold }
        Label { text: Qt.formatDate(root.now, "dddd, d MMMM"); color: root.muted; font.pixelSize: 15 }
    }
    Timer { interval: 10000; running: true; repeat: true; onTriggered: root.now = new Date() }

    Flickable {
        id: viewport
        anchors.fill: parent
        contentWidth: width
        contentHeight: Math.max(height, card.height + 48)
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        function ensureVisible(item) {
            const top = item.mapToItem(contentItem, 0, 0).y;
            if (top < contentY + 16) contentY = Math.max(0, top - 16);
            else if (top + item.height > contentY + height - 16)
                contentY = Math.min(contentHeight - height, top + item.height - height + 16);
        }

        Rectangle {
            id: card
            x: root.narrow ? (viewport.width - width) / 2 : Math.round(viewport.width * 0.075)
            y: Math.max(24, (viewport.height - height) / 2)
            width: Math.min(440, viewport.width - 32)
            height: form.implicitHeight + 2 * root.inset
            color: root.surface
            radius: root.corner
            border.width: root.edge
            border.color: root.outline
            opacity: root.exiting ? 0.0 : (root.entered ? 1.0 : 0.0)
            scale: root.exiting ? 0.96 : (root.entered ? 1.0 : 0.96)
            transform: Translate {
                x: root.shakeOffset
                y: root.exiting ? -18 : (root.entered ? 0 : 24)
                Behavior on y { enabled: root.motion; NumberAnimation { duration: root.exiting ? 220 : 340; easing.type: root.exiting ? Easing.InCubic : Easing.OutCubic } }
            }
            Behavior on opacity { enabled: root.motion; NumberAnimation { duration: root.exiting ? 220 : 320; easing.type: root.exiting ? Easing.InCubic : Easing.OutCubic } }
            Behavior on scale { enabled: root.motion; NumberAnimation { duration: root.exiting ? 220 : 340; easing.type: root.exiting ? Easing.InCubic : Easing.OutCubic } }

            SequentialAnimation {
                id: failShake
                NumberAnimation { target: root; property: "shakeOffset"; to: -8; duration: 45; easing.type: Easing.OutQuad }
                NumberAnimation { target: root; property: "shakeOffset"; to: 8; duration: 60; easing.type: Easing.InOutQuad }
                NumberAnimation { target: root; property: "shakeOffset"; to: -5; duration: 55; easing.type: Easing.InOutQuad }
                NumberAnimation { target: root; property: "shakeOffset"; to: 4; duration: 50; easing.type: Easing.InOutQuad }
                NumberAnimation { target: root; property: "shakeOffset"; to: 0; duration: 50; easing.type: Easing.OutQuad }
            }

            ColumnLayout {
                id: form
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: root.inset }
                spacing: 0

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    Action {
                        icon.source: "icons/menu.svg"
                        enabled: false
                        opacity: 1
                        implicitWidth: 40
                        implicitHeight: 40
                        background: Rectangle { color: root.field; radius: Math.min(root.corner, 10) }
                        Accessible.name: "Raccon"
                    }
                    Label { text: "Raccon"; font.pixelSize: 20; font.weight: Font.DemiBold; Layout.fillWidth: true }
                    Label { text: sddm.hostName; color: root.muted; font.pixelSize: 12; Layout.maximumWidth: 150 }
                }
                Rectangle { Layout.fillWidth: true; Layout.topMargin: root.compact ? 16 : 20; Layout.bottomMargin: root.compact ? 16 : 24; height: 1; color: root.outline }
                Label { text: qsTr("Welcome back"); font.pixelSize: 26; font.weight: Font.DemiBold; Layout.fillWidth: true }
                Label { text: qsTr("Sign in to your desktop."); color: root.muted; Layout.topMargin: 6; Layout.bottomMargin: root.compact ? 16 : 24; Layout.fillWidth: true }

                Label { text: qsTr("User"); Layout.bottomMargin: 8 }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Field {
                        id: username
                        objectName: "username"
                        Layout.fillWidth: true
                        text: userModel.lastUser
                        placeholderText: qsTr("Username")
                        enabled: !root.busy
                        Accessible.name: qsTr("Username")
                        KeyNavigation.tab: chooseUser.visible ? chooseUser : password
                        KeyNavigation.backtab: shutdownBtn
                        onAccepted: password.forceActiveFocus()
                    }
                    Action {
                        id: chooseUser
                        icon.source: "icons/down.svg"
                        implicitWidth: 44
                        implicitHeight: 48
                        visible: userItems.count > 0
                        enabled: !root.busy
                        Accessible.name: qsTr("Choose user")
                        KeyNavigation.tab: password
                        KeyNavigation.backtab: username
                        onClicked: users.open()
                        Controls.Menu {
                            id: users
                            y: parent.height + 4
                            width: Math.min(300, card.width - 56)
                            padding: 6
                            enter: Transition {
                                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: root.motion ? 150 : 0 }
                                NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: root.motion ? 150 : 0; easing.type: Easing.OutCubic }
                            }
                            exit: Transition {
                                NumberAnimation { property: "opacity"; from: 1; to: 0; duration: root.motion ? 110 : 0 }
                            }
                            background: Rectangle { color: root.field; radius: Math.min(root.corner, 10); border.width: 1; border.color: root.outline }
                            Instantiator {
                                id: userItems
                                model: userModel
                                delegate: Controls.MenuItem {
                                    required property string name
                                    required property string realName
                                    text: realName ? realName + " (" + name + ")" : name
                                    font.family: root.family
                                    font.pixelSize: 14
                                    contentItem: Label { text: parent.text; color: parent.highlighted ? root.onAccent : root.foreground }
                                    background: Rectangle { color: parent.highlighted ? root.accent : "transparent"; radius: Math.min(root.corner, 6) }
                                    onTriggered: { username.text = name; password.forceActiveFocus(); }
                                }
                                onObjectAdded: (index, object) => users.insertItem(index, object)
                                onObjectRemoved: (index, object) => users.removeItem(object)
                            }
                        }
                    }
                }
                Label { text: qsTr("Password"); Layout.topMargin: root.compact ? 12 : 16; Layout.bottomMargin: 8 }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Field {
                        id: password
                        objectName: "password"
                        Layout.fillWidth: true
                        echoMode: showPassword.checked ? TextInput.Normal : TextInput.Password
                        placeholderText: qsTr("Enter your password")
                        enabled: !root.busy
                        Accessible.name: qsTr("Password")
                        KeyNavigation.tab: showPassword
                        KeyNavigation.backtab: chooseUser.visible ? chooseUser : username
                        onAccepted: root.login()
                        onTextEdited: root.message = ""
                    }
                    Action {
                        id: showPassword
                        checkable: true
                        icon.source: checked ? "icons/conceal.svg" : "icons/reveal.svg"
                        implicitWidth: 44
                        implicitHeight: 48
                        enabled: !root.busy
                        Accessible.name: checked ? qsTr("Hide password") : qsTr("Show password")
                        KeyNavigation.tab: session
                        KeyNavigation.backtab: password
                    }
                }
                Label { text: qsTr("Session"); Layout.topMargin: root.compact ? 12 : 16; Layout.bottomMargin: 8 }
                Controls.ComboBox {
                    id: session
                    objectName: "session"
                    Layout.fillWidth: true
                    implicitHeight: 44
                    leftPadding: 14
                    rightPadding: 40
                    model: sessionModel
                    textRole: "name"
                    currentIndex: sessionModel.lastIndex
                    enabled: !root.busy && count > 0
                    font.family: root.family
                    font.pixelSize: 14
                    Accessible.name: qsTr("Desktop session")
                    KeyNavigation.tab: signIn
                    KeyNavigation.backtab: showPassword
                    onActiveFocusChanged: if (activeFocus) viewport.ensureVisible(session)
                    contentItem: Label { text: session.count ? session.displayText : qsTr("No sessions installed"); verticalAlignment: Text.AlignVCenter }
                    indicator: Image { x: session.width - width - 14; y: (session.height - height) / 2; width: 14; height: 14; source: "icons/down.svg" }
                    background: Rectangle {
                        color: root.field
                        radius: Math.min(root.corner, 10)
                        border.width: session.visualFocus ? 2 : root.edge
                        border.color: session.visualFocus ? root.accent : root.outline
                    }
                    delegate: Controls.ItemDelegate {
                        required property string name
                        required property int index
                        width: session.width - 12
                        implicitHeight: 44
                        highlighted: session.highlightedIndex === index
                        contentItem: Label { text: parent.name; color: parent.highlighted ? root.onAccent : root.foreground; verticalAlignment: Text.AlignVCenter }
                        background: Rectangle { color: parent.highlighted ? root.accent : "transparent"; radius: Math.min(root.corner, 6) }
                    }
                    popup: Controls.Popup {
                        y: session.height + 4
                        width: session.width
                        padding: 6
                        implicitHeight: Math.min(contentItem.implicitHeight + 12, 240)
                        enter: Transition {
                            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: root.motion ? 150 : 0 }
                            NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: root.motion ? 150 : 0; easing.type: Easing.OutCubic }
                        }
                        exit: Transition {
                            NumberAnimation { property: "opacity"; from: 1; to: 0; duration: root.motion ? 110 : 0 }
                        }
                        contentItem: ListView { clip: true; implicitHeight: contentHeight; model: session.popup.visible ? session.delegateModel : null; currentIndex: session.highlightedIndex; boundsBehavior: Flickable.StopAtBounds; Controls.ScrollBar.vertical: Controls.ScrollBar {} }
                        background: Rectangle { color: root.field; radius: Math.min(root.corner, 10); border.width: 1; border.color: root.outline }
                    }
                }
                Label {
                    id: feedback
                    objectName: "feedback"
                    Layout.fillWidth: true
                    Layout.topMargin: 12
                    Layout.bottomMargin: 12
                    text: root.message || (keyboard.capsLock ? qsTr("Caps Lock is on") : " ")
                    color: root.message ? root.error : root.muted
                    font.pixelSize: 12
                    elide: Text.ElideNone
                    wrapMode: Text.WordWrap
                    Accessible.role: Accessible.AlertMessage
                }
                Action {
                    id: signIn
                    objectName: "signIn"
                    Layout.fillWidth: true
                    primary: true
                    text: root.busy ? qsTr("Signing in…") : qsTr("Sign in")
                    icon.source: "icons/next.svg"
                    enabled: !root.busy && username.text.trim().length > 0 && session.currentIndex >= 0
                    KeyNavigation.tab: restartBtn
                    KeyNavigation.backtab: session
                    onClicked: root.login()
                }
                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: root.compact ? 12 : 18
                    spacing: 8
                    Action {
                        id: restartBtn
                        Layout.fillWidth: true
                        icon.source: "icons/reboot.svg"
                        text: qsTr("Restart")
                        enabled: !root.busy && sddm.canReboot
                        KeyNavigation.tab: shutdownBtn
                        KeyNavigation.backtab: signIn
                        onClicked: root.confirmPower("restart")
                    }
                    Action {
                        id: shutdownBtn
                        Layout.fillWidth: true
                        icon.source: "icons/shutdown.svg"
                        text: qsTr("Shut down")
                        enabled: !root.busy && sddm.canPowerOff
                        KeyNavigation.tab: username
                        KeyNavigation.backtab: restartBtn
                        onClicked: root.confirmPower("shutdown")
                    }
                }
                Label {
                    Layout.fillWidth: true
                    Layout.topMargin: 10
                    text: qsTr("Tab: navigate · Alt+S: session · Alt+R/P: power · Esc: reset")
                    color: root.muted
                    font.pixelSize: 11
                    opacity: 0.72
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }

    Controls.Popup {
        id: powerPrompt
        parent: Controls.Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(400, root.width - 32)
        padding: 24
        modal: true
        focus: true
        closePolicy: Controls.Popup.CloseOnEscape | Controls.Popup.CloseOnPressOutside
        enter: Transition {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: root.motion ? 170 : 0 }
            NumberAnimation { property: "scale"; from: 0.94; to: 1; duration: root.motion ? 180 : 0; easing.type: Easing.OutCubic }
        }
        exit: Transition {
            NumberAnimation { property: "opacity"; from: 1; to: 0; duration: root.motion ? 130 : 0 }
            NumberAnimation { property: "scale"; from: 1; to: 0.96; duration: root.motion ? 130 : 0; easing.type: Easing.InCubic }
        }
        onOpened: powerCancelBtn.forceActiveFocus()
        onClosed: password.forceActiveFocus()
        background: Rectangle { color: root.surface; radius: root.corner; border.width: 1; border.color: root.outline }
        Controls.Overlay.modal: Rectangle { color: "#99000000" }
        contentItem: ColumnLayout {
            spacing: 20
            Label { text: root.powerAction === "restart" ? qsTr("Restart the computer?") : qsTr("Shut down the computer?"); font.pixelSize: 18; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            RowLayout {
                spacing: 8
                Action {
                    id: powerCancelBtn
                    text: qsTr("Cancel")
                    Layout.fillWidth: true
                    KeyNavigation.right: powerConfirmBtn
                    KeyNavigation.tab: powerConfirmBtn
                    onClicked: powerPrompt.close()
                }
                Action {
                    id: powerConfirmBtn
                    primary: true
                    text: root.powerAction === "restart" ? qsTr("Restart") : qsTr("Shut down")
                    Layout.fillWidth: true
                    KeyNavigation.left: powerCancelBtn
                    KeyNavigation.backtab: powerCancelBtn
                    onClicked: {
                        powerPrompt.close();
                        root.exiting = true;
                        powerExitTimer.restart();
                    }
                }
            }
        }
    }
    Timer {
        id: powerExitTimer
        interval: root.motion ? 190 : 0
        repeat: false
        onTriggered: {
            if (root.powerAction === "restart") sddm.reboot();
            else sddm.powerOff();
        }
    }
    function confirmPower(action) { powerAction = action; powerPrompt.open(); }
    function login() {
        if (busy || !username.text.trim() || session.currentIndex < 0) return;
        message = "";
        busy = true;
        showPassword.checked = false;
        sddm.login(username.text.trim(), password.text, session.currentIndex);
    }
    Connections {
        target: sddm
        function onLoginFailed() {
            root.busy = false;
            root.message = qsTr("Sign-in failed. Check your user and password.");
            if (root.motion) failShake.restart();
            password.clear();
            password.forceActiveFocus();
        }
        function onLoginSucceeded() {
            password.clear();
            root.exiting = true;
        }
    }
    Component.onCompleted: {
        if (session.currentIndex < 0 && session.count > 0) session.currentIndex = 0;
        entered = true;
        if (username.text) password.forceActiveFocus(); else username.forceActiveFocus();
    }
}
