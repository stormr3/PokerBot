"""Check 7: Slow CPU stress test (3 concurrent matches + 2 busy-loop processes pinned to same cores)."""
import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

PY311 = r"C:\Users\Deep\AppData\Local\Programs\Python\Python311\python.exe"
BOT = str(Path(os.environ["TEMP"]) / "pb_ship_extract" / "bot.py")
ENGINE = r"c:\VSC_Projects\PokerBots\engine.py"


def pin_current_process(mask: int) -> None:
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    k32.SetProcessAffinityMask.restype = ctypes.c_int
    handle = k32.GetCurrentProcess()
    ok = k32.SetProcessAffinityMask(handle, mask)
    if not ok:
        raise OSError(f"SetProcessAffinityMask({mask:#x}) failed: {ctypes.GetLastError()}")


def get_affinity_mask(pid_or_handle=None) -> int:
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.GetProcessAffinityMask.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
    ]
    k32.GetProcessAffinityMask.restype = ctypes.c_int
    h = pid_or_handle if pid_or_handle is not None else k32.GetCurrentProcess()
    proc_mask = ctypes.c_size_t()
    sys_mask = ctypes.c_size_t()
    ok = k32.GetProcessAffinityMask(h, ctypes.byref(proc_mask), ctypes.byref(sys_mask))
    return proc_mask.value if ok else -1


def main():
    # Pin driver to 2 logical cores (CPU 0 and CPU 1 -> mask 0x3).
    # Child processes (2 busy loops + 3 engine.py + their bot subprocesses) inherit this affinity.
    mask = 0x3
    pin_current_process(mask)
    print(f"Pinned driver PID={os.getpid()} to affinity mask={get_affinity_mask():#x}")

    busy_code = "x=0\nwhile True:\n x=(x+1)&0xffffffff"
    busy_procs = [
        subprocess.Popen([PY311, "-c", busy_code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(2)
    ]
    print(f"Started 2 busy-loop processes: {[p.pid for p in busy_procs]}")

    matches = [
        ("m1_call", r"opponents\always_call.py", "901", r"audit\logs_ship_slow1"),
        ("m2_raise", r"opponents\always_raise.py", "902", r"audit\logs_ship_slow2"),
        ("m3_tight", r"opponents\tight_raiser.py", "903", r"audit\logs_ship_slow3"),
    ]

    t0 = time.perf_counter()
    procs = []
    try:
        for name, opp, seed, log_dir in matches:
            p = subprocess.Popen(
                [
                    PY311, ENGINE, BOT, opp,
                    "--stage", "1", "--seed", seed,
                    "--log-dir", log_dir, "--python", PY311,
                ],
                cwd=r"c:\VSC_Projects\PokerBots",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            print(f"Launched {name} PID={p.pid} affinity={get_affinity_mask(int(p._handle)):#x}", flush=True)
            procs.append((name, p))

        for name, p in procs:
            out, err = p.communicate(timeout=300)
            elapsed = time.perf_counter() - t0
            print(f"\n=== {name} (exit={p.returncode}, wall={elapsed:.1f}s) ===")
            print(out.strip())
            if err.strip():
                print("STDERR:", err.strip())
    finally:
        for bp in busy_procs:
            bp.kill()
            bp.wait()
        print("\nStopped 2 busy-loop processes.")


if __name__ == "__main__":
    main()
