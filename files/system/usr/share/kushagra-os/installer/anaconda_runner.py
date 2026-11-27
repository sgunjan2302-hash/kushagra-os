#!/usr/bin/env python3
"""Non-interactive Anaconda launcher for Kushagra OS Stage 1 K-Installer."""

import runpy
import sys
import traceback

from pyanaconda.core.configuration.system import SystemSection


def _extract_exc_tuple(exc_info):
    """Extract a (type, value, traceback) tuple from meh/Anaconda exception objects."""
    if exc_info is None:
        return None
    inner = getattr(exc_info, "exc_info", None)
    if inner is not None and inner is not exc_info:
        extracted = _extract_exc_tuple(inner)
        if extracted is not None:
            return extracted
    if isinstance(exc_info, tuple) and len(exc_info) == 3 and exc_info[0] is not None:
        return exc_info
    ty = getattr(exc_info, "type", None)
    val = getattr(exc_info, "value", None)
    tb = getattr(exc_info, "stack", None) or getattr(exc_info, "tb", None)
    if ty is not None and val is not None:
        return (ty, val, tb)
    return None


def _non_interactive_handle_exception(self, *args, **kwargs):
    """Fail fast on Anaconda exceptions instead of hanging on TTY prompts."""
    exc_info = args[0] if args else kwargs.get("exc_info") or kwargs.get("dump_info")
    exc_tuple = _extract_exc_tuple(exc_info)
    if exc_tuple is not None:
        traceback.print_exception(*exc_tuple, file=sys.stderr)
    else:
        cur_ty, cur_val, cur_tb = sys.exc_info()
        if cur_ty is not None:
            traceback.print_exception(cur_ty, cur_val, cur_tb, file=sys.stderr)
        elif exc_info is not None:
            print(f"Anaconda exception: {exc_info!r}", file=sys.stderr)
        else:
            print("Anaconda exception occurred without traceback details.", file=sys.stderr)
    sys.stderr.flush()

    try:
        run_ks = getattr(self, "_run_kickstart_scripts", None)
        if callable(run_ks):
            run_ks()
    except Exception as ks_exc:
        print(f"Warning: _run_kickstart_scripts failed: {ks_exc}", file=sys.stderr)
        sys.stderr.flush()

    sys.exit(1)


def _patch_anaconda() -> None:
    """Prevent premature reboot, TTY takeover, and LiveCD keyboard hijacking."""
    SystemSection.can_reboot = property(lambda self: False)
    SystemSection.can_switch_tty = property(lambda self: False)
    SystemSection.can_audit = property(lambda self: False)
    SystemSection.can_activate_keyboard = property(lambda self: False)
    SystemSection.can_activate_layouts = property(lambda self: False)

    try:
        from pyanaconda.exception import AnacondaExceptionHandler

        AnacondaExceptionHandler.handleException = _non_interactive_handle_exception
    except Exception as exc:
        print(
            f"Warning: could not install non-interactive AnacondaExceptionHandler: {exc}",
            file=sys.stderr,
        )
        sys.stderr.flush()


def main() -> None:
    _patch_anaconda()
    sys.argv = ["/usr/bin/anaconda", *sys.argv[1:]]
    runpy.run_path("/usr/bin/anaconda", run_name="__main__")


if __name__ == "__main__":
    main()
