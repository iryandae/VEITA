# Visually Encrypted Image Transfer Application (VEITA)
## Description
This application was made for image encryption using visual cryptographic method to improve security and privacy in data transfer in a form of image(s). This was a project for my cryptography course.

## Usages
To run the code as **sender**, use this following command:
```
python viscrypt.py gen input output n [--send hosts] [--send-port start_port]
```
Make sure to change the input to the image name and the n value for the number of shares wanted.
Targetet host are required to send the image while the port will be set as default (8000) if left empty.

To run the code as **reciever**, use this following command:
```
python viscrypt.py recv host port dest_dir [--max n] [--reconstruct-after k]
```
Make sure to change the host, ports, and destination directory for saving the received image(s).
You can also limit the number of shares received and enabling auto reconstruct after receiving a certain amount of shares.

The `attacker.py` simulate outsider that trying to interupt image transfer between sender and reciever.
You can run it using this following command:
```
python attacker.py recv host port dest_dir
```
Make sure to assign the host and port you want to interupt.
The destination directory will be the location you want to use to save the received image(s).
