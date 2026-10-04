"""
SecureStego — Command-Line Interface

Thin wrapper around crypto_service and stego_service for manual testing.

Usage:
  python -m app.cli encode --input cover.png --output stego.png \\
      --message "secret" --mode password --password "s3cure!"

  python -m app.cli decode --input stego.png --password "s3cure!"

  python -m app.cli keygen --output-dir ./keys/

Security note (Rule 5.1): The CLI never logs/prints passwords, keys, or
intermediate crypto material. It prints only the final decoded message
(which the user explicitly requested) and status confirmations.
"""

import argparse
import os
import sys

from app.services.crypto_service import (
    CryptoError,
    encrypt_mode_a,
    encrypt_mode_b,
    decrypt_mode_a,
    decrypt_mode_b,
    generate_rsa_keypair,
)
from app.services.stego_service import (
    StegoError,
    embed,
    extract,
)

# Mode flag constants (same as used throughout the system)
MODE_A_FLAG = 0x00
MODE_B_FLAG = 0x01


def _cmd_encode(args: argparse.Namespace) -> None:
    """Handle the 'encode' subcommand."""
    # Read message from --message or --message-file
    if args.message:
        plaintext = args.message.encode("utf-8")
    elif args.message_file:
        with open(args.message_file, "rb") as f:
            plaintext = f.read()
    else:
        print("Error: Provide --message or --message-file.", file=sys.stderr)
        sys.exit(1)

    # Encrypt based on mode
    if args.mode == "password":
        if not args.password:
            print("Error: --password is required for password mode.", file=sys.stderr)
            sys.exit(1)
        payload = encrypt_mode_a(plaintext, args.password)
        mode_flag = MODE_A_FLAG
    elif args.mode == "user_bound":
        if not args.pubkey:
            print("Error: --pubkey is required for user_bound mode.", file=sys.stderr)
            sys.exit(1)
        with open(args.pubkey, "rb") as f:
            public_key_pem = f.read()
        payload = encrypt_mode_b(plaintext, public_key_pem)
        mode_flag = MODE_B_FLAG
    else:
        print(f"Error: Unknown mode '{args.mode}'.", file=sys.stderr)
        sys.exit(1)

    # Embed into image
    output = embed(args.input, payload, mode_flag, args.output)
    print(f"Encoding complete. Stego image saved to: {output}")


def _cmd_decode(args: argparse.Namespace) -> None:
    """Handle the 'decode' subcommand."""
    # Extract payload and mode flag from stego image
    payload, mode_flag = extract(args.input)

    # Decrypt based on detected mode flag
    if mode_flag == MODE_A_FLAG:
        if not args.password:
            print("Error: --password is required to decode a Mode A image.", file=sys.stderr)
            sys.exit(1)
        plaintext = decrypt_mode_a(payload, args.password)
    elif mode_flag == MODE_B_FLAG:
        if not args.privkey:
            print("Error: --privkey is required to decode a Mode B image.", file=sys.stderr)
            sys.exit(1)
        with open(args.privkey, "rb") as f:
            private_key_pem = f.read()
        plaintext = decrypt_mode_b(payload, private_key_pem)
    else:
        print(f"Error: Unknown mode flag 0x{mode_flag:02X} in stego image.", file=sys.stderr)
        sys.exit(1)

    # Output the decoded message
    try:
        print(f"Decoded message: {plaintext.decode('utf-8')}")
    except UnicodeDecodeError:
        # Binary data — save to file
        out_file = args.output or "decoded_output.bin"
        with open(out_file, "wb") as f:
            f.write(plaintext)
        print(f"Decoded binary data saved to: {out_file}")


def _cmd_keygen(args: argparse.Namespace) -> None:
    """Handle the 'keygen' subcommand — generate an RSA keypair."""
    output_dir = args.output_dir or "."
    os.makedirs(output_dir, exist_ok=True)

    public_pem, private_pem = generate_rsa_keypair()

    pub_path = os.path.join(output_dir, "public.pem")
    priv_path = os.path.join(output_dir, "private.pem")

    with open(pub_path, "wb") as f:
        f.write(public_pem)
    with open(priv_path, "wb") as f:
        f.write(private_pem)

    print(f"RSA keypair generated:")
    print(f"  Public key:  {pub_path}")
    print(f"  Private key: {priv_path}")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="securestego",
        description="SecureStego — Encrypted image steganography",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- encode ---
    encode_parser = subparsers.add_parser("encode", help="Encrypt and embed a message into an image")
    encode_parser.add_argument("--input", "-i", required=True, help="Path to cover image (PNG recommended)")
    encode_parser.add_argument("--output", "-o", required=True, help="Path for output stego image")
    encode_parser.add_argument("--message", "-m", help="Text message to embed")
    encode_parser.add_argument("--message-file", "-f", help="File to embed (binary or text)")
    encode_parser.add_argument("--mode", required=True, choices=["password", "user_bound"],
                               help="Encryption mode: 'password' (Mode A) or 'user_bound' (Mode B)")
    encode_parser.add_argument("--password", "-p", help="Password for Mode A encryption")
    encode_parser.add_argument("--pubkey", help="Path to recipient's public key PEM file (Mode B)")

    # --- decode ---
    decode_parser = subparsers.add_parser("decode", help="Extract and decrypt a message from a stego image")
    decode_parser.add_argument("--input", "-i", required=True, help="Path to stego image")
    decode_parser.add_argument("--password", "-p", help="Password for Mode A decryption")
    decode_parser.add_argument("--privkey", help="Path to private key PEM file (Mode B)")
    decode_parser.add_argument("--output", "-o", help="Output path for decoded binary data (optional)")

    # --- keygen ---
    keygen_parser = subparsers.add_parser("keygen", help="Generate an RSA keypair for Mode B")
    keygen_parser.add_argument("--output-dir", "-d", default=".", help="Directory to save keypair files")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "encode":
            _cmd_encode(args)
        elif args.command == "decode":
            _cmd_decode(args)
        elif args.command == "keygen":
            _cmd_keygen(args)
    except (CryptoError, StegoError) as e:
        # Rule 5.3 — generic error message for all crypto/stego failures
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
