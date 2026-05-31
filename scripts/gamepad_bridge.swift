#!/usr/bin/env swift
/// GameController → stdout JSON bridge for DeepSight Host
///
/// Reads controller state via Apple GameController framework and prints one
/// JSON line per poll interval. Works with controllers that macOS recognizes
/// but SDL2/pygame cannot access (HID permission issue on modern macOS).
///
/// Usage:
///   swift scripts/gamepad_bridge.swift [--hz 50]
///   Output: {"ts":1234.5,"axes":[0.0,-0.5,0.2,0.0,0.3,0.0],"buttons":[false,...],"hat":[0,0]}

import GameController
import Foundation

var stderrHandle = FileHandle.standardError
func log(_ msg: String) {
    if let data = (msg + "\n").data(using: .utf8) {
        stderrHandle.write(data)
    }
}

let hz: Double = {
    let args = CommandLine.arguments
    if let idx = args.firstIndex(of: "--hz"), idx + 1 < args.count {
        return Double(args[idx + 1]) ?? 50
    }
    return 50
}()

let pollInterval = 1.0 / hz

var controller: GCController?
var extended: GCExtendedGamepad?

// ── Discovery (pump run loop until controller appears) ──

let existing = GCController.controllers()
if let c = existing.first {
    controller = c
    extended = c.extendedGamepad
    log("bridge: using already-connected controller: \(c.vendorName ?? "?")")
}

if controller == nil {
    log("bridge: waiting for controller...")
    var done = false

    let center = NotificationCenter.default
    var observer: NSObjectProtocol?
    observer = center.addObserver(
        forName: .GCControllerDidBecomeCurrent,
        object: nil,
        queue: .main
    ) { note in
        if let c = note.object as? GCController {
            controller = c
            extended = c.extendedGamepad
            done = true
        }
    }

    GCController.startWirelessControllerDiscovery { }

    // Pump run loop until controller found or timeout
    let deadline = Date().timeIntervalSince1970 + 10
    while !done && Date().timeIntervalSince1970 < deadline {
        RunLoop.current.run(mode: .default, before: Date(timeIntervalSinceNow: 0.1))
    }

    if let obs = observer {
        center.removeObserver(obs)
    }
}

guard let c = controller, let gamepad = extended else {
    log("bridge: no controller with extended gamepad profile")
    exit(1)
}

let name = c.vendorName ?? "Unknown"
log("bridge: connected to \(name)")
FileHandle.standardError.synchronizeFile()

// ── Poll loop ──

var nextPoll = Date().timeIntervalSince1970

while true {
    // Pump run loop so GCController data is refreshed
    RunLoop.current.run(mode: .default, before: Date(timeIntervalSinceNow: 0.001))

    let dpad = gamepad.dpad
    let ls = gamepad.leftThumbstick
    let rs = gamepad.rightThumbstick

    // Axes: left_x, left_y, right_x, right_y, left_trigger, right_trigger
    let axes: [Double] = [
        Double(ls.xAxis.value),
        Double(ls.yAxis.value),
        Double(rs.xAxis.value),
        Double(rs.yAxis.value),
        Double(gamepad.leftTrigger.value),
        Double(gamepad.rightTrigger.value),
    ]

    // Buttons: A, B, X, Y, LB, RB, LT(dig), RT(dig), Back, Start, L3, R3, Logo
    let buttons: [Bool] = [
        gamepad.buttonA.isPressed,
        gamepad.buttonB.isPressed,
        gamepad.buttonX.isPressed,
        gamepad.buttonY.isPressed,
        gamepad.leftShoulder.isPressed,
        gamepad.rightShoulder.isPressed,
        gamepad.leftTrigger.isPressed,
        gamepad.rightTrigger.isPressed,
        gamepad.buttonOptions?.isPressed ?? false,
        gamepad.buttonMenu.isPressed,
        gamepad.leftThumbstickButton?.isPressed ?? false,
        gamepad.rightThumbstickButton?.isPressed ?? false,
        gamepad.buttonHome?.isPressed ?? false,
    ]

    let hatX = (dpad.right.isPressed ? 1 : 0) - (dpad.left.isPressed ? 1 : 0)
    let hatY = (dpad.up.isPressed ? 1 : 0) - (dpad.down.isPressed ? 1 : 0)

    let axesStr = axes.map { String(format: "%.4f", $0) }.joined(separator: ",")
    let btnsStr = buttons.map { $0 ? "1" : "0" }.joined(separator: ",")
    let ts = String(format: "%.3f", Date().timeIntervalSince1970)

    print("{\"ts\":\(ts),\"axes\":[\(axesStr)],\"buttons\":[\(btnsStr)],\"hat\":[\(hatX),\(hatY)]}")
    fflush(stdout)

    // Sleep till next poll
    nextPoll += pollInterval
    let now = Date().timeIntervalSince1970
    let sleepTime = nextPoll - now
    if sleepTime > 0 {
        usleep(UInt32(sleepTime * 1_000_000))
    } else {
        nextPoll = now  // reset if we fell behind
    }
}
