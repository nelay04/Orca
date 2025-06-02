from py_vapid import Vapid01
from cryptography.hazmat.primitives import serialization
import base64

vapid = Vapid01()
vapid.generate_keys()

# Export public key in raw format (X9.62 uncompressed point format)
public_bytes = vapid.public_key.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint
)
public_key_b64 = base64.urlsafe_b64encode(public_bytes).decode('utf-8')

# Export private key in raw format
private_bytes = vapid.private_key.private_numbers().private_value.to_bytes(32, 'big')
private_key_b64 = base64.urlsafe_b64encode(private_bytes).decode('utf-8')

print("Public Key:", public_key_b64)
print("Private Key:", private_key_b64)
