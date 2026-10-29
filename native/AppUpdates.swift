import AppKit
import Sparkle

// Keep updates out of development launches. No participant information goes into
// the feed request. Sparkle verifies the archive before extracting it.
final class AppUpdates: NSObject, SPUUpdaterDelegate {
    var controller: SPUStandardUpdaterController!
    var send: (([String: Any]) -> Void)?
    private var timer: Timer?
    private var started = false
    private var busy = true
    private var lastReply = Date.distantPast
    private var install: (() -> Void)?
    static let requestID = 2_000_000_000

    func start(menu: NSMenu, send: @escaping ([String: Any]) -> Void) {
        guard !CommandLine.arguments.contains("--development-source"),
              Bundle.main.object(forInfoDictionaryKey: "SUPublicEDKey") != nil else { return }
        self.send = send
        controller = SPUStandardUpdaterController(startingUpdater: false, updaterDelegate: self, userDriverDelegate: nil)
        let item = NSMenuItem(title: "Check for Updates…", action: #selector(SPUStandardUpdaterController.checkForUpdates(_:)), keyEquivalent: "")
        item.target = controller
        menu.insertItem(item, at: 0)
        timer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in self?.poll() }
        poll()
    }

    private func poll() {
        send?(["id": Self.requestID, "path": install == nil ? "updates/status" : "updates/prepare"])
    }

    func receive(_ reply: [String: Any]) -> Bool {
        guard reply["id"] as? Int == Self.requestID else { return false }
        guard let result = reply["result"] as? [String: Any], let busy = result["busy"] as? Bool else {
            self.busy = true
            return true
        }
        self.busy = busy; lastReply = Date()
        if !started { started = true; controller.startUpdater() }
        if result["ready"] as? Bool == true, let handler = install {
            install = nil; timer?.invalidate(); handler()
        }
        return true
    }

    func updater(_ updater: SPUUpdater, didAbortWithError error: Error) {
        install = nil
        send?(["id": Self.requestID, "path": "updates/cancel"])
        if timer?.isValid != true {
            timer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in self?.poll() }
        }
    }

    func updater(_ updater: SPUUpdater, mayPerform updateCheck: SPUUpdateCheck) throws {
        if busy || Date().timeIntervalSince(lastReply) > 5 {
            throw NSError(domain: "BandstandUpdates", code: 1, userInfo: [NSLocalizedDescriptionKey: "Finish recording or training before checking for updates."])
        }
    }

    func updater(_ updater: SPUUpdater, shouldPostponeRelaunchForUpdate item: SUAppcastItem, untilInvokingBlock installHandler: @escaping () -> Void) -> Bool {
        install = installHandler
        poll() // The service atomically reserves the idle state before we quit.
        return true
    }
}
