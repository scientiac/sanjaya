# sanjaya
A medium of communication for specially abled people.

The key in the project is a fake.
Requirements are available in requirements.txt.

After installing the requirements run the server with the following command and connect to the server address it prints out via a browser:
```bash
python index.py
```

This will be on a raspberry Pi and can be ported to cheaper boards for affordability with compromises being:
1. Unable to use the device without internet if online generativve modals are used in a cheaper hardware.
1. Expensive hardware will be able to run the predictive modals on device thus not needing a constant internet connection.

## GPIO
Button connected to `GPIO17` on raspberry pi and `Ground`.
