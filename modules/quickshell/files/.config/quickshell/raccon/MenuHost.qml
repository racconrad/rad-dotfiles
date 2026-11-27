import QtQuick
import Quickshell
import Quickshell.Io

// Menu plus the live data its embedded side pages need.
Menu {
  id: root

  readonly property string home: Quickshell.env("HOME")
  property var agenda: ({})
  property var timerState: ({})

  Process {
    running: true
    command: [root.home + "/.local/bin/desktop-menu", "calendar-watch"]
    stdout: SplitParser { onRead: line => { try { root.agenda = JSON.parse(line); } catch (e) {} } }
  }

  Process {
    running: true
    command: [root.home + "/.local/bin/countdown", "--listen"]
    stdout: SplitParser { onRead: line => { try { root.timerState = JSON.parse(line); } catch (e) {} } }
  }

  calendarPage: Component { MenuCalendar { model: root.agenda } }
  timerPage: Component { MenuTimer { model: root.timerState } }
}
