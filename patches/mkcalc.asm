; PCR state-1 fallback for the XREAL Air 2 DP bridge (DP 1140).
; Called (LCALL) from 0x472F in place of the "MKvalue = 0x%lx" debug print.
; If the hardware measurement MK (XDATA 0448) is non-zero, return untouched.
; Otherwise derive band/MK from the stream: Q = (bw * Mvid) / (Nvid >> 6),
; bw = IRAM 2Eh (DPCD 0x100 LINK_BW_SET), Mvid = F3CC.., Nvid = F3D8..
; band = doublings until Q*2^band >= 0x7C0; MK = (Q << band) * 116.
fix:
 MOV DPTR,#0448h
 LCALL 1AFEh
 MOV A,R4
 ORL A,R5
 ORL A,R6
 ORL A,R7
 JZ calc
 RET
calc:
 MOV DPTR,#0F3D8h          ; R4..R7 = Nvid
 MOVX A,@DPTR
 MOV R5,A
 INC DPTR
 MOVX A,@DPTR
 MOV R6,A
 INC DPTR
 MOVX A,@DPTR
 MOV R7,A
 CLR A
 MOV R4,A
 MOV R0,#06h
 LCALL 1A9Eh               ; Nvid >> 6
 MOV A,R7
 ORL A,R6
 ORL A,R5
 JNZ nz
 MOV R7,#01h
nz:
 MOV DPTR,#06F8h
 LCALL 1B16h               ; park divisor
 MOV DPTR,#0F3CCh          ; R4..R7 = Mvid
 MOVX A,@DPTR
 MOV R5,A
 INC DPTR
 MOVX A,@DPTR
 MOV R6,A
 INC DPTR
 MOVX A,@DPTR
 MOV R7,A
 CLR A
 MOV R4,A
 MOV R0,A
 MOV R1,A
 MOV R2,A
 MOV R3,2Eh
 LCALL 1963h               ; X = Mvid * bw
 MOV DPTR,#06F8h
 LCALL 1B0Ah               ; R0..R3 = divisor
 LCALL 19EEh               ; Q = X / divisor
 MOV A,R4
 ORL A,R5
 JZ q16
 MOV R6,#0Fh
 MOV R7,#80h
q16:
 MOV R2,#00h
 MOV A,R6
 ORL A,R7
 JNZ loop
 MOV R6,#0Bh               ; no usable stream data: 1080p60 values
 MOV R7,#00h
 MOV R2,#03h
 SJMP mk
loop:
 CLR C
 MOV A,R7
 SUBB A,#0C0h
 MOV A,R6
 SUBB A,#07h
 JNC mk
 CJNE R2,#07h,shift
 SJMP mk
shift:
 MOV A,R7
 ADD A,R7
 MOV R7,A
 MOV A,R6
 RLC A
 MOV R6,A
 INC R2
 SJMP loop
mk:
 MOV DPTR,#0F263h          ; PLL band = R2
 MOVX A,@DPTR
 ANL A,#0F8h
 ORL A,R2
 MOVX @DPTR,A
 CLR A
 MOV R4,A
 MOV R5,A
 MOV R0,A
 MOV R1,A
 MOV R2,A
 MOV R3,#74h
 LCALL 1963h               ; MK = V * 116
 MOV DPTR,#0448h
 LCALL 1B16h
 RET
