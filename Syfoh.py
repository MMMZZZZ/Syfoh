import string
import json
import argparse
import struct
from pathlib import Path
from time import sleep
try:
    import serial
    serialAvailable = True
except:
    serialAvailable = False
if (serialAvailable):
    from serial.tools.list_ports import comports
try:
    import rtmidi
    midiAvailable = True
except:
    midiAvailable = False


scriptDir = Path(__file__).parent
with open(scriptDir / "Sysex-Name-Number-Mapping.json") as f:
    names2num = json.load(f)
for k,v in names2num.items():
    if type(v) == str:
        if "x" in v:
            names2num[k] = int(v, 16)
        else:
            names2num[k] = int(v)
with open(scriptDir / "Sysex-Properties-Mapping.json") as f:
    m = json.load(f)
mapping = dict()
for k, v in m.items():
    if type(k) == str:
        if "x" in k:
            k = int(k, 16)
        else:
            k = int(k)
    mapping[k] = v

def findInt(num:str):
    try:
        n = int(num)
    except:
        try:
            n = int(num, 2)
        except:
            try:
                n = int(num, 16)
            except:
                return None
    return n

def sysexBytes(number, targetMSB, targetLSB, value, deviceID=127, protocolVer=1, **kwargs):
    start = bytes([0xf0, 0x00, 0x26, 0x05, protocolVer, deviceID])
    for i in range(2):
        start += bytes([number & 0x7f])
        number >>= 8
    start += bytes([targetLSB, targetMSB])
    for i in range(5):
        start += bytes([value & 0x7f])
        value >>= 7
    start += bytes([0xf7])
    return start

def str2sysexDict(s:str):
    sysex = {"number": 0, "targetMSB": 0, "targetLSB": 0, "value": 0, "deviceID": 127, "reading": False}
    readCommands = {"check": 0x02, "read": 0x03, "get": 0x04}
    s = s.split(" ")
    sl = [strng.lower() for strng in s]
    readOnly = False
    valStart = len(sl)
    if "to" not in sl:
        readOnly = True
    else:
        valStart = sl.index("to")
        sysexVal = " ".join(s[valStart + 1:])
    s = [strng for strng in sl[:valStart] if strng]
    if readOnly:
        if s[0] in readCommands:
            readOnly = readCommands[s[0]]
            sysex["reading"] = True
        else:
            return -1
    elif s[0] != "set":
        return -1
    num = findInt(s[1])
    if num is None:
        if s[1] in names2num:
            num = names2num[s[1]]
        else:
            return -1
    sysex["number"] = num
    targets = []
    if len(s) > 4 and s[2] in ("of", "for"):
        targets.append({"name": s[3], "val": s[4], "type": "None"})
        if len(s) > 7 and s[5] in "and":
            targets.append({"name": s[6], "val": s[7], "type": "None"})
            if len(s) > 10 and s[8] == "and":
                targets.append({"name": s[9], "val": s[10], "type": "None"})
        for t in targets:
            t["val"] = t["val"].replace("all", "127")
            if t["name"] == "device":
                n = findInt(s[1])
                if n is None:
                    return -1
                sysex["deviceID"] = n
                continue
            elif t["name"] == mapping[num]["targetMSB-name"]:
                t["type"] = "targetMSB"
            elif t["name"] == mapping[num]["targetLSB-name"]:
                t["type"] = "targetLSB"
            else:
                return -1
            n = findInt(t["val"])
            if n is None:
                if t["val"] in mapping[num][t["type"]]:
                    n = mapping[num][t["type"]][t["val"]]
                else:
                    return -1
            t["val"] = n
            sysex[t["type"]] = t["val"]

    if readOnly:
        # When reading, what has been processed above as sysex number actually
        # belongs to the value (while the number indicates the type of read command).
        sysex["value"] = sysex["number"]
        sysex["number"] = readOnly
    else:
        if mapping[num]["type"] == "str":
            sysexVal = sysexVal[:4].encode("iso-8859-1")
            sysex["value"] = 0
            for i,e in enumerate(sysexVal):
                sysex["value"] += e << (8 * i)
        else:
            sysexVal = sysexVal.replace(" ", "")
            n = findInt(sysexVal)
            if n is None:
                try:
                    # Convert float object to 32bit IEEE754 float, then store these bytes in an int
                    # such that it can be later processed and packed by sysexBytes (packed into 7bit chunks).
                    n = struct.unpack("<I", struct.pack("<f", float(sysexVal)))[0]
                    # if it's not a float we're already in th except section and the following won't be executed
                    sysex["number"] |= 0x2000
                except:
                    if sysexVal in mapping[num]["value"]:
                        n = mapping[num]["value"][sysexVal]
                    else:
                        return -1
            sysex["value"] = n
    return sysex

def hexStr(b:bytes):
    return " ".join(["{:02x}".format(c) for c in b])

