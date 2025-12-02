# Visually Encrypted Image Transfer Application (VEITA)

## Description
VEITA is a tool for performing **visual cryptography–based image splitting and secure multi-channel transfer**.  
It generates multiple image shares, sends them over customizable network channels, and reconstructs the original only when enough shares are received.

Originally created for a cryptography course, it now includes full support for complex network routing, multi-threaded receivers, shuffled ports, and automated reconstruction.

## Usages
### Generating Shares
```
python viscrypt.py gen input_image output_prefix n [--send hosts] [--send-port start_port]
```
#### Parameters
| Argument | Description |
| -------- | ------- |
| input_image  | Source image file name |
| output_prefix | Prefix for generated share files |
| n | Number of shares to generate |
| --send hosts | Send generated shares to targets |
| --send-port start_port | Starting port for auto assigned ports (default: 8000) |

#### Host formats supported
- `"x.x.x.x"` for auto-port assignment
- `"x.x.x.x:port"` or `x.x.x.x:port;x.x.x.x:port;...;x.x.x.x:port` for explicit port
- `"x.x.x.x;x.x.x.x;...;x.x.x.x"` for multiple reciever

### Receiving Shares
```
python viscrypt.py recv host port dest_dir [--max n] [--reconstruct-after k] [--scramble-ports N]
```
#### Parameters
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

## License
This project was developed for academic purposes in cryptography courses.
Use responsibly.
