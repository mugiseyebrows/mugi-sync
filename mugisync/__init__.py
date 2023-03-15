from eventloop import EventLoop, FileSystemWatch, Timer, SingleShotTimer, walk, Schedule
import eventloop.base
from colorama import Fore, Back, Style, init as colorama_init
import os
import shutil
import datetime
from dataclasses import dataclass
import argparse
import re
import paramiko

# set DEBUG_MUGISYNC=1
# DEBUG_MUGISYNC=1
if 'DEBUG_MUGISYNC' in os.environ and os.environ['DEBUG_MUGISYNC'] == "1":
    debug_print = print
else:
    debug_print = lambda *args, **kwargs: None

@dataclass
class MainArgs:
    src: str
    dst: str
    include: list = None
    exclude: list = None
    short_log: bool = False
    create: bool = False
    no_initial_sync: bool = False

@dataclass
class SshArgs:
    host: str
    user: str
    password: str
    key: str
    src: str
    dst: str

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class Logger(eventloop.base.Logger):

    def __init__(self, src, dst):
        super().__init__()
        self._src = src
        self._dst = dst

    def print_info(self, msg):
        print(Fore.WHITE + now_str() + " " + Fore.YELLOW + Style.BRIGHT + msg + Fore.RESET + Style.NORMAL)

    def print_question(self, msg):
        print(Fore.WHITE + Fore.MAGENTA + Style.BRIGHT + msg + Fore.RESET + Style.NORMAL + " ", end="")

    def print_error(self, msg):
        print(Fore.WHITE + now_str() + " " + Fore.RED + msg + Fore.RESET)

    def print_copied(self, src, dst):
        print(Fore.WHITE + now_str() + " " + Fore.GREEN + Style.BRIGHT + src + Fore.WHITE + ' -> ' + Fore.GREEN + dst + Fore.RESET + Style.NORMAL)


def unix_path_join(*args):
    return os.path.join(*args).replace("\\","/")

def count_slashes(path):
    cnt = 0
    for c in path:
        if c == '/' or c == '\\':
            cnt += 1
    return cnt

def sftp_put_files(sshArgs: SshArgs, files, logger: Logger):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(sshArgs.host, username=sshArgs.user, password=sshArgs.password, key_filename=sshArgs.key)
    ftp = ssh.open_sftp()

    dirs = set()

    for src in files:

        rel = os.path.relpath(src, sshArgs.src)

        dst = unix_path_join(sshArgs.dst, rel)

        dirname = os.path.dirname(dst)
        
        while dirname != '/':
            if dirname == '':
                break
            dirs.add(dirname)
            dirname = os.path.dirname(dirname)

    dirs = list(dirs)

    dirs.sort(key=count_slashes)

    #print("dirs", dirs); exit(0)

    for d in dirs:
        try:
            ftp.mkdir(d)
        except IOError as e:
            #print(e)
            pass

    for src in files:
        rel = os.path.relpath(src, sshArgs.src)
        dst = unix_path_join(sshArgs.dst, rel)
        #print("{} ftp.put {} {}".format(datetime.datetime.now(), src, dst))
        
        try:
            ftp.put(src, dst)
            logger.print_copied(src, dst)
        except IOError as e:
            logger.print_error(str(e))
    ftp.close()

def makedirs(path):
    try:
        os.makedirs(path)
    except OSError:
        pass

def create_dir(src, dst, logger):
    dst_dir = os.path.dirname(dst)
    makedirs(dst_dir)
    ok = os.path.isdir(dst_dir)
    if not ok:
        logger.print_error("Failed to create {}".format(dst_dir))
    return ok

def remove_dst(src, dst, logger):
    if not os.path.exists(dst):
        return True
    try:
        os.remove(dst)
    except Exception as e:
        logger.print_error("Failed to remove {}".format(dst))
        print(e)
        return False
    return True

def copy_to_dst(src, dst, logger):
    try:
        shutil.copy(src, dst)
    except Exception as e:
        logger.print_error("Failed to copy {} -> {}".format(src, dst))
        print(e)
        return False
    return True

class Executor(eventloop.base.Executor):

    def __init__(self, sshArgs, logger):
        super().__init__()
        self._sshArgs = sshArgs
        self._logger = logger

    def execute(self, task):
        src, dst = task

        if os.path.isdir(src):
            return True
            
        if not os.path.exists(src):
            return True

        logger = self._logger

        if self._sshArgs:
            sftp_put_files(self._sshArgs, [src], logger)
        else:
            ok = create_dir(src, dst, logger)
            ok = ok and remove_dst(src, dst, logger)
            ok = ok and copy_to_dst(src, dst, logger)
            if ok:
                logger.print_copied(src, dst)
            else:
                logger.print_info("Rescheduling {}".format(src))
            return ok

ALGORITHMS = ['ecdsa','ed25519','rsa','dsa']

