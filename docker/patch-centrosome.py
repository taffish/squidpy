"""Apply the documented packaging/byte-API backport to the exact upstream sdist."""
import hashlib
from pathlib import Path


def edit(name, expected, changes):
    path = Path(name)
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise SystemExit(f"unexpected upstream file: {name}")
    for old, new in changes:
        if data.count(old) != 1:
            raise SystemExit(f"expected one patch hunk in {name}")
        data = data.replace(old, new)
    path.write_bytes(data)


edit("setup.py", "84285ad22655be790936671eca0007fff999a692cd86dbc2ce38e240eb6fde7c", [
    (b'"pillow>=7.1.0,<12"', b'"pillow==13.0.0"'),
    (b'version="1.3.4"', b'version="1.3.4+taffish.1"'),
])
edit("centrosome/bg_compensate.py", "3024eb5650ddf11f40ea2f1ecbacb6b6909c958778540b13da3d5e1ce8c07998", [
    (b'if img.mode == "I;16":', b'if img.mode in ("I;16", "I;16L", "I;16B", "I;16N"):'),
    (b'np.fromstring(img.tostring(), np.uint8)', b'np.frombuffer(img.tobytes(), np.uint8)'),
    (b'if img.tag.prefix == "MM" else', b'if img.mode == "I;16B" else'),
    (b'if 281 in img.tag:', b'if 281 in getattr(img, "tag", {}):'),
    # An L pixel converts exactly to float32 (0..255), with no rescaling.
    # backgr uses finfo; its numerical code and stop criterion are untouched.
    (b'        img = np.array(img)', b'        img = np.array(img, dtype=np.float32) if img.mode == "L" else np.array(img)'),
])
