#!/usr/bin/env python3
"""Tiny two-pass 8051 assembler for the handful of instructions our patches use.

Source is a list of strings; "label:" defines a label.  Supported forms:
  MOV DPTR,#imm16   LCALL addr|label   LJMP addr|label   RET
  MOVX A,@DPTR      MOVX @DPTR,A       INC DPTR          CLR A     CLR C
  MOV Rn,A          MOV A,Rn           MOV Rn,#imm       MOV Rn,dir        MOV A,#imm
  MOV dir,A         MOV A,dir          MOV dir,#imm      ORL A,Rn          ADD A,Rn
  ANL A,#imm        ORL A,#imm         SUBB A,#imm       RLC A             INC Rn
  JZ/JNZ/JC/JNC/SJMP label             CJNE Rn,#imm,label                PUSH/POP dir
  DB b1,b2,...
"""
import re

RN = {"R%d" % i: i for i in range(8)}
SFR = {"ACC": 0xE0, "B": 0xF0, "DPL": 0x82, "DPH": 0x83, "PSW": 0xD0}


def num(t):
    t = t.strip()
    if t.upper() in SFR:
        return SFR[t.upper()]
    return int(t[:-1], 16) if t.lower().endswith("h") else int(t, 0)


def assemble(lines, origin):
    def encode(op, args, pc, labels, final):
        def target(t):
            if t in labels:
                return labels[t]
            if final:
                raise ValueError("unknown label %s" % t)
            return pc
        def rel(t, size):
            off = target(t) - (pc + size)
            if final and not -128 <= off <= 127:
                raise ValueError("branch out of range at 0x%04X -> %s" % (pc, t))
            return off & 0xFF
        a = [x.strip() for x in args.split(",")] if args else []
        u = [x.upper() for x in a]
        if op == "RET": return [0x22]
        if op == "CLR" and u == ["A"]: return [0xE4]
        if op == "CLR" and u == ["C"]: return [0xC3]
        if op == "RLC" and u == ["A"]: return [0x33]
        if op == "INC" and u == ["DPTR"]: return [0xA3]
        if op == "INC" and u == ["A"]: return [0x04]
        if op == "INC" and u[0] in RN: return [0x08 + RN[u[0]]]
        if op == "MOVX" and u == ["A", "@DPTR"]: return [0xE0]
        if op == "MOVX" and u == ["@DPTR", "A"]: return [0xF0]
        if op in ("LCALL", "LJMP"):
            t = target(a[0]) if a[0] in labels or not re.match(r"^(0x|[0-9])", a[0]) else num(a[0])
            return [0x12 if op == "LCALL" else 0x02, (t >> 8) & 0xFF, t & 0xFF]
        if op in ("JZ", "JNZ", "JC", "JNC", "SJMP"):
            return [{"JZ": 0x60, "JNZ": 0x70, "JC": 0x40, "JNC": 0x50, "SJMP": 0x80}[op], rel(a[0], 2)]
        if op == "CJNE" and u[0] == "A" and a[1].startswith("#"):
            return [0xB4, num(a[1][1:]), rel(a[2], 3)]
        if op == "CJNE" and u[0] in RN:
            return [0xB8 + RN[u[0]], num(a[1][1:]), rel(a[2], 3)]
        if op in ("PUSH", "POP"):
            return [0xC0 if op == "PUSH" else 0xD0, num(a[0])]
        if op == "DB":
            return [num(x) for x in a]
        if op in ("ORL", "ANL", "ADD", "SUBB") and u[0] == "A":
            base = {"ORL": 0x40, "ANL": 0x50, "ADD": 0x20, "SUBB": 0x90}[op]
            if u[1] in RN: return [base + 8 + RN[u[1]]]
            if a[1].startswith("#"): return [base + 4, num(a[1][1:])]
        if op == "MOV":
            d, s = u
            if d == "DPTR": v = num(a[1][1:]); return [0x90, v >> 8, v & 0xFF]
            if d in RN and s == "A": return [0xF8 + RN[d]]
            if d == "A" and s in RN: return [0xE8 + RN[s]]
            if d in RN and s.startswith("#"): return [0x78 + RN[d], num(a[1][1:])]
            if d in RN: return [0xA8 + RN[d], num(a[1])]
            if d == "A" and s.startswith("#"): return [0x74, num(a[1][1:])]
            if d == "A": return [0xE5, num(a[1])]
            if s == "A": return [0xF5, num(a[0])]
            if s.startswith("#"): return [0x75, num(a[0]), num(a[1][1:])]
            return [0x85, num(a[1]), num(a[0])]          # MOV dir,dir: src then dst
        raise ValueError("unsupported: %s %s" % (op, args))

    def one_pass(labels, final):
        pc, out, new = origin, [], {}
        for raw in lines:
            line = raw.split(";")[0].strip()
            if not line:
                continue
            if line.endswith(":"):
                new[line[:-1]] = pc
                continue
            op, _, args = line.partition(" ")
            enc = encode(op.upper(), args.strip(), pc, labels, final)
            out += enc
            pc += len(enc)
        return bytes(out), new

    _, labels = one_pass({}, False)
    code, labels2 = one_pass(labels, False)
    code, _ = one_pass(labels2, True)
    return code
