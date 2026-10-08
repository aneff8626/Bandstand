import Foundation
import CoreBluetooth

func emit(_ object: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: object), let line = String(data: data, encoding: .utf8) {
        print(line); fflush(stdout)
    }
}
// Reading authorization does not instantiate a central manager or request access.
let authorization = CBManager.authorization
if authorization != .allowedAlways {
    emit(["type":"status", "state":"authorization_unavailable", "message":"Bluetooth access is not already authorized for this process. No permission was requested.", "authorization": authorization.rawValue])
    exit(0)
}
final class Bridge: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    var central: CBCentralManager!
    var device: CBPeripheral?
    var control: CBCharacteristic?
    var subscribed = Set<String>()
    var started = false
    var lastData = Date()
    let suffix = "-4C4D-454D-96BE-F03BAC821358"
    let names = ["273E0003":"TP9", "273E0004":"AF7", "273E0005":"AF8", "273E0006":"TP10"]
    var timer: Timer?
    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: nil, options: [CBCentralManagerOptionShowPowerAlertKey: false])
        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            guard let s = self else { return }
            if s.started && Date().timeIntervalSince(s.lastData) > 10, let d = s.device {
                emit(["type":"status","state":"reconnecting","message":"EEG stream stopped; reconnecting."])
                s.central.cancelPeripheralConnection(d)
            } else if s.started { s.command("k") }
        }
    }
    func scan() {
        guard central.state == .poweredOn else { return }
        emit(["type":"status","state":"scanning","message":"Waiting for Muse 2. Turn on your headset; close other apps connected to it."])
        central.scanForPeripherals(withServices: [CBUUID(string:"FE8D")], options:nil)
    }
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn { scan() }
        else { emit(["type":"status","state":"bluetooth_unavailable","message":"Bluetooth is not powered on or is unavailable. No system settings were changed."]) }
    }
    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral, advertisementData: [String:Any], rssi RSSI:NSNumber) {
        let name = peripheral.name ?? advertisementData[CBAdvertisementDataLocalNameKey] as? String ?? ""
        guard name.lowercased().hasPrefix("muse") && device == nil else { return }
        device = peripheral; central.stopScan(); peripheral.delegate = self
        emit(["type":"status","state":"connecting","message":"Connecting to \(name)","device":name])
        central.connect(peripheral, options:nil)
    }
    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        started = false; subscribed.removeAll(); lastData = Date()
        peripheral.discoverServices([CBUUID(string:"FE8D")])
    }
    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) { reset() }
    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) { reset() }
    func reset() { device = nil; control = nil; started = false; subscribed.removeAll(); scan() }
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        for service in peripheral.services ?? [] { peripheral.discoverCharacteristics(nil, for:service) }
    }
    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        for c in service.characteristics ?? [] {
            let id = c.uuid.uuidString.uppercased()
            if id.hasPrefix("273E0001") { control = c; command("h"); command("p21") }
            if names.keys.contains(where:{id.hasPrefix($0)}) { peripheral.setNotifyValue(true, for:c) }
        }
    }
    func peripheral(_ peripheral: CBPeripheral, didUpdateNotificationStateFor characteristic: CBCharacteristic, error: Error?) {
        if let error = error { emit(["type":"status","state":"error","message":error.localizedDescription]); return }
        if characteristic.isNotifying { subscribed.insert(characteristic.uuid.uuidString) }
        if subscribed.count == 4 && !started && control != nil {
            started = true; command("d")
            emit(["type":"status","state":"connected","message":"Muse connected. Waiting for EEG samples.","device":peripheral.name ?? "Muse"])
        }
    }
    func command(_ text:String) {
        guard let d=device, let c=control else { return }
        let bytes=Array((text+"\n").utf8)
        d.writeValue(Data([UInt8(bytes.count)]+bytes), for:c, type:c.properties.contains(.writeWithoutResponse) ? .withoutResponse : .withResponse)
    }
    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard let data=characteristic.value, data.count == 20 else { return }
        let id=characteristic.uuid.uuidString.uppercased()
        guard let prefix=names.keys.first(where:{id.hasPrefix($0)}), let name=names[prefix] else { return }
        lastData=Date()
        let b=[UInt8](data); let counter=Int(b[0])*256+Int(b[1])
        var values=[Double]()
        for i in stride(from:2, to:20, by:3) {
            values.append((Double(Int(b[i])*16 + Int(b[i+1]>>4))-2048)*0.48828125)
            values.append((Double(Int(b[i+1]&15)*256 + Int(b[i+2]))-2048)*0.48828125)
        }
        emit(["type":"packet","channel":name,"counter":counter,"received":Date().timeIntervalSince1970,"values":values])
    }
}
let bridge=Bridge()
RunLoop.main.run()
