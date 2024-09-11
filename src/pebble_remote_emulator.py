#!/usr/bin/python3
# Emulator for Hunter Douglas Pebble Remote
# Author Andrew Fiddian-Green 

import bluetooth_constants
import bluetooth_classes
import bluetooth_utils
import bluetooth_exceptions

import dbus
import dbus.exceptions
import dbus.service
import dbus.mainloop.glib

import sys
import socket
import os
import threading

from gi.repository import GObject
from gi.repository import GLib
from bluetooth_constants import DBUS_PROPERTIES_INTERFACE
from logging.config import listen

sys.path.insert(0, '.')

DEVICE_INFO_SERVICE_UUID = '180a'
DEVICE_INFO_FIRMWARE_VERSION_CHARACTERISTIC_UUID = '2a26'
DEVICE_INFO_HARDWARE_VERSION_CHARACTERISTIC_UUID = '2a27'
DEVICE_INFO_MANUFACTURER_CHARACTERISTIC_UUID = '2a29'
DEVICE_INFO_MODEL_NUMBER_CHARACTERISTIC_UUID = '2a24'
DEVICE_INFO_SERIAL_NUMBER_CHARACTERISTIC_UUID = '2a25'
DEVICE_INFO_SOFTWARE_VERSION_CHARACTERISTIC_UUID = '2a28'

UNKNOWN_SERVICE_UUID = 'cafe9000-c0ff-ee01-8000-a110ca7ab1e0'
UNKNOWN_CHARACTERISTIC_UUID = 'cafe9003-c0ff-ee01-8000-a110ca7ab1e0'

PEBBLE_REMOTE_SERVICE_UUID = 'fdc0'
PEBBLE_REMOTE_CHARACTERISTIC_UID = 'cafe8001-c0ff-ee01-8000-a110ca7ab1e0'

BATTERY_LEVEL_SERVICE_UUID = '180f'
BATTERY_LEVEL_CHARACTERISTIC_UUID = '2a19'

PEBBLE_REMOTE_BASE_PATH = '/whitebear/pebble'
PEBBLE_AGENT_PATH = PEBBLE_REMOTE_BASE_PATH + '/agent'

pebble_application = None


class PebbleAdvertisement(bluetooth_classes.Advertisement):
    
    def __init__(self, bus, index, advertising_type):
        bluetooth_classes.Advertisement.__init__(self, bus, PEBBLE_REMOTE_BASE_PATH, index, advertising_type)
        self.add_manufacturer_data(0x819, [0])
        self.add_local_name('PR:9999')
        self.include_tx_power = True
        self.add_service_uuid(PEBBLE_REMOTE_SERVICE_UUID)


class BatteryCharacteristic(bluetooth_classes.Characteristic):

    def __init__(self, bus, index, service):
        bluetooth_classes.Characteristic.__init__(self, bus, index, BATTERY_LEVEL_CHARACTERISTIC_UUID, ['read'], service)

    def ReadValue(self, options):
        return dbus.Byte(88)


class BatteryService(bluetooth_classes.Service):

    def __init__(self, bus, index):
        bluetooth_classes.Service.__init__(self, bus, PEBBLE_REMOTE_BASE_PATH, index, BATTERY_LEVEL_SERVICE_UUID, True)
        self.add_characteristic(BatteryCharacteristic(bus, 0, self))


class UnknownCharacteristic(bluetooth_classes.Characteristic):

    def __init__(self, bus, index, service):
        bluetooth_classes.Characteristic.__init__(self, bus, index, UNKNOWN_CHARACTERISTIC_UUID, ["indicate", "write"], service)


class UnknownService(bluetooth_classes.Service):

    def __init__(self, bus, index):
        bluetooth_classes.Service.__init__(self, bus, PEBBLE_REMOTE_BASE_PATH, index, UNKNOWN_SERVICE_UUID, True)
        self.add_characteristic(UnknownCharacteristic(bus, 0, self))


