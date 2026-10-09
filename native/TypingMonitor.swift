import AppKit
import ApplicationServices
import Carbon

// Opt-in, passive keyboard observation. Permission setup is user-initiated. No clipboard reads,
// field-value reads, injected keys, network transport, or automatic startup.
final class TypingMonitor {
    var tap: CFMachPort?
    var source: CFRunLoopSource?
    var timer: Timer?
    var statusItem: NSStatusItem?
    var active = false
    var lastContext = ""
    var lastReason = ""
    var emit: ([String:Any])->Void
    var stopped: ()->Void
    init(emit:@escaping ([String:Any])->Void, stopped:@escaping ()->Void) {self.emit=emit;self.stopped=stopped}
    func permissions()->[String:Any] {
        let listen=CGPreflightListenEventAccess(),access=AXIsProcessTrusted()
        return ["inputMonitoring":listen,"accessibility":access,"available":listen && access,"active":active,
                "appPath":Bundle.main.bundleURL.path,"bundleIdentifier":Bundle.main.bundleIdentifier ?? "unknown",
                "processID":ProcessInfo.processInfo.processIdentifier,"secureInput":IsSecureEventInputEnabled(),
                "diagnosticsVersion":2,
                "reason":listen && access ? "Ready. Protected fields, terminals and Muse Lab controls are skipped." : "Enable typing access to open macOS settings. Allow Muse Lab (or Bandstand) in Accessibility and Input Monitoring; macOS may require reopening the app."]
    }
    func requestAccess()->[String:Any] {
        if !AXIsProcessTrusted() {
            NSWorkspace.shared.open(URL(string:"x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")!)
        } else if !CGPreflightListenEventAccess() {
            NSWorkspace.shared.open(URL(string:"x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent")!)
        }
        return permissions()
    }
    func start()->[String:Any] {
        if active {return permissions()}
        guard CGPreflightListenEventAccess() && AXIsProcessTrusted() else {return permissions()}
        let mask=(CGEventMask(1)<<CGEventType.keyDown.rawValue) | (CGEventMask(1)<<CGEventType.leftMouseDown.rawValue) | (CGEventMask(1)<<CGEventType.rightMouseDown.rawValue)
        let context=Unmanaged.passUnretained(self).toOpaque()
        tap=CGEvent.tapCreate(tap:.cgSessionEventTap,place:.headInsertEventTap,options:.listenOnly,eventsOfInterest:mask,callback:{ _,type,event,info in
            guard let info=info else {return Unmanaged.passUnretained(event)}
            let monitor=Unmanaged<TypingMonitor>.fromOpaque(info).takeUnretainedValue()
            if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
                monitor.stop();monitor.stopped();return Unmanaged.passUnretained(event)
            }
            monitor.handle(type,event);return Unmanaged.passUnretained(event)
        },userInfo:context)
        guard let tap=tap else {var r=permissions();r["reason"]="macOS did not allow a keyboard event tap. Recording has not started.";return r}
        source=CFMachPortCreateRunLoopSource(kCFAllocatorDefault,tap,0)
        CFRunLoopAddSource(CFRunLoopGetMain(),source,.commonModes);CGEvent.tapEnable(tap:tap,enable:true);active=true
        statusItem=NSStatusBar.system.statusItem(withLength:NSStatusItem.variableLength);statusItem?.button?.title="● EEG typing"
        let menu=NSMenu();let label=NSMenuItem(title:"Typing capture is ON · local only",action:nil,keyEquivalent:"");label.isEnabled=false;menu.addItem(label)
        let stop=NSMenuItem(title:"Stop typing capture & save",action:#selector(stopFromMenu),keyEquivalent:"");stop.target=self;menu.addItem(stop);statusItem?.menu=menu
        timer=Timer.scheduledTimer(withTimeInterval:0.5,repeats:true){[weak self] _ in self?.checkContext()}
        checkContext();return permissions()
    }
    @objc func stopFromMenu(){stop();stopped()}
    func stop(){
        guard active || tap != nil else {return}
        emit(["kind":"boundary","onset":Date().timeIntervalSince1970]);active=false
        timer?.invalidate();timer=nil
        if let tap=tap {CGEvent.tapEnable(tap:tap,enable:false);CFMachPortInvalidate(tap)}
        if let source=source {CFRunLoopRemoveSource(CFRunLoopGetMain(),source,.commonModes)}
        tap=nil;source=nil
        if let item=statusItem {NSStatusBar.system.removeStatusItem(item)};statusItem=nil;lastContext=""
    }
    func attribute(_ element:AXUIElement,_ key:String)->CFTypeRef? {
        var value:CFTypeRef?;guard AXUIElementCopyAttributeValue(element,key as CFString,&value) == .success else{return nil};return value
    }
    func safeContext()->(String,String) {
        if IsSecureEventInputEnabled(){return ("","Secure input active — capture paused")}
        guard CGPreflightListenEventAccess() && AXIsProcessTrusted() else{return ("","Capture access unavailable")}
        guard let app=NSWorkspace.shared.frontmostApplication,let bundle=app.bundleIdentifier else{return ("","No active text field")}
        if app.processIdentifier==ProcessInfo.processInfo.processIdentifier{return ("","Use another app, or switch to editor recording")}
        let excluded=["com.apple.Terminal","com.googlecode.iterm2","com.mitchellh.ghostty","dev.warp.Warp-Stable","com.1password.1password","com.agilebits.onepassword7","com.apple.loginwindow","com.apple.systempreferences"]
        if excluded.contains(bundle){return ("","Protected app — capture paused")}
        let application=AXUIElementCreateApplication(app.processIdentifier)
        // App-level focus can be a web/document wrapper. Resolve the actual focused
        // descendant, never an arbitrary editable sibling or a document's contents.
        let roots=[AXUIElementCreateSystemWide(),application]
        var candidates:[AXUIElement]=[]
        for root in roots {
            var chain:[AXUIElement]=[]
            var current=root
            for _ in 0..<8 {
                guard let value=attribute(current,kAXFocusedUIElementAttribute),
                      CFGetTypeID(value)==AXUIElementGetTypeID() else {break}
                let next=value as! AXUIElement
                if CFEqual(current,next) {break}
                current=next
                var pid:pid_t=0
                if AXUIElementGetPid(current,&pid) == .success && pid==app.processIdentifier {
                    chain.insert(current,at:0)
                }
            }
            candidates.append(contentsOf:chain)
        }
        // Chromium can return its application/web wrapper instead of the focused
        // editable node. Search only the frontmost window, accepting AXFocused
        // nodes rather than arbitrary text fields. Never read field values.
        if bundle.hasPrefix("com.google.Chrome"),
           let windowValue=attribute(application,kAXFocusedWindowAttribute),
           CFGetTypeID(windowValue)==AXUIElementGetTypeID() {
            var queue=[windowValue as! AXUIElement]
            var cursor=0
            let deadline=Date().addingTimeInterval(0.08)
            var focused:[AXUIElement]=[]
            while cursor<queue.count && cursor<1500 && Date()<deadline {
                let node=queue[cursor];cursor+=1
                if (attribute(node,kAXFocusedAttribute) as? Bool)==true {
                    focused.insert(node,at:0)
                }
                if let children=attribute(node,kAXChildrenAttribute) as? [AXUIElement] {
                    queue.append(contentsOf:children.prefix(max(0,1500-queue.count)))
                }
            }
            candidates.insert(contentsOf:focused,at:0)
        }
        var selected:AXUIElement?
        var observedRole="unknown"
        for candidate in candidates {
            var current:AXUIElement?=candidate
            var editable:AXUIElement?
            var protected=false
            // A caret or text leaf may have an editable parent (e.g. document editors).
            // Check every ancestor for protected content before accepting that parent.
            for _ in 0..<16 {
                guard let node=current else {break}
                var pid:pid_t=0
                guard AXUIElementGetPid(node,&pid) == .success && pid==app.processIdentifier else {break}
                let role=attribute(node,kAXRoleAttribute) as? String ?? "unknown"
                let subrole=attribute(node,kAXSubroleAttribute) as? String ?? ""
                if editable == nil {observedRole=role}
                if subrole==kAXSecureTextFieldSubrole || (attribute(node,"AXProtectedContent") as? Bool)==true {
                    protected=true;break
                }
                if editable == nil && [kAXTextFieldRole,kAXTextAreaRole,kAXComboBoxRole].contains(role) {editable=node}
                guard let parent=attribute(node,kAXParentAttribute),CFGetTypeID(parent)==AXUIElementGetTypeID() else {break}
                let next=parent as! AXUIElement
                if CFEqual(node,next) {break};current=next
            }
            // Never fall back to another candidate when the actual focus is protected.
            if protected {return ("","Password/protected field — capture paused")}
            if let editable=editable {selected=editable;break}
        }
        guard let element=selected else {
            return ("","Editor not exposed as a text field ("+observedRole+") — capture paused")
        }
        // Field identity is used only to cancel partial words when focus changes; it is not stored.
        return (bundle+":"+String(CFHash(element)),"Recording new typing in "+(app.localizedName ?? bundle))
    }
    func checkContext(){
        guard active else{return};let (context,reason)=safeContext()
        if context != lastContext {emit(["kind":"boundary","onset":Date().timeIntervalSince1970]);lastContext=context}
        if reason != lastReason {lastReason=reason;statusItem?.button?.title=context.isEmpty ? "◌ EEG typing paused":"● EEG typing";emit(["kind":"status","reason":reason,"paused":context.isEmpty,"onset":Date().timeIntervalSince1970])}
    }
    func handle(_ type:CGEventType,_ event:CGEvent){
        guard active else{return};checkContext()
        if type != .keyDown {emit(["kind":"boundary","onset":Date().timeIntervalSince1970]);return}
        guard !lastContext.isEmpty else{return}
        var chars=[UniChar](repeating:0,count:16);var count=0
        event.keyboardGetUnicodeString(maxStringLength:16,actualStringLength:&count,unicodeString:&chars)
        let text=String(utf16CodeUnits:chars,count:count)
        let flags=event.flags;let shortcut=flags.contains(.maskCommand)||flags.contains(.maskControl)||flags.contains(.maskAlternate)
        let wall=Date().timeIntervalSince1970-(ProcessInfo.processInfo.systemUptime-Double(event.timestamp)/1e9)
        emit(["kind":"key","onset":wall,"text":shortcut ? "":text,"keycode":event.getIntegerValueField(.keyboardEventKeycode),"shortcut":shortcut,"app":lastContext.components(separatedBy:":").first ?? ""])
    }
}
