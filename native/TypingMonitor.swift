import AppKit
import ApplicationServices
import Carbon

// Opt-in, passive keyboard observation. No permission prompts, clipboard reads,
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
                "reason":listen && access ? "Ready. Protected fields, terminals and Muse Lab controls are skipped." : "Typing in other apps needs Muse Lab enabled under macOS Privacy & Security → Input Monitoring and Accessibility. No permission prompts were opened."]
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
        guard let value=attribute(application,kAXFocusedUIElementAttribute),CFGetTypeID(value)==AXUIElementGetTypeID() else{return ("","No accessible text field — capture paused")}
        let element=value as! AXUIElement
        let role=attribute(element,kAXRoleAttribute) as? String ?? ""
        let subrole=attribute(element,kAXSubroleAttribute) as? String ?? ""
        if subrole==kAXSecureTextFieldSubrole || (attribute(element,"AXProtectedContent") as? Bool)==true{return ("","Password/protected field — capture paused")}
        guard [kAXTextFieldRole,kAXTextAreaRole,kAXComboBoxRole].contains(role) else{return ("","Outside a text field — capture paused")}
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
