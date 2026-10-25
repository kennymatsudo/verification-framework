# Vault requirements

- VR-1 A secret stored under a name can be read back under that name by a caller with the service token.
- VR-2 A call without the service token is refused with 401 and reads or writes nothing.
- VR-3 The service refuses to start without the service token, so a misconfigured deploy fails loudly.
