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
    property string message: ""
    property string powerAction: ""
    property date now: new Date()

    FontLoader { id: bundledFont; source: cfg("fontFile", "") }
    Image {
        anchors.fill: parent
        source: root.cfg("wallpaper", "")
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        visible: status === Image.Ready
    }
    Rectangle {
        anchors.fill: parent
        color: root.color
        opacity: Number(root.cfg("dim", "0.24"))
        visible: root.cfg("wallpaper", "") !== ""
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
        onActiveFocusChanged: if (activeFocus) viewport.ensureVisible(action)
        background: Rectangle {
            radius: Math.min(root.corner, 10)
            color: action.primary || action.hovered || action.down ? root.accent : "transparent"
            border.width: action.visualFocus ? 2 : (action.primary ? 0 : root.edge)
            border.color: action.visualFocus ? root.accent : root.outline
            Behavior on color { enabled: root.motion; ColorAnimation { duration: 110 } }
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
        Label { text: Qt.formatTime(root.now, "hh:mm"); font.pixelSize: 42; font.weight: Font.Medium }
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
                        onClicked: users.open()
                        Controls.Menu {
                            id: users
                            y: parent.height + 4
                            width: Math.min(300, card.width - 56)
                            padding: 6
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
                    onClicked: root.login()
                }
                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: root.compact ? 12 : 18
                    spacing: 8
                    Action {
                        Layout.fillWidth: true
                        icon.source: "icons/reboot.svg"
                        text: qsTr("Restart")
                        enabled: !root.busy && sddm.canReboot
                        onClicked: root.confirmPower("restart")
                    }
                    Action {
                        Layout.fillWidth: true
                        icon.source: "icons/shutdown.svg"
                        text: qsTr("Shut down")
                        enabled: !root.busy && sddm.canPowerOff
                        onClicked: root.confirmPower("shutdown")
                    }
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
        background: Rectangle { color: root.surface; radius: root.corner; border.width: 1; border.color: root.outline }
        Controls.Overlay.modal: Rectangle { color: "#99000000" }
        contentItem: ColumnLayout {
            spacing: 20
            Label { text: root.powerAction === "restart" ? qsTr("Restart the computer?") : qsTr("Shut down the computer?"); font.pixelSize: 18; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            RowLayout {
                spacing: 8
                Action { text: qsTr("Cancel"); Layout.fillWidth: true; onClicked: powerPrompt.close() }
                Action {
                    primary: true
                    text: root.powerAction === "restart" ? qsTr("Restart") : qsTr("Shut down")
                    Layout.fillWidth: true
                    onClicked: {
                        powerPrompt.close();
                        if (root.powerAction === "restart") sddm.reboot(); else sddm.powerOff();
                    }
                }
            }
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
            password.clear();
            password.forceActiveFocus();
        }
        function onLoginSucceeded() { password.clear(); }
    }
    Component.onCompleted: {
        if (session.currentIndex < 0 && session.count > 0) session.currentIndex = 0;
        if (username.text) password.forceActiveFocus(); else username.forceActiveFocus();
    }
}
