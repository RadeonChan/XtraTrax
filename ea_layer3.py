"""Repack MPEG1 Layer3 coefficients into bounded EA SCHl packets."""
from pathlib import Path
import struct
from itertools import chain

class Unsupported(ValueError):pass
class Bits:
 def __init__(self,b):self.bits=''.join(f'{v:08b}' for v in b);self.pos=0
 def take(self,n):
  if n<0 or self.pos+n>len(self.bits):raise ValueError('Truncated MP3 bit data.')
  s=self.bits[self.pos:self.pos+n];self.pos+=n;return s
 def get(self,n):return int(self.take(n),2) if n else 0
def packed(s):
 s+='0'*(-len(s)%8);return int(s,2).to_bytes(len(s)//8,'big')
def validate_side(s):
 # Retail assumes bounded spectral counts and valid Huffman table selectors.
 p=Bits(b'');p.bits=s
 if p.get(9)>288:raise ValueError('Invalid MP3 coefficient count.')
 p.get(8);p.get(4);switched=p.get(1)
 if switched:
  if p.get(2)==0:raise ValueError('Invalid MP3 block type.')
  p.get(1);tables=[p.get(5),p.get(5)]
 else:
  tables=[p.get(5) for _ in range(3)]
  if p.get(4)+p.get(3)>20:raise ValueError('Invalid MP3 frequency regions.')
 if any(t in (4,14) for t in tables):raise ValueError('Invalid MP3 Huffman table.')
def frames(path):
 reservoir=b'';first=True;profile=None
 with Path(path).open('rb') as f:
  head=f.read(10)
  if head[:3]==b'ID3':
   if any(v&128 for v in head[6:10]):raise ValueError('Invalid ID3 size.')
   size=0
   for v in head[6:10]:size=(size<<7)|v
   if size>16*1024*1024:raise ValueError('MP3 metadata too large.')
   f.seek(10+size+(10 if head[3]==4 and head[5]&16 else 0))
  else:f.seek(0)
  while True:
   h=f.read(4)
   if not h:break
   if h[:3]==b'TAG' and len(f.read(125))==124:break
   if len(h)!=4:raise ValueError('Truncated MP3 header.')
   x=int.from_bytes(h,'big');ver=(x>>19)&3;layer=(x>>17)&3;bi=(x>>12)&15;ri=(x>>10)&3;mode=(x>>6)&3
   if x>>21!=2047 or ver!=3 or layer!=1 or not 1<=bi<=14 or ri==3:raise Unsupported('Requires MPEG1 Layer3.')
   rate=[44100,48000,32000][ri];channels=1 if mode==3 else 2
   if profile is not None and profile!=(rate,channels):raise Unsupported('Changing MP3 format.')
   profile=rate,channels
   size=144000*[0,32,40,48,56,64,80,96,112,128,160,192,224,256,320][bi]//rate+((x>>9)&1)
   data=f.read(size-4)
   if len(data)!=size-4:raise ValueError('Truncated MP3 frame.')
   crc=0 if x&(1<<16) else 2;side_size=17 if channels==1 else 32
   side=Bits(data[crc:crc+side_size]);main=data[crc+side_size:]
   back=side.get(9);side.get(5 if channels==1 else 3);scfsi=[side.take(4) for _ in range(channels)]
   info=[[(side.get(12),side.take(47)) for _ in range(channels)] for _ in range(2)]
   for granule in info:
    for _,s in granule:validate_side(s)
   if first and main[:4] in (b'Info',b'Xing'):
    # Xing is metadata, not an audio frame. Keep its reservoir bytes if referenced.
    reservoir=main[-511:];first=False;continue
   first=False
   if back>len(reservoir):raise ValueError('MP3 reservoir underflow.')
   bits=Bits((reservoir[-back:] if back else b'')+main);packet=b''
   for gr in range(2):
    s=f'00000000{ver:02b}{ri:02b}{mode:02b}{(x>>4)&3:02b}{gr:01b}'
    if gr:s+=''.join(scfsi)
    s+=''.join(f'{n:012b}'+si for n,si in info[gr])
    s+=''.join(bits.take(n) for n,_ in info[gr]);packet+=packed(s)
   reservoir=(reservoir+main)[-511:]
   yield rate,channels,packet
def field(k,v):
 b=v.to_bytes(max(1,(v.bit_length()+7)//8),'big');b=b'\0'+b if b[0]&128 else b
 return bytes([k,len(b)])+b
def block(tag,b):
 b+=b'\0'*(-len(b)%4);return tag+struct.pack('<I',len(b)+8)+b
def write(path,dest,samples,progress=lambda value:None):
 if not 0<samples<=44100*60*30:raise ValueError('Track must be between one sample and 30 minutes.')
 count=0;remaining=samples
 packets=iter(frames(path));initial=[]
 for _ in range(2):
  try:initial.append(next(packets))
  except StopIteration:break
 groups=chain([initial] if initial else [],([p] for p in packets))
 with Path(dest).open('wb') as f:
  for group in groups:
   rate,ch,_=group[0];payload=b''.join(p[2] for p in group)
   if (rate,ch)!=(44100,2):raise Unsupported('Direct repacking requires 44.1 kHz stereo.')
   if count==0:
    header=b'PT\0\0'+bytes.fromhex('06 01 65 0b 01 02 fd')+b''.join(field(k,v) for k,v in [(0x80,2),(0x85,samples),(0x82,ch),(0x84,rate),(0xa0,23)])+b'\xff'
    f.write(block(b'SCHl',header));count_pos=f.tell();f.write(block(b'SCCl',struct.pack('<I',0)))
   # Two initial frames let independent MPEG reconstruction establish sync.
   # Join raw granules here; SCHl alignment padding is added only afterwards.
   n=min(len(group)*1152-1105 if count==0 else 1152,remaining)
   if n:
    f.write(block(b'SCDl',struct.pack('<III',n,0,1)+payload));remaining-=n;count+=1
    progress((samples-remaining)/samples)
  if remaining or not count:raise ValueError('MP3 contains insufficient audio.')
  f.write(block(b'SCEl',b''));f.seek(count_pos);f.write(block(b'SCCl',struct.pack('<I',count)))
 return dict(samples=samples,packets=count,bytes=Path(dest).stat().st_size)
def direct_compatible(path):
 """Only preserve streams with an explicit, supported gapless encoder delay."""
 with Path(path).open('rb') as f:
  h=f.read(10)
  if h[:3]==b'ID3':
   if len(h)!=10 or any(v&128 for v in h[6:10]):return False
   size=0
   for v in h[6:10]:size=(size<<7)|v
   if size>16*1024*1024:return False
   f.seek(10+size+(10 if h[3]==4 and h[5]&16 else 0))
  else:f.seek(0)
  b=f.read(1600)
 if len(b)<40:return False
 x=int.from_bytes(b[:4],'big')
 if x>>21!=2047 or (x>>19)&3!=3 or (x>>17)&3!=1 or (x>>10)&3!=0 or (x>>6)&3==3:return False
 offset=36+(0 if x&(1<<16) else 2)
 if b[offset:offset+4] not in (b'Info',b'Xing'):return False
 flags=int.from_bytes(b[offset+4:offset+8],'big');pos=offset+8
 for flag,size in [(1,4),(2,4),(4,100),(8,4)]:
  if flags&flag:pos+=size
 if b[pos:pos+4] not in (b'LAME',b'Lavf',b'Lavc'):return False
 delay=int.from_bytes(b[pos+21:pos+24],'big')>>12
 return delay==576
