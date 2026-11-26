"""Public certificate inventory. Never accepts or stores private keys."""
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import ExtendedKeyUsageOID
from datetime import datetime, timezone

def certificate_metadata(pem: str, purpose: str):
    if pem.count("-----BEGIN CERTIFICATE-----") != 1 or not pem.strip().startswith("-----BEGIN CERTIFICATE-----") or not pem.strip().endswith("-----END CERTIFICATE-----"):
        raise ValueError("Expected one public PEM certificate")
    cert=x509.load_pem_x509_certificate(pem.encode("ascii"))
    if cert.not_valid_after_utc <= datetime.now(timezone.utc):
        raise ValueError("Certificate expired")
    try:
        ca=cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    except x509.ExtensionNotFound:
        ca=False
    if (purpose=="ca")!=ca:
        raise ValueError("Certificate purpose does not match CA constraint")
    if purpose!="ca":
        try:
            eku=cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        except x509.ExtensionNotFound:
            raise ValueError("Extended key usage required")
        expected=ExtendedKeyUsageOID.CLIENT_AUTH if purpose=="client" else ExtendedKeyUsageOID.SERVER_AUTH
        if expected not in eku:
            raise ValueError("Certificate extended key usage mismatch")
    return dict(fingerprint=cert.fingerprint(hashes.SHA256()).hex(),subject=cert.subject.rfc4514_string(),issuer=cert.issuer.rfc4514_string(),serial=format(cert.serial_number,"x"),not_before=cert.not_valid_before_utc,not_after=cert.not_valid_after_utc)
