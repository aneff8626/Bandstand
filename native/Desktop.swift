import AppKit
import WebKit
import Foundation
import CoreBluetooth

func bandstandDataRoot(_ root:URL)->URL {
 let userConfig=URL(fileURLWithPath:NSHomeDirectory()+"/Library/Application Support/Bandstand/local-settings.json")
 let config=FileManager.default.fileExists(atPath:userConfig.path) ? userConfig : root.appendingPathComponent("local-settings.json")
 let settings=(try? Data(contentsOf:config)).flatMap { try? JSONSerialization.jsonObject(with:$0) as? [String:Any] }
 return URL(fileURLWithPath:ProcessInfo.processInfo.environment["BANDSTAND_DATA_DIR"] ?? settings?["data_dir"] as? String ?? NSHomeDirectory()+"/Library/Application Support/Bandstand/data")
}

final class MuseWebView: WKWebView {
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }
    override func otherMouseDown(with event: NSEvent) {
        if event.buttonNumber == 3 || event.buttonNumber == 4 { return }
        super.otherMouseDown(with:event)
    }
    override func otherMouseUp(with event: NSEvent) {
        guard event.buttonNumber == 3 || event.buttonNumber == 4 else { super.otherMouseUp(with:event); return }
        let direction = event.buttonNumber == 3 ? -1 : 1
        evaluateJavaScript("window.bandstandNavigate?.(\(direction))")
    }

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
        window.title=CommandLine.arguments.contains("--development-source") ? "Bandstand · Development" : "Bandstand";window.contentView=web;window.center();window.makeKeyAndOrderFront(nil)
        let mainMenu=NSMenu();let appItem=NSMenuItem();mainMenu.addItem(appItem);let appMenu=NSMenu();appMenu.addItem(withTitle:"Quit Bandstand",action:#selector(NSApplication.terminate(_:)),keyEquivalent:"q");appItem.submenu=appMenu
        let editItem=NSMenuItem();mainMenu.addItem(editItem);let edit=NSMenu(title:"Edit");edit.addItem(withTitle:"Copy",action:#selector(NSText.copy(_:)),keyEquivalent:"c");edit.addItem(withTitle:"Paste",action:#selector(NSText.paste(_:)),keyEquivalent:"v");edit.addItem(withTitle:"Select All",action:#selector(NSText.selectAll(_:)),keyEquivalent:"a");editItem.submenu=edit;NSApp.mainMenu=mainMenu
        process=Process();let bundledPython=Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/python/bin/python3.12")
        process.executableURL=FileManager.default.isExecutableFile(atPath:bundledPython.path) ? bundledPython : root.appendingPathComponent(".venv/bin/python");process.arguments=[root.appendingPathComponent("desktop_service.py").path];process.currentDirectoryURL=root
        var environment=ProcessInfo.processInfo.environment; environment["MUSE_NATIVE_BLUETOOTH"]="1"; environment["PYTHONDONTWRITEBYTECODE"]="1"; process.environment=environment
        input=Pipe();output=Pipe();process.standardInput=input;process.standardOutput=output
        let privateURL=bandstandDataRoot(root)
        try? FileManager.default.createDirectory(at:privateURL,withIntermediateDirectories:true,attributes:[.posixPermissions:0o700])
        let log=privateURL.appendingPathComponent("desktop.log");FileManager.default.createFile(atPath:log.path,contents:nil,attributes:[.posixPermissions:0o600]);process.standardError=try? FileHandle(forWritingTo:log)
        output.fileHandleForReading.readabilityHandler={ [weak self] handle in
            let data=handle.availableData;guard !data.isEmpty,let s=self else{return}
            DispatchQueue.main.async {s.pending.append(data);while let range=s.pending.range(of:Data([10])) {let line=s.pending.subdata(in:0..<range.lowerBound);s.pending.removeSubrange(0..<range.upperBound);if let text=String(data:line,encoding:.utf8){s.web.evaluateJavaScript("window.museReceive(\(text))",completionHandler:nil)}}}
        }
        do {try process.run()} catch {let alert=NSAlert();alert.messageText="Bandstand could not start";alert.informativeText="The local analysis service is missing or could not launch. Reinstall the app or rebuild from source.";alert.runModal();NSApp.terminate(nil);return}
        transportOutput={ [weak self] event in self?.sendService(["id":-1,"path":"bluetooth_native","body":event]) }
        if CommandLine.arguments.contains("--development-smoke-output") {}
        else if CBManager.authorization == .allowedAlways { bluetooth=Bridge() }
        else { emit(["type":"status","state":"authorization_unavailable","message":"Click Connect Muse to set up Bluetooth access for Muse Lab.","authorization":CBManager.authorization.rawValue]) }
        typingMonitor=TypingMonitor(emit:{[weak self] event in self?.sendService(["id":-1,"path":"typing/native_event","body":event])},stopped:{[weak self] in self?.sendService(["id":-1,"path":"typing/stop","body":["reason":"Stopped from menu bar"]])})
        web.load(URLRequest(url:URL(string:"muselab://app/")!));NSApp.activate(ignoringOtherApps:true)
    }
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard let index=CommandLine.arguments.firstIndex(of:"--development-smoke-output"),index+1<CommandLine.arguments.count else{return}
        webView.evaluateJavaScript("document.documentElement.getAttribute('data-development-marker')") {value,error in
            let result:[String:Any] = ["marker":value as? String ?? "", "root":self.root.path,"runtime":self.process.executableURL?.path ?? "","data":bandstandDataRoot(self.root).path,"title":self.window.title,"error":error?.localizedDescription ?? ""]
            if let data=try? JSONSerialization.data(withJSONObject:result) {try? data.write(to:URL(fileURLWithPath:CommandLine.arguments[index+1]))}
            NSApp.terminate(nil)
        }
    }
    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, message.frameInfo.request.url?.scheme == "muselab", let body=message.body as? [String:Any] else{return}
        if let path=body["path"] as? String,path.hasPrefix("system_typing/") {
            let result:[String:Any]
            if path == "system_typing/request_access" {result=typingMonitor?.requestAccess() ?? ["available":false]}
            else if path == "system_typing/start" {result=typingMonitor?.start() ?? ["available":false]}
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
let sourceRoot=executable.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
var root=FileManager.default.fileExists(atPath:bundledRoot.appendingPathComponent("desktop_service.py").path) ? bundledRoot : sourceRoot
// Contributor mode is explicit; normal installed launches always use bundled code.
if let index=CommandLine.arguments.firstIndex(of:"--development-source") {
 guard index+1<CommandLine.arguments.count else {fputs("Missing development checkout path.\n",stderr);exit(2)}
 let candidate=URL(fileURLWithPath:CommandLine.arguments[index+1]).standardizedFileURL.resolvingSymlinksInPath()
 let required=["desktop_service.py","web/index.html","backend.json"]
 guard required.allSatisfy({FileManager.default.fileExists(atPath:candidate.appendingPathComponent($0).path)}) else {
  fputs("Development source needs desktop_service.py, web/index.html and a non-production backend.json.\n",stderr);exit(2)
 }
 // Validate with sealed code and bundled Python BEFORE executing any checkout code.
 let validator=Process();validator.executableURL=Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/python/bin/python3.12")
 validator.arguments=["-I","-B","-c","import sys;sys.path.insert(0,sys.argv[1]);import backend_config;c=backend_config.load(sys.argv[2]);assert c['name'] in ('development','staging'), 'Production backend refused'",bundledRoot.path,candidate.path]
 validator.standardOutput=FileHandle.nullDevice
 do {try validator.run();validator.waitUntilExit()} catch {fputs("Contributor mode needs the bundled Python runtime.\n",stderr);exit(2)}
 guard validator.terminationStatus==0 else {fputs("Development backend validation failed; no checkout code was run.\n",stderr);exit(2)}
 root=candidate
 setenv("BANDSTAND_DATA_DIR",NSHomeDirectory()+"/Library/Application Support/Bandstand Development/data",1)
}
if CommandLine.arguments.contains("--development-smoke-output") && !CommandLine.arguments.contains("--development-source") {exit(2)}
let app=NSApplication.shared
app.setActivationPolicy(.regular)
let delegate=App(root:root);app.delegate=delegate;app.run()

 }
}
