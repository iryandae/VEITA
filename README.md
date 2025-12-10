# Visually Encrypted Image Transfer Application (VEITA)
VEITA is a tool for performing **[visual cryptography–based image splitting](https://en.wikipedia.org/wiki/Visual_cryptography) and secure multi-channel transfer**.  
It generates multiple image shares, sends them over customizable network channels, and reconstructs the original only when enough shares are received.

## Table of Contents
- [Requirements](#requirements)
- [CLI Version](#cli-version)
  - [Generating Shares](#generating-shares)
  - [Receiving Shares](#receiving-shares)
- [GUI Version](#gui-version)
  - [Send Tab](#send-tab)
  - [Receiver Tab](#receiver-tab)
  - [Log Tab](#log-tab)


# Requirements
- Python 3.11.9 or latest
- NumPy 1.26.1
- Pillow 10.1.0


---
# CLI Version

## Generating Shares
```
python viscrypt.py gen input_image output_prefix n [--send hosts] [--send-port start_port]
```
### Parameters
| Argument | Description |
| -------- | ------- |
| input_image  | Source image file name |
| output_prefix | Prefix for generated share files |
| n | Number of shares to generate |
| --send hosts | Send generated shares to targets |
| --send-port start_port | Starting port for auto assigned ports (default: 8000) |

### Host formats supported
- `"x.x.x.x"` for auto-port assignment
- `"x.x.x.x:port"` or `x.x.x.x:port;x.x.x.x:port;...;x.x.x.x:port` for explicit port
- `"x.x.x.x;x.x.x.x;...;x.x.x.x"` for multiple reciever

## Receiving Shares
```
python viscrypt.py recv host port dest_dir [--max n] [--reconstruct-after k] [--scramble-ports N]
```
### Parameters
| Argument | Description |
| -------- | ------- |
| host | Interface to bind (`0`, `all`, or `*` allowed) |
| port | Single port or  list (e.g. `8000;8001;8002`) |
| dest_dir | Directory name to save received shares |
| --max n | Stop receiver after saving n amount of shares |
| --reconstruct-after k | Auto-reconstruct after receiving k amount of shares |
| --scramble-ports p | Auto-assign p number of ports |

> notes:
> - assign port to `0` if you want to use the `--scarmble-ports`.
> - start the reciever before generating shares

---

# GUI Version
VEITA includes a graphical interface allowing users to interact with the system without command-line knowledge.  
The GUI provides **tab-based control** for sending, receiving, and monitoring logs.

## Send Tab

<img width="1077" height="690" alt="VEITA GUI - send tab" src="https://github.com/user-attachments/assets/495b246e-c54f-402c-9710-15209a00adbb" />

### Features:
- **Input image selection**  
  Choose an image file to be split into visual cryptography shares.

- **Number of shares**  
  Specify how many shares to generate (minimum 2).

- **Generate button**  
  Produces shares and displays them in the *Available Shares* listbox.

- **Targets field**  
  Hosts can be entered in formats:
  - `x.x.x.x` (auto-port)
  - `x.x.x.x:port`
  - Multiple hosts: `host1;host2;host3`

- **Start port**  
  Used for hosts without explicit ports (default: `8000`).

- **Refresh button**  
  Reloads the output directory to update the share list.

- **Send Selected button**  
  Sends highlighted shares in the list to the target destinations.

## Receiver Tab

<img width="1077" height="690" alt="image" src="https://github.com/user-attachments/assets/6d9aa7d6-3dbf-44f8-a1d5-75b4342cab35" />



### Features:
- **Save folder**  
  Folder where incoming shares will be saved.

- **Host binding**  
  Options:  
  - `0.0.0.0` (bind all IPs)  
  - Specific IP or interface  

- **Port field**  
  Supports:
  - Single port (e.g., `8000`)
  - Multiple ports (`8000;8001;8002`)
  - Or set the amount of ports when using `Scramble Ports`

- **Max files field**  
  Auto-stops the receiver after a certain number of shares.

- **Reconstruct after field**  
  Auto-reconstructs the image when enough shares are collected.

- **Stop button**  
  Stops all active receivers.
  
- **Start Receiver button**  
  Launches listeners in the background.

---

## Log Tab

<img width="1077" height="690" alt="VEITA GUI - log tab" src="https://github.com/user-attachments/assets/e09ccc7f-d32a-4161-88a0-d50921bbbf2f" />

Displays:
- Sent files  
- Incoming shares  
- Active threads  
- Reconstruction events  
- Errors/warnings  

Useful for debugging and network monitoring.