if __name__ == "__main__":
    desc = """Sysex-Tool for Syntherrupter
              Convert human readable commands into MIDI Sysex commands and send them to a serial port. 
              Developped by Max Zuidberg, licensed under MPL-2.0"""
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument("-i", "--input", type=str, required=False, default="",
                        help="Command as string or path to text file.")
    parser.add_argument("-m", "--mode", type=str, required=False, default="",
                        help="Select what output is generated. Can be SER/SERIAL, MID/MIDI, HEX or BIN (case insensitive). "
                             "For SERIAL and MIDI a port must be specified using -p/--port. "
                             "For HEX an output file can be specified using -o/--output. "
                             "For BIN an output file must be specified using -o/--output.")
    parser.add_argument("-o", "--output", required=False, default="",
                        help="Output file for hex or binary data.")
    parser.add_argument("-p", "--port", required=False,
                        help="Serial or MIDI port to send commands to. Example (Windows): \"COM3\". If an integer is "
                             "given, it'll be used as index in the list of available ports (see -l/--list).")
    parser.add_argument("-b", "--baudrate", required=False, type=int, default=115200,
                        help="Select baudrate for serial commands. Default is 115200baud/s.")
    parser.add_argument("-l", "--list", required=False, action="store_true",
                        help="List all available serial and MIDI ports.")

    args = parser.parse_args()

    serialPorts = []
    midiPorts = []
    if serialAvailable:
        serialPorts = [p.name for p in comports()]
    if midiAvailable:
        midi = rtmidi.MidiOut()
        midiPorts = midi.get_ports()

    if args.list:
        if serialAvailable:
            print("List of available serial ports:")
            for i, p in enumerate(serialPorts):
                print("{:3}: \"{}\"".format(i, p))
        else:
            print("To list or use serial ports you need to install the pyserial package: "
                  "https://pypi.org/project/pyserial/")
        if midiAvailable:
            print("List of available MIDI ports")
            for i, p in enumerate(midiPorts):
                print("{:3}: \"{}\"".format(i, p))
        else:
            print("To list or use MIDI ports you need to install the python-rtmidi package: "
                  "https://pypi.org/project/python-rtmidi/")
        exit()

    if not args.mode:
        parser.error("-m/--mode is required.")
    if not args.input:
        parser.error("-i/--input is required.")

    args.mode = args.mode[:3].upper()
    if args.mode not in ["SER", "HEX", "BIN", "MID"]:
        parser.error("Invalid mode. Must be SER/SERIAL, MID/MIDI, HEX or BIN")

    if args.output:
        out = Path(args.output)
        try:
            with open(out, "wb") as f:
                f.close()
        except:
            parser.error("Invalid output file.")
    elif args.mode == "BIN":
        parser.error("Valid output file required.")
    else:
        out = ""

    p = Path(args.input)
    cmds = []
    if p.is_file():
        with open(p) as f:
            cmds = [cmd.rstrip("\n") for cmd in f.readlines()]
    else:
        cmds.append(args.input)

    strCmds = []
    reading = []
    for i,e in enumerate(cmds):
        cmds[i] = str2sysexDict(e)
        if cmds[i] == -1:
            print("Ignored invald command: {}".format(e))
        else:
            reading[i] = cmds[i]["reading"]
            cmds[i] = sysexBytes(**cmds[i])
            strCmds.append(hexStr(cmds[i]))

    if args.mode == "SER":
        if serialAvailable:
            portOk = (args.port in serialPorts)
            if not portOk:
                isInt = True
                try:
                    args.port = int(args.port)
                except:
                    isInt = False
                if isInt and args.port < len(serialPorts):
                    portOk = True
                    args.port = serialPorts[args.port]
            if not portOk:
                parser.error("Specified port \"{}\" not among available ports or index too high. "
                             "{} ports available: {}".format(args.port, len(serialPorts),
                                                             ", ".join(["\"" + p + "\"" for p in serialPorts])))
            ser = serial.Serial()
            ser.baudrate = args.baudrate
            ser.port = args.port
            ser.open()
            for i,e in enumerate(cmds):
                print(strCmds[i])
                ser.write(e)
                while ser.out_waiting:
                    pass
                # Let Syntherrupter process the data
                sleep(0.04)
            ser.close()
            print("Sent {} command(s) to serial port.".format(len(cmds)))
        else:
            parser.error("To use the serial feature you need to install the pyserial package: "
                         "https://pypi.org/project/pyserial/")

    elif args.mode == "MID":
        if midiAvailable:
            portOk = (args.port in midiPorts)
            if portOk:
                args.port = midiPorts.index(args.port)
            else:
                isInt = True
                try:
                    args.port = int(args.port)
                except:
                    isInt = False
                if isInt and args.port < len(midiPorts):
                    portOk = True
            if not portOk:
                parser.error("Specified port \"{}\" not among available ports or index too high. "
                             "{} ports available: {}".format(args.port, len(midiPorts), ", ".join(["\"" + p + "\"" for p in midiPorts])))
            midi.open_port(args.port)
            for i,e in enumerate(cmds):
                print(strCmds[i])
                midi.send_message(e)
                # Let Syntherrupter process the data
                sleep(0.04)
            del midi
            print("Sent {} command(s) to MIDI port.".format(len(cmds)))
        else:
            parser.error("To use the MIDI feature you need to install the python-rtmidi package: "
                         "https://pypi.org/project/python-rtmidicd/")

    elif args.mode == "HEX":
        for cmd in strCmds:
            print(cmd)
        if (out):
            with open(out, "w") as f:
                f.writelines(strCmds)
                print("Wrote {} command(s) as hex to file.".format(len(cmds)))

    elif args.mode == "BIN":
        with open(out, "wb") as f:
            for i,e in enumerate(cmds):
                print(strCmds[i], end="")
                f.write(e)
            print("Wrote {} command(s) as binary to file.".format(len(cmds)))
