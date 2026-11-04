"""Descriptor-anchored resource transactions; adapted from the Apache-2.0 TAFFISH Kaiju helper."""
import contextlib, ctypes, fcntl, hashlib, json, os, shutil, signal, stat, subprocess, sys, tempfile, time
from pathlib import Path

class Interrupted(BaseException):
    def __init__(self, signum):
        self.signum = signum


def interrupt(signum, _frame):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    raise Interrupted(signum)


@contextlib.contextmanager
def blocked_signals():
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
    try:
        yield
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def inode(metadata):
    return metadata.st_dev, metadata.st_ino


def durable_mode(descriptor, mode, path_metadata):
    """Require descriptor AND directory-entry permissions before publication.

    Shared filesystems may briefly cache the pre-chmod attributes. Retry only
    observation of this same inode; never chmod a mutable path or accept drift.
    """
    identity = inode(os.fstat(descriptor))
    os.fchmod(descriptor, mode)
    os.fsync(descriptor)
    deadline = time.monotonic() + 2
    while True:
        current = path_metadata()
        require(inode(current) == identity, 'entry replaced during permission synchronization')
        if stat.S_IMODE(current.st_mode) == mode and stat.S_IMODE(os.fstat(descriptor).st_mode) == mode:
            return
        require(time.monotonic() < deadline, 'filesystem did not synchronize requested permissions; retained for diagnosis')
        time.sleep(0.02)


def open_directory(path):
    """Open every physical path component without following replacement links."""
    require(path.is_absolute() and '..' not in path.parts, 'absolute physical path required')
    descriptor = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in path.parts[1:]:
            new = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = new
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


class Directory:
    """Descriptor-anchored I/O; cleanup never resolves a mutable parent path."""
    def __init__(self, path=None, parent=None, name=None):
        self.parent, self.name = parent, name
        if parent is None:
            self.path = Path(path).resolve(strict=True)
            self.fd = open_directory(self.path)
        else:
            parent.guard()
            self.path = parent.path / name
            self.fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent.fd)
        self.identity = inode(os.fstat(self.fd))
        self.owned = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        os.close(self.fd)

    def guard(self):
        if self.parent is not None:
            self.parent.guard()
            current = os.stat(self.name, dir_fd=self.parent.fd, follow_symlinks=False)
            require(stat.S_ISDIR(current.st_mode) and inode(current) == self.identity,
                    'directory identity changed; retained for diagnosis: ' + str(self.path))
        else:
            other = open_directory(self.path)
            try:
                require(inode(os.fstat(other)) == self.identity, 'root identity changed; retained for diagnosis')
            finally:
                os.close(other)

    def names(self):
        self.guard()
        # A new open-file description avoids shared readdir cookies/offsets.
        descriptor = os.open('.', os.O_RDONLY | os.O_DIRECTORY, dir_fd=self.fd)
        try:
            return sorted(os.listdir(descriptor))
        finally:
            os.close(descriptor)

    def exists(self, name):
        try:
            os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False

    def info(self, name):
        return os.stat(name, dir_fd=self.fd, follow_symlinks=False)

    def file(self, name, flags=os.O_RDONLY, mode=0o600):
        self.guard()
        descriptor = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, mode, dir_fd=self.fd)
        try:
            metadata = os.fstat(descriptor)
            require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1,
                    'not a single-link regular file: ' + name)
            require(inode(self.info(name)) == inode(metadata), 'file identity changed: ' + name)
            return descriptor
        except BaseException:
            os.close(descriptor)
            raise

    def read(self, name, limit=1024**2):
        descriptor = self.file(name)
        with os.fdopen(descriptor, 'rb') as stream:
            require(os.fstat(stream.fileno()).st_size <= limit, 'metadata too large: ' + name)
            return stream.read()

    def digest(self, name):
        descriptor = self.file(name)
        with os.fdopen(descriptor, 'rb') as stream:
            fields = ('st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_uid', 'st_gid', 'st_nlink')
            changes = {}
            for attempt in range(3):
                # Shared mounts can refresh cached attributes on the first read.
                # Discard that entire digest, never the stability checks. Accept
                # only a complete stable read of the same single-link inode.
                stream.seek(0)
                before = os.fstat(stream.fileno())
                h = hashlib.sha256()
                for block in iter(lambda: stream.read(8 * 1024**2), b''):
                    h.update(block)
                after = os.fstat(stream.fileno())
                self.guard()
                require(inode(self.info(name)) == inode(after), 'file replaced during verification: ' + name)
                require(after.st_nlink == 1, 'file link count changed during verification: ' + name)
                changes = {field: (getattr(before, field), getattr(after, field))
                           for field in fields if getattr(before, field) != getattr(after, field)}
                if not changes:
                    return before.st_size, h.hexdigest()
                if attempt < 2:
                    time.sleep(0.02)
            raise ValueError('file changed during verification: ' + name + ' ' + json.dumps(changes))

    def create(self, name):
        # Record ownership before a pending signal can reach cleanup.
        with blocked_signals():
            descriptor = self.file(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            self.owned[name] = inode(os.fstat(descriptor))
        return os.fdopen(descriptor, 'wb')

    def write(self, name, content):
        with self.create(name) as stream:
            stream.write(content)
            stream.flush()
            durable_mode(stream.fileno(), 0o644, lambda: self.info(name))

    def clean_owned(self):
        self.guard()
        require(set(self.names()) == set(self.owned), 'unexpected staging entry; retained for diagnosis')
        for name, identity in self.owned.items():
            metadata = self.info(name)
            require(stat.S_ISREG(metadata.st_mode) and inode(metadata) == identity,
                    'staging file replaced; retained for diagnosis: ' + name)
        for name, identity in self.owned.items():
            self.guard()
            metadata = self.info(name)
            require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1 and inode(metadata) == identity,
                    'staging entry changed before cleanup; retained: ' + name)
            os.unlink(name, dir_fd=self.fd)
        self.guard()
        os.rmdir(self.name, dir_fd=self.parent.fd)