class PebbleCharacteristic(bluetooth_classes.Characteristic):

    def __init__(self, bus, index, service):
        self.socket = None
        self.socket_listener = None
        self.socket_path = PEBBLE_REMOTE_BASE_PATH + '/socket/' + service.uuid + '/' + str(index)
        bluetooth_classes.Characteristic.__init__(self, bus, index, PEBBLE_REMOTE_SERVICE_UUID, ["notify", "write"], service)
        
    def __del__(self):
        if self.socket != None:
            self.socket.close()

        if self.socket_listener != None:
            self.socket_listener.join(5)
        
        self.socket_unlink()

    def WriteValue(self, value, options):
        print("WriteValue: " + bluetooth_utils.byteArrayToHexString(value))
  
    def StartNotify(self):
        print("StartNotify")
        self.notifying = True

    def StopNotify(self):
        print("StopNotify")
        self.notifying = False

    def socket_process_data(self):
        print("socket processing data")    

        while True:
            read_data = self.socket.recv(64)
            if read_data == None:
                break
            
            print("socket read: " + bluetooth_utils.byteArrayToHexString(read_data))
            
            write_data = read_data[::-1]  # testing: reverse the bytes
            self.socket.send(write_data)
            print("socket write: " + bluetooth_utils.byteArrayToHexString(write_data))

        self.socket.close()
        self.socket_unlink()
        print("socket closed")
        
    def socket_unlink(self):
        try:
            os.unlink(self.socket_path)
        except OSError:
            if os.path.exists(self.socket_path):
                raise

    @dbus.service.method(bluetooth_constants.BLUEZ_GATT_CHARACTERISTIC_INTERFACE, in_signature='a{sv}')
    def AcquireWrite(self, options):
        print("AcquireWrite")
        
        self.socket_unlink()
        
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(self.socket_path)
        self.socket.listen(5)
        print("socket opened")
        
        self.socket_listener = threading.Thread(target=self.socket_process_data)
        self.socket_listener.start()
        socket_file = self.socket.makefile("rwb")

        print("return socket as file")
        return socket_file, 64  # hard code MTU to 64 bytes

        
class PebbleService(bluetooth_classes.Service):

    def __init__(self, bus, index):
        bluetooth_classes.Service.__init__(self, bus, PEBBLE_REMOTE_BASE_PATH, index, PEBBLE_REMOTE_SERVICE_UUID, True)
        self.add_characteristic(PebbleCharacteristic(bus, 0, self))


class ManufacturerCharacteristic(bluetooth_classes.Characteristic):

    def __init__(self, bus, index, service):
        bluetooth_classes.Characteristic.__init__(self, bus, index, DEVICE_INFO_MANUFACTURER_CHARACTERISTIC_UUID, ['read'], service)

    def ReadValue(self, options):
        return b'Hunter Douglas'


class ModelNumberCharacteristic(bluetooth_classes.Characteristic):

    def __init__(self, bus, index, service):
        bluetooth_classes.Characteristic.__init__(self, bus, index, DEVICE_INFO_MODEL_NUMBER_CHARACTERISTIC_UUID, ['read'], service)

    def ReadValue(self, options):
        return b"Pebble Remote"


class SerialNumberCharacteristic(bluetooth_classes.Characteristic):

    def __init__(self, bus, index, service):
        bluetooth_classes.Characteristic.__init__(self, bus, index, DEVICE_INFO_SERIAL_NUMBER_CHARACTERISTIC_UUID, ['read'], service)

    def ReadValue(self, options):
        return b"9999"


class FirmwareVersionCharacteristic(bluetooth_classes.Characteristic):

    def __init__(self, bus, index, service):
        bluetooth_classes.Characteristic.__init__(self, bus, index, DEVICE_INFO_FIRMWARE_VERSION_CHARACTERISTIC_UUID, ['read'], service)

    def ReadValue(self, options):
        return b"80"


class HardwareVersionCharacteristic(bluetooth_classes.Characteristic):

    def __init__(self, bus, index, service):
        bluetooth_classes.Characteristic.__init__(self, bus, index, DEVICE_INFO_HARDWARE_VERSION_CHARACTERISTIC_UUID, ['read'], service)

    def ReadValue(self, options):
        return b"1234"


