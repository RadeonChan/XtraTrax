"""Package existing Breathe artwork as an ICO; requires Pillow 12.3.0.
Uses the retained Wikimedia PNG rendering. No generated or redrawn artwork.
"""
from pathlib import Path
import hashlib
from PIL import Image
root=Path(__file__).resolve().parent
source=root/'third-party-icon/Breathe-media-optical-500.png'
assert hashlib.sha256(source.read_bytes()).hexdigest()=="41a1d82189d56384c0b0be5f825a57b009cbedba72e52fb89cc90b5840ac9d4a"
sizes=[16,20,24,32,40,48,64,128,256]
with Image.open(source) as original:
 assert original.size==(500,500)
 frames=[original.convert('RGBA').resize((n,n),Image.Resampling.LANCZOS) for n in sizes]
frames[-1].save(root/'assets/XtraTrax.ico',format='ICO',sizes=[(n,n) for n in sizes],append_images=frames[:-1])
print('Packaged original Breathe artwork at sizes:',sizes)
