# MQTT Data Processing Documentation

## Overview
This document describes the MQTT data processing logic for the Ezville Wallpad Home Assistant integration.

## Key Features

### 1. Packet Separation
- MQTT messages may contain multiple packets concatenated together
- Packets are separated by the 0xF7 marker
- Each packet starts with 0xF7

### 2. Deduplication
- Uses signature-based deduplication to avoid processing repeated packets
- Signature = first 4 bytes of the packet (F7 + device_id + device_num + command)
- Only processes packets when the data has changed

### 3. Unknown Device Support
- Automatically creates entities for unknown devices
- Unknown devices are named "Unknown XX" where XX is the device ID in hex
- Tracks device_id, device_num, command, and raw data
- Creates sensor entities to display the raw packet data

### 4. Logging
- Logs all new/changed packets in hex format
- Logs when a packet signature is updated with new values
- Provides detailed packet analysis for debugging

## Example Log Output

```
Converted hex message: f7 60 01 01 03 00 03 02 95 f6
Converted hex message: f7 39 1f 01 00 d0 20
Converted hex message: f7 39 1f 81 07 00 90 01 64 10 01 38 8b a0
Updated signature f7391f81: 07 00 90 01 64 10 01 38 8b a0
```

## Implementation Details

### Packet Processing Flow
1. Receive MQTT message containing raw bytes
2. Split message into individual packets by F7 markers
3. For each packet:
   - Calculate signature (first 4 bytes)
   - Check if packet is new or changed
   - If new/changed:
     - Log the packet
     - Update stored value
     - Process the packet
   - If duplicate: skip processing

### Unknown Device Handling
- Device ID not in STATE_HEADER or ACK_HEADER → Create unknown device
- Entity name: "Unknown {device_id_hex}"
- Stores full packet data and parsed fields
- Updates on any packet change

## Configuration
No special configuration needed. The system automatically:
- Detects and processes all F7-prefixed packets
- Creates entities for known and unknown devices
- Updates states only when data changes
