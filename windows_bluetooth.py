"""Muse BLE transport on a dedicated asyncio/MTA thread (Windows)."""
import asyncio
import threading
import time

BASE = '273e{}-4c4d-454d-96be-f03bac821358'
EEG = dict(zip(('0003','0004','0005','0006'), ('TP9','AF7','AF8','TP10')))

def decode_eeg(data, channel):
    if len(data) != 20:
        raise ValueError('Muse EEG packet must contain 20 bytes')
    values = []
    for i in range(2,20,3):
        values.extend(((data[i]*16+(data[i+1]>>4)-2048)*.48828125,
                       ((data[i+1]&15)*256+data[i+2]-2048)*.48828125))
    return dict(channel=channel,counter=int.from_bytes(data[:2],'big'),received=time.time(),values=values)

class MuseBluetooth:
    def __init__(self, engine):
        self.engine=engine
        self.thread=None
        self.cancel=threading.Event()

    def connect(self):
        if self.thread and self.thread.is_alive():
            raise ValueError('Bluetooth is still connecting or disconnecting. Please wait a moment.')
        self.cancel.clear()
        self.status('scanning','Searching for Muse. Turn it on and close other headset apps.')
        self.thread=threading.Thread(target=self.worker,daemon=True)
        self.thread.start()

    def disconnect(self):
        self.cancel.set()
        self.status('disconnected','Disconnected. Click Connect Bluetooth to reconnect.')

    def status(self, state, message):
        with self.engine.lock:
            self.engine.live_status=dict(state=state,message=message)
            if self.engine.source=='live': self.engine.status=self.engine.live_status.copy()

    def worker(self):
        try:
            asyncio.run(self.run())
        except Exception as error:
            if not self.cancel.is_set():
                self.status('bluetooth_error',f'Bluetooth: {error}. Check Windows Bluetooth is on; close other Muse apps and try Connect again.')

    async def run(self):
        from bleak import BleakScanner, BleakClient
        # A separate thread avoids WebView2's STA GUI event loop.
        async def find():
            return await BleakScanner.discover(timeout=8,return_adv=True)
        task=asyncio.create_task(find())
        while not task.done():
            if self.cancel.is_set():
                task.cancel()
                try: await task
                except asyncio.CancelledError: pass
                return
            await asyncio.sleep(.1)
        devices=[device for device,adv in (await task).values()
                 if (adv.local_name or device.name or '').lower().startswith('muse')]
        if not devices: raise ValueError('No Muse found nearby')
        if len(devices)>1: raise ValueError('Multiple Muse headsets found. Turn off the others, then retry')
        if self.cancel.is_set(): return
        self.status('connecting','Connecting to Muse…')
        async with BleakClient(devices[0],timeout=15) as client:
            if self.cancel.is_set(): return
            control=client.services.get_characteristic(BASE.format('0001'))
            if control is None: raise ValueError('This headset does not expose the supported Muse EEG service')
            async def command(text):
                payload=(text+'\n').encode('ascii')
                await client.write_gatt_char(control,bytes([len(payload)])+payload,
                    response='write-without-response' not in control.properties)
            await command('h'); await command('p21')
            self.status('subscribing','Preparing four EEG channels…')
            last=[time.monotonic()]
            def notify(channel, data):
                if self.cancel.is_set(): return
                packet=decode_eeg(data,channel)
                with self.engine.lock:
                    if self.engine.source!='live' or self.cancel.is_set(): return
                    self.engine.assembler.add(packet)
                    last[0]=time.monotonic()
            for suffix,channel in EEG.items():
                await client.start_notify(BASE.format(suffix),lambda sender,data,ch=channel:notify(ch,data))
            await command('d')
            self.status('connected','Muse connected. Waiting for EEG samples.')
            try:
                while not self.cancel.is_set():
                    if not client.is_connected: raise ValueError('Muse disconnected; reconnect to start a new recording')
                    if time.monotonic()-last[0]>10: raise ValueError('Connected but no EEG packets received for 10 seconds')
                    await asyncio.sleep(.1)
            finally:
                if client.is_connected:
                    try: await asyncio.wait_for(command('h'),2)
                    except Exception: pass
