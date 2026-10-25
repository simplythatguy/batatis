"""Desktop engine entry: `python -m engine.desktop`, started only by the desktop host over pipes."""
from __future__ import annotations

import os
import sys


def main() -> None:
    from . import bridge
    from .workspace import BODY_LIMIT, Workspace, WorkspaceRefused, config_from_env

    write = bridge.protocol_output()
    try:
        workspace = Workspace(config_from_env(os.environ))
    except WorkspaceRefused as refused:
        write(bridge.encode({'t': 'refused', 'protocol': bridge.PROTOCOL, 'reason': str(refused)}))
        os._exit(3)
    clean = bridge.run(workspace.app(), hello=workspace.hello(), control=workspace.control,
                       body_limit=BODY_LIMIT, write=write)
    sys.stderr.flush()
    # A synchronous handler still running in a worker thread must not keep the process alive.
    os._exit(0 if clean else 2)


if __name__ == '__main__':
    main()
