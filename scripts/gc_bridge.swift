// gc_bridge.swift — GCController → stdout JSON for DeepSight Host
//
// Reads game controllers via Apple GameController.framework and outputs
// one JSON line per poll (~250 Hz). Button order matches SDL2/pygame
// convention so the same config mapping works across backends.
//
// SDL2 button order:
//   0=A, 1=B, 2=X, 3=Y, 4=LB, 5=RB, 6=Back, 7=Start, 8=L3, 9=R3, 10=Home,
//   11=LT(digital), 12=RT(digital)
//
// Build:
//   swiftc -O -o scripts/gc_bridge scripts/gc_bridge.swift \
//     -framework AppKit -framework GameController
//
// Install:
//   sudo cp scripts/gc_bridge /usr/local/bin/deepsight_gc_bridge
//
// Usage:
//   deepsight_gc_bridge [--debug]

import GameController
import Foundation
import AppKit

var debugFlag = CommandLine.arguments.contains("--debug")
func eprint(_ msg: String) {
    msg.withCString { fputs($0, stderr); fputc(10, stderr); fflush(stderr) }
}
func dprint(_ msg: String) { if debugFlag { eprint(msg) } }

dprint("gc_bridge: pid=\(getpid())")

// ── Poll a gamepad ────────────────────────────────────────────────────
func pollGamepad(_ gp: GCExtendedGamepad) {
    let axes: [Double] = [
        Double(max(-1, min(1, gp.leftThumbstick.xAxis.value))),
        Double(max(-1, min(1, gp.leftThumbstick.yAxis.value))),
        Double(max(-1, min(1, gp.rightThumbstick.xAxis.value))),
        Double(max(-1, min(1, gp.rightThumbstick.yAxis.value))),
        Double(max(-1, min(1, gp.leftTrigger.value))),
        Double(max(-1, min(1, gp.rightTrigger.value))),
    ]
    let btns: [Int] = [
        gp.buttonA.isPressed ? 1 : 0,
        gp.buttonB.isPressed ? 1 : 0,
        gp.buttonX.isPressed ? 1 : 0,
        gp.buttonY.isPressed ? 1 : 0,
        gp.leftShoulder.isPressed ? 1 : 0,
        gp.rightShoulder.isPressed ? 1 : 0,
        gp.buttonOptions?.isPressed ?? false ? 1 : 0,
        gp.buttonMenu.isPressed ? 1 : 0,
        gp.leftThumbstickButton?.isPressed ?? false ? 1 : 0,
        gp.rightThumbstickButton?.isPressed ?? false ? 1 : 0,
        gp.buttonHome?.isPressed ?? false ? 1 : 0,
        gp.leftTrigger.isPressed ? 1 : 0,
        gp.rightTrigger.isPressed ? 1 : 0,
    ]
    let dp = gp.dpad
    let hatX = (dp.right.isPressed ? 1 : 0) - (dp.left.isPressed ? 1 : 0)
    let hatY = (dp.up.isPressed ? 1 : 0) - (dp.down.isPressed ? 1 : 0)

    let axStr = axes.map { String(format: "%.4f", $0) }.joined(separator: ",")
    let btnStr = btns.map { String($0) }.joined(separator: ",")
    let line = "{\"ts\":\(String(format: "%.3f", Date().timeIntervalSince1970)),\"axes\":[\(axStr)],\"buttons\":[\(btnStr)],\"hat\":[\(hatX),\(hatY)]}"
    line.withCString { fputs($0, stdout); fputc(10, stdout) }
    fflush(stdout)
    // Also write to file for open-launched testing
    if let fh = FileHandle(forWritingAtPath: "/tmp/gc_bridge_output.txt") {
        fh.seekToEndOfFile()
        (line + "\n").withCString { fh.write(Data(bytes: $0, count: Int(strlen($0)))) }
    }
}

// ── App Delegate ───────────────────────────────────────────────────────
final class BridgeDelegate: NSObject, NSApplicationDelegate {
    var pollTimer: Timer?
    var connectObserver: NSObjectProtocol?

    func applicationDidFinishLaunching(_ n: Notification) {
        // Visible window — GCController delivery requires foreground app
        let win = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 200, height: 100),
            styleMask: [.titled, .closable],
            backing: .buffered,
            defer: true
        )
        win.title = "DeepSight GC Bridge"
        win.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        // Check for already-connected controller
        let controllers = GCController.controllers()
        dprint("controllers().count = \(controllers.count)")
        if let c = controllers.first, let gp = c.extendedGamepad {
            dprint("HAS_CONTROLLER: \(c.vendorName ?? "?")")
            startPolling(gp)
            return
        }

        // Wait for connection
        dprint("WAITING for controller...")
        connectObserver = NotificationCenter.default.addObserver(
            forName: .GCControllerDidConnect, object: nil, queue: .main
        ) { [weak self] n in
            guard let self,
                  let c = n.object as? GCController,
                  let gp = c.extendedGamepad,
                  self.pollTimer == nil else { return }
            dprint("CONNECTED: \(c.vendorName ?? "?")")
            self.startPolling(gp)
        }
        GCController.startWirelessControllerDiscovery()
    }

    func startPolling(_ gp: GCExtendedGamepad) {
        if let obs = connectObserver {
            NotificationCenter.default.removeObserver(obs)
            connectObserver = nil
        }
        dprint("POLLING...")
        pollTimer = Timer.scheduledTimer(withTimeInterval: 0.004, repeats: true) { _ in
            pollGamepad(gp)
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }
}

// ── Main ──────────────────────────────────────────────────────────────
let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = BridgeDelegate()
app.delegate = delegate
app.run()
