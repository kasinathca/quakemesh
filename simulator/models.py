from __future__ import annotations
from dataclasses import dataclass

@dataclass
class VirtualPhone:
    device_id:str
    latitude:float
    longitude:float
    seq:int=0
    def next_seq(self)->int:
        self.seq+=1; return self.seq