class SoftwareVersionCharacteristic(bluetooth_classes.Characteristic):

    def __init__(self, bus, index, service):
        bluetooth_classes.Characteristic.__init__(self, bus, index, DEVICE_INFO_SOFTWARE_VERSION_CHARACTERISTIC_UUID, ['read'], service)

    def ReadValue(self, options):
        return b"80"


class DeviceInformationService(bluetooth_classes.Service):

    def __init__(self, bus, index):
        bluetooth_classes.Service.__init__(self, bus, PEBBLE_REMOTE_BASE_PATH, index, DEVICE_INFO_SERVICE_UUID, True)
        self.add_characteristic(ManufacturerCharacteristic(bus, 0, self))
        self.add_characteristic(ModelNumberCharacteristic(bus, 1, self))
        self.add_characteristic(SerialNumberCharacteristic(bus, 2, self))
        self.add_characteristic(HardwareVersionCharacteristic(bus, 3, self))
        self.add_characteristic(FirmwareVersionCharacteristic(bus, 4, self))
        self.add_characteristic(SoftwareVersionCharacteristic(bus, 5, self))


class PebbleApplication(bluetooth_classes.Application):

    def __init__(self, bus):
        bluetooth_classes.Application.__init__(self, bus)
        self.add_service(DeviceInformationService(bus, 0))
        self.add_service(UnknownService(bus, 2))
        self.add_service(PebbleService(bus, 1))
        self.add_service(BatteryService(bus, 3))


def register_ad_cb():
    print('Pebble advertisements running')


def register_ad_error_cb(error):
    print('Error: Failed to register advertisements: ' + str(error))
    mainloop.quit()


def register_app_cb():
    print('Pebble application running')


def register_app_error_cb(error):
    print('Failed to register application: ' + str(error))
    mainloop.quit()


dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()

bluez_path = bus.get_object(bluetooth_constants.BLUEZ_SERVICE_NAME, bluetooth_constants.BLUEZ_NAMESPACE)
agent_manager = dbus.Interface(bluez_path, bluetooth_constants.BLUEZ_AGENT_MANAGER_INTERFACE)

adapter_path = bluetooth_constants.BLUEZ_NAMESPACE + '/' + bluetooth_constants.BLUEZ_ADAPTER_NAME
bluetooth_adapter = bus.get_object(bluetooth_constants.BLUEZ_SERVICE_NAME, adapter_path)

advertising_manager = dbus.Interface(bluetooth_adapter, bluetooth_constants.BLUEZ_ADVERTISING_MANAGER_INTERFACE)
service_manager = dbus.Interface(bluetooth_adapter, bluetooth_constants.BLUEZ_GATT_MANAGER_INTERFACE)
properties_manager = dbus.Interface(bluetooth_adapter, bluetooth_constants.DBUS_PROPERTIES_INTERFACE)

pebble_advertisement = PebbleAdvertisement(bus, 0, 'peripheral')
pebble_application = PebbleApplication(bus)
pebble_agent = bluetooth_classes.Agent(bus, PEBBLE_AGENT_PATH)

properties_manager.Set(bluetooth_constants.BLUEZ_ADAPTER_INTERFACE, "Powered", dbus.Boolean(0))
properties_manager.Set(bluetooth_constants.BLUEZ_ADAPTER_INTERFACE, "Alias", dbus.String('PR:9999'))
properties_manager.Set(bluetooth_constants.BLUEZ_ADAPTER_INTERFACE, "Powered", dbus.Boolean(1))

mainloop = GLib.MainLoop()

agent_manager.RegisterAgent(PEBBLE_AGENT_PATH, "NoInputNoOutput")
advertising_manager.RegisterAdvertisement(pebble_advertisement.get_path(), {}, reply_handler=register_ad_cb, error_handler=register_ad_error_cb)
service_manager.RegisterApplication(pebble_application.get_path(), {}, reply_handler=register_app_cb, error_handler=register_app_error_cb)

agent_manager.RequestDefaultAgent(PEBBLE_AGENT_PATH)
print('Pebble agent registered')

mainloop.run()

