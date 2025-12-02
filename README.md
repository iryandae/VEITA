# Visually Encrypted Image Transfer Application (VEITA)
## Description
This application was made for image encryption using visual cryptographic method to improve security and privacy in data transfer in a form of image(s). This was a project for my cryptography course.

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
