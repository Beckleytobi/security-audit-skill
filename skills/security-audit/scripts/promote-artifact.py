"""Trusted Linux-side promotion of one declared scratch file.

This runs only after the target container has exited. Both directory roots are
Docker mounts supplied by the parent, never paths supplied by target code.
"""

import os
import stat
import sys


MAX_BYTES = 1048576


def promote(name):
    if not name or name in {".", ".."} or "/" in name or "\\" in name or "\x00" in name:
        raise ValueError("artifact must be one simple filename")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    scratch = os.open("/scratch", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    artifacts = os.open("/artifacts", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        source = os.open(name, flags, dir_fd=scratch)
        try:
            before = os.fstat(source)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_BYTES:
                raise ValueError("source type, link count, or size rejected")
            data = bytearray()
            while len(data) <= before.st_size:
                chunk = os.read(source, min(65536, before.st_size + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
            after = os.fstat(source)
            if len(data) != before.st_size or (
                after.st_dev, after.st_ino, after.st_mode, after.st_nlink,
                after.st_size, after.st_mtime_ns, after.st_ctime_ns
            ) != (
                before.st_dev, before.st_ino, before.st_mode, before.st_nlink,
                before.st_size, before.st_mtime_ns, before.st_ctime_ns
            ):
                raise ValueError("source changed during promotion")
            destination = os.open(
                name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600, dir_fd=artifacts,
            )
            try:
                result = os.fstat(destination)
                if not stat.S_ISREG(result.st_mode) or result.st_nlink != 1:
                    raise ValueError("destination type or link count rejected")
                view = memoryview(data)
                while view:
                    view = view[os.write(destination, view):]
                os.fsync(destination)
            except BaseException:
                os.close(destination)
                os.unlink(name, dir_fd=artifacts)
                raise
            else:
                os.close(destination)
        finally:
            os.close(source)
    finally:
        os.close(artifacts)
        os.close(scratch)


if __name__ == "__main__":
    try:
        promote(sys.argv[1])
    except (IndexError, OSError, ValueError) as error:
        print(f"promotion rejected: {error}", file=sys.stderr)
        sys.exit(1)
