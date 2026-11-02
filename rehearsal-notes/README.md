`test_no_echo_canary.py` is the no-echo canary harness, and `walk.log` is the end-to-end script-layer walk on a synthetic request (THHSRDLENQ-99186, THHSAQUIRE-99187).
Both ran against `rehearsal/dogfood` at 07c0171. In the log, `<repo>` is this checkout and `<project>` is the throwaway request project.
Run the harness from the repository root with `python3 -I rehearsal-notes/test_no_echo_canary.py`. It needs bash, jq and git, prints one line per case (LEAK, clean or by-design) and never fails.