def main(*main_args):
    
    colorama_init()

    example_text = """examples:
  mugisync /path/to/src /path/to/dst -i "*.cpp" -e "moc_*" ".git"
  mugisync /src/path/libfoo.dll /dst/path
  mugisync /path/to/src root@192.168.0.1:/root/src
    """

    parser = argparse.ArgumentParser(prog="mugisync", epilog=example_text, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('src', help="source directory or file")
    parser.add_argument('dst', help="destination directory or file (or remote path)")
    parser.add_argument('-i','--include', nargs='+', help="include globs")
    parser.add_argument('-e','--exclude', nargs='+', help="exclude globs")
    parser.add_argument('-c','--create', action='store_true', help="create target directory")
    parser.add_argument('-P', '--password', help='ssh password')
    parser.add_argument('-k','--key', help='path to ssh key file, if no password provided tries to find ssh key with common name in ~/.ssh')
    parser.add_argument('-a', '--algorithm', choices=ALGORITHMS, help='ssh key algorithm')
    parser.add_argument('-y', '--yes', action='store_true', help='force initial update (bypass user confirmation)')

    if len(main_args) == 2:
        args = MainArgs(*main_args)
    else:
        args = parser.parse_args()
    
    debug_print(args)

    m = re.match('(.+)@(.+):(.+)', args.dst)
    sftp_mode = m is not None

    #print('sftp_mode',sftp_mode)

    logger = Logger(args.src, args.dst)

    sshArgs = None
    key = None
    if sftp_mode:
        if args.key:
            key = args.key
            if os.path.exists(key):
                debug_print('ssh key found {}'.format(key))
            else:
                logger.print_error('{} not exist'.format(key))
                key = None
        elif args.algorithm:
            key = os.path.join(os.path.expanduser('~'),'.ssh','id_{}'.format(args.algorithm))
            if os.path.exists(key):
                debug_print('ssh key found {}'.format(key))
            else:
                logger.print_error('{} not exist'.format(key))
                key = None
        elif args.password is None:
            for name in ALGORITHMS:
                key = os.path.join(os.path.expanduser('~'),'.ssh','id_{}'.format(name))
                if os.path.exists(key):
                    debug_print('ssh key found {}'.format(key))
                    break
            else:
                key = None
                logger.print_error('no ssh key found and no password provided')
    
        user = m.group(1)
        host = m.group(2)
        dst = m.group(3)
        sshArgs = SshArgs(host=host, user=user, password=args.password, key=key, src=args.src, dst=dst)
    
    #print(args); exit(0)

    if sshArgs is None and args.create:
        makedirs(args.dst)
        if not os.path.isdir(args.dst):
            logger.print_error("Failed to create {}".format(args.dst))
            return

    if sshArgs is None and os.path.isdir(args.src) and os.path.isfile(args.dst):
        logger.print_error("{} is dir and {} is file, cannot syncronize dir to file".format(args.src, args.dst))
        parser.print_help()
        return

    executor = Executor(sshArgs, logger)

    schedule = Schedule(executor)

    def dst_path(path):
        if sshArgs:
            return None
        dst = None
        if os.path.isfile(args.src):
            if os.path.isfile(args.dst):
                dst = args.dst
            elif os.path.isdir(args.dst):
                dst = os.path.join(args.dst, os.path.basename(args.src))
            else:
                logger.print_error("{} not a file not a dir".format(args.dst))
                return
        elif os.path.isdir(args.src):
            if os.path.isfile(args.dst):
                pass
            elif os.path.isdir(args.dst):
                dst = os.path.join(args.dst, os.path.relpath(path, args.src))
            else:
                logger.print_error("{} not a file not a dir".format(args.dst))
                return
        else:
            logger.print_error("{} not a file not a dir".format(args.src))
            return
        return dst

    def on_change(path, event):
        src = path
        dst = dst_path(src)
        schedule.append((src, dst), 1)

    def initial_sync():
        _, files = walk(args.src, args.include, args.exclude)
        if sshArgs:
            if args.yes:
                yes = True
            else:
                logger.print_question("Push {} files from {} to {} [Y/n]?".format(len(files), args.src, args.dst))
                ans = input()
                yes = ans in ['y','Y','']

            if yes:
                sftp_put_files(sshArgs, files, logger)
        else:
            tasks = []
            for src in files:
                dst = dst_path(src)
                if not os.path.exists(dst):
                    add = True
                else:
                    m1 = os.path.getmtime(src)
                    m2 = os.path.getmtime(dst)
                    add = m2 <= m1
                if add:
                    tasks.append((src, dst))

            if len(tasks) > 0:
                if args.yes:
                    yes = True
                else:
                    logger.print_question("Push {} files from {} to {} [Y/n]?".format(len(tasks), args.src, args.dst))
                    ans = input()
                    yes = ans in ['y','Y','']
                
                if yes:
                    for task in tasks:
                        schedule.append(task, 1)
            
    loop = EventLoop()

    logger.print_info("Initial sync")
    initial_sync()

    watch = FileSystemWatch(loop)
    logger.print_info("Watching {}".format(args.src))
    watch.start(args.src, on_change, recursive=True, include=args.include, exclude=args.exclude)
    loop.start()

if __name__ == "__main__":
    main()