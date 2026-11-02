#!/usr/bin/env python3
"""Run the real Qt 6 greeter offscreen with isolated test models and snapshots."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import os

MOCKS = r'''
    // Test-only objects. This file is generated in a temporary theme directory.
    property QtObject sddm: QtObject {
        property string hostName: "desktop"
        property bool canReboot: true
        property bool canPowerOff: true
        property int attempts: 0
        property int powerCalls: 0
        property int lastSession: -1
        signal loginFailed()
        signal loginSucceeded()
        function login(user, secret, index) { attempts++; lastSession = index; }
        function reboot() { powerCalls++; }
        function powerOff() { powerCalls++; }
    }
    property ListModel sessionModel: ListModel {
        property int lastIndex: 0
        ListElement { name: "Wayfire" }
        ListElement { name: "GNOME" }
    }
    property ListModel userModel: ListModel {
        property string lastUser: "user"
        property int lastIndex: 0
        ListElement { name: "user"; realName: "Desktop user" }
        ListElement { name: "guest"; realName: "Guest" }
    }
    property QtObject keyboard: QtObject { property bool capsLock: false }
'''

CHECKS = r'''
    TestCase { id: keyDriver; name: "RacconKeyboard"; when: false }
    function check(ok, message) { if (!ok) throw new Error("CHECK_FAILED: " + message); }
    Timer {
        interval: 350; running: true
        onTriggered: {
            root.Window.window.width = WIDTH;
            root.Window.window.height = HEIGHT;
            root.width = WIDTH; root.height = HEIGHT;
            check(session.count === 2, "session model");
            check(userItems.count === 2, "user menu model");
            check(password.activeFocus, "initial password focus");
            username.forceActiveFocus();
            keyDriver.keyClick(Qt.Key_Tab);
            check(chooseUser.activeFocus, "tab reaches account menu");
            keyDriver.keyClick(Qt.Key_Tab);
            check(password.activeFocus, "tab reaches password");
            keyDriver.keyClick(Qt.Key_Tab);
            check(showPassword.activeFocus, "tab reaches password visibility");
            keyDriver.keyClick(Qt.Key_Tab);
            check(session.activeFocus, "tab reaches session");
            username.text = ""; root.login();
            check(sddm.attempts === 0, "empty username blocked");
            username.text = "user"; password.text = "test-only";
            session.currentIndex = 1; showPassword.checked = true;
            root.login(); root.login();
            check(sddm.attempts === 1 && sddm.lastSession === 1 && root.busy, "single login with selected session");
            check(!showPassword.checked, "password hidden on submit");
            sddm.loginFailed();
            check(!root.busy && password.text === "" && root.message.length > 0, "failure recovery");
            check(password.activeFocus, "retry focus");
            root.confirmPower("restart");
            check(powerPrompt.visible && sddm.powerCalls === 0, "power confirmation");
            powerPrompt.close();
            users.open(); session.popup.open();
            menuCheck.start();
        }
    }
    Timer {
        id: menuCheck; interval: 100
        onTriggered: {
            check(users.count === 2, "user menu delegates");
            check(session.popup.contentItem.count === 2, "session menu delegates");
            users.close(); session.popup.close();
            root.message = "";
            username.text = "user"; session.currentIndex = 0;
            screenshot.start();
        }
    }
    Timer {
        id: screenshot; interval: 300
        onTriggered: {
            check(card.width <= root.width - 32, "card fits width");
            check(card.height + 48 <= root.height || viewport.contentHeight > root.height, "short screen scroll");
            root.grabToImage(function(result) {
                check(result.saveToFile("SNAPSHOT"), "screenshot saved");
                console.log("RACCON_CHECKS_PASSED");
            });
        }
    }
'''


def check_theme(theme, output, width, height):
    with tempfile.TemporaryDirectory(prefix='raccon-sddm-check-') as temp:
        target = Path(temp) / 'raccon'
        shutil.copytree(theme, target)
        src = 'import QtTest\n' + (target / 'Main.qml').read_text().replace('id: root', 'id: root\n' + MOCKS, 1)
        checks = CHECKS.replace('WIDTH', str(width)).replace('HEIGHT', str(height)).replace('"SNAPSHOT"', json.dumps(str(output)))
        (target / 'Main.qml').write_text(src.rsplit('}', 1)[0] + checks + '}\n')
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', QT_FORCE_STDERR_LOGGING='1')
        process = subprocess.Popen(['sddm-greeter-qt6', '--test-mode', '--theme', str(target)],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        try:
            logs, _ = process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            process.terminate()
            logs, _ = process.communicate(timeout=3)
        if 'RACCON_CHECKS_PASSED' not in logs or re.search(r'CHECK_FAILED|ReferenceError|TypeError|Unable to assign|is not a type', logs):
            raise RuntimeError(logs)
        print(f'{width}x{height}: authentication, menus, focus, power confirmation and snapshot passed: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('theme', type=Path)
    parser.add_argument('--output', type=Path, default=Path('/tmp'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for w, h in ((1920, 1080), (800, 600), (640, 480)):
        check_theme(args.theme, args.output / f'raccon-sddm-{w}x{h}.png', w, h)
