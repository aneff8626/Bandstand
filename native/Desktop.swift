import AppKit
import WebKit
import Foundation
import CoreBluetooth

func bandstandDataRoot(_ root:URL)->URL {
 let settings=(try? Data(contentsOf:root.appendingPathComponent("local-settings.json"))).flatMap { try? JSONSerialization.jsonObject(with:$0) as? [String:Any] }
 return URL(fileURLWithPath:ProcessInfo.processInfo.environment["BANDSTAND_DATA_DIR"] ?? settings?["data_dir"] as? String ?? NSHomeDirectory()+"/Library/Application Support/Bandstand/data")
}

final class MuseWebView: WKWebView {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
}

final class LocalFiles: NSObject, WKURLSchemeHandler {
    let root: URL
    init(root:URL) { self.root=root }
    func webView(_ webView: WKWebView, start urlSchemeTask: WKURLSchemeTask) {
        guard let url=urlSchemeTask.request.url else { return }
        let path=url.path
        let file:URL
        if path.hasPrefix("/stimuli/") { let privateFile=bandstandDataRoot(root).appendingPathComponent("stimuli").appendingPathComponent(url.lastPathComponent);file=FileManager.default.fileExists(atPath:privateFile.path) ? privateFile : root.appendingPathComponent("stimuli").appendingPathComponent(url.lastPathComponent) }
        else { file=root.appendingPathComponent("web").appendingPathComponent(path=="/" ? "index.html" : url.lastPathComponent) }
        guard let data=try? Data(contentsOf:file) else { urlSchemeTask.didFailWithError(NSError(domain:"MuseLab",code:404)); return }
        let types=["html":"text/html", "js":"text/javascript", "css":"text/css", "png":"image/png"]
        let response=HTTPURLResponse(url:url,statusCode:200,httpVersion:nil,headerFields:["Content-Type": (types[file.pathExtension] ?? "application/octet-stream")+"; charset=utf-8", "Cache-Control":"no-store"])!
        urlSchemeTask.didReceive(response);urlSchemeTask.didReceive(data);urlSchemeTask.didFinish()
    }
    func webView(_ webView: WKWebView, stop urlSchemeTask: WKURLSchemeTask) {}
}
final class App: NSObject, NSApplicationDelegate, WKScriptMessageHandler, WKNavigationDelegate, WKUIDelegate {
    var window:NSWindow!; var web:WKWebView!; var process:Process!; var input:Pipe!; var output:Pipe!; var pending=Data()
    var bluetooth:Bridge?
    var typingMonitor:TypingMonitor?
    let root:URL
    init(root:URL) {self.root=root}
    func applicationDidFinishLaunching(_ notification: Notification) {
        let config=WKWebViewConfiguration();config.setURLSchemeHandler(LocalFiles(root:root),forURLScheme:"muselab")
        config.userContentController.add(self,name:"muse")
        let script="""
        (()=>{let id=0;const pending=new Map();window.museNative=(path,body)=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});window.webkit.messageHandlers.muse.postMessage({id:n,path,body:body??null});setTimeout(()=>{if(pending.has(n)){pending.delete(n);reject(Error('Local analysis service timed out'))}},30000)});window.museReceive=(r)=>{const p=pending.get(r.id);if(!p)return;pending.delete(r.id);r.error?p.reject(Error(r.error)):p.resolve(r.result)};})();
        """
        config.userContentController.addUserScript(WKUserScript(source:script,injectionTime:.atDocumentStart,forMainFrameOnly:true))
        web=MuseWebView(frame:.zero,configuration:config);web.navigationDelegate=self;web.uiDelegate=self
        window=NSWindow(contentRect:NSRect(x:0,y:0,width:1450,height:960),styleMask:[.titled,.closable,.miniaturizable,.resizable],backing:.buffered,defer:false)
        window.title="Bandstand";window.contentView=web;window.center();window.makeKeyAndOrderFront(nil)
        let mainMenu=NSMenu();let appItem=NSMenuItem();mainMenu.addItem(appItem);let appMenu=NSMenu();appMenu.addItem(withTitle:"Quit Bandstand",action:#selector(NSApplication.terminate(_:)),keyEquivalent:"q");appItem.submenu=appMenu
        let editItem=NSMenuItem();mainMenu.addItem(editItem);let edit=NSMenu(title:"Edit");edit.addItem(withTitle:"Copy",action:#selector(NSText.copy(_:)),keyEquivalent:"c");edit.addItem(withTitle:"Paste",action:#selector(NSText.paste(_:)),keyEquivalent:"v");edit.addItem(withTitle:"Select All",action:#selector(NSText.selectAll(_:)),keyEquivalent:"a");editItem.submenu=edit;NSApp.mainMenu=mainMenu
        process=Process();let bundledPython=root.deletingLastPathComponent().appendingPathComponent("python/bin/python3.12")
        process.executableURL=FileManager.default.isExecutableFile(atPath:bundledPython.path) ? bundledPython : root.appendingPathComponent(".venv/bin/python");process.arguments=[root.appendingPathComponent("desktop_service.py").path];process.currentDirectoryURL=root
        var environment=ProcessInfo.processInfo.environment; environment["MUSE_NATIVE_BLUETOOTH"]="1"; process.environment=environment
        input=Pipe();output=Pipe();process.standardInput=input;process.standardOutput=output
        let settingsURL=root.appendingPathComponent("local-settings.json")
        let settings=(try? Data(contentsOf:settingsURL)).flatMap { try? JSONSerialization.jsonObject(with:$0) as? [String:Any] }
        let privatePath=environment["BANDSTAND_DATA_DIR"] ?? settings?["data_dir"] as? String ?? NSHomeDirectory()+"/Library/Application Support/Bandstand/data"
        let privateURL=URL(fileURLWithPath:privatePath)
        try? FileManager.default.createDirectory(at:privateURL,withIntermediateDirectories:true,attributes:[.posixPermissions:0o700])
        let log=privateURL.appendingPathComponent("desktop.log");FileManager.default.createFile(atPath:log.path,contents:nil,attributes:[.posixPermissions:0o600]);process.standardError=try? FileHandle(forWritingTo:log)
        output.fileHandleForReading.readabilityHandler={ [weak self] handle in
            let data=handle.availableData;guard !data.isEmpty,let s=self else{return}
            DispatchQueue.main.async {s.pending.append(data);while let range=s.pending.range(of:Data([10])) {let line=s.pending.subdata(in:0..<range.lowerBound);s.pending.removeSubrange(0..<range.upperBound);if let text=String(data:line,encoding:.utf8){s.web.evaluateJavaScript("window.museReceive(\(text))",completionHandler:nil)}}}
        }
        do {try process.run()} catch {let alert=NSAlert();alert.messageText="Bandstand could not start";alert.informativeText="The local analysis service is missing or could not launch. Reinstall the app or rebuild from source.";alert.runModal();NSApp.terminate(nil);return}
        transportOutput={ [weak self] event in self?.sendService(["id":-1,"path":"bluetooth_native","body":event]) }
        if CBManager.authorization == .allowedAlways { bluetooth=Bridge() }
        else { emit(["type":"status","state":"authorization_unavailable","message":"Click Connect Muse to set up Bluetooth access for Muse Lab.","authorization":CBManager.authorization.rawValue]) }
        typingMonitor=TypingMonitor(emit:{[weak self] event in self?.sendService(["id":-1,"path":"typing/native_event","body":event])},stopped:{[weak self] in self?.sendService(["id":-1,"path":"typing/stop","body":["reason":"Stopped from menu bar"]])})
        web.load(URLRequest(url:URL(string:"muselab://app/")!));NSApp.activate(ignoringOtherApps:true)
    }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, message.frameInfo.request.url?.scheme == "muselab", let body=message.body as? [String:Any] else{return}
        if let path=body["path"] as? String,path.hasPrefix("system_typing/") {
            let result:[String:Any]
            if path == "system_typing/start" {result=typingMonitor?.start() ?? ["available":false]}
            else if path == "system_typing/stop" {typingMonitor?.stop();result=["active":false]}
            else {result=typingMonitor?.permissions() ?? ["available":false]}
            let reply:[String:Any]=["id":body["id"] ?? 0,"result":result]
            if let data=try? JSONSerialization.data(withJSONObject:reply),let text=String(data:data,encoding:.utf8){web.evaluateJavaScript("window.museReceive(\(text))",completionHandler:nil)}
            return
        }
        if body["path"] as? String == "typing/stop" {typingMonitor?.stop()}
        if body["path"] as? String == "bluetooth_disconnect" {
            bluetooth?.disconnect()
            let reply:[String:Any] = ["id":body["id"] ?? 0,"result":["disconnected":true]]
            if let data=try? JSONSerialization.data(withJSONObject:reply),let text=String(data:data,encoding:.utf8){web.evaluateJavaScript("window.museReceive(\(text))",completionHandler:nil)}
            return
        }
        if body["path"] as? String == "bluetooth_connect" {
            let auth=CBManager.authorization
            if auth == .denied || auth == .restricted {
                emit(["type":"status","state":"authorization_unavailable","message":"Bandstand Bluetooth access is blocked. Enable it in System Settings → Privacy & Security → Bluetooth.","authorization":auth.rawValue])
                NSWorkspace.shared.open(URL(string:"x-apple.systempreferences:com.apple.preference.security?Privacy_Bluetooth")!)
            } else if bluetooth == nil { bluetooth=Bridge() } else { bluetooth?.reconnect() }
            let reply:[String:Any] = ["id":body["id"] ?? 0,"result":["authorization":auth.rawValue]]
            if let data=try? JSONSerialization.data(withJSONObject:reply), let text=String(data:data,encoding:.utf8) {web.evaluateJavaScript("window.museReceive(\(text))",completionHandler:nil)}
            return
        }
        sendService(body)
    }
    func sendService(_ body:[String:Any]) {
        guard let data=try? JSONSerialization.data(withJSONObject:body) else{return}
        do {try input.fileHandleForWriting.write(contentsOf:data+Data([10]))} catch {NSLog("Service pipe failed: \(error)")}
    }
    func webView(_ webView:WKWebView,decidePolicyFor navigationAction:WKNavigationAction,decisionHandler:@escaping(WKNavigationActionPolicy)->Void){
        if let url=navigationAction.request.url, ["http","https"].contains(url.scheme ?? "") {NSWorkspace.shared.open(url);decisionHandler(.cancel)}else{decisionHandler(.allow)}
    }
    func webView(_ webView:WKWebView,createWebViewWith configuration:WKWebViewConfiguration,for navigationAction:WKNavigationAction,windowFeatures:WKWindowFeatures)->WKWebView? {if let url=navigationAction.request.url, ["http","https"].contains(url.scheme ?? ""){NSWorkspace.shared.open(url)};return nil}
    func webView(_ webView:WKWebView,runOpenPanelWith parameters:WKOpenPanelParameters,initiatedByFrame frame:WKFrameInfo,completionHandler:@escaping([URL]?)->Void){let panel=NSOpenPanel();panel.allowsMultipleSelection=parameters.allowsMultipleSelection;panel.canChooseDirectories=false;panel.beginSheetModal(for:window){response in completionHandler(response == .OK ? panel.urls:nil)}}
    func applicationShouldTerminateAfterLastWindowClosed(_ sender:NSApplication)->Bool {true}
    func applicationWillTerminate(_ notification:Notification) {typingMonitor?.stop();try? input?.fileHandleForWriting.close();if process?.isRunning == true {let deadline=Date().addingTimeInterval(3);while process.isRunning && Date()<deadline {Thread.sleep(forTimeInterval:0.05)};if process.isRunning {process.terminate()}}}
}
@main
struct MuseMain {
 static func main() {
let executable=URL(fileURLWithPath:CommandLine.arguments[0]).resolvingSymlinksInPath()
let bundledRoot=Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/app")
let sourceRoot=CommandLine.arguments.count>1 ? URL(fileURLWithPath:CommandLine.arguments[1]) : executable.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
let root=FileManager.default.fileExists(atPath:bundledRoot.appendingPathComponent("desktop_service.py").path) ? bundledRoot : sourceRoot
let app=NSApplication.shared
app.setActivationPolicy(.regular)
let delegate=App(root:root);app.delegate=delegate;app.run()

 }
}
