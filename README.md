# Syfoh

## Overview 

Syfoh - **Sy**sex commands **fo**r **h**umans - is a simple Python command line tool which takes a human readable source and generates Sysex commands as defined by the [Syntherrupter Sysex Standard](https://github.com/MMMZZZZ/Syntherrupter/blob/dev/Documentation/Wiki/Custom%20MIDI%20Commands.md#system-exclusive-messages-sysex):

```
Input:  Set ontime for coil 1 and mode simple to 100

Output: F0 00 26 05 01 7F 21 00 01 00 64 00 00 00 00 F7
```

It can [batch process text files](#batch-processing-text-files) with multiple commands and save the output as text or binary file, or send it directly to a serial port. 

## Requirements

* [Python 3](https://www.python.org/downloads/)
* Optional: [pyserial](https://pypi.org/project/pyserial/)
* Optional: [python-rtmidi](https://pypi.org/project/python-rtmidi/)

## Setup

* Install Python 3. Make sure you tick the option to add python to your PATH variable (I think this only applies to windows users but not sure). 
* Optional: open a console and install the two optional python modules by executing `pip install pyserial` (similarly for rtmidi). 
* Optional: follow the [Syntherrupter PC MIDI Setup](https://github.com/MMMZZZZ/Syntherrupter#pc-midi-setup) to communicate with Syntherrupter via MIDI. 
* Clone this repository. You can also download it but cloning (f.ex. using [GitHub Desktop]()) makes it easier to keep the script up to date. 
* Open a console inside the folder of this repository. If you open your console elsewhere you need to specify the full path to the script in the next step.
* Run the script with `python Syfoh.py -h`. 

## The Human Readable Sysex Format

Input commands have the following basic structure:
```
set [sysex number] for [target name] [target value] and [another target name] [value] to [sysex value]
```

## Usage

A complete description of the command line options can be obtained with 

```
python Syfoh.py -h
```

Process a text file and save it as `.syx` (binary) file. This file can be directly sent to a serial port using tools like Realterm. This file can also be processed by any generic Sysex tools (f.ex. converted into a MIDI file). Vendor-specific tools likely won't work. 
```
python Syfoh.py -i "Example-Input.txt" -m BIN -o "Sysex-binary.syx"
```

Write the hex data to the console output (file input):
```
python Syfoh.py -i "Example-Input.txt" -m HEX
```

Process a single command and let Syfoh sent it directly to serial port 2 (with the default baudrate of 115200baud/s):
```
python Syfoh.py -i "set some-command to some-value" -m SER -p COM2
```
Sending data to a MIDI port works exactly the same but with `-m MID`. Note that you can get a list of ports using the `-l` parameter. On top of that you can use the index of the resulting list instead of the port name. Again, please check out the `-h/--help` for details. 

### Examples and Explanations

* The structure is case insensitive. 
* hex (`0x...`), binary (`0b...`) and decimal notation are valid for any integer
* The sysex command can either be selected by its short name, long name or parameter number. See [Sysex-Name-Number-Mapping.json](/Sysex-Name-Number-Mapping.json) for the full list of short and long names.
* For every command, there may be optional or required targets, like the coil that shall be modified. In case the names for those targets are not obvious from the [sysex command documentation](https://github.com/MMMZZZZ/Syntherrupter/blob/dev/Documentation/Wiki/Custom%20MIDI%20Commands.md#system-exclusive-messages-sysex), the full list of names for every command is contained in the [Sysex-Properties-Mapping.json](/Sysex-Properties-Mapping.json) file.
* Similarly, the target values and the sysex value can be replaced by keywords, like `enabled`/`disabled` instead of `1`/`0`, or `simple`/`midi-live`/... for the `mode` target. Again, all those keywords should be obvious from the documentation of the commands and if not, are contained in the json file linked above.
* Unless noted otherwise, all values are zero indexed. This means f.ex. that coil numbers run from 0 to 5 (unlike in the Syntherrupter UI) and MIDI Channels run from 0-15. Check the documentation linked above for details about the supported value ranges of every command.

```
Command:       Set enable for mode simple to enabled
Equal variant: set Mode-Enable for MODE 1 to 0x01
Equal variant: set 0x20 for MODE simple to 1
```

* In addition to the command-specific targets, a target device can be specified using `device [deviceID]`. If no device is given, the command is sent as broadcast to all devices. In a nutshell, this is necessary if more than one Syntherrupter is connected to the same MIDI bus. More details can be found in the [sysex command documentation](https://github.com/MMMZZZZ/Syntherrupter/blob/dev/Documentation/Wiki/Custom%20MIDI%20Commands.md#system-exclusive-messages-sysex). 
* Multiple targets are separated by `and`. The order is not important.
* Almost all parameters can be written with floats - except for things like enable/disable commands where floats don't make sense. Therefore you don't need to convert anything to percent or permille. Details and conventions for float values can be found in the [sysex command documentation](https://github.com/MMMZZZZ/Syntherrupter/blob/dev/Documentation/Wiki/Custom%20MIDI%20Commands.md#conventions).

For MIDI program/envelope `0x20` on device `0`, set the amplitude of step 1 to 1.75. 
```
Command:       set envelope-amplitude for device 0 and program 0x20 and step 1 to 1750
Equal variant: set envelope-amplitude for device 0 and program 0x20 and step 1 to 1.75
```

* Broadcasting/wildcards not only work for the device but for all targets, too. You can broadcast by explicitly writing the broadcast value `127` or `0x7f` or by using the keyword `all`. Not all commands support broadcasting because it doesn't always make sense. 

```
Command:       set ontime for mode simple and coil all to 42
Equal variant: set ontime for mode simple and coil 127 to 42
```

* For string commands, the first 4 characters behind the `to ` (including the first space behind `to`!) are taken as string. This part obviously is case sensitive and can contain additional spaces.
* Remember, because of the limited sysex size, every sysex command can only carry up to 4 characters. Strings longer than 4 characters are split into "char-groups".
* char-group 0 will cause the target device to delete the entire string (overwrite with `\x00`). Hence no additional `\x00` character is needed at the end.

Set the name of user 0 (admin) to `Hello, World!`:
```
set user-name for user 0 and char-group 0 to Hell
set user-name for user 0 and char-group 1 to o, W
set user-name for user 0 and char-group 2 to orld
set user-name for user 0 and char-group 3 to !
```

## Batch Processing Text Files

Syfoh can not only accept a single command from the command line but also a text file with any amount of commands, one per line. Here's and example of how such a file could look (Included in this repository as [Example-Input.txt](/Example-Input.txt)). It enables stereo for all 6 coils, sets reach mode to constant and distributes them equally across the stereo range. The example also demonstrates how easy such setups are with the float commands; no need to mess with fractions of 127 or other weird values. 

Any line that doesn't mach the format will be ignored. So you can use C style comments, Python style, whatever. You probably could write plain text and it would be properly ignored. Only thing you can't do is write a comment in the same line as a command. 

**Important** if you're using batch processing you should [disable UI Updates (Sysex command `0x226`)](https://github.com/MMMZZZZ/Syntherrupter/blob/dev/Documentation/Wiki/Custom%20MIDI%20Commands.md#0x220-0x23f-ui-settings), otherwise Syntherrupter might not be able to process the commands fast enough. With UI Updates disabled there are no issues (processing time <<10ms; commands send with 40ms delay). 

```
# Disable UI updates to ensure fast processing
set ui-update to manual

# Configure stereo mode, range and position for all six coils
set midi-pan-cfg for coil all to constant
set midi-pan-reach for coil all to 0.1
set midi-pan-pos for coil 0 to 0.0
set midi-pan-pos for coil 1 to 0.2
set midi-pan-pos for coil 2 to 0.4
set midi-pan-pos for coil 3 to 0.6
set midi-pan-pos for coil 4 to 0.8
set midi-pan-pos for coil 5 to 1.0
```
