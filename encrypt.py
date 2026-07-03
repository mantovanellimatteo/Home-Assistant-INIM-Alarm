import base64
import os
import sys
import subprocess

# AES-256-CBC Key extracted from inimclient binary
qwords = [
    0x2333634E3F4C6658,
    0x3F2F4D3747316473,
    0x6E42432E337C3D26,
    0x5A4659385431452C
]
key = b""
for q in qwords:
    key += q.to_bytes(8, byteorder='little')
key_hex = key.hex()

def pkcs7_pad(data):
    padding_len = 16 - (len(data) % 16)
    return data + bytes([padding_len] * padding_len)

def encrypt(plaintext):
    padded = pkcs7_pad(plaintext.encode('utf-8'))
    iv = os.urandom(16)
    iv_hex = iv.hex()
    
    proc = subprocess.Popen(
        ['openssl', 'enc', '-aes-256-cbc', '-K', key_hex, '-iv', iv_hex],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = proc.communicate(input=padded)
    if proc.returncode != 0:
        raise Exception(f"Encryption failed: {err.decode('utf-8')}")
        
    final_data = iv + out
    return base64.b64encode(final_data).decode('utf-8')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 encrypt.py <string_to_encrypt>")
        sys.exit(1)
        
    plaintext = sys.argv[1]
    encrypted = encrypt(plaintext)
    print(encrypted)