def check_directory(root, writable=False, mode=None):
    root.guard()
    metadata = os.fstat(root.fd)
    require(not metadata.st_mode & 0o022, 'root must not be group/world writable')
    if mode is not None:
        require(stat.S_IMODE(metadata.st_mode) == mode, 'directory permission drift: ' + str(root.path))
    if writable:
        require(metadata.st_uid == os.geteuid() and metadata.st_mode & 0o200,
                'installer must own and be able to write root')


def promote(parent, source, destination):
    parent.guard()
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, 'renameat2', None)
    require(rename is not None, 'atomic no-replace promotion unavailable')
    if rename(parent.fd, os.fsencode(source), parent.fd, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), destination)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(',', ':')).encode()


def command(stage, argv, cwd=None, pass_fds=()):
    # A disk-backed bounded diagnostic tail avoids storing large progress logs in RAM.
    with tempfile.TemporaryFile() as log:
        child = None
        try:
            with blocked_signals():
                child = subprocess.Popen(argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, pass_fds=pass_fds)
            code = child.wait()
        except BaseException:
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
            raise
        if code:
            log.seek(max(0, log.tell() - 32768))
            print(f'squidpy-data: stage={stage} exit={code}', file=sys.stderr)
            print('\n'.join(log.read().decode(errors='replace').splitlines()[-100:]), file=sys.stderr)
            raise SystemExit(code if code > 0 else 128 - code)


def obtain(item, cache, source_dir):
    blob = item['sha256']
    partial = item['sha256'] + '.part'
    if cache.exists(blob):
        require(cache.digest(blob) == (item['size'], item['sha256']), 'corrupt cache; inspect exact file: ' + blob)
        return blob
    descriptor = cache.file(partial, os.O_RDWR | os.O_CREAT)
    with os.fdopen(descriptor, 'r+b', buffering=0) as out:
        metadata = os.fstat(descriptor)
        require(metadata.st_uid == os.geteuid() and not metadata.st_mode & 0o077, 'partial must be private and owned')
        require(metadata.st_size <= item['size'], 'oversize partial cache')
        if source_dir is not None:
            with Directory(source_dir) as source:
                require(source.digest(item['name']) == (item['size'], item['sha256']), 'source checksum/size mismatch')
                with os.fdopen(source.file(item['name']), 'rb') as inp:
                    remaining = metadata.st_size
                    while remaining:
                        block = inp.read(min(8 * 1024**2, remaining))
                        require(block, 'source truncated during resume; partial retained')
                        require(out.read(len(block)) == block, 'partial prefix differs from source; retained')
                        remaining -= len(block)
                    shutil.copyfileobj(inp, out, 8 * 1024**2)
        elif metadata.st_size < item['size']:
            command('download', ['curl', '--fail', '--location', '--proto', '=https', '--proto-redir', '=https',
                                '--connect-timeout', '30', '--speed-limit', '1024', '--speed-time', '120',
                                '--retry', '3', '--retry-delay', '3', '--continue-at', '-',
                                '--max-filesize', str(item['size']), '--output', '/proc/self/fd/' + str(descriptor), item['url']],
                    pass_fds=(descriptor,))
        os.fsync(descriptor)
        require(inode(cache.info(partial)) == inode(metadata), 'partial replaced; retained for diagnosis')
    require(cache.digest(partial) == (item['size'], item['sha256']),
            'download checksum/size mismatch; private partial retained: ' + partial)
    promote(cache, partial, blob)
    return blob
